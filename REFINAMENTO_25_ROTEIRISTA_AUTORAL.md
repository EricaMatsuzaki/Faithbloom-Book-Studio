# Refinamento 25 — Roteirista Autoral, Skills Compartilhadas e Biblioteca de Versões

## Objetivo
Permitir que a autora compare os quatro estilos formais com uma quinta versão autoral, garantindo que **todas as versões sejam escritas sobre a mesma skill profissional `storyteller` do Roteirista** e que nenhuma versão já criada seja perdida.

## Arquitetura narrativa
Todos os agentes que escrevem história herdam o mesmo núcleo profissional do Roteirista (`storyteller`):
- storytelling infantil;
- gancho inicial;
- page-turn structure;
- read-aloud rhythm;
- arco emocional;
- ação visual;
- repetição suave;
- integração cristã natural;
- continuidade de série;
- fechamento memorável.

Sobre esse núcleo comum, os quatro estilos recebem especializações diferentes:
1. **📖 Aventura — Roteirista + especialização Aventura**
2. **🎵 Poético/Rimado — Roteirista + especialização Poética**
3. **🌿 Fábula cristã — Roteirista + especialização Fábula**
4. **✨ Misto — Roteirista + especialização Mista**
5. **⭐ Escolha do Roteirista — Roteirista com liberdade criativa**, sem obrigação de imitar um estilo formal isolado.

A comparação passa a ser editorialmente justa: todos recebem o mesmo padrão-base de storytelling; o que muda nos quatro estilos é a forma de contar, enquanto a quinta versão permite ao Roteirista escolher livremente a estratégia que considerar mais forte.

## Fluxo
1. Gerador de Ideias cria conceitos variados.
2. Curador organiza emoção, lição e referência bíblica candidata.
3. A autora pode pedir **Visão do Roteirista** antes da história completa.
4. Comparative Story Director gera os quatro estilos formais, cada um herdando `storyteller` + sua especialização.
5. **Versão do Roteirista** gera uma quinta história completa usando a mesma skill `storyteller`, com liberdade para escolher a melhor estratégia narrativa.
6. Todas as versões ficam na **Biblioteca de Versões Narrativas**.
7. A autora pode tornar outra versão ativa depois, sem regenerar as histórias.
8. Derivados da versão anterior são preservados em histórico antes da troca.

## Benefício de manutenção
O contrato `storyteller` é uma fonte central. Quando a skill do Roteirista evoluir — por exemplo, gancho, page-turn, ritmo em voz alta ou critérios de fechamento — os quatro estilos comparativos passam a receber a mesma evolução automaticamente, sem duplicar essas regras em quatro agentes diferentes.

## Segurança editorial
- premissa, personagens, faixa etária, lição cristã e referência bíblica continuam protegidos;
- nenhuma versão é aprovada automaticamente;
- nenhuma ilustração é gerada durante a comparação;
- troca de versão invalida os derivados ativos, mas os preserva em histórico;
- mudanças de coleção/faixa arquivam versões antigas em vez de apagá-las;
- o Revisor continua independente do Roteirista para manter controle de qualidade real.

## Correção adicional
`licao_final` estruturada em JSON/dict é normalizada para texto editorial limpo antes de aparecer na interface ou seguir para o livro, evitando exibição de objetos como `{'texto': ...}`.

## Validação
O Refinamento 25 possui testes específicos que verificam que os quatro estilos herdam o contrato `storyteller` e continuam preservando suas especializações. O resultado final do GitHub Actions deve ser registrado após a execução do commit atual.
