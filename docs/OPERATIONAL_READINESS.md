# O que falta para a operação completa

Atualizado em 25/10/2026, após os lotes de agentes, fila/perfis, execução visual/editorial e proteção do salvamento legado.

A autora confirmou que IA e armazenamento já estão configurados no Streamlit.
Este documento separa correções de código, validação com serviços reais e
requisitos para atender várias contas. Configuração não comprova que uma geração
real terminou corretamente. O modo comercial continua bloqueado.

## Correções deste lote

| Área | Comportamento corrigido | Limite preservado |
| --- | --- | --- |
| Fila | Uma tentativa persistida identifica o responsável e impede execução simultânea nos backends suportados. Abrir outra aba não recupera uma execução ativa. Pausa e cancelamento sobrevivem ao retorno do executor. | O piloto legado depende do lock no mesmo host; a fila não virou um serviço distribuído de execução em segundo plano. |
| Recuperação | Uma tentativa sem resultado confirmado fica incerta. Recuperação exige conferência; liberar uma instância de outro servidor exige confirmação de desligamento, evidência e a tentativa exata. Um responsável local vivo não pode ser liberado dessa forma. | Nenhum prazo ou botão de continuar autoriza reenviar automaticamente uma chamada incerta. A conferência no provedor continua humana. |
| Resultados recebidos | Se o checkpoint final falhar, a interface mantém o resultado recebido na sessão para recuperação, sem gerar de novo. | Uma sessão do navegador não é backup durável. Uma falha simultânea de armazenamento e sessão pode exigir recuperar o resultado no provedor. |
| Perfis e vínculos | Atualizações de autoria, perfis de trabalho e vínculos de projetos usam o documento atual. Edições de campos diferentes e atualizações de compartilhamento, miniatura e histórico não apagam umas às outras. Resumos antigos não rebaixam versões mais novas. | Perfil e catálogo são documentos separados, com consistência eventual; não existe transação entre eles. |
| Cache e estado da interface | Leitura e ativação de um projeto revalidam a conta mesmo quando há cache. Trocar de conta não reutiliza o livro de outra pessoa. Edições ainda não salvas da própria conta são preservadas. | Os perfis editoriais não são autenticação; a identidade continua vindo do contexto verificado no servidor. |
| Book Doctor e consumo | Cache de projetos, histórico de gerações, limites locais e supressão de duplicatas são separados por conta nos caminhos corrigidos. | Históricos locais não viram uma contabilidade distribuída ou persistente entre servidores. |
| Exportações e arquivos | PDF, EPUB, pacotes de distribuição, HQ e produtos especializados validam destinos e referências. Um pacote não apaga o diretório anterior inteiro. A HQ rejeita um destino que sobrescreveria uma imagem usada na exportação. | Ainda é preciso migrar e auditar os demais caminhos legados antes de liberar várias contas. |
| Biblioteca de imagens | Metadados, miniaturas e fallbacks não ignoram uma negativa de acesso nem copiam arquivos locais de outra conta. | Aprovação humana de Masters e fidelidade visual continuam necessárias. |
| Execução visual | Reserva de orçamento e primeira tentativa paga são confirmadas juntas no livro-razão do projeto. Checkpoints e reconciliação verificam a tentativa atual; um retorno atrasado não substitui a conferência humana. A interface lê os totais desse registro. | A proteção exige armazenamento local compartilhado ou RPC; o piloto legado coordena somente o mesmo host/cache. Galeria, cenas, aprovações e limites por plano continuam em registros separados. |
| Produtos editoriais especializados | Studio e Orquestrador compartilham a tentativa paga no produto canônico. Respostas recebidas são salvas antes de aplicar a unidade; a recuperação reutiliza essas respostas e preserva edições concorrentes. A interface permite conferir resultados incertos e baixar a cópia recebida. | Outros executores e escritores legados de Book Master ainda precisam migrar. A criação do produto e seu run são registros separados. A evidência de encerramento remoto continua dependendo do operador. |
| Salvamento legado de livros | O writer central revalida destino existente, identidade e permissão e recusa substituir produtos com registro de execução editorial. Um snapshot antigo não pode apagar uma tentativa para liberar outra chamada paga. | Os fluxos especializados que ainda usam o writer genérico recebem veto e precisam de migração. Snapshots narrativos comuns ainda precisam de revisão/baseline; veja [BOOK_WRITE_GUARD.md](BOOK_WRITE_GUARD.md). |

