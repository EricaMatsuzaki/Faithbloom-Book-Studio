# Refinamento 22 — Visual Master Restoration

O fluxo visual reutiliza **Asset Library**, `storage_backend` e o cliente
OpenRouter existentes. Uploads entram como `REFERENCE`; restaurações criam
versões filhas `MASTER_CANDIDATE`; aprovação humana e confirmação explícita são
necessárias antes de atribuir `COLOR_MASTER` ou `LINEART_MASTER`.

O original é imutável no fluxo: resultados usam `create_version`, conservando
`parent_asset_id` e `version_group`. A substituição de um Master registra o
anterior em `metadata.master_history`.

## Limites antes de Stable

- Geração depende do modelo de imagem configurado no OpenRouter e do seu suporte
  efetivo a referências visuais.
- As métricas da auditoria são sinais técnicos, não notas nem garantia de
  qualidade de impressão; o tamanho final/PPI e o resultado visual exigem QA.
- O modo Local é adequado ao desenvolvimento. **A persistência real no
  Streamlit Cloud ainda precisa ser validada com Supabase antes de Stable.**
- Este refinamento não executa deploy nem promove a aplicação para Stable.
