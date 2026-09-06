# Refinamento 24 — Prompt-Mestre Compliance & Narrative Style Studio

## Objetivo

Transformar os itens ainda não formalizados do Prompt-Mestre em regras e ferramentas explícitas do FaithBloom, preservando o pipeline existente e sem aumentar o número padrão de páginas para colorir.

## Decisões editoriais confirmadas

- **Lição de Moral é obrigatória e bloqueante.** Sem `licao_final`, o livro não pode receber `pacote_pronto=True`.
- Story Books usam **3 páginas para colorir** como padrão atual do SaaS.
- Existem quatro estilos narrativos formais:
  1. Estilo 1 — Aventura
  2. Estilo 2 — Poético/Rimado
  3. Estilo 3 — Fábula cristã
  4. Estilo misto
- A autora pode comparar a mesma premissa nos quatro estilos antes de escolher o definitivo.

## Entregas

### Narrative Style System

- `agents/estilos_narrativos.py` centraliza os quatro estilos.
- O Roteirista lê `estilo_narrativo` e incorpora a instrução correspondente ao prompt de geração.
- O comparador possui dois modos:
  - **Amostra rápida dos 4 estilos**: não altera título, moral, cenas nem aprovação da história.
  - **História completa nos 4 estilos**: permite aplicar uma versão completa; ao aplicar, `revisao_aprovada=False` para obrigar nova revisão editorial.
- Personagens, premissa, lição cristã e referência bíblica devem permanecer equivalentes entre as versões.

### Complementos editoriais

`agents/complementos_editoriais.py` gera e estrutura:

- Mensagem de Boas-vindas;
- Mensagem para Pais/Educadores, com tema, emoção, princípio bíblico, habilidade socioemocional, perguntas e aplicações;
- Ficha Pedagógica, com faixa etária, tema, emoção, habilidade socioemocional, valor cristão, referência bíblica, objetivo pedagógico, psicologia das cores e perguntas de reflexão.

O agente não reescreve a história e não inventa/traduz livremente texto bíblico.

### Prompt-Mestre Studio

Nova página Streamlit: `pages/38_Prompt_Mestre_Studio.py`.

Permite:

- escolher formalmente um estilo;
- gerar amostras dos quatro estilos;
- gerar histórias completas nos quatro estilos;
- aplicar a versão escolhida;
- gerar e editar Boas-vindas;
- gerar e editar Pais/Educadores;
- gerar e editar Ficha Pedagógica;
- editar a Lição de Moral obrigatória;
- visualizar bloqueios, recomendações e itens concluídos do Prompt-Mestre.

### Compliance

`prompt_master_compliance.py` diferencia:

- **Bloqueio:** Lição de Moral ausente.
- **Recomendações:** estilo não escolhido, Boas-vindas ausente, Pais/Educadores ausente, Ficha Pedagógica ausente, menos de 3 páginas para colorir.

### Pipeline

- `graph.py` usa `LivroStatePromptMestre`, preservando os novos campos no LangGraph.
- Após o Revisor aprovar a história, o pipeline automatizado gera os complementos editoriais antes de seguir ao Ilustrador.
- `agents/diagramador.py` inclui o compliance no checklist e impede `pacote_pronto=True` quando a Moral está ausente.

## Segurança editorial

1. Amostra de estilo não substitui conteúdo aprovado.
2. História completa escolhida exige nova revisão.
3. A IA não valida automaticamente a obra como pronta.
4. Texto bíblico completo continua protegido pelo Bible Guard; este refinamento usa somente referência bíblica nos complementos.
5. O padrão de 3 páginas para colorir não é alterado.

## Limite deste refinamento

Os novos conteúdos editoriais ficam estruturados no estado do livro e disponíveis ao pipeline. A criação de **páginas físicas dedicadas** para Boas-vindas, Pais/Educadores e Ficha Pedagógica no `renderizador_editorial.py` deve ser feita em um passo separado e testado contra paginação, paridade, KDP preflight e PDFs já existentes. Este refinamento evita alterar silenciosamente o layout print-ready atual.
