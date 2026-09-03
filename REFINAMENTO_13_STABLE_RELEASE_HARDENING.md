# Refinamento 13 — Stable Release Hardening

## Objetivo
Preparar o FaithBloom para uma futura tag Stable sem declarar produção pronta antes do smoke test real.

## Entregas
- `stable_hardening.py`: schema v3, migrações, recovery, settings, permissions, audit log, diagnostics e Stable Gate.
- `pages/28_🧱_Stable_Release_Hardening.py`: painel operacional.
- escrita local atômica em `storage_backend.py`.
- testes automatizados específicos.

## Regras de segurança
- Bible Guard permanece obrigatório.
- secrets nunca são gravados nas configurações do Studio.
- recovery cria cópia de trabalho; não existe overwrite silencioso.
- papéis internos não são autenticação. Produção multiusuário exige OIDC/external auth.
- Stable Gate é interno e não substitui smoke test do Streamlit Cloud, KDP Previewer, EPUBCheck, prova física ou aprovação de plataformas.
