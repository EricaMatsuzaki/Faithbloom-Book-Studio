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
- Psicologia das cores e emoções é **obrigatória cena por cena/página por página** como direção visual.
- A tabela do Prompt-Mestre Erica Matsuzaki é a **fonte cromática canônica**.
- A roda de Plutchik é usada como **taxonomia emocional** para família, intensidade e combinações; suas cores não substituem a tabela canônica do FaithBloom.
- A paleta emocional nunca pode recolorir Character DNA e nunca deve transformar a cena inteira em monocromática.

## Entregas

### Narrative Style System

- `agents/estilos_narrativos.py` centraliza os quatro estilos.
- O Roteirista lê `estilo_narrativo` e incorpora a instrução correspondente ao prompt de geração.
- O comparador possui dois modos:
  - **Amostra rápida dos 4 estilos**: não altera título, moral, cenas nem aprovação da história.
  - **História completa nos 4 estilos**: permite aplicar uma versão completa; ao aplicar, `revisao_aprovada=False` para obrigar nova revisão editorial.
- Personagens, premissa, lição cristã e referência bíblica devem permanecer equivalentes entre as versões.
- A narrativa recebe musicalidade infantil leve, repetição natural, onomatopeias equilibradas quando ligadas à ação e uma jornada com movimento, humor leve, tensão segura, transformação emocional, descoberta espiritual e recompensa/celebração.
- As quatro histórias completas também geram os metadados emocionais cena a cena, para a versão escolhida não perder a integração com o Emotional & Color Director.

### Emotional & Color Engine

O sistema existente `emotion_colors.py` + `emotional_color_director.py` foi ampliado sem criar um segundo motor concorrente.

#### Camada 1 — Tabela canônica do Prompt-Mestre

A tabela oficial permanece:

| Emoção | Cor-base | Atmosfera | Uso espiritual/editorial |
| --- | --- | --- | --- |
| Alegria | amarelo-dourado | brilho leve | Amor de Deus e gratidão |
| Tristeza | azul-claro | suave e reflexiva | Deus consola corações |
| Medo | roxo-escuro | fria e contrastada | Confiar em Deus |
| Raiva | vermelho/laranja | forte | Perdão e domínio próprio |
| Nojo | verde-claro | difusa e sutil | Escolher o que é puro |
| Ansiedade | rosa/lilás | névoa suave | Entregar preocupações |
| Vergonha | pêssego | doce e vulnerável | Somos amados |
| Inveja | verde-musgo | luz fria | Contentamento |
| Tédio | cinza-azulado | lenta | Redescobrir propósito |
| Esperança/Fé | dourado + azul-celeste | luminosa | Clímax espiritual/final |

Cada emoção canônica também possui **cores de apoio** para evitar monocromia.

#### Camada 2 — Emoções complementares

Curiosidade, frustração, decepção, insegurança, acolhimento, gratidão, descoberta espiritual, paz e encantamento funcionam como nuances que apontam para uma base canônica e refinam atmosfera, luz e cores de apoio.

#### Camada 3 — Plutchik

`emotional_color_director.py` formaliza as 8 famílias de Plutchik:

- alegria;
- confiança;
- medo;
- surpresa;
- tristeza;
- nojo;
- raiva;
- antecipação.

A intensidade 1–5 é convertida em nível emocional baixo/médio/alto (por exemplo, serenidade → alegria → êxtase; apreensão → medo → terror). Combinações reconhecidas, como antecipação + alegria → otimismo, são registradas como metadados emocionais. Para livros de 3–8 anos, isso orienta a direção interna do sistema; não obriga o texto infantil a usar termos intensos como “terror” ou “fúria”.

#### Metadados por cena

`CenaTexto` e o Roteirista passam a formalizar, por cena:

- `emocao` principal canônica;
- `emocao_secundaria` opcional;
- `intensidade_emocional` 1–5;
- `transicao_emocional` opcional;
- expressão/personagem principal;
- figurino e contexto visual.

