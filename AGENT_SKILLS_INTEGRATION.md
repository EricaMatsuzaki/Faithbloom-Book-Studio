# Contratos e integração dos agentes — 15/09/2026

A auditoria identificou agentes fora do cadastro central, documentação de skills
inconsistente e saídas pedagógicas sem validação suficiente. Esta alteração
estende os módulos existentes na feature branch do PR #18.

## Alterações

- Cadastro v3: 27 papéis em 25 módulos principais, com herança explícita para
  estilos, Roteirista Autoral e HQ. Todos os arquivos de agents/ são cobertos.
- Editor Pedagógico e Diretor de Cena recebem contratos formais. Os engenheiros
  reutilizam suas competências canônicas, sem DNA literário aplicado ao código.
- Auditoria detecta agentes sem perfil, contrato ausente, handoff desconhecido,
  serviço inexistente e JSON desatualizado. JSONs são gerados pelo cadastro.
- Complementos recebem cenas completas e mapa emocional. Campos obrigatórios,
  quantidade de perguntas e referência bíblica são conferidos antes de substituir
  conteúdo salvo. Dados inválidos não apagam a versão anterior.
- Diretor de Cena recebe idade e contexto do projeto, resolve Style DNA oficial
  quando vinculado e preserva esse contexto no prompt visual. Novas propostas
  incompletas ou repetidas são rejeitadas. Normalização legada é mantida.
- Capas de livros de colorir reutilizam o contrato de capa e evitam tipografia
  gerada pela IA.
- Engenharia está disponível na página Agent Skills e na navegação do Jarvis.
  Auditoria local reutiliza scripts_fullstack_audit. Revisão profunda opcional
  usa o roteador de texto existente e exige citações conferíveis nas fontes.
- Incidentes técnicos repetidos do Autopilot incluem plano de revisão profunda.

## Limites de execução

Conforme o dossiê mestre de 15/09, anexo página 182, os engenheiros são contratos
internos aplicados por um executor autorizado, não robôs autônomos externos.
O diagnóstico não executa patches retornados pela IA, não roda testes por conta
própria, não faz deploy e não altera a release. Propostas sem evidência de runtime
não são apresentadas como correções concluídas.

## Validação desta alteração

- 691 testes locais passaram, incluindo regressões de contexto, validação,
  preservação de estado, navegação e evidência da revisão técnica.
- Streamlit AppTest: página Agent Skills abriu, recebeu um pedido e executou
  diagnóstico local com cadastro válido, sem exceções.
- O CI do commit publicado é a evidência remota; consultar o PR #18.
- Não houve chamada paga nem teste com chaves/Storage de produção.

A base canônica do piloto (32 páginas, 11 cenas, moral e Eclesiastes 3:1),
originais, Masters e regras de aprovação não são substituídos por esta alteração.
Testes de contrato não garantem qualidade literária ou identidade visual de toda
resposta futura. O piloto com APIs e persistência reais continua necessário.
