# Refinamento 14 — Production Deployment & Real E2E

Este refinamento prepara o FaithBloom para validação real em produção sem declarar falsamente que um teste offline equivale a um deploy validado.

## Incluído
- página **Production Deployment & Real E2E**;
- snapshot de configuração sem revelar secrets;
- adapter para identidade `st.user`/OIDC quando disponível;
- inventário do storage local com SHA-256;
- planejador e executor seguro de migração de storage, sem apagar a origem e sem sobrescrever conflitos por padrão;
- health check de produção;
- probe real write/read/delete do storage sob ação explícita;
- checklist de Real E2E no Streamlit Cloud;
- gate separado entre “pronto para validar em nuvem” e “Stable”.

## Regra de segurança
O pacote **não** se autodeclara Stable. A tag Stable só deve ser promovida depois de evidência real no ambiente de destino: boot, autenticação, persistência, roundtrip de projeto, chamada mínima à OpenRouter, Quality Guardian, pacote de distribuição e persistência após restart/redeploy.

## Secrets esperados para produção
Configure-os no provedor/Streamlit Secrets, nunca no GitHub:
- `OPENROUTER_API_KEY`
- `FAITHBLOOM_DEPLOYMENT_MODE=production`
- `FAITHBLOOM_STORAGE_MODE=supabase`
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `FAITHBLOOM_SUPABASE_BUCKET` (opcional)
- configuração OIDC/autenticação externa adequada ao deploy.