Exemplo de transição: `tristeza → começando a surgir esperança`.

#### Aplicação visual

O Ilustrador recebe de forma determinística:

- emoção e subemoção;
- intensidade;
- leitura Plutchik;
- cor-base canônica;
- cores de apoio;
- atmosfera e luz;
- intenção espiritual/editorial;
- transição emocional;
- regra de não monocromia;
- Identity Lock / Character DNA.

A transição deve aparecer como evolução gradual de luz, atmosfera e cores do cenário, nunca como troca brusca de toda a imagem.

### Emotional & Color Director UI

A página `pages/17_🎭_Emotional_Color_Director.py` agora pode trabalhar com o livro ativo e permite revisar, cena por cena:

- emoção principal;
- subemoção;
- intensidade 1–5;
- transição emocional;
- trava de emoção;
- instrução editorial da autora;
- cor-base e cores de apoio;
- família/nível Plutchik;
- uso espiritual/editorial.

O mapa pode ser salvo em `mapa_emocional` **antes da geração das ilustrações**. A tela não gera imagens. Projetos antigos com emoções acentuadas ou intensidade inválida são normalizados com fallback seguro para revisão, sem crash do Studio.

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
- **Recomendações:** estilo não escolhido, Boas-vindas ausente, Pais/Educadores ausente, Ficha Pedagógica ausente, menos de 3 páginas para colorir, mapa emocional ausente/incompleto ou metadados emocionais por cena incompletos.
- **Aprovado:** psicologia das cores página por página quando o mapa corresponde à estrutura atual da história.

O Quality Guardian existente continua responsável pelo bloqueio grave quando houver evidência de que a direção emocional recoloriu uma característica bloqueada do personagem.

### Pipeline

- `graph.py` usa `LivroStatePromptMestre`, preservando os novos campos no LangGraph.
- Após o Revisor aprovar a história, o pipeline automatizado gera os complementos editoriais antes de seguir ao Ilustrador.
- `agents/diagramador.py` inclui o compliance no checklist e impede `pacote_pronto=True` quando a Moral está ausente.
- O Ilustrador consome o Emotional & Color Director em cada cena.

## Segurança editorial

1. Amostra de estilo não substitui conteúdo aprovado.
2. História completa escolhida exige nova revisão.
3. A IA não valida automaticamente a obra como pronta.
4. Texto bíblico completo continua protegido pelo Bible Guard; este refinamento usa somente referência bíblica nos complementos.
5. O padrão de 3 páginas para colorir não é alterado.
6. Plutchik organiza emoção; não substitui a tabela de cores do Prompt-Mestre.
7. Psicologia das cores altera ambiente/luz/atmosfera, nunca identidade canônica dos personagens.
8. Cenas não devem ficar monocromáticas apenas para representar emoção.
9. Transições cromáticas devem acompanhar a mudança emocional gradualmente.

## Testes dedicados

Além dos testes anteriores do Refinamento 24, `tests/test_refinamento24_emotional_color_engine.py` cobre:

- preservação da tabela canônica;
- mapeamento Plutchik independente das cores;
- subemoção, intensidade e transição;
- schema formal dos campos emocionais da cena;
- regra não monocromática;
- Character DNA protegido;
- passagem da direção emocional completa ao prompt do Ilustrador;
- compatibilidade com intensidade legada inválida;
- exigência dos metadados emocionais também nas quatro histórias completas.

`tests/test_refinamento24_prompt_mestre.py` também valida a regra de psicologia das cores página por página no compliance.

## Limite deste refinamento

Os novos conteúdos editoriais ficam estruturados no estado do livro e disponíveis ao pipeline. A criação de **páginas físicas dedicadas** para Boas-vindas, Pais/Educadores e Ficha Pedagógica no `renderizador_editorial.py` deve ser feita em um passo separado e testado contra paginação, paridade, KDP preflight e PDFs já existentes. Este refinamento evita alterar silenciosamente o layout print-ready atual.
