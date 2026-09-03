# FaithBloom 2.0 — Refinamento 05

## Coloring Book Doctor + Age & Complexity QA + Cover Master

Este refinamento parte integralmente do Refinamento 04 e preserva todos os módulos anteriores.

### O que entrou

- `coloring_book_doctor.py`: auditoria especializada de line art por faixa etária.
- Perfis: 3–4, 5–6, 7–8, 9–12, adolescente/adulto e personalizado.
- Métricas explicáveis: cinzas residuais, cobertura de tinta, densidade de borda, densidade de arestas, componentes geométricos, índice relativo de espessura e PPI efetivo quando o tamanho físico é informado.
- `gerar_plano_recuperacao`: decide entre manter, normalizar line art, revisar enquadramento, revisar resolução/reilustrar ou revisão manual — sem executar silenciosamente.
- Recuperação determinística em lote somente para assets explicitamente selecionados; originais permanecem intocados.
- Plano de miolo/acabamento com essenciais e opcionais: rosto, copyright, “Este livro pertence a”, instruções, teste de cores, preview colorido, personagens, dedicatória, certificado, agradecimento, outros livros, QR/site e desenho livre.
- `cover_master.py`: arte Master versionada, variações de frente/contracapa, aprovação/seleção, Character Universe + Style DNA, texto localizado sobre a mesma arte e montagem física pelo motor matemático existente.
- A IA é instruída a gerar **arte sem texto**; título, autora, sinopse, lombada, bleed, safe zones e barcode são aplicados pelo motor editorial.
- `pages/20_🖍️_Coloring_Book_Doctor.py`: fluxo visual completo.

### Regras preservadas

1. Diagnosticar primeiro, corrigir depois.
2. Nenhum original é sobrescrito.
3. Nenhuma “nota estética” é inventada.
4. Upscale determinístico é tratado como interpolação, não como recuperação mágica de detalhe.
5. Reilustração/Character Restoration continua exigindo aprovação no Restoration Studio.
6. O Cover Master preserva versões A/B/C e reutiliza personagens oficiais em novas poses, roupas, expressões, cenários, estações e festividades sem alterar Character DNA.
7. O Quality Guardian final continua uma etapa independente futura.
