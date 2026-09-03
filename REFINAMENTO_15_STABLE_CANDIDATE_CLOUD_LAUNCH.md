# Refinamento 15 — Stable Candidate & Cloud Launch Checklist

Esta camada fecha a preparação para uma candidata Stable sem confundir QA offline, checkboxes ou geração de ZIP com uma validação real de produção.

## Principais entregas

- `stable_candidate.py` com manifest/fingerprint do código e configuração versionada;
- checklist cloud com evidência registrável por item obrigatório;
- Candidate Gate separado do Stable Promotion Gate;
- registro persistente de Release Candidates;
- invalidação automática da candidata quando o código/configuração muda;
- plano de rollback não destrutivo e separado para código/dados;
- sign-off humano obrigatório antes de recomendar a tag Stable;
- Evidence Bundle em ZIP com manifest, evidências, gate, QA, configuração sanitizada e rollback;
- rota `30_🏆_Stable_Candidate_Cloud_Launch.py`.

## Política

O FaithBloom não cria a tag Git, não faz deploy e não publica livros automaticamente. `PASS` significa que as evidências internas necessárias foram registradas e que a equipe pode executar manualmente a etapa seguinte.