## Próximas prioridades de código

1. **Demais gastos e chamadas entre servidores.** Migrar os executores pagos de
   narrativa, áudio e automações que ainda não usam tentativas persistidas.
   A execução especializada já compartilha tentativas entre Studio e Orquestrador.
   A execução visual reserva saldo e registra a tentativa no mesmo livro-razão,
   mas os limites ainda pertencem aos planos; falta definir uma autoridade única
   para o limite do projeto e a coordenação de alterações de aprovação/origem.
   Os controles diários de consumo também precisam de integração própria.
2. **Demais registros compartilhados.** Migrar índices da galeria, personagens,
   estilos, planos, checkpoints e atualizações simultâneas do mesmo Book Master.
   Todos os escritores de um índice precisam usar o mesmo contrato; migrar só um
   deles não impede perda de atualizações. Preservar aprovações e originais.
3. **Demais arquivos e estados legados.** Completar o inventário de gerações,
   renderizadores e diretórios ainda compartilhados e adotar os limites de conta
   em todos os caminhos antes de liberar a interface comercial.
4. **Serviços oferecidos por conta.** Concluir proteção de credenciais OAuth,
   receptor público de webhooks, agendamento, cobrança, planos e cotas conforme
   os produtos que serão disponibilizados.

## Ativação e validação fora do código

- **Aceitação no Streamlit:** observar um livro novo e sua continuação, colorir,
  imagens, tradução, voz, HQ, PDF/EPUB e recuperação após interrupção. Conferir
  também olhos e outros detalhes dos Masters nas imagens reais. Testes com
  provedores simulados não medem a qualidade dessas saídas.
- **Banco concorrente:** revisar e ensaiar a migração Supabase em homologação,
  importar/verificar JSONs, testar permissões e backup/restauração antes de
  ativar `rpc_cas` em todos os escritores. Nenhuma migração foi aplicada por
  este lote; ver [STORAGE_CONCURRENCY.md](STORAGE_CONCURRENCY.md).
- **Operação com várias contas:** validar login e permissões reais, negação entre
  duas contas, cotas, cobrança, backup, restauração, observabilidade e múltiplos
  servidores. Os bloqueios de `saas_access.py` permanecem ativos.
- **Integrações externas:** testar OAuth, entrega de mensagens, custo declarado
  do WhatsApp e permissões do microfone no navegador. Nenhuma mensagem ou
  geração paga foi enviada pelos testes deste lote.

## Como funciona a compatibilidade do piloto

Os consumidores migrados usam `storage_updates.update_json_document`.
Armazenamento local e Supabase `rpc_cas` usam a API atômica estrita do backend.
O piloto com Supabase Storage legado usa, somente quando o chamador permite
explicitamente, um lock de arquivo por registro no mesmo host. Esse lock depende
de todos os processos compartilharem o mesmo diretório de cache; não coordena
servidores com discos separados. O status geral do backend continua declarando
essa limitação.

Uma falha de RPC, permissão, transporte ou JSON não ativa fallback de gravação.
Callbacks não chamam provedores nem fazem uploads. Uma resposta de gravação
incerta não autoriza chamar o provedor. O padrão de configuração do armazenamento
e o namespace da autora no piloto não foram alterados.

As evidências e a contagem final estão registradas no commit e no GitHub
Actions. Os testes relevantes são `test_queue_execution_claims.py`,
`test_storage_updates.py`, `test_profile_atomic_updates.py`,
`test_tenant_runtime_boundaries.py`, `test_saas_export_boundaries.py`,
`test_saas_specialist_outputs.py`, `test_visual_execution_integration.py`,
`test_visual_execution_atomic.py`, `test_visual_execution_ui_workflow.py`,
`test_editorial_generation_atomic.py`, `test_editorial_generation_acceptance.py`
e `test_editorial_recovery_ui.py`.
