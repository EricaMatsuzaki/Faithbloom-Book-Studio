"""
Roteiro do segundo livro ("Quando Mel Aprendeu o Verdadeiro Sentido do
Natal"), transcrito a partir das páginas que a Erica já tinha
produzido no Canva. Já está no formato que o pipeline espera
(state.LivroState) - pronto para pular Roteirista/Revisor e ir direto
pro Ilustrador.

Uso (ver README_NATAL.md):
    from historia_natal import ESTADO_INICIAL_NATAL
    # ... depois passe ESTADO_INICIAL_NATAL pro grafo, mas rode só a
    # partir do nó "ilustrador" (ver instruções no final deste arquivo)
"""

from state import LivroState, PersonagemDNA, CenaTexto

CENAS_NATAL: list[CenaTexto] = [
    CenaTexto(
        numero=1,
        texto="Era dezembro. O vento estava frio. As luzes da cidade brilhavam "
              "como estrelinhas felizes, anunciando que algo muito especial "
              "estava chegando.",
        emocao="esperanca",
        figurino="cachecol vermelho",
        contexto_visual="rua da cidade à noite, decorada de Natal, neve caindo, vitrines de brinquedos",
    ),
    CenaTexto(
        numero=2,
        texto="Mel caminhava com seu cachecol vermelho balançando. Ela estava "
              "animada. Adorava o Natal! — O Natal está chegando! — disse "
              "ela, com os olhinhos brilhando.",
        emocao="alegria",
        figurino="cachecol vermelho",
        contexto_visual="mesma rua decorada, Mel andando sozinha, animada",
    ),
    CenaTexto(
        numero=3,
        texto="Mas aquele ano seria diferente. Mel queria muito um presente... "
              "um presente grande, lindo... Mas mamãe disse que não "
              "poderiam comprar. O coração de Mel ficou pequenininho.",
        emocao="tristeza",
        figurino="cachecol vermelho",
        contexto_visual="Mel parada em frente a uma vitrine de brinquedos, olhando triste, uma lágrima no rosto",
    ),
    CenaTexto(
        numero=4,
        texto="De repente... PUF! Fitas, sinos e papéis coloridos voaram pelo ar!",
        emocao="alegria",
        figurino="cachecol vermelho",
        contexto_visual="explosão cômica de confete e fitas coloridas na rua nevada",
    ),
    CenaTexto(
        numero=5,
        texto="Era Max, o panda-vermelho mais fofinho e desajeitado. Ele "
              "carregava uma caixa enorme... mas tropeçou e caiu bem na "
              "frente de Mel. — PUF!",
        emocao="alegria",
        figurino="cachecol verde",
        contexto_visual="Max caído no chão nevado no meio de fitas e confetes, caixa aberta ao lado",
        personagem_principal="Max",
    ),
    CenaTexto(
        numero=6,
        texto="Mel arregalou os olhos. Max ficou sem graça e juntou as "
              "patinhas. — Oi... Mel? Eu queria fazer enfeites de Natal... "
              "mas acho que preciso de ajuda.",
        emocao="vergonha",
        figurino="cachecol verde",
        contexto_visual="Mel e Max se encontrando pela primeira vez, cenário de rua decorada",
    ),
    CenaTexto(
        numero=7,
        texto="Mel sentiu um quentinho no coração. — Eu ajudo! — disse ela. "
              "— E conheço alguém que pode ajudar ainda mais... a Manu! "
              "Então foram juntos chamá-la.",
        emocao="alegria",
        figurino="cachecol vermelho",
        contexto_visual="Mel e Max de mãos dadas/lado a lado, indo em direção a algum lugar",
    ),
    CenaTexto(
        numero=8,
        texto="Manu ouviu a ideia e sorriu. — Claro que eu ajudo! E os três "
              "seguiram pela neve, começando uma aventura cheia de surpresas.",
        emocao="alegria",
        figurino="vestido vermelho",
        contexto_visual="Mel, Manu e Max juntos caminhando pela rua nevada, árvore de Natal ao fundo",
        personagem_principal="Manu",
    ),
    CenaTexto(
        numero=9,
        texto="Enquanto andavam, Mel perguntou: — Manu... por que o Natal é "
              "tão importante?",
        emocao="esperanca",
        figurino="cachecol vermelho",
        contexto_visual="os três andando, Mel olhando para Manu com curiosidade",
    ),
    CenaTexto(
        numero=10,
        texto="Manu respondeu com uma voz bem doce: — Porque é o dia em que "
              "Jesus nasceu. Ele é o maior presente que Deus nos deu.",
        emocao="esperanca",
        figurino="vestido vermelho",
        contexto_visual="Manu de mãos postas, expressão serena, árvore de Natal e luzes ao fundo",
        personagem_principal="Manu",
    ),
    CenaTexto(
        numero=11,
        texto="Mel ficou pensando. — Mas... Jesus é mesmo um presente? "
              "— O maior de todos — disse Manu. — Ele trouxe amor, "
              "esperança e salvação. Os brinquedos acabam... mas Jesus "
              "fica conosco para sempre.",
        emocao="esperanca",
        figurino="cachecol vermelho",
        contexto_visual="os três parados, conversa séria e doce, luz suave",
    ),
    CenaTexto(
        numero=12,
        texto="Então algo brilhou dentro de Mel. Uma luz pequenininha, "
              "quentinha... como uma estrelinha nascendo no coração dela.",
        emocao="esperanca",
        figurino="cachecol vermelho",
        contexto_visual="close no rosto de Mel, um coraçãozinho de luz brilhando entre suas patas",
    ),
    CenaTexto(
        numero=13,
        texto="— Vamos começar nossa primeira missão! — disse Max. Eles "
              "foram escolher a árvore de Natal. E claro... escolheram a "
              "maior da praça!",
        emocao="alegria",
        figurino="cachecol verde",
        contexto_visual="praça da cidade, árvore de Natal gigante e decorada, os três admirando",
    ),
    CenaTexto(
        numero=14,
        texto="Na cozinha, fizeram biscoitos de gengibre. Max espirrou "
              "açúcar para todos os lados... e virou um panda de neve! "
              "Todos riram muito.",
        emocao="alegria",
        figurino="cachecol verde, coberto de açúcar de confeiteiro",
        contexto_visual="cozinha aconchegante, biscoitos em forma de estrela na bancada, bagunça divertida de açúcar",
    ),
    CenaTexto(
        numero=15,
        texto="Depois, prepararam sacolas com mantas, biscoitos fresquinhos "
              "e um cartão com o versículo: \"Hoje vos nasceu o Salvador, "
              "que é Cristo, o Senhor.\" (Lucas 2:11)",
        emocao="esperanca",
        figurino="cachecol vermelho",
        contexto_visual="mesa com várias sacolas vermelhas de presente, biscoitos, cartõezinhos com o versículo",
    ),
    CenaTexto(
        numero=16,
        texto="No orfanato, as crianças correram até eles. Abraçaram, riram...",
        emocao="alegria",
        figurino="cachecol vermelho",
        contexto_visual="sala de orfanato decorada de Natal, várias crianças correndo para abraçar Mel e Max, lareira acesa",
    ),
    CenaTexto(
        numero=17,
        texto="Eles entregaram as sacolas para cada criança. E elas ficaram "
              "radiantes ao ver as sacolinhas. Parecia que o Natal tinha "
              "chegado ali...",
        emocao="alegria",
        figurino="cachecol vermelho",
        contexto_visual="crianças sentadas em círculo segurando as sacolas vermelhas, sorrindo",
    ),
    CenaTexto(
        numero=18,
        texto="Depois, todos pintaram estrelas e laços para colocar na "
              "grande árvore do orfanato. O lugar ficou ainda mais "
              "bonito... parecia que a alegria morava lá dentro.",
        emocao="alegria",
        figurino="cachecol vermelho",
        contexto_visual="crianças e os três amigos pintando enfeites juntos, sala iluminada, árvore ao fundo",
    ),
    CenaTexto(
        numero=19,
        texto="Então foram visitar Dona Lúcia, uma senhora que morava "
              "sozinha. Quando abriu a porta, tinha lágrimas nos olhos. "
              "— Faz tanto tempo que não recebo carinho no Natal...",
        emocao="tristeza",
        figurino="cachecol vermelho",
        contexto_visual="porta de uma casa simples, neve caindo, senhora idosa emocionada abrindo a porta",
    ),
    CenaTexto(
        numero=20,
        texto="Eles deram a sacola para ela. Sentaram, tomaram chocolate "
              "quente e comeram os biscoitos de gengibre juntos. Foi um "
              "momento inesquecível!",
        emocao="esperanca",
        figurino="cachecol vermelho",
        contexto_visual="sala aconchegante com lareira, todos sentados juntos tomando chocolate quente",
    ),
    CenaTexto(
        numero=21,
        texto="Mel sentiu o coração quentinho. Nenhum presente faria ela se "
              "sentir assim. Era alegria de verdade.",
        emocao="esperanca",
        figurino="cachecol vermelho",
        contexto_visual="close em Mel sorrindo, luz dourada suave",
    ),
    CenaTexto(
        numero=22,
        texto="A noite chegou. As pessoas se reuniram perto da grande "
              "árvore, cantando baixinho. Belém. Jesus. Luz. Esperança. "
              "Mel entendeu tudo — não com os olhos, mas com o coração.",
        emocao="esperanca",
        figurino="cachecol vermelho",
        contexto_visual="praça à noite, multidão reunida ao redor da árvore de Natal iluminada, cantando",
    ),
]

