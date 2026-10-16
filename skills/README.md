# FaithBloom Agent Skills

`agent_skills.py` é o cadastro executável dos contratos editoriais, visuais e técnicos.
Os JSONs desta pasta são exportações verificadas desse cadastro, não outra fonte de regras.

- 31 papéis em 29 módulos principais; três módulos de narrativa herdam Storyteller.
- Todo arquivo de `agents/` precisa de perfil próprio ou herança declarada.
- O verificador confere campos, módulos, chamadas de contrato, destinos de handoff e sincronização dos JSONs.
- Serviços determinísticos (Bíblia, qualidade, áudio, impressão e outros) têm destinos explícitos, sem duplicar sua lógica como novos agentes de IA.
- Perfil válido significa configuração consistente. Qualidade narrativa, identidade visual e funcionamento em produção ainda exigem avaliação de resultados.
- Governança de IA, dados, TI e cibersegurança possuem diagnósticos executáveis e histórico no painel de Governança; as pré-validações conectadas aos executores registram seu escopo e mantêm desconhecida a prontidão comercial sem evidência.

Para conferir: `python agent_skills.py`. Após alterar contratos: `python agent_skills.py --export`.

## Engenharia

Os engenheiros são contratos e workflows internos aplicados por um executor autorizado,
conforme o dossiê mestre de 15/09/2026 (anexo, página 182). Não são robôs externos autônomos.
A tela Agent Skills inclui Engenharia: auditoria local reutiliza `scripts_fullstack_audit`,
e revisão profunda opcional envia somente fontes selecionadas ao roteador textual existente.
As citações dos achados são conferidas contra essas fontes. Diagnósticos e propostas
não são apresentados como correções, testes ou deploys realizados.

PR #18 permanece Draft na feature branch. Original, Masters e histórico são preservados.
Bestseller Readiness não é promessa de vendas.
