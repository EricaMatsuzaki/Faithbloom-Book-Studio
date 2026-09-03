# Refinamento 11 — Publishing & Distribution Center

O Refinamento 11 transforma o Publishing Platform Engine em uma camada operacional de distribuição.

## O que foi adicionado

- Quality Guardian como gate obrigatório de release: relatório e certificado precisam corresponder ao fingerprint atual da obra.
- Matriz de edições por plataforma, produto e locale.
- Compatibilidade e preflight reutilizados do Platform Engine, sem redimensionamento silencioso.
- Platform Registry continua expansível; plataformas personalizadas entram automaticamente no Center.
- Snapshot da especificação usada em cada edição, com versão, data e fontes registradas.
- Bloqueio de especificações não verificadas/desatualizadas antes da liberação.
- Proteção de exclusividade digital/KDP Select.
- Readiness de metadados e registro interno de disclosure de IA.
- Pacote ZIP separado por canal somente quando a edição está pronta internamente.
- Tracking explícito: draft, ready, submitted, processing, live, rejected, paused e withdrawn.
- Status externo nunca é inferido; é registrado pela autora.
- Persistência de planos e histórico de distribuição.
- Nenhuma API externa publica automaticamente nesta versão.

## Regra de segurança editorial

`READY` significa apenas que o FaithBloom não encontrou bloqueios internos conhecidos segundo as especificações registradas. Não significa que Amazon, Apple, Kobo, IngramSpark ou qualquer outra plataforma aprovou o arquivo. Previewers, validadores, formulários oficiais e provas físicas continuam necessários quando aplicáveis.
