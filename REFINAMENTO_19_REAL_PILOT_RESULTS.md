# Refinamento 19 — resultados dos pilotos reais

Os três PDFs enviados foram analisados em modo rápido, sem modificar os originais e sem decodificar todas as imagens. PPI abaixo é apenas hipótese conservadora de página inteira; não deve ser usado sozinho para mandar reilustrar uma página.

## 🌷 Quando Mel Aprendeu a Esperar
- arquivo: `Quando Mel Aprendeu a Esperar - PORTUGUÊS.pdf`
- SHA-256: `736c6618f9af85ba93081dff2d81a053db184b6df0f33cc05209bd9f4f19e14c`
- páginas: **26**
- tamanho(s): **[[8.625, 8.75]] pol.**
- XObjects de imagem encontrados: **54**
- gate do piloto: **manual-review**

- capa multilíngue analisada: **7 páginas**, tamanho **[[17.3229, 8.75]] pol.**.

## 🎄 Quando Mel Aprendeu o Verdadeiro Sentido do Natal
- arquivo: `Quando Mel Aprendeu o Verdadeiro Sentido do Natal.pdf`
- SHA-256: `5302028bf77af092da9408064ff4994624dd8fcd042b09d006ab7e2951264872`
- páginas: **32**
- tamanho(s): **[[8.625, 8.75]] pol.**
- XObjects de imagem encontrados: **39**
- gate do piloto: **manual-review**

- forte sobreposição textual adjacente: **16–17**. Confirmar visualmente antes de editar.

- Bible Guard: `Lucas 2:11` aparece **25 vezes** na camada textual da página 21. Isso pode refletir duplicação gráfica/textual do PDF; não é corrigido automaticamente.

## 🖍️ Bolufinhas / Cute Friends
- arquivo: `Bolufinhas friends(1).pdf`
- SHA-256: `7f8da0c007ad0a268a7d939df20449bc2a861a00b53ab3a44fad46ab4442b44e`
- páginas: **74**
- tamanho(s): **[[8.625, 8.75]] pol.**
- XObjects de imagem encontrados: **40**
- gate do piloto: **manual-review**

- forte sobreposição textual adjacente: **1–2, 2–3, 3–4, 4–5**. Confirmar visualmente antes de editar.

## Conclusões de integração
- O primeiro livro continua adequado como piloto Master para construção do Character/Style reference; o piloto não escolhe sozinho uma imagem Master.
- O livro de Natal reproduziu automaticamente os dois pontos editoriais que já haviam sido observados: forte sobreposição entre as páginas 16–17 e repetição de Lucas 2:11 na camada textual da página 21.
- O arquivo atual de Bolufinhas/Cute Friends possui **74 páginas** nesta versão enviada. As páginas 1–5 formam um cluster textual muito semelhante, coerente com a existência de múltiplas propostas de capa e exigindo seleção consciente de Cover Master.
- A auditoria completa do Book Doctor continua disponível para extração de imagens; o Refinamento 19 adiciona triagem rápida para PDFs grandes antes dessa etapa.
