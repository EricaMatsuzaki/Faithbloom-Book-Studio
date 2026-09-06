# Refinamento 25 — Roteirista Autoral, Skills Compartilhadas e Biblioteca de Versões

## Objetivo
Dar a todas as versões narrativas o mesmo núcleo profissional de storytelling, permitir uma versão autoral livre do Roteirista, preservar as histórias geradas e abrir uma biblioteca opcional de estilos adicionais sem aumentar automaticamente o custo do comparador principal.

## Núcleo compartilhado de Roteirista
Os quatro estilos formais do Prompt-Mestre herdam integralmente a skill `storyteller` e acrescentam apenas sua especialização:

1. 📖 Aventura — Roteirista + especialização Aventura.
2. 🎵 Poético/Rimado — Roteirista + especialização Poética.
3. 🌿 Fábula cristã — Roteirista + especialização Fábula.
4. ✨ Misto — Roteirista + especialização Mista.
5. ⭐ Versão do Roteirista — mesma skill-base, com liberdade criativa para escolher a melhor estratégia narrativa.

A skill-base inclui storytelling infantil, gancho inicial, page-turn structure, read-aloud rhythm, arco emocional, ação visual, repetição suave, integração cristã natural, continuidade de série e fechamento memorável. Melhorias futuras no contrato `storyteller` passam automaticamente para os estilos que o herdam.

## Fluxo
1. Gerador de Ideias cria conceitos variados.
2. Curador organiza emoção, lição e referência bíblica candidata.
3. A autora pode pedir **Visão do Roteirista** antes da história completa.
4. Comparative Story Director gera os quatro estilos formais com a mesma skill-base do Roteirista.
5. **Versão do Roteirista** gera uma quinta história completa com liberdade autoral.
6. Todas as versões ficam na **Biblioteca de Versões Narrativas**.
7. A autora pode tornar outra versão ativa depois, sem regenerar as histórias.
8. Derivados da versão anterior são preservados em histórico antes da troca.
9. A área **➕ Explorar outros estilos** permite gerar estilos adicionais somente sob demanda.

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

### Originalidade
O sistema usa os princípios gerais de conto cumulativo/lengalenga, mas proíbe copiar frases, refrões, personagens ou estruturas textuais distintivas de obras existentes.

## Biblioteca de Versões
- Aventura, Poético/Rimado, Fábula, Misto, Roteirista e estilos adicionais podem ser preservados.
- Escolher uma versão não apaga as outras.
- A autora pode voltar e mudar a versão ativa sem pagar novamente por versões já geradas.
- Ao trocar a versão ativa, derivados já produzidos são arquivados antes da invalidação dos derivados ativos.
- Mudanças de coleção/faixa arquivam versões antigas em vez de apagá-las.

## Segurança editorial
- premissa, personagens, faixa etária, lição cristã e referência bíblica continuam protegidos;
- nenhuma versão é aprovada automaticamente;
- nenhuma ilustração é gerada durante a comparação narrativa;
- o Revisor continua independente do Roteirista;
- estilos adicionais só são gerados quando a autora pedir.

## Correção adicional
`licao_final` estruturada em JSON/dict é normalizada para texto editorial limpo antes de aparecer na interface ou seguir para o livro, evitando exibição de objetos como `{'texto': ...}`.

## Validação
- GitHub Actions: **337 passed, 1 skipped, 0 failures**.
- Testes confirmam que `ESTILOS_NARRATIVOS` continua contendo exatamente os quatro estilos oficiais.
- Testes confirmam que `Cumulativo/Lengalenga` fica em registro separado de estilos adicionais.
- Testes confirmam herança da skill `storyteller`, originalidade, aplicação como versão ativa e exposição da biblioteca opcional na interface.
