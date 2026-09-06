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

## Quality Guardian final

`quality_guardian.py` e `pages/25_🛡️_Quality_Guardian.py` implementam o gate final independente. Ele agrega evidências dos Studios anteriores, sinaliza bloqueios/recomendações, exige decisões explícitas da autora e somente então pode emitir um certificado **interno** FaithBloom. Ele não corrige o livro silenciosamente, não inventa notas percentuais e não substitui validações oficiais das plataformas.

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

## FaithBloom 2.0 — Fase 2: Editor Editorial

Adicionado ao fluxo de criação de livros:
- edição cena a cena antes de qualquer geração em massa de ilustrações;
- bloqueio de cenas aprovadas;
- histórico da versão anterior de cada cena;
- ações rápidas (simplificar, menos diálogo, mais emoção, mais ação visual, leitura em voz alta);
- prompt livre para alterar SOMENTE uma cena;
- alternativas de versículo e lição de moral com aprovação da autora;
- preservação de ilustrações já prontas por cena;
- passagem para referências dos personagens somente depois da aprovação editorial.

## FaithBloom 2.0 — Fase 3: Personagens e Galeria de Variações

Implementado nesta fase:
- primeira referência visual preservada como Opção 1;
- botão para gerar +2 opções sem apagar anteriores;
- criação de variação a partir da opção selecionada;
- prompt livre de ajuste (ex.: "mais fofuxa, menor, mais rosinha");
- seleção e aprovação explícita da aparência;
- DNA visual travado após aprovação;
- bloqueio da geração em massa de cenas enquanto houver personagem não aprovado;
- favoritos por variação;
- upload de uma nova referência como opção adicional;
- Galeria de Imagens separada da Biblioteca Oficial;
- salvar qualquer variação na Galeria para uso futuro;
- página Personagens agora possui abas Biblioteca Oficial e Galeria.

Observação: a Galeria desta fase usa armazenamento local, assim como o restante do protótipo atual. Para SaaS multiusuário, migrar para banco + object storage na fase de infraestrutura.


## FaithBloom 2.0 — Fase 4: Retomar Livro + Ilustração Cena por Cena

- `historia_natal.py` pode ser carregado diretamente em **Retomar Livro** sem passar por Roteirista/Revisor.
- Personagens precisam ser aprovados/travados antes das cenas, reaproveitando a Galeria de Variações da Fase 3.
- Cada cena agora aceita **Gerar**, **Gerar nova**, **Criar variação**, **Enviar imagem própria**, **Aprovar/travar**, **Salvar na Galeria** e **Voltar à versão anterior**.
- Pedidos livres por cena (ex.: “deixe Mel mais alegre, não altere Manu nem o cenário”) são aplicados somente àquela cena.
- A imagem anterior nunca é apagada ao gerar uma nova: fica em `historico_imagens_cenas`.
- O processamento final só é liberado depois de todas as imagens terem sido aprovadas; nessa etapa o sistema não regera as cenas já aprovadas.
- As cenas salvas na Galeria podem ser reutilizadas futuramente, inclusive como base para o Coloring Book Studio/Line Art.


## FaithBloom 2.0 — Fase 5: Qualidade de Impressão / KDP

Adicionado motor de preflight que mede pixels reais e PPI efetivo no tamanho final, calcula bleed, pixels mínimos, margem externa e gutter, e bloqueia exportação quando há arte abaixo do padrão. O original/master nunca é destruído; `preparar_master_print_ready()` cria uma cópia específica para impressão e não faz upscale silencioso.

Também foi corrigida a regra de royalties: paperback Amazon.com usa 50% abaixo do limiar e 60% a partir de US$9.99; a faixa de preço da opção de 70% do eBook Amazon.com foi atualizada para US$2.99–US$12.99 (vigente desde 07/07/2026).

O painel Lançamento agora tem a aba **Preflight KDP**. Esta fase NÃO marca automaticamente um livro como publicado/pronto: PDF final, fontes incorporadas, transparências achatadas, Print Previewer e prova física continuam checkpoints separados.


