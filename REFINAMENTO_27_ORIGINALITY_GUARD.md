# Refinamento 27 — Originality & Ineditism Guard

## Objetivo

O FaithBloom deve produzir obras **originais, exclusivas e editorialmente distintivas**, usando referências externas somente para identificar mecanismos gerais de qualidade — nunca para copiar expressão específica.

Princípio central:

> **Inspiração nos mecanismos. Originalidade absoluta na execução.**

## O que pode inspirar

Princípios e mecanismos gerais, por exemplo:

- conto cumulativo / lengalenga;
- repetição e musicalidade;
- humor cotidiano;
- terceira pessoa próxima;
- page-turn;
- profundidade emocional;
- quadrinhos/HQ como formato;
- onomatopeias;
- transformação emocional;
- recompensa emocional;
- estrutura de aventura, fábula ou mistério leve.

Esses mecanismos não autorizam copiar a expressão de uma obra específica.

## O que é proibido

O FaithBloom não deve copiar ou imitar:

- voz autoral;
- frases, diálogos, bordões ou refrões distintivos;
- personagens ou combinações distintivas de personagens;
- sequência específica de cenas;
- piadas recorrentes específicas;
- resolução narrativa específica;
- títulos excessivamente próximos;
- traço de artista, composição visual distintiva ou identidade visual de franquia;
- layout característico de obra/editora;
- instruções como “no estilo de”, “copie”, “mesma voz”, “mesmo traço” ou equivalentes.

## Arquitetura em três camadas

### 1. Prevention Contract

O Roteirista recebe `creation_originality_contract()` junto de sua skill. Referências declaradas ficam marcadas como **principles_only/mechanisms_only**. Se uma referência estiver muito presente, o agente deve aumentar a distância criativa em premissa concreta, personagens, causalidade, sequência, mecanismo de humor, refrão e resolução.

O Comparative Story Director já possui proibição explícita de copiar frases, refrões, bordões, voz autoral, estruturas textuais distintivas, layouts ou personagens de obras existentes e herda a skill `storyteller`.

### 2. Originality & Ineditism Guard

`originality_guard.py` executa checks determinísticos sobre evidências disponíveis:

- pedido explícito de imitação direta;
- sobreposição de sequências textuais longas com trechos de referência fornecidos para clearance;
- proximidade excessiva de título;
- clusters de nomes de personagens coincidentes;
- proveniência inadequada de referência de inspiração.

**Importante:** resumos conceituais não são tratados como texto protegido. A comparação textual usa apenas `protected_text`, `text_excerpt` ou `quoted_excerpt` fornecidos para auditoria.

### 3. Finalization Gate

O Diagramador executa o Originality Guard antes de marcar `pacote_pronto`.

- `BLOCKED` → pacote não pode ser finalizado;
- `NEEDS_REVIEW` → pacote pode continuar tecnicamente, mas recebe alerta para decisão humana;
- `PASS_INTERNAL` → nenhum bloqueio foi encontrado nos checks/evidências locais disponíveis.

## Limite honesto

`PASS_INTERNAL` **não significa** “obra juridicamente inédita em todo o mundo”.

O FaithBloom não possui automaticamente acesso a todo o corpus mundial de livros, registros de copyright, catálogos editoriais e obras não digitalizadas. Para lançamentos relevantes, o fluxo pode ser complementado por:

- pesquisa externa de título e premissa;
- comparação com referências específicas conhecidas;
- revisão editorial humana;
- clearance jurídico quando houver risco concreto.

O sistema nunca deve gerar um “percentual de originalidade jurídica” inventado.

## Relação com as referências criativas discutidas

Obras, séries e filmes mencionados pela autora servem apenas para identificar **experiências de leitura desejadas**, como:

- vontade de reler e participar;
- humor e identificação com a infância;
- leitura visual rápida e divertida;
- profundidade emocional e transformação.

Essas referências não devem ser usadas como templates copiáveis, nem seus nomes precisam aparecer nos prompts de geração quando os mecanismos já estiverem formalizados no FaithBloom.

## Resultado editorial desejado

Cada obra FaithBloom deve possuir:

- personagens próprios;
- voz própria;
- premissa concreta própria;
- cenas próprias;
- humor próprio;
- refrões próprios quando existirem;
- resolução própria;
- identidade visual própria;
- Heart Arc próprio;
- verdade de fé integrada organicamente à jornada específica daquela história.