LICAO_FINAL_NATAL = (
    "O Natal é sobre Jesus. Os presentes acabam. Mas o amor d'Ele dura "
    "para sempre."
)

DEDICATORIA_REFERENCIA_NATAL = (
    "Dedicatória de Natal, à Deus Nosso Criador pelo presente de Jesus; "
    "à mãe Sedinei e ao pai Keiichi (falecido) pelo amor e união; ao "
    "marido Kleber e filha Larissa Ayumi como fontes de inspiração; à "
    "tia Jasmina e em lembrança da avó Andrelina, avô José e tio Bene; "
    "aos irmãos, familiares e amigos; e ao pequeno leitor, para "
    "descobrir o verdadeiro sentido do Natal."
)

ESTADO_INICIAL_NATAL = LivroState(
    colecao="Pequenas Histórias, Grandes Lições",
    titulo="Quando Mel Aprendeu o Verdadeiro Sentido do Natal",
    emocao_central="esperanca",
    aprendizado_cristao="o verdadeiro sentido do Natal é o amor e a generosidade, não os presentes",
    versiculo_referencia="Lucas 2:11",
    idioma_original="pt-BR",
    idiomas_alvo=["en", "es", "de", "ja"],
    paginas_minimas=24,
    cenas_texto=CENAS_NATAL,
    licao_final=LICAO_FINAL_NATAL,
    revisao_aprovada=True,  # já foi "revisado" por você mesma no Canva
    personagens={
        "Mel": PersonagemDNA(
            nome="Mel",
            descricao_fixa=(
                "gatinha bege clara, olhos verdes grandes e brilhantes, "
                "laço vermelho na orelha esquerda, proporção cabeça "
                "grande / corpo pequeno e rechonchudo"
            ),
            imagem_referencia="",
            origem_referencia="",
            papel="protagonista",
        ),
        "Max": PersonagemDNA(
            nome="Max",
            descricao_fixa=(
                "panda-vermelho fofo e desajeitado, pelagem laranja com "
                "manchas brancas no rosto, cachecol verde, proporção "
                "arredondada e atrapalhada"
            ),
            imagem_referencia="",
            origem_referencia="",
            papel="amigo",
        ),
        "Manu": PersonagemDNA(
            nome="Manu",
            descricao_fixa=(
                "menina de cabelo castanho liso na altura dos ombros, "
                "olhos verdes, vestido vermelho de gola branca, um pouco "
                "mais velha que uma criança pequena (pré-adolescente)"
            ),
            imagem_referencia="",
            origem_referencia="",
            papel="mentor",
        ),
    },
    # Preencher com a lista real de pessoas antes de rodar a Dedicatória
    # Dinâmica - ver DEDICATORIA_REFERENCIA_NATAL acima como few-shot.
    lista_dedicatoria=[],
)