## FaithBloom 2.0 - Fase 6: Renderizador Editorial PDF

A Fase 6 adiciona o motor `renderizador_editorial.py` e transforma o layout lógico do
Diagramador em um PDF físico do miolo. O exportador trabalha com páginas individuais,
trim/bleed em medidas reais, gutter/margens seguras, ilustrações full-bleed, páginas de
texto e line arts dentro da safe area.

Fluxo no Painel de Lançamento:

1. Rode o Preflight KDP da Fase 5.
2. Abra a aba **PDF Print Ready**.
3. Gere o miolo somente quando os assets estiverem aprovados (ou marque explicitamente
   a opção de prova interna, que nunca deve ser confundida com arquivo final).
4. O FaithBloom inspeciona o PDF com `pypdf`: contagem de páginas, MediaBox/tamanho e
   detecção de fontes incorporadas.
5. Baixe o PDF e faça a validação humana no KDP Print Previewer + prova física.

Dependências novas: `reportlab` e `pypdf`.

**Importante:** capa física não é incluída no miolo. Ela continua sendo arquivo separado.
A próxima evolução recomendada é a montagem matemática do wrap físico (contracapa +
lombada + capa), em vez de pedir que a IA gere a geometria completa.

## FaithBloom 2.0 — Fase 7: Capa Física Profissional

A capa paperback deixou de ser um único wrap "desenhado" pela IA. O fluxo agora é:

1. gerar/enviar uma arte frontal sem texto;
2. gerar/enviar uma arte de contracapa sem texto;
3. calcular a lombada pelo total de páginas e tipo de papel;
4. montar matematicamente verso + lombada + frente, com bleed de 0.125";
5. reservar safe area e região de barcode;
6. aplicar título/autora/sinopse com fonte real (não tipografia inventada pela IA);
7. só usar texto na lombada quando o livro tiver mais de 79 páginas;
8. gerar preview PNG com guias e PDF final sem guias/crop marks;
9. validar automaticamente que o PDF da capa tem uma página e o tamanho físico esperado.

**Importante:** o KDP Cover Calculator/Template continua sendo a referência final antes do upload. Use exatamente o mesmo trim, papel e contagem de páginas do PDF final. O Print Previewer e a prova física continuam no checklist de publicação.

---

## FaithBloom 2.0 — Fase 8: Coloring Book Studio

A Fase 8 transforma o antigo gerador de line art em um estúdio independente para projetos **infantis, juvenis, adultos e personalizados**.

### Origens disponíveis por página

- Gerar nova line art com IA.
- Prompt livre da autora.
- Usar line art pronta sem gastar crédito de geração.
- Transformar foto real em line art.
- Transformar ilustração/imagem existente em line art.
- Reutilizar uma imagem salva na Galeria.
- Reutilizar personagem aprovado da Biblioteca de Personagens.

### Presets de estilo

Os estilos ficam em `presets_line_art/` e são reutilizáveis entre livros. Cada preset registra público, faixa/nível, espessura de contorno, complexidade, nível de fundo, tamanho das áreas para colorir, direção visual e prompt-base.

O sistema inclui presets iniciais (Baby Cute, Cute & Cozy, Junior Detail e Botanical Relax), mas a autora pode criar, salvar, favoritar, duplicar e excluir seus próprios estilos sem limite lógico imposto pelo código.

Uma página também pode receber uma instrução adicional sem alterar o preset salvo — por exemplo: “flores maiores, menos detalhes no fundo, personagem menor e mais fofo”.

### Histórico e variações

Uma imagem aprovada nunca é automaticamente apagada quando uma nova variação é solicitada. Cada página mantém `variacoes`, permitindo testar alternativas e voltar a uma versão anterior. A página só entra no fechamento do projeto depois da aprovação explícita.

### Integração com as fases anteriores

- A **Galeria** da Fase 3 pode fornecer imagens/cenas para virar line art.
- A **Biblioteca de Personagens** pode fornecer personagens oficiais para novas páginas.
- A **capa física** usa o compositor matemático da Fase 7 (frente e verso gerados separadamente; wrap montado pelo FaithBloom).
- O **PDF Print Ready do miolo** continua sob responsabilidade do renderizador da Fase 6.

