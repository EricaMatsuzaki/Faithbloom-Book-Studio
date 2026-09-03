# Refinamento 12 — Production Release & Project Hub

## Objetivo
Consolidar a operação editorial em um painel por obra, sem duplicar a lógica dos Studios e sem transformar presença de arquivo em aprovação de qualidade.

## Incluído
- Project Hub por Book Master salvo;
- pipeline consolidado: Master, Editorial, Personagens, Visual, Tradução, Activity, Audiobook, Quality Guardian e Distribuição;
- status baseados em evidências (`Concluído`, `Em andamento`, `Revisar`, `Bloqueado`, `Não iniciado`, `Opcional`);
- próxima ação recomendada determinística;
- matriz por locale separando texto, audiobook e distribuição;
- detecção de Quality Guardian e plano de distribuição obsoletos por fingerprint;
- links diretos para os Studios responsáveis;
- snapshot JSON de acompanhamento;
- política explícita: sem score fictício, sem aprovação automática e sem alteração do Book Master pelo Hub.

## Importante
O Project Hub é uma camada de coordenação. Ele não substitui o Quality Guardian, o preflight da plataforma, a aprovação humana de páginas, a escuta do audiobook ou a confirmação externa de publicação.
