# Refinamento 23 — Character Guide, Looks, Scene Director e Prompt Livre

## Objetivo

Transformar **Personagens & Galeria** em uma central de personagens reutilizáveis, inspirada em um *character/style guide*: a identidade canônica fica bloqueada, enquanto roupa, acessórios, pose, ação, emoção, cenário, estação e festividade podem variar de forma controlada.

## Entregas

- **Biblioteca Oficial** passa a ler o `Character Universe` como fonte de verdade.
- **Character Guide** mostra campos bloqueados do Character DNA, variáveis controladas e variáveis livres de cena.
- **Base neutra candidata**: personagem limpo, corpo inteiro, fundo neutro; 1 resultado ou A/B/C; nasce como `MASTER_CANDIDATE` e nunca vira Master automaticamente.
- **Looks reutilizáveis**: figurino, acessórios temporários, estação, festividade, emoção/cenário opcionais e usos sugeridos.
- **Scene Director**: recebe trecho/frase da história; usa LLM textual para propor exatamente 3 direções visuais; cada proposta contém cenário, ação, poses, emoção, psicologia das cores, iluminação, câmera, figurino/acessórios e props; nenhuma imagem é gerada na etapa de ideias; a autora escolhe/combina antes de gerar 1 imagem ou A/B/C.
- **Prompt Livre & Variações**: a autora descreve livremente cenário, pose, emoção, roupa e acessórios; o app injeta automaticamente o Identity Lock; permite usar Look salvo e/ou asset existente como base; suporta personagem único ou cena multi-personagem.
- **Ações pós-geração**: renomear sem alterar ID; aprovar como `APPROVED_VARIATION` no mesmo asset; variar novamente preservando parent/version group; abrir para Line Art; arquivar; abrir Asset Library; encaminhar candidata aprovada para revisão de Master no Character Universe.

## Regras de segurança editorial

1. **Gerar ≠ aprovar ≠ promover Master.**
2. Aprovação de variação é *in place*; não duplica arquivo.
3. Master exige promoção humana explícita no fluxo existente.
4. Psicologia das cores atua em cenário, iluminação, contraste e atmosfera; não recolore olhos, cabelo, pele/pelagem ou marcas canônicas.
5. Origem em um livro não significa exclusividade: assets podem ser reutilizados conforme metadados/tags.
6. Arquivar remove do fluxo normal sem apagar histórico/bytes.
7. Exclusão permanente permanece protegida pelo Asset Library & Media Manager.

## Persistência

O refinamento reutiliza a infraestrutura existente:
- `Character Universe` para DNA/Masters/Reference Pack;
- `Asset Library` para assets, versões, tags e arquivo;
- storage backend local/Supabase;
- OpenRouter para LLM de texto e geração de imagem.

Nenhum Secret, configuração de deploy ou branch `main` é alterado por este refinamento.