# ---------------------------------------------------------------------
# COMO RODAR SÓ A PARTIR DO ILUSTRADOR (pulando Roteirista/Revisor):
#
#   from graph import construir_grafo
#   from openrouter_client import chamar_llm, gerar_imagem, gerar_audio
#   from historia_natal import ESTADO_INICIAL_NATAL
#
#   grafo = construir_grafo(chamar_llm, gerar_imagem, gerar_audio)
#   resultado = grafo.invoke(ESTADO_INICIAL_NATAL, config={"start_at": "ilustrador"})
#
# Nota: dependendo da versão do LangGraph, "start_at" pode não existir
# como parâmetro direto - a forma mais simples e garantida é chamar os
# nós manualmente em sequência, pulando roteirista/revisor:
#
#   from agents.ilustrador import ilustrador_node
#   from agents.atividades_colorir import atividades_colorir_node
#   from agents.audiobook import audiobook_node, narracao_node
#   from agents.dedicatoria import dedicatoria_node
#   from agents.tradutor import tradutor_node
#   from agents.sinopse import sinopse_node
#   from agents.diagramador import diagramador_node
#
#   s = dict(ESTADO_INICIAL_NATAL)
#   s = ilustrador_node(s, gerar_imagem)
#   s = atividades_colorir_node(s, gerar_imagem)
#   s = audiobook_node(s, chamar_llm)
#   s = narracao_node(s, gerar_audio)
#   s = dedicatoria_node(s, chamar_llm)
#   s = tradutor_node(s, chamar_llm)
#   s = sinopse_node(s, chamar_llm)
#   s = diagramador_node(s)
# ---------------------------------------------------------------------
