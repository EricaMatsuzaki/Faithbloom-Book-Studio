# FaithBloom Book Studio 2.0 — Refinamento 09

## 🎧 Audiobook Studio Professional

Este refinamento transforma o antigo agente de audiobook em um Studio editorial com aprovação humana e produção por segmentos.

### Fluxo

`Story/Translation Master → roteiro de performance → Voice Profiles/Casting → pronúncia → preview → versões A/B/C → aprovação por segmento → fila TTS → QA técnico → mix final → escuta/aprovação da autora → pacote de estúdio`

### Recursos principais

- Narrador único ou narrador + personagens.
- Voice Profiles reutilizáveis por locale, estilo, ritmo, velocidade e ID opcional do provedor.
- Modos **Automático** e **Studio**. O automático aplica direção conservadora por emoção sem alterar texto; o Studio permite controle cena a cena.
- AI Voice Director opcional para emoção, ritmo, pausas, ênfases e divisão de falas. Sugestões que alterem/omitam palavras do texto-fonte são descartadas.
- Texto-fonte protegido por fingerprint SHA-256; aprovação do roteiro falha se o conteúdo verbal for reescrito.
- Dicionário de pronúncia que altera somente a entrada do TTS, nunca o texto editorial exibido.
- Preview por cena e produção completa somente depois de roteiro aprovado.
- Versões A/B/C de áudio por segmento, favoritos e aprovação explícita.
- Fila cooperativa com pause/resume/cancel/checkpoints, integrada ao guardrail de custo.
- QA técnico com duração, codec, sample rate, bitrate, ritmo observado e métricas de volume quando FFmpeg estiver disponível.
- Mix final opcional com FFmpeg, pausas aprovadas entre segmentos e loudness normalization.
- Aprovação final exige escuta humana registrada; metadados técnicos não fingem avaliar emoção/interpretação.
- Pacote ZIP de estúdio com roteiro, dicionário de pronúncia, clips aprovados, mix final e readiness.

### Bible Guard

O Audiobook Studio nunca usa `versiculo_texto_original` ou texto bíblico legado como material de tradução/narração automática. Ele utiliza:

1. somente a referência; ou
2. o texto exato de um `BibleVerseRecord` previamente aprovado pela autora, com versão registrada.

O AI Voice Director recebe instrução explícita para não traduzir, completar ou parafrasear versículos.

### Observação sobre plataformas

O pacote gerado é um **Master de estúdio**, não uma certificação ACX/Audible/Kobo/Apple/Spotify etc. Requisitos de cada destino pertencem ao Publishing & Distribution Center e devem ser validados antes do upload.
