# Proteção do salvamento legado de livros

Atualizado em 25/10/2026.

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

Essa proteção tem um limite funcional explícito: aplicação genérica de imagens,
mapa emocional e atualizações de autoria/skills em produtos especializados são
recusadas enquanto esses fluxos não tiverem writers próprios que preservem a
execução. As páginas 32/37 ainda precisam de tratamento dedicado desse veto.
O bloqueio não deve ser removido para contornar a migração.

Snapshots narrativos comuns ainda não têm proteção geral de revisão/baseline.
Este lote não resolve todas as perdas concorrentes de notas ou aprovações.
Assets enviados antes de surgir um conflito podem permanecer órfãos; não há
transação entre arquivos e JSON. A compatibilidade Supabase legada continua
limitada a processos no mesmo host/cache; o modo RPC não foi ativado pelo lote.

O snapshot de código passou em 1.932 testes e 2 subtestes, incluindo processos
Linux reais, conflitos de revisão e provedores/HTTP simulados. A auditoria
registrou zero bloqueadores e 69 avisos, três adicionais por imports de helpers
entre testes. A fixture visual foi ajustada para simular uma restauração externa
pelo backend de teste, preservando os asserts de identidade e de chamadas.
Nenhuma geração paga, migração, mensagem ou ativação comercial foi realizada.
