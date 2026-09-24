# Refinamento 28 — FaithBloom Emotional Experience Engine™

## Objetivo

Fazer com que sentimentos e emoções sejam **vivências narrativas reais**, e não apenas rótulos decorativos. A criança acompanha acontecimentos bons e difíceis, percebe como eles afetam o personagem, vê reações, escolhas, consequências, descobertas e transformação.

O sistema usa somente mecanismos gerais de narrativa emocional. Não copia personagens, cenas, diálogos, estruturas distintivas, voz autoral ou identidade de obras existentes.

## Princípio causal

**acontecimento concreto → emoção/sensação → reação → escolha/tentativa → consequência → descoberta/aprendizado → transformação**

Uma emoção importante deve aparecer por comportamento, corpo, expressão, pensamento, diálogo ou escolha — não apenas pela frase “ela ficou triste”.

## Regras editoriais

1. Emoções não são tratadas como “boas” ou “más”. O FaithBloom mostra formas saudáveis, morais e adequadas à idade de responder ao que se sente.
2. A personagem pode sentir emoções contraditórias ao mesmo tempo quando isso for adequado à faixa etária.
3. Aprendizado pode nascer de alegria, amizade, descoberta, vitória, humor, gratidão e amor — não somente de dor ou erro.
4. Frustração, tristeza, perda, saudade, rejeição, vergonha, medo, raiva, nojo, inveja, ansiedade, timidez e solidão podem existir sem serem apagados artificialmente.
5. Alegria, curiosidade, amor, pertencimento, coragem, esperança, alívio, gratidão, paz e celebração também precisam ter função narrativa real quando aparecerem.
6. Fé acompanha a emoção; não a invalida. A personagem pode continuar triste, com medo ou ansiosa e ainda encontrar consolo, ajuda, coragem e confiança em Deus.
7. Perdas e decepções não precisam ser magicamente revertidas. A transformação pode significar lembrar, aceitar apoio, perdoar, recomeçar, amadurecer ou seguir em frente.
8. Humor pode coexistir com vulnerabilidade sem ridicularizar sofrimento ou humilhar personagens.
9. Não é necessário trocar de emoção em cada cena. Sentimentos importantes podem se desenvolver e respirar por várias cenas.
10. A descoberta deve emergir da experiência; evitar mentor/adulto entregando toda a moral antes que a criança-personagem viva o conflito.

## Profundidade por faixa etária

### 3–5 anos
Emoções predominantemente concretas e imediatas. Alegria, tristeza, medo, raiva, surpresa, frustração, ciúme simples, vergonha simples, curiosidade, carinho e alívio. Mostrar principalmente por ação, rosto, corpo e falas curtas.

### 3–8 anos
Faixa ampla com emoções concretas e espaço para frustração, insegurança, vergonha, ciúme, preocupação, inveja, ansiedade leve, coragem, esperança e gratidão. Pequenas emoções mistas podem aparecer quando a ação deixa a situação compreensível.

### 6–8 anos
Mais espaço para comparação, pertencimento, medo de falhar, culpa ligada ao comportamento, orgulho saudável, inveja, vergonha, timidez, ansiedade antecipatória leve e insegurança. É apropriado mostrar duas emoções coexistindo, por exemplo: feliz pela amiga e decepcionada consigo; com medo e curiosa ao mesmo tempo.

### 9–12 anos
Permite maior nuance: ambivalência, ansiedade antecipatória, medo de julgamento, exclusão, solidão, saudade, perda/luto em abordagem segura, identidade, autoestima, responsabilidade, lealdade, injustiça e pressão social. A personagem pode levar mais tempo para compreender o que sente.

Esses perfis são **heurísticas editoriais**, não regras universais de desenvolvimento infantil nem diagnóstico psicológico.

## Integração no FaithBloom

O engine é injetado em `instrucao_faixa_etaria()`. Isso faz com que a mesma orientação emocional chegue automaticamente aos fluxos que já usam o Age Profile Engine, incluindo:

- quatro estilos narrativos formais;
- estilos adicionais;
- ⭐ Versão do Roteirista;
- 🤖 ponte de IA externa por Prompt/Ideia;
- Revisor Editorial;
- demais agentes que consomem a instrução etária oficial.

Ele trabalha junto, e não no lugar, do **FaithBloom Heart Arc™**:

**Encantamento → Emoção → Experiência → Descoberta → Transformação → Fé**

O Heart Arc descreve a macrojornada. O Emotional Experience Engine descreve **como a vida emocional acontece por dentro dessa jornada**.

## Regra-mãe

> A criança entra pela história, vive acontecimentos reais com o personagem, sente junto, percebe escolhas e consequências e só então encontra uma descoberta, transformação e verdade de fé.
