# Refinamento 25 — Roteirista Autoral e Biblioteca de Versões

## Objetivo
Permitir que a autora compare os quatro estilos formais com uma quinta versão gerada pela skill real `storyteller` do Roteirista, sem perder nenhuma versão já criada.

## Fluxo
1. Gerador de Ideias cria conceitos variados.
2. Curador organiza emoção, lição e referência bíblica candidata.
3. A autora pode pedir **Visão do Roteirista** antes da história completa.
4. Comparative Story Director continua gerando os quatro estilos formais.
5. **Versão do Roteirista** gera uma quinta história completa usando a skill formal `storyteller`, com liberdade para escolher a melhor estratégia narrativa.
6. Todas as versões ficam na **Biblioteca de Versões Narrativas**.
7. A autora pode tornar outra versão ativa depois, sem regenerar as histórias.
8. Derivados da versão anterior são preservados em histórico antes da troca.

## Segurança editorial
- premissa, personagens, faixa etária, lição cristã e referência bíblica continuam protegidos;
- nenhuma versão é aprovada automaticamente;
- nenhuma ilustração é gerada durante a comparação;
- troca de versão invalida os derivados ativos, mas os preserva em histórico;
- mudanças de coleção/faixa arquivam versões antigas em vez de apagá-las.

## Correção adicional
`licao_final` estruturada em JSON/dict agora é normalizada para texto editorial limpo antes de aparecer na interface ou seguir para o livro, evitando exibição de objetos como `{'texto': ...}`.

## Validação
GitHub Actions: 330 passed, 1 skipped, 0 failures no commit de implementação/testes.