### Observação de persistência

Galeria, presets e bibliotecas ainda usam armazenamento local para validação do motor. Antes do SaaS multiusuário em produção, devem migrar para banco de dados + object storage persistente.

---

## FaithBloom 2.0 — Fase 9: Galeria, Biblioteca e Persistência

Esta fase substitui a dependência direta de pastas locais por uma camada de storage configurável (`storage_backend.py`).

### Modos
- `local`: desenvolvimento; grava em `.faithbloom_data/`.
- `supabase`: recomendado no Streamlit Cloud; persiste livros, personagens, galeria, presets e assets em um bucket privado.

### Secrets do Streamlit (produção)
```toml
FAITHBLOOM_STORAGE_MODE = "supabase"
SUPABASE_URL = "https://SEU-PROJETO.supabase.co"
SUPABASE_SERVICE_ROLE_KEY = "SUA-CHAVE-SERVICE-ROLE"
FAITHBLOOM_SUPABASE_BUCKET = "faithbloom"
```
Crie antes no Supabase Storage um bucket privado chamado `faithbloom`. Nunca versione a service-role key.

### O que fica persistente
- projetos de Story Books e Coloring Books;
- imagens da Galeria;
- personagens oficiais e suas referências;
- selo/faixa das coleções;
- presets de Line Art;
- referências de imagens/áudios/PDFs usadas nos states, salvas como `fb://...` e materializadas sob demanda.

### Compatibilidade
A API pública de `armazenamento.py` foi preservada para manter as telas/agentes existentes. Há também um migrador que copia dados das pastas legadas para o backend ativo sem apagar os originais.

## Fase 10 — Interface Premium / Dashboard Futurista Acolhedor

A Fase 10 moderniza a experiência visual sem alterar o motor editorial das fases anteriores.

Principais mudanças:

- dashboard reorganizado em **Story Book Studio** e **Coloring Book Studio**;
- atalhos reais para Retomar Livro, Galeria, Personagens, Análise, Etapas e Lançamento;
- destaque rápido para retomar `historia_natal.py`;
- identidade visual premium com glassmorphism leve e gradientes teal/azul/lilás;
- componentes compartilhados em `estilo.py`, aplicados automaticamente às páginas existentes;
- métricas, botões, inputs, tabs, expanders e sidebar redesenhados;
- layout wide nos fluxos principais para aproveitar melhor telas desktop;
- responsividade básica para telas menores;
- o visual evita estética cyberpunk escura e mantém uma linguagem acolhedora/editorial.

A Fase 10 é deliberadamente visual: regras editoriais, persistência, impressão, KDP,
Coloring Studio e personagens continuam usando os módulos das fases anteriores.

## Fase 11 — Integração e testes end-to-end

A Fase 11 adiciona um **Quality Gate** antes de gastar créditos com produção em massa.

Novos arquivos:

- `integracao_e2e.py` — diagnóstico de ambiente, imports, contratos entre módulos e readiness do Story Book.
- `pages/9_🧪_Teste_End_to_End.py` — Central de Testes no Streamlit.
- `tests/test_integracao_e2e.py` — testes offline com `unittest`.
- `scripts_smoke_e2e.py` — smoke test via terminal, sem API.

O diagnóstico padrão **não chama OpenRouter**. Há um botão separado para uma única chamada curta de texto quando a autora quiser validar a chave/API conscientemente.

O livro `historia_natal.py` é o projeto piloto da integração: a Central verifica sua estrutura e oferece atalho para `Retomar Livro`, onde personagens devem ser aprovados antes das cenas. A estratégia recomendada é gerar 1 cena piloto, depois 3 cenas distribuídas pelo arco e só então o lote completo.

Rodar no terminal sem gastar créditos:

```bash
python -m unittest tests/test_integracao_e2e.py -v
python scripts_smoke_e2e.py
```

## Fase 12 — Piloto Visual do Livro de Natal

