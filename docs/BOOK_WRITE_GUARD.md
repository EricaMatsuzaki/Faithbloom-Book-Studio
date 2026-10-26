# Proteção do salvamento legado de livros

Atualizado em 26/10/2026.

`armazenamento.atualizar_livro_salvo` autoriza a referência e verifica o livro
atual antes de preparar assets. A gravação usa a atualização atômica suportada
pelo backend e repete a verificação de identidade, destino e proteção editorial
no momento do commit. O callback não envia assets nem chama provedores.

Um destino ausente não é criado por essa API de atualização. IDs divergentes são
recusados; livros legados sem ID preservam a compatibilidade existente. URIs
canônicas da própria conta são aceitas após autorização. Outra conta, ausência
de ator e acesso somente de leitura falham antes de ler o documento e seus assets.

A presença de `editorial_product.execution`, inclusive vazia, inválida ou terminal,
impede uma substituição pelo writer genérico. A mesma guarda recusa introduzir
esse registro por um payload legado. Isso fecha o caso reproduzido em que uma
cópia antiga apagava uma tentativa ativa e permitia uma segunda chamada paga.
`save_product` continua usando seu caminho próprio com revisão e tentativa.

Aplicação de imagens, mapa emocional e autoria/skills usam agora
`editorial_project_updates`: atualizações restritas aos campos pretendidos,
comparadas com o documento observado pela tela. Produtos especializados passam
pelo writer de execução próprio, preservando tentativas e revisões. Uma geração
ativa, incerta ou com resposta recebida ainda não aplicada impede essas edições.
A guarda do writer genérico permanece; esses fluxos não a contornam.

Snapshots narrativos comuns usam a versão efetivamente aberta, mantida em um
registro interno limitado e referenciada por um identificador opaco na sessão.
Campos independentes são mesclados; alterações concorrentes do mesmo campo
geram conflito antes de substituir o conteúdo. Contexto ausente ou expirado
exige reabrir o projeto. A recuperação conserva o resultado recebido e repete
somente o salvamento, com conferência explícita antes de reaplicá-lo.
Assets enviados antes de surgir um conflito podem permanecer órfãos; não há
transação entre arquivos e JSON. A compatibilidade Supabase legada continua
limitada a processos no mesmo host/cache; o modo RPC não foi ativado pelo lote.

O snapshot de código passou em 2.029 testes e 2 subtestes, incluindo processos
Linux reais, conflitos de revisão e provedores/HTTP simulados. A auditoria
registrou zero bloqueadores e 75 avisos. Os percursos entre telas e os limites
da evidência estão em [PILOT_FLOW_RECOVERY.md](PILOT_FLOW_RECOVERY.md).
Nenhuma geração paga, migração, mensagem ou ativação comercial foi realizada.
