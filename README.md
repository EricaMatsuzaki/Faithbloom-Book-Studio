# Pipeline de agentes - Livros infantis (Erica Matsuzaki)

Esqueleto funcional do pipeline discutido: 7 agentes em LangGraph que
levam do briefing da história até o pacote pronto para publicação
manual na KDP.

## Estrutura

```
state.py            -> estado compartilhado entre os agentes
emotion_colors.py    -> dicionário fixo emoção -> cor -> atmosfera
kdp_rules.py         -> regras de páginas mínimas, idiomas elegíveis, e
                        cálculo de dimensões de capa (lombada, wrap)
marca.py             -> sobrepõe faixa/selo da coleção via PIL (NÃO
                        gerados pela IA - garante consistência exata)
openrouter_client.py -> chamadas reais de texto e imagem via OpenRouter
app.py               -> frontend Streamlit para criar um livro do ZERO
app_retomar.py       -> frontend Streamlit para RETOMAR um livro cujo
                        roteiro já existe (ex: o livro de Natal),
                        pulando Curador/Roteirista/Revisor
historia_natal.py    -> roteiro do livro de Natal já transcrito, pronto
                        para usar com app_retomar.py
armazenamento.py     -> salva cada livro finalizado como JSON local
                        (passo intermediário antes de um banco de dados
                        real - ver seção de roadmap abaixo), organizado
                        por coleção, e mantém a biblioteca de
                        personagens de cada coleção separada

## Livros de colorir (projeto separado)

Diferente dos livros com história, um livro de colorir é só um tema
visual coeso (bichinhos, princesas, carros, aviões, navios, objetos
fofos - qualquer coisa) com várias páginas dentro, sem narrativa.

```
state_colorir.py             -> estado do projeto (mais simples que
                                 o LivroState - sem roteiro/dedicatória)
agents/gerador_ideias_colorir.py -> sugere temas de livro de colorir,
                                 cobrindo tipos variados, não só animais
agents/line_art_colorir.py   -> gera cada página + a capa; aplica o
                                 código visual macho/fêmea quando o
                                 tema tem personagens com gênero
agents/diagramador_colorir.py -> monta o layout do miolo (rosto/título
                                 + "este livro pertence a" + páginas de
                                 colorir com VERSO EM BRANCO cada uma +
                                 branco extra se precisar completar
                                 número par) e valida contra a KDP
                                 (mínimo 24 páginas p/ preto e branco)
