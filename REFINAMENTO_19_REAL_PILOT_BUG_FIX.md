# Refinamento 19 — Real Pilot & Bug Fix Release

Objetivo: validar o FaithBloom com projetos reais antes da próxima Stable Candidate, sem acrescentar um novo grande Studio criativo.

## Projetos-piloto oficiais

1. **Quando Mel Aprendeu a Esperar** — Master visual/editorial da coleção.
2. **Quando Mel Aprendeu o Verdadeiro Sentido do Natal** — piloto de remasterização/consistência.
3. **Bolufinhas / Cute Friends** — piloto de coloring, line art, Cover Master e biblioteca de personagens.

## Novidades

- `real_pilot.py`: auditoria rápida de PDF por metadados/XObjects, sem decodificar todas as imagens.
- detecção conservadora de forte sobreposição textual entre páginas adjacentes;
- alerta de repetição da referência bíblica na camada textual, sem alterar ou traduzir versículos;
- histórico de runs com SHA-256 e política de original protegido;
- Bug Registry com severidade, reprodução, evidência e reteste;
- status `fixed` separado de `verified`;
- gate para a próxima candidata exige os três pilotos e zero bugs blocker/high abertos;
- nova página `🧪 Real Pilot & Bug Fix`.

## Bug/performance corrigido pelo próprio piloto

A auditoria completa do Book Doctor pode ser pesada em PDFs grandes porque precisa acessar bytes/decodificar imagens. O piloto real ganhou um caminho de **auditoria rápida** que lê Width/Height dos XObjects diretamente do PDF para triagem, mantendo a auditoria completa disponível quando a extração das imagens for realmente necessária.

Nenhum resultado do piloto é tratado como aprovação de Amazon/KDP/Apple/Kobo ou substituto de revisão visual/humana.
