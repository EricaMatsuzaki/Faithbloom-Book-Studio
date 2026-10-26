# FaithBloom Agent Skills

`agent_skills.py` contém os contratos executáveis dos **31 papéis em 29 módulos**.
Os JSONs desta pasta são exportações verificadas desse cadastro. Três módulos de
narrativa herdam o contrato de Storyteller; 16 serviços de handoff preservam sua
implementação real, sem serem apresentados como novos agentes de IA.

Cada cargo declara missão, competências, critérios de qualidade, limites,
evidências, entradas e saídas esperadas, funções reais de execução e destinos de
handoff. O cadastro v4 verifica competências essenciais específicas do cargo,
além de contagens de campos. A ausência de um ilustrador, revisor ou serviço de
cores não pode ser compensada por um nome em comentário.

`require_role_ready(role_id)` bloqueia a execução se faltarem competências
essenciais, contrato operacional, executor ou handoff obrigatório. `skill_contract`
aplica essa validação antes de montar a instrução de um agente generativo.
Executores determinísticos usam o mesmo gate sem receber um prompt de IA
artificial. O verificador lê código local, não chama provedores nem exige chaves.

`role_readiness(role_id)` retorna configuração e erros sem executar o agente.
`agent_capability_inventory()` separa presença no código, injeção do contrato,
gates determinísticos, evidência de testes fornecida e limitações externas. Uma
função encontrada por AST não é apresentada como execução ou qualidade validada.

O cadastro não é um despachante automático: a conexão de cada fluxo, suas
aprovações, a validação da saída e a persistência são responsabilidade dos
executores. Uma lista de skills e um prompt não comprovam excelência profissional,
fidelidade visual, qualidade literária ou funcionamento em produção.

Para conferir: `python agent_skills.py`. Para atualizar as exportações depois de
alterar contratos: `python agent_skills.py --export`.

## Engenharia e governança

O papel `saas_automation_engineer` já reúne SaaS, Full-Stack e Automação. Não há
um segundo agente desconectado chamado Full Stack Developer. O engenheiro e o
revisor profundo executam diagnóstico e revisão de fontes; uma proposta não é
apresentada como patch, teste ou deploy realizado. Alterações no código dependem
de um executor autorizado, com verificação própria.

Governança de IA, dados, TI e cibersegurança possuem funções determinísticas,
relatórios com escopo e guardas pré-ação nos executores conectados. `UNKNOWN`
permanece quando falta evidência. O diagnóstico não constitui certificação nem
substitui testes de produção. O Orquestrador central, Character Universe e o
diretor emocional são componentes de workflow/serviço, identificados por seus
arquivos reais, sem perfis LLM fictícios.

Consulte [Contratos e integração dos agentes](../AGENT_SKILLS_INTEGRATION.md)
para o escopo e os limites desta integração.
