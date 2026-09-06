# Refinamento 25 — Roteirista Autoral, Skills Compartilhadas e Biblioteca de Versões

## Objetivo
Dar a todas as versões narrativas o mesmo núcleo profissional de storytelling, permitir uma versão autoral livre do Roteirista, preservar as histórias geradas e abrir uma biblioteca opcional de estilos e formatos adicionais sem aumentar automaticamente o custo do comparador principal.

## Núcleo compartilhado de Roteirista
Os quatro estilos formais do Prompt-Mestre herdam integralmente a skill `storyteller` e acrescentam apenas sua especialização:

1. 📖 Aventura — Roteirista + especialização Aventura.
2. 🎵 Poético/Rimado — Roteirista + especialização Poética.
3. 🌿 Fábula cristã — Roteirista + especialização Fábula.
4. ✨ Misto — Roteirista + especialização Mista.
5. ⭐ Versão do Roteirista — mesma skill-base, com liberdade criativa para escolher a melhor estratégia narrativa.

A skill-base inclui storytelling infantil, gancho inicial, page-turn structure, read-aloud rhythm, arco emocional, ação visual, repetição suave, integração cristã natural, continuidade de série e fechamento memorável. Melhorias futuras no contrato `storyteller` passam automaticamente para os estilos que o herdam.

## Arquitetura editorial: Estilo ≠ Formato
O FaithBloom separa duas decisões que não devem ser confundidas:

- **Estilo narrativo** = como a história é contada: Aventura, Poético, Fábula, Misto, Cumulativo/Lengalenga, Cotidiano Cômico/Diário Visual etc.
- **Formato narrativo visual** = como a história é apresentada: livro ilustrado tradicional, Quadrinhos/HQ infantil e futuros formatos.

Isso permite combinações profissionais, por exemplo:
- Aventura + Quadrinhos/HQ;
- Misto + Quadrinhos/HQ;
- Cotidiano Cômico + Quadrinhos/HQ;
- Cumulativo/Lengalenga + livro ilustrado tradicional.

A história literária original é preservada quando um formato visual é criado.

## Fluxo
1. Gerador de Ideias cria conceitos variados.
2. Curador organiza emoção, lição e referência bíblica candidata.
3. A autora pode pedir **Visão do Roteirista** antes da história completa.
4. Comparative Story Director gera os quatro estilos formais com a mesma skill-base do Roteirista.
5. **Versão do Roteirista** gera uma quinta história completa com liberdade autoral.
6. Todas as versões ficam na **Biblioteca de Versões Narrativas**.
7. A autora pode tornar outra versão ativa depois, sem regenerar as histórias.
8. Derivados da versão anterior são preservados em histórico antes da troca.
9. A própria tela **História em 4 Estilos** oferece o atalho **➕ Explorar outros estilos narrativos**.
10. A área de estilos adicionais gera cada alternativa somente sob demanda.
11. Depois de escolher uma história completa, a autora pode adaptar essa mesma história para um **formato narrativo visual**, como Quadrinhos/HQ infantil.

## Primeiro estilo adicional oficial — 🔁 Cumulativo / Lengalenga
Este estilo foi adicionado como biblioteca opcional e NÃO entra automaticamente nas quatro chamadas do comparador principal.

### DNA narrativo
- acumulação progressiva de personagem, ação, objeto, som, tentativa ou consequência;
- refrão curto, original, memorável e fácil de antecipar;
- musicalidade, ritmo, repetição intencional e onomatopeias quando fizerem sentido;
- possibilidade de contagem e pequenas variações progressivas;
- prazer de antecipação, participação e releitura;
- humor crescente por situações, reações e surpresas, sem ridicularizar personagens;
- clímax construído pela própria acumulação;
- resolução satisfatória, transformação emocional e lição cristã natural;
- cenas com ações visuais claras para favorecer ilustrações simples, expressivas e divertidas.

### Adequação etária
- **3–5:** forte prioridade para simplicidade, refrão, repetição e participação.
- **6–8:** mantém o mecanismo cumulativo, acrescentando variações, causa-consequência e humor mais elaborado.
- **9–12:** somente quando a estrutura puder ganhar sofisticação suficiente para não infantilizar.

### Meta editorial
Criar prazer de antecipação e releitura: a criança reconhece o padrão, participa, ri e quer ouvir de novo.

## Segundo estilo adicional oficial — 😄 Cotidiano Cômico / Diário Visual
Também herda integralmente a skill `storyteller`, mas acrescenta uma especialização voltada à identificação da criança com a protagonista e ao impulso de continuidade.