Antes de gerar as 22 cenas, o FaithBloom agora usa um **Visual Quality Gate**:
1. exige Mel, Manu e Max com aparência aprovada;
2. gera apenas uma cena crítica (por padrão, cena 8 com o trio);
3. exige checklist humano de identidade, cores/acessórios, proporções, figurino, emoção, cenário, ausência de texto e qualidade;
4. valida um lote de 3 cenas representativas (início/meio/final);
5. só então sinaliza que a produção completa está liberada.

Para provedores que recebem uma única `imagem_base`, o módulo `piloto_visual.py` cria uma **folha composta de referências aprovadas** dos personagens presentes na cena. Assim, uma cena com Mel + Manu + Max não depende apenas da referência do protagonista.

Página: `pages/10_🎄_Piloto_Visual.py`.


## Fase 13 — Custos, segurança e controle de geração

A Fase 13 adiciona guardrails de produção ao cliente OpenRouter:

- bloqueio de geração duplicada enquanto a mesma requisição está em andamento;
- cooldown curto para reduzir duplo clique acidental;
- retry apenas em falhas transitórias/429/5xx, com backoff exponencial;
- orçamento diário configurável e bloqueio preventivo antes da chamada;
- limite configurável de imagens por lote;
- estimativas de texto, imagem e áudio configuráveis por Secrets;
- aproveitamento de custo reportado pelo provedor quando disponível;
- log JSONL sanitizado em `.faithbloom_data/geracoes.jsonl`, sem prompt completo, headers ou chaves;
- mensagens de erro que não despejam payloads ou respostas sensíveis;
- painel `pages/11_🛡️_Custos_e_Seguranca.py` com simulador, resumo de orçamento e histórico.

**Importante:** as estimativas financeiras não são uma tabela oficial de preços. Modelos e provedores mudam; ajuste os valores nos Secrets conforme sua configuração real.

## Fase 14 — Fila de Produção persistente

A Fase 14 adiciona `fila_producao.py` e a página **🏭 Fila de Produção**.

Principais garantias:
- checkpoint persistente antes/depois de cada item;
- pausar, continuar e cancelar jobs;
- recuperação segura após restart: jobs `executando` voltam `pausados`;
- itens já `concluido` não são gerados novamente;
- falhas pausam a fila e preservam o erro/tentativas;
- lote respeita `FAITHBLOOM_MAX_IMAGENS_LOTE` da Fase 13;
- snapshot do state pode ser salvo como nova versão de livro a qualquer momento;
- imagens geradas pela fila **não são aprovadas automaticamente**: revisão humana continua obrigatória.

A implementação atual é uma fila cooperativa adequada ao Streamlit: o processamento acontece em passos/lotes acionados pela interface e cada passo é persistido. Para produção multiusuário contínua, mantenha esta API e mova o executor para um worker externo (Celery/RQ/serviço de jobs).

## Fase 15 — Pacote Comercial e de Publicação

Adiciona revisão centralizada de metadados, até 7 keywords, até 3 categorias, registro de conteúdo gerado por IA, checklist de readiness e exportação de um ZIP organizado com PDFs disponíveis, metadata, marketing e registros internos. O pacote auxilia o upload manual; não publica automaticamente e não substitui o KDP Previewer/prova física.

---

## Fase 16 — QA Final, Estabilização e Release Candidate

A Fase 16 fecha o ciclo principal do FaithBloom Book Studio 2.0. O objetivo desta fase não é adicionar um novo gerador, mas consolidar e testar as fases anteriores antes do deploy.

### O que foi acrescentado

- `qa_release.py`: quality gate offline de release.
- `release_info.py`: versão consolidada `2.0.0-rc1`.
- Página **✅ QA Final & Release** no Streamlit.
- Validação de sintaxe de todos os `.py`.
- Validação de dependências declaradas no `requirements.txt`.
- Verificação de rotas `pages/*.py` referenciadas pela interface.
- Verificação de padrões comuns de chaves/segredos acidentalmente versionados.
- Verificação do projeto piloto `historia_natal.py`.
- Execução integrada da suíte de testes automatizados.
- `.gitignore` de produção para caches, Secrets e assets temporários.
- Limpeza de `__pycache__`, `.pyc` e logs/runtime do pacote de distribuição.
- Correção de warnings de arquivos não fechados no teste da Fase 15.