app_colorir.py                -> frontend Streamlit dedicado
```

Regra de estilo fixa (macho/fêmea, quando o tema usa personagens com
gênero): macho tem olhos sem cílios e blush em círculo tracejado;
fêmea tem cílios, blush em coração, e acessório (laço). Temas sem
gênero (veículos, objetos) usam só o estilo base, sem essa distinção.

A capa é gerada na MESMA técnica vetor simples do miolo (nunca
aquarela/pintura), usando uma página de line art já aprovada como
imagem-base - isso resolve o problema de inconsistência entre capa e
miolo que a Erica teve no "Cute Friends". Assim como nos livros de
história, capa e contracapa são dois arquivos SEPARADOS (`capa_ebook`
e `capa_fisica_wrap`), com a mesma lógica de cálculo de lombada da
KDP (`kdp_rules.py`) e a mesma composição de selo/faixa via PIL
(`marca.py`) - reaproveitável entre livros de colorir se você usar o
mesmo nome de marca. O `diagramador_colorir_node` roda antes da
geração de capa e calcula a contagem REAL de páginas do miolo -
incluindo o VERSO EM BRANCO atrás de cada página de colorir (padrão da
indústria: giz de cera, lápis de cor e principalmente marcador
atravessam o papel fino da KDP e estragariam o desenho seguinte se as
páginas fossem impressas dos dois lados). Isso praticamente dobra a
contagem de páginas em relação ao número de desenhos - 20 desenhos
viram ~44 páginas de miolo, contando rosto/título e "este livro
pertence a".
agents/
  curador_tema.py       -> a partir só de um tema/resumo, sugere
                           emoção, versículo e lição (autora confirma
                           ou edita antes de seguir)
  gerador_ideias.py     -> sugere várias ideias de tema do zero, para
                           quando faltar inspiração
  criador_personagem.py -> expande uma ideia curta ("um coelhinho
                           tímido") no DNA visual completo de um
                           personagem novo, sob demanda
  roteirista.py       -> escreve a história (cadência narrativa fixa)
  revisor.py           -> checa continuidade e adequação etária
  ilustrador.py        -> NÚCLEO da consistência visual (ver abaixo)
  atividades_colorir.py -> 3 páginas de line-art para colorir
                            (início, virada emocional, final)
  audiobook.py           -> roteiro com pausas/entonação + narração
                            real em MP3 via TTS da OpenRouter
  dedicatoria.py       -> dedicatória dinâmica ligada ao tema
  tradutor.py           -> tradução + localização + regra do versículo
  sinopse.py             -> sinopse de vendas (KDP + contracapa)
  pesquisa_mercado.py    -> sugere 7 palavras-chave e categorias pra
                            KDP (ver aviso de limitação abaixo)
  diagramador.py         -> layout final + validação KDP
  capa.py                -> capa eBook + capa física (wraparound)
  marketing.py           -> material de lançamento: post de Instagram,
                            descrição Pinterest, e-mail de anúncio,
                            pedido de avaliação
graph.py             -> monta o LangGraph completo
main.py              -> exemplo de execução via terminal
pages/7_🚀_Lançamento.py -> painel: palavras-chave, categorias,
                            calculadora de preço/royalty (fórmula
                            oficial da KDP), material de divulgação
```

## Sobre "virar best-seller" — o que este pipeline cobre e o que não cobre

O pipeline resolve bem a parte de PRODUÇÃO (consistência visual,
conformidade técnica KDP, estrutura narrativa, marca). O painel de
Lançamento acrescenta pesquisa de palavras-chave/categoria,
calculadora de preço/royalty e material de divulgação - peças que
antes faltavam completamente. IMPORTANTE: nenhuma dessas ferramentas
usa dados reais de venda/busca da Amazon (não existe API pública pra
isso) - são sugestões por boas práticas gerais, um ponto de partida,
não uma garantia. O que continua fora do escopo do código, e pesa
muito pra sucesso de vendas real: qualidade estética final da
ilustração (revisão humana sempre necessária antes de publicar),
tração de marketing de verdade (redes sociais, lista de e-mail,
parcerias), avaliações dos primeiros leitores, e ajuste de
preço/categoria ao longo do tempo observando o desempenho real (KDP
Reports).

## Identidade visual

`.streamlit/config.toml` define o tema de cores (teal + dourado + creme,
baseado no selo/faixa que a Erica já usa) e `estilo.py` traz o CSS
compartilhado (cabeçalho com gradiente, cards de navegação, badges de
status, sidebar estilizada) aplicado em todas as páginas via
`aplicar_estilo()` e `hero(titulo, subtitulo)`. Pra manter a
identidade consistente ao criar novas páginas, sempre chamar essas
duas funções logo depois do `st.set_page_config(...)`.

## Como rodar a interface (menu lateral com todas as ferramentas)

```
export OPENROUTER_API_KEY="sua-chave-aqui"
pip install -r requirements.txt
streamlit run app.py
```

O Streamlit gera o menu lateral automaticamente a partir dos arquivos
em `pages/` - `app.py` é só a tela inicial (visão geral e atalhos).
As ferramentas ficam todas no menu lateral:

```
app.py                                  -> Home/hub (visão geral)
pages/
  1_📖_Criar_do_Zero.py                  -> escrever uma história nova
  2_📚_Retomar_Livro.py                   -> roteiro já pronto, pula pro Ilustrador
  3_🖍️_Livros_de_Colorir.py                -> projetos de line art
  4_🎯_Ir_Direto_para_Etapa.py              -> roda só UM agente específico,
                                             em cima de um livro já salvo
                                             (ex: só regerar a capa, só
                                             rodar o Tradutor de novo)
  5_🔍_Analisar_Livro.py                     -> vê tudo que foi gerado pra um
                                             livro salvo: texto cena a
                                             cena, personagens usados,
                                             dedicatória, sinopse,
                                             traduções, checklist KDP
  6_👤_Personagens.py                         -> biblioteca de personagens
                                             de cada coleção, com a
                                             referência visual de cada um
```

## O que resolve o problema de consistência visual

O `agents/ilustrador.py` implementa a solução para o problema que você
teve na prática (precisar pedir várias vezes até a imagem ficar
parecida):

1. Gera **uma vez** uma "character sheet" de referência por personagem
   (3-4 poses/ângulos).
2. Toda cena seguinte usa essa imagem como **imagem-base** (não gera
   mais só a partir de texto) - isso é o que trava a aparência.
3. Separa **DNA fixo** (nunca muda: espécie, olhos, proporção) de
   **figurino variável** (roupa/acessório, decidido pelo Roteirista
   conforme a narrativa, nunca aleatoriamente).
4. Gera também a **capa**, com os elementos fixos de marca da coleção:
   a barra branca no topo com o nome da coleção em maiúsculas, o
   título grande abaixo, e o nome da autora na parte inferior - usando
   a mesma referência visual do protagonista para manter consistência
   entre capa e miolo.

Para isso funcionar de verdade você precisa de um provedor de imagem
com suporte a referência visual: GPT Image, Flux (com IP-Adapter),
Midjourney (`--cref`) ou Ideogram são as opções mais confiáveis hoje.

## Coleções

Cada livro pertence a uma coleção (ex: "Pequenas Histórias, Grandes
Lições"). Personagens são reutilizáveis DENTRO da mesma coleção (Mel,
Téo, Manu, Max aparecem como opção em todo livro novo dessa coleção),
mas nunca vazam pra uma coleção diferente — uma coleção nova sempre
começa com biblioteca de personagens vazia. Isso é controlado por
`armazenamento.carregar_biblioteca_personagens()` /
`atualizar_biblioteca_personagens()`, separado por pasta em
`bibliotecas_personagens/`.

## Capa, contracapa e tamanho do livro