### DNA narrativo
- terceira pessoa próxima/focalizada na protagonista;
- conflitos reconhecíveis da infância: escola, família, irmãos, amizades, tarefas, animais, pequenas competições, vergonha, ciúme, frustração, planos e mal-entendidos;
- humor de personalidade, situação, tentativa e consequência;
- frases relativamente curtas, diálogos rápidos e mini-ganchos;
- mudanças emocionais claras e coerentes;
- pequenos exageros cômicos originais;
- motivos recorrentes e piadas internas originais;
- listas, bilhetes, lembretes, rabiscos ou notas de diário como sugestões editoriais de elementos gráficos;
- lição cristã emergindo das escolhas, consequências, reconciliação, gratidão e transformação, sem sermão longo.

### Adequação etária
- **6–8:** prioridade para humor visual, diálogos curtos, conflitos simples e emoções claramente reconhecíveis.
- **9–12:** pensamentos mais elaborados, conflitos sociais mais ricos, ironia infantil leve e maior autonomia da protagonista.
- **3–5:** somente em versão bastante simplificada, concreta e visual.

### Meta editorial
Criar identificação e vontade de continuar: a criança pensa “isso poderia acontecer comigo” e quer acompanhar a próxima confusão da protagonista.

### Originalidade
O sistema usa recursos gerais de narrativa cotidiana/humorística, mas proíbe copiar voz autoral, bordões, personagens, piadas recorrentes, cenas, layouts ou identidade visual distintiva de séries existentes.

## Primeiro formato narrativo visual — 🗯️ Quadrinhos / HQ infantil
Quadrinhos/HQ é tratado como FORMATO, não como mais um estilo. Ele pode ser combinado com qualquer história completa já escolhida.

### O adaptador de HQ herda a skill `storyteller` e acrescenta
- narrativa visual sequencial;
- divisão em páginas e painéis;
- um beat visual principal por painel;
- diálogos curtos e naturais;
- caixas de narração somente quando necessárias;
- SFX/onomatopeias em moderação;
- timing cômico e expressões visuais;
- ganchos de virada de página;
- continuidade de personagem, figurino e contexto;
- adaptação da quantidade de painéis à faixa etária.

### Painéis por faixa etária
- **3–5:** normalmente 1–3 painéis por página;
- **6–8 / 3–8:** normalmente 2–4 painéis por página;
- **9–12:** normalmente 3–6 painéis por página.

Esses números são heurísticos de legibilidade, não metas rígidas.

### Regra técnica de texto
Balões, legendas e SFX ficam como **campos estruturados de texto para o Diagramador**. O gerador de imagens não deve produzir texto legível dentro das ilustrações. Assim, a arte permanece limpa e o texto é composto profissionalmente depois.

### Originalidade
O FaithBloom usa a linguagem geral dos quadrinhos, mas proíbe copiar personagens, bordões, traço, timing, enquadramentos distintivos, design de página ou identidade visual de coleções existentes.

## Biblioteca de Versões
- Aventura, Poético/Rimado, Fábula, Misto, Roteirista e estilos adicionais podem ser preservados.
- Escolher uma versão não apaga as outras.
- A autora pode voltar e mudar a versão ativa sem pagar novamente por versões já geradas.
- Ao trocar a versão ativa, derivados já produzidos são arquivados antes da invalidação dos derivados ativos.
- Mudanças de coleção/faixa arquivam versões antigas em vez de apagá-las.
- Formatos visuais gerados ficam em biblioteca própria e não substituem a história literária de origem.

## Segurança editorial
- premissa, personagens, faixa etária, lição cristã e referência bíblica continuam protegidos;
- nenhuma versão é aprovada automaticamente;
- nenhuma ilustração é gerada durante a comparação narrativa ou durante a criação do roteiro de HQ;
- o Revisor continua independente do Roteirista;
- estilos e formatos adicionais só são gerados quando a autora pedir;
- nenhuma opção pode imitar voz, personagens, bordões, refrões, traço ou identidade visual de obra existente.

## Correção adicional
`licao_final` estruturada em JSON/dict é normalizada para texto editorial limpo antes de aparecer na interface ou seguir para o livro, evitando exibição de objetos como `{'texto': ...}`.

## Validação
A suíte automatizada cobre: manutenção dos quatro estilos oficiais, herança da skill `storyteller`, geração opcional do Cumulativo/Lengalenga, geração opcional do Cotidiano Cômico/Diário Visual, originalidade, aplicação como versão ativa, biblioteca de versões, adaptador de Quadrinhos/HQ, preservação da história fonte, separação entre estilo e formato, preservação do botão de rascunho e atalho da tela principal para a biblioteca de estilos adicionais.
