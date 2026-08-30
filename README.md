#FaithBloom AI é um nome em inglês formado por três ideias:

Faith = Fé
Bloom = Florescer / desabrochar
AI = Artificial Intelligence / Inteligência Artificial

Então, conceitualmente, FaithBloom AI pode ser entendido como:

🌷 “Fé que Floresce com Inteligência Artificial”

ou, de maneira mais poética para a marca:

✨ “Onde histórias fazem a fé florescer.”

Acho especialmente interessante o verbo bloom, porque em inglês ele transmite a ideia de uma flor que se abre e, figurativamente, de alguém ou algo que cresce, se desenvolve e alcança seu potencial.

Para o seu SaaS, a mensagem poderia ser:

🌷 FaithBloom AI

Pequenas histórias. Grandes lições. Uma fé que floresce.

Em inglês:

Little Stories. Big Lessons. Faith That Blooms.

E existe uma conexão muito bonita com a proposta editorial: a IA é a ferramenta, mas o centro da marca continua sendo histórias infantis, valores cristãos e crescimento da fé.

Eu só faria uma distinção entre os nomes:

FaithBloom AI → nome da marca/SaaS
FaithBloom Book Studio → nome da plataforma/editor de livros
Pequenas Histórias com Grandes Lições → nome da coleção de livros

Isso cria uma arquitetura de marca bastante organizada. Por exemplo:

FaithBloom AI
Christian Storytelling & Book Studio

📚 Coleção: Pequenas Histórias com Grandes Lições
✍️ Autora: Erica Matsuzaki


# Pipeline de agentes - Livros infantis (Erica Matsuzaki)

Esqueleto funcional do pipeline discutido: 7 agentes em LangGraph que
levam do briefing da história até o pacote pronto para publicação
manual na KDP.

## Estrutura

```
state.py            -> estado compartilhado entre os agentes
emotion_colors.py    -> dicionário fixo emoção -> cor -> atmosfera
kdp_rules.py         -> regras de páginas mínimas e idiomas elegíveis
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
  diagramador.py         -> layout final + validação KDP
graph.py             -> monta o LangGraph completo
main.py              -> exemplo de execução via terminal
```

## Como rodar a interface (sem terminal, depois do primeiro setup)

```
export OPENROUTER_API_KEY="sua-chave-aqui"
pip install streamlit langgraph requests --break-system-packages
streamlit run app.py
```

A tela deixa escolher entre "só tenho um tema" (o Curador de Tema sugere
versículo/emoção/lição e você confirma ou edita) ou preencher tudo
manualmente, mostra a referência visual dos personagens ANTES de gastar
créditos gerando o livro inteiro, e no final mostra o pacote pronto com
o checklist da KDP.

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
