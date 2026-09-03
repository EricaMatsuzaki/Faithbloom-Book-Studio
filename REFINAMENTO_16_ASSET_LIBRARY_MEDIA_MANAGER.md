# Refinamento 16 — Asset Library & Media Manager

Este refinamento foi criado antes da promoção Stable para evitar que o crescimento da Galeria transforme o acervo do FaithBloom em uma coleção difícil de encontrar, reutilizar ou limpar.

## Princípios

- O arquivo físico permanece único no storage; filtros e coleções virtuais não duplicam bytes.
- Arquivar é a ação padrão para limpeza. Exclusão permanente exige confirmação e ausência de vínculos encontrados.
- Masters, originais publicados e assets vinculados recebem proteção extra.
- Busca e facetas trabalham sobre metadados; nenhum score estético fictício é criado.
- Miniaturas são persistidas separadamente para não carregar imagens originais gigantes em cada página da galeria.
- O Book Master não é modificado pelo Media Manager.

## Novidades

- `asset_library.py`: catálogo enriquecido compatível com a Galeria existente.
- `pages/31_🖼️_Asset_Library_Media_Manager.py`: painel visual completo.
- Grade grande, compacta e lista, com paginação.
- Busca por nome/tags/personagem/coleção/livro/emoção/estação/festividade e filtros adicionais.
- Badges de Character Master, Color Master, Line Art Master, Cover Master, Style Reference, aprovada, favorita e original bloqueado.
- Coleções virtuais/pastas sem duplicação física.
- Histórico de versões por `version_group`.
- Seleção múltipla e ações em lote (favoritar, arquivar, tags, coleções).
- Rastreamento sob demanda “Onde este asset está sendo usado?” por asset ID e storage URI.
- Triagem de duplicatas por fingerprint de conteúdo.
- Storage Manager com contagem, tamanho conhecido e preenchimento controlado de metadados técnicos.
- Thumbnails persistentes para imagens raster.
- Upload direto para a Asset Library.
- Handoff de asset selecionado para Coloring Studio, Restoration Studio e Character Universe.
- Coloring Studio respeita o asset pré-selecionado na biblioteca.
- Restoration Studio pode usar o asset selecionado como referência visual adicional.
- Character Universe pode adicionar o asset ao Reference Pack ou defini-lo como Color/Line Art Master.

## Compatibilidade

`armazenamento.salvar_na_galeria()` e `listar_galeria()` foram mantidos para não quebrar os Studios anteriores. Novos itens passam a nascer no schema de asset v2, enquanto registros antigos são normalizados de forma não destrutiva.

## Segurança editorial

O Media Manager não apaga assets automaticamente, não remove versões A/B/C por conta própria e não assume que um arquivo sem referência encontrada está necessariamente sem uso quando a varredura foi truncada.