### Quality gate offline

Na raiz do projeto:

```bash
python qa_release.py
```

ou:

```bash
python -m unittest discover -s tests -v
```

O gate offline **não chama a OpenRouter e não gasta créditos**.

### Release Candidate

Versão desta entrega:

```text
FaithBloom Book Studio 2.0.0-rc1
```

Antes de marcar a versão como estável, faça o smoke test real no Streamlit Cloud:

1. navegar por todas as páginas principais;
2. testar uma chamada mínima de texto;
3. gerar uma referência de personagem e uma cena piloto;
4. validar custo/log sanitizado;
5. salvar e reabrir um projeto no storage persistente;
6. gerar PDF de prova e capa de prova;
7. testar o fluxo `historia_natal.py` do ponto de retomada.

Depois desse smoke test, a recomendação é criar a tag/release estável no GitHub como `v2.0.0`.

---

## Refinamento 03 — Character Universe + Emotional & Color Director

Esta cópia parte do Refinamento 02 (Book Doctor) e adiciona Character Master/DNA estruturado,
variações protegidas, Style DNA e direção emocional/cromática cena a cena.
Consulte `REFINAMENTO_03_CHARACTER_EMOTIONAL_DIRECTOR.md`.

## Refinamento 04 — Restoration Studio + Book Doctor Integration

O Refinamento 04 transforma a auditoria do Book Doctor em um fluxo de restauração controlada:

- `restoration_studio.py` mantém um plano por projeto, decisões e versões derivadas.
- `pages/19_✨_Restoration_Studio.py` permite comparar **Original × Remastered**.
- Ações disponíveis: manter original, melhoria técnica, limpeza de line art, corrigir apenas personagem, reilustrar e criar variação.
- Character Master e Style DNA podem ser vinculados ao projeto auditado.
- A geração por IA pode receber a **cena-base + Character Master visual** como referências separadas.
- Coloring Books recebem métricas objetivas de Line Art QA (tons de cinza, cobertura de tinta e proximidade das bordas), sem inventar avaliação estética.
- Line art pode ser normalizada para preto/branco puro em cópia separada, com controle de espessura e upscale.
- O Book Doctor aceita capa em imagem ou PDF/wrap e sinaliza PDFs com múltiplas páginas/versões.
- Todo original preservado recebe SHA-256 em `originais/manifest.json`.

O upscale determinístico não é tratado como recuperação mágica de detalhes: o sistema registra explicitamente que redimensionamento Lanczos melhora amostragem/tamanho, mas não cria informação semântica ausente. Versões só seguem adiante após aprovação humana.

## Refinamento 05 — Coloring Book Doctor + Age & Complexity QA + Cover Master

Adiciona auditoria especializada de livros de colorir por faixa etária, triagem geométrica explicável de line art, plano/recuperação determinística em lote, checklist de miolo e acabamento e um Cover Master versionado conectado ao Character Universe e Style DNA. A IA cria somente arte; o wrap físico continua sendo calculado pelo motor de capa profissional. Consulte `REFINAMENTO_05_COLORING_BOOK_DOCTOR.md`.


## Refinamento 06 — Translation & Localization Studio

O tradutor trabalha por **locale/mercado**, não apenas por idioma. Inglês pode ser en-US, en-CA, en-GB, en-AU ou en-INT; o mesmo conceito vale para português, espanhol e francês. O modo recomendado é Natural Infantil, com glossário protegido da coleção e onomatopeias localizadas em intensidade baixa, equilibrada ou expressiva.

**Bible Guard:** versículos são conteúdo protegido. A IA nunca recebe permissão para traduzir, completar ou inventar o texto bíblico. O texto só entra na exportação quando foi fornecido/selecionado e aprovado pela autora com versão/fonte; caso contrário aparece somente a referência.