O tamanho do livro (trim size) NÃO é adivinhado pelo sistema - é
escolhido na tela de coleção (`trim_largura_in`/`trim_altura_in`,
padrão 8.5"x8.5"). A partir disso e da contagem final de páginas,
`kdp_rules.calcular_dimensoes_capa_fisica()` calcula a largura exata
da lombada e o tamanho total do arquivo de capa física, seguindo a
fórmula oficial da KDP (bleed de 0.125", 300 DPI).

Dois arquivos SEMPRE separados do miolo e um do outro:
- `capa_ebook` - só a arte frontal, tamanho de pixel recomendado pra eBook.
- `capa_fisica_wrap` - o arquivo único wraparound (contracapa + lombada
  + capa) no tamanho exato calculado pra aquele livro específico.

O selo/emblema da coleção e a faixa "COLEÇÃO X" são elementos de marca
FIXOS - eles não são redesenhados pela IA a cada capa (isso
reintroduziria inconsistência). A autora envia um PNG do selo (e
opcionalmente da faixa) uma vez na tela de coleção, e `marca.py`
sobrepõe essa mesma imagem via PIL em toda capa gerada dali em diante.
Se nenhuma faixa for enviada, o sistema desenha uma faixa simples com
fonte real (não pela IA).

## Privacidade — dados pessoais nunca vão pro código

O repositório é **público** no GitHub. Nomes reais de família (lista
da dedicatória) NUNCA devem aparecer hardcoded em nenhum arquivo `.py`
— eles são digitados na tela do Streamlit a cada sessão, e ficam
salvos só localmente (`livros_salvos/`, `bibliotecas_personagens/`,
`marca_colecoes/`), pastas que o `.gitignore` já exclui do versionamento.
Se algum desses arquivos já foi commitado por engano antes deste
`.gitignore` existir, ele continua no histórico do Git mesmo depois de
apagado - nesse caso é preciso reescrever o histórico (`git filter-repo`
ou similar) ou, mais simples, tornar o repositório privado.

## Roadmap para virar SaaS de verdade (fila, banco, autenticação)

O que existe hoje já resolve "gerar um livro pra mim, testando na minha
máquina". Pra virar um produto que outras pessoas usam, faltam 3 camadas
em volta do motor - nenhuma delas muda a lógica dos agentes, só embrulha:

1. **Fila de jobs**: a geração leva minutos (várias chamadas de LLM +
   20+ imagens), então não pode ser uma resposta HTTP síncrona. Solução
   simples: Celery + Redis, ou um worker que lê uma fila e roda
   `graph.invoke()` em segundo plano, salvando o progresso pra o
   frontend consultar.
2. **Banco de dados**: hoje os resultados só existem em memória/arquivo
   local. Precisa de uma tabela de "livros" (status, dono, JSON do
   estado final) e um bucket de armazenamento pras imagens geradas
   (ex: Postgres + S3-compatível).
3. **Autenticação e billing**: se for produto multiusuário, precisa de
   login e controle de quota/créditos (cada geração custa em tokens de
   texto + imagem via OpenRouter).

Nenhuma dessas 3 é grande sozinha, mas juntas dão bastante trabalho de
infraestrutura - normalmente é o próximo passo depois de validar que o
motor gera livros com a qualidade que você quer.

## Sobre audiobook: KDP "virtual voice" vs. o áudio gerado aqui

A KDP tem uma opção própria chamada "Audiobooks with virtual voice"
(beta, só EUA por enquanto) que narra automaticamente o texto do seu
ebook - mas é a Amazon quem escolhe a voz e a entonação, sem usar as
marcações de pausa/emoção que a Erica pediu.

O `agents/audiobook.py` + `narracao_node` fazem o caminho oposto: geram
o roteiro com controle de pausa/entonação e já produzem o MP3 real via
TTS (Gemini 3.1 Flash TTS por padrão, que aceita tags inline
parecidas com as nossas). Esse áudio é o que você usaria para
distribuir via ACX (a plataforma de audiobook da Amazon/Audible,
separada da KDP) ou de forma independente - dando controle total sobre
a interpretação, o que importa bastante pra evangelização infantil.

## O que falta para rodar de verdade

1. Instalar dependências: `pip install langgraph anthropic --break-system-packages`
2. Implementar `chamar_llm()` e `gerar_imagem()` em `main.py` com suas
   chaves de API reais.
3. Preencher `lista_dedicatoria` em `main.py` com os dados reais da
   família (não deixados aqui por serem dados pessoais).
4. Trocar o retorno "bruto" dos agentes por parsing real de JSON
   (recomendo `pydantic` para validar a estrutura que cada agente
   devolve).
5. Adicionar um passo de aprovação humana depois da character sheet do
   Ilustrador, antes de gerar as cenas (evita gastar créditos de imagem
   gerando 24+ cenas com um personagem que você ainda não aprovou).

## Regras de negócio já embutidas no código

- Páginas mínimas: 24 (premium color), nunca abaixo, config em
  `paginas_minimas`.
- Layout alterna lado texto/imagem a cada spread (padrão de mercado).
- Índia cai automaticamente para "somente eBook" na tradução (paperback
  não suportado hoje).
- Versículo bíblico nunca é traduzido literalmente - o prompt do
  Tradutor instrui buscar a referência oficial no idioma alvo.
- O pipeline NUNCA publica sozinho - `pacote_pronto` só indica que está
  tudo pronto para você clicar em "Publicar" manualmente na KDP,
  inclusive preenchendo a declaração de conteúdo gerado por IA.
