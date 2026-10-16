# Atualizações concorrentes de JSON

## O que esta entrega garante

`BACKEND.update_json(path, callback, default)` atualiza o documento sem perder
uma atualização concorrente. O callback recebe uma cópia do valor atual e
devolve o valor novo. Ele precisa ser puro: não chamar IA, cobrar, publicar,
escrever outros registros nem alterar estado externo. O modo RPC pode repetir
o callback após um conflito, até o limite explícito de tentativas (padrão 5).
Erros de transporte, permissão ou dados inválidos não são repetidos nem viram
um índice vazio.

Um timeout depois de enviar CAS pode deixar o resultado da confirmação incerto.
Recarregar o registro e reconciliar pelo ID estável da operação antes de tentar
novamente evita repetir um lançamento já aceito pelo banco; o timeout não
autoriza reenviar geração ou cobrança.

Também existem `get_json_snapshot` e `compare_and_swap_json`, para uma edição
que precisa guardar a revisão lida e apresentar um conflito recuperável ao
usuário. `StorageConflict` rejeita uma revisão desatualizada antes de substituir
o documento. O resultado de geração já recebido deve permanecer no estado do
fluxo enquanto se resolve o conflito; não se deve gerar/cobrar novamente.

- Local: lock por caminho entre threads, `flock` entre processos no mesmo disco
  e substituição atômica do arquivo. Revisão é o SHA-256 dos bytes atuais, não
  um contador histórico. Armazenamento em discos diferentes ou sistemas de
  arquivos sem suporte confiável a `flock` não fornece essa garantia.
- Supabase legado (`storage`, padrão): uploads continuam compatíveis, mas não
  oferecem CAS entre workers. Pedir `update_json` nesse modo falha explicitamente
  com `StorageConcurrencyUnsupported`; não degrada para upload sem proteção.
- Supabase opcional (`rpc_cas`): JSONs ficam em uma tabela PostgreSQL e CAS é
  uma única instrução de banco condicionada à revisão. Mídia permanece no bucket
  privado. A revisão cresce inclusive ao excluir (tombstone), evitando que um
  escritor antigo recrie um registro excluído. SQL fornecido, não aplicado.

O wrapper de contas valida leitura e escrita antes de qualquer RPC ou callback.
Paths retornados em `fb://tenants/...` continuam privados; o prefixo original
da autora no piloto não é adotado automaticamente por uma conta de cliente.

## Ativação opcional do Supabase

Não alterar a configuração de produção só por existir este arquivo. A migração
`migrations/20261015_json_compare_and_swap.sql` precisa ser revisada/aplicada por
um operador com acesso ao banco. Ela não migra objetos nem modifica Masters.

1. Pausar escritores de todos os workers; fazer backup do banco e bucket privado
   pelo procedimento operacional já existente. Registrar o inventário de JSONs
   e seus valores completos, mantendo os caminhos e o bucket exatos.
2. Aplicar a migração. Confirmar RLS ativo e que `anon`/`authenticated` não têm
   acesso à tabela/RPC. Somente o backend com chave de servidor chama os RPCs;
   a identidade da conta é imposta pelo wrapper Python, não por input do browser.
3. Importar os JSONs existentes, sem sobrescrever entradas prévias. Para cada
   `(bucket,path)`, inserir o JSON original com revisão 1, `deleted=false`.
   Validar quantidade, caminhos e igualdade estrutural de cada valor importado.
   Arquivos de mídia e seus bytes originais permanecem no bucket.
4. Testar em homologação a leitura de projetos antigos, listagem, salvamento,
   duas sessões concorrentes, exclusão/recriação e negação entre duas contas.
   Validar backup/restauração incluindo **a tabela e o bucket**.
5. Só então definir `FAITHBLOOM_SUPABASE_JSON_MODE=rpc_cas` em todos os workers
   e liberar escrita. O padrão continua `storage`. Um RPC ausente/indisponível
   interrompe a operação sem fallback. Um JSON legado ainda não importado gera
   `StorageMigrationRequired` antes que vire um novo índice vazio.

Depois de gravar no modo RPC, retornar simplesmente a `storage` exibiria versões
antigas. Rollback exige parar escritores e exportar/verificar a tabela de volta
ao armazenamento legado, respeitando tombstones, antes de mudar a configuração.
Tombstones não autorizam apagar arquivos oficiais ou restaurar por cima de Masters.

## Consumidores que ainda precisam usar a API

Atomicidade de um `put_json` não torna seguro um `get_json` + `put_json` separado.
O código de negócio precisa usar o callback transacional ou passar a revisão
original. Antes de anunciar concorrência completa, revisar ao menos:

| Consumidor | Registros compartilhados |
|---|---|
| `armazenamento.py` | catálogos de coleções e biblioteca; atualização do mesmo Book Master |
| `orchestrator_visual.py` | índices de planos/World Masters, saldo/reserva de orçamento |
| `generation_autosave.py` | snapshots de uma mesma obra em duas sessões |
| `author_profiles.py`, `family_profiles.py` | índices e vínculos de projetos |
| `character_universe.py`, `asset_library.py`, `style_dna.py` | índices de personagens, galeria, estilos |
| `activity_studio.py`, `audiobook_studio.py`, `coloring_studio.py` | índices de projetos e checkpoints |
| `publishing_distribution.py` | índice de pacotes e atualização de planos |
| `fila_producao.py` | claim/lease de jobs; um lock de JSON não torna toda a fila distribuída |
| `stable_hardening.py`, `production_deployment.py`, `real_pilot.py` | históricos compartilhados e eventos |
| `editorial_dispatch.py`, `visual_execution.py`, `editorial_autopilot_storage.py` | execução, despesas/reservas e recuperação |

Esta infraestrutura não faz transação entre documentos diferentes. Um orçamento
compartilhado deve reservar saldo e registrar a operação no **mesmo documento**
ou usar uma transação própria de banco. Não chamar o provedor dentro do callback.
Listagens paginadas não são snapshots transacionais de todos os documentos;
não usar uma listagem para reconstruir e substituir catálogos em produção ativa.
Nenhum teste local com doubles confirma instalação/permissões de um Supabase real.