A tela `Translation & Localization Studio` preserva versões A/B/C, roda QA estrutural, oferece revisor linguístico independente e pode extrair a camada de texto de PDFs de traduções antigas para auditoria sem OCR automático.


## 📐 Refinamento 07 — Publishing Platform Engine

O FaithBloom agora possui um **Platform Registry expansível** e um fluxo **Book Master → edições derivadas**. O novo módulo compara destinos, preserva especificações versionadas, permite cadastrar novas plataformas, mantém histórico de overrides, gera planos de publicação, preflight por destino, EPUB 3 (fixed/reflowable) e pacote multicanal com bloqueios explícitos.

Perfis técnicos pré-configurados incluem Amazon KDP, IngramSpark, Lulu, Kobo Writing Life, Apple Books, Google Play Books, Draft2Digital e Barnes & Noble Press. Outros canais aparecem como perfis de distribuição e podem receber especificações adicionais sem alterar o núcleo do SaaS. A política do motor é **nunca redimensionar ou converter silenciosamente**.

## 🎧 Refinamento 09 — Audiobook Studio Professional

A página `Audiobook Studio Professional` cria edições de áudio a partir do Story/Translation Master. O texto narrado permanece protegido; direção de emoção, ritmo, pausas e casting é armazenada separadamente. O Studio oferece Voice Profiles, dicionário de pronúncia, previews, versões A/B/C, fila TTS, QA técnico, mix final e aprovação humana antes de seguir para distribuição.

**Bible Guard:** o Studio nunca traduz/inventa texto bíblico. Sem registro de versão aprovada, narra somente a referência.

O FFmpeg é opcional para inspeção avançada, ajuste de velocidade e montagem do Master. Sem FFmpeg, os clips continuam disponíveis individualmente e o sistema não finge ter criado o mix final.


## Refinamento 11 — Publishing & Distribution Center

O FaithBloom agora possui um centro operacional de distribuição em `pages/26_🌐_Publishing_Distribution_Center.py`. Ele conecta o Quality Guardian aprovado ao Platform Registry, cria matriz de edições por plataforma/produto/locale, preserva snapshots das especificações, bloqueia conflitos de exclusividade, gera pacotes por canal apenas quando o preflight interno está pronto e registra manualmente o ciclo `draft → submitted → processing → live`. O sistema não publica automaticamente nem considera `READY` como aprovação de terceiros.


## 🧱 Refinamento 13 — Stable Release Hardening

Adiciona uma camada operacional antes da tag Stable: schema de projeto versionado com migrações idempotentes, recovery points imutáveis, escrita local atômica, onboarding/configurações sem armazenamento de secrets, diagnóstico de ambiente, matriz de papéis/permissões, audit log sanitizado e Stable Gate offline.

**Importante:** os papéis internos (`owner/editor/reviewer/viewer`) são uma política de autorização e **não substituem autenticação**. Em `FAITHBLOOM_DEPLOYMENT_MODE=production`, o Stable Gate bloqueia a liberação se não houver autenticação real configurada (`FAITHBLOOM_AUTH_MODE=oidc` ou `external`), storage persistente e chave da OpenRouter. Recovery nunca sobrescreve silenciosamente o Book Master; primeiro cria uma cópia de trabalho.

## 🖼️ Refinamento 16 — Asset Library & Media Manager

O FaithBloom agora possui uma biblioteca visual preparada para crescer. A rota `pages/31_🖼️_Asset_Library_Media_Manager.py` organiza imagens, line arts, capas, referências, áudios e documentos com miniaturas, paginação, busca, filtros, favoritos, Masters, versões, coleções virtuais e rastreamento de uso.

As coleções virtuais **não duplicam arquivos no storage**. Assets podem ser arquivados sem serem apagados; exclusão permanente é bloqueada para Masters, originais protegidos e itens com vínculos encontrados. O Storage Manager calcula metadados técnicos sob demanda em vez de baixar todo o bucket automaticamente.

A Asset Library também funciona como ponto de reutilização: um asset selecionado pode seguir para Coloring Studio, Restoration Studio ou Character Universe, reduzindo gerações desnecessárias e mantendo referências oficiais organizadas.
