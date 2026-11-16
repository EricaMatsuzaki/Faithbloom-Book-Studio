# Contratos e integração dos agentes — 17/10/2026

O cadastro v4 descreve 31 cargos em 29 módulos, três módulos narrativos herdados
e 16 serviços de handoff. A auditoria anterior verificava principalmente número
de skills, nomes de papel e presença de `skill_contract` na AST. Isso não bastava
para detectar uma competência central removida ou um executor substituído por
um arquivo vazio.

## Conexões implementadas no cadastro

- Contrato específico por cargo com competências essenciais, entradas, saídas,
  funções reais de execução, critérios, evidências e handoffs obrigatórios.
- `require_role_ready` verifica o cargo e os executores dos destinos diretos.
  Competência essencial ausente, destino removido, função inexistente ou stub
  bloqueia antes da chamada do provedor. A validação é local e não cobra APIs.
- `skill_contract` usa o gate e inclui entradas, saídas e limites na instrução do
  agente generativo. Contrato descartado ou existente só em comentário não
  satisfaz a auditoria estática.
- Serviços de Bíblia, emoção/cores, consistência, áudio, impressão e publicação
  têm funções de destino verificadas, sem duplicar sua lógica como agentes LLM.
- Exportações JSON, inclusive os seis perfis técnicos, carregam o mesmo contrato
  canônico e são conferidas contra o código.
- `agent_capability_inventory` apresenta evidências por cargo e distingue AST,
  execução testada, qualidade da saída e validação externa. O campo
  `provided_runtime_evidence` aceita evidência de teste com escopo explícito;
  não converte presença de arquivo em sucesso de execução.

## Responsabilidades que não são novos agentes

O Full-Stack Developer corresponde ao cargo existente `saas_automation_engineer`,
cujo módulo é `agents/engenheiro_saas_automacao.py`. O revisor técnico independente
é `deep_code_review_engineer`. Seus diagnósticos e planos não aplicam patches,
executam testes ou fazem deploy por conta própria. Essas ações continuam sendo
do executor autorizado e precisam de evidência própria.

O Orquestrador central é um workflow implementado em `orchestrator_visual.py`,
`editorial_dispatch.py` e `orchestrator_execution_ui.py`. O diretor emocional é o
serviço `emotional_color_director.py`; Character Universe, Quality Guardian,
preflight de impressão e validação bíblica também mantêm implementações próprias.
Eles não precisam de um perfil LLM fictício para serem executáveis. As famílias
de produtos especializados são serviços de `editorial_products.py`, com schemas
e revisões por produto, não cargos adicionais assumidos pelo cadastro.

## Validação e limites

`tests/test_role_skills_execution.py` verifica todos os 31 contratos e inclui
falhas negativas: remover skill essencial apesar de restarem várias outras,
remover handoff, adulterar saída esperada, cadastrar destino inexistente e
substituir executor por comentário/pass. Nessas falhas, o provedor não é chamado.
Os testes de ativação dos executores e os testes dos fluxos continuam separados:
conferem a chamada real, saídas e preservação de versões com provedores simulados.

Um cadastro consistente não mede excelência profissional. O modelo pode
desobedecer a instruções; uma resposta ainda precisa de validação e revisão.
Provedores pagos, qualidade artística, identidade dos olhos dos personagens,
fontes externas, segurança comercial e comportamento no Streamlit de produção
dependem de verificações específicas. Esta integração não enviou mensagens,
não fez chamadas pagas e não habilitou migrações ou produção comercial.

O relatório de auditoria diferencia cada evidência observada de pendências.
Os testes da revisão final e o commit publicado devem ser consultados no PR
correspondente; este documento não transforma resultados históricos de outro PR
em evidência da versão atual.
