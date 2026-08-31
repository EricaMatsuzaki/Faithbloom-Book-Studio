"""
Estado compartilhado do pipeline de geração de livros infantis.

Esse objeto circula entre todos os agentes no LangGraph. Cada agente lê o
que precisa e escreve de volta o que produziu, sem apagar o que os
agentes anteriores já colocaram.
"""

from typing import TypedDict, Literal


class CenaTexto(TypedDict):
    numero: int
    texto: str                 # texto narrativo da cena (10-25 palavras, curto)
    emocao: str                # uma das chaves de emotion_colors.EMOCOES
    figurino: str              # o que o personagem principal está vestindo/carregando NESSA cena
    contexto_visual: str       # cenário, hora do dia, clima - herda da cena anterior salvo mudança explícita
    personagem_principal: str  # nome do personagem em foco na cena (chave em state.personagens); default = protagonista


class CenaImagem(TypedDict):
    numero: int
    prompt_final: str          # prompt de imagem já com DNA fixo + figurino + paleta de emoção
    caminho_arquivo: str       # onde a imagem gerada foi salva
    aprovado: bool             # marcado True depois de revisão humana ou automática


class PersonagemDNA(TypedDict):
    nome: str
    descricao_fixa: str        # tudo que NUNCA muda: espécie/idade aparente, cor dos olhos, proporção, marcas
    imagem_referencia: str     # caminho da imagem "modelo" usada como referência em toda geração
    origem_referencia: str     # "enviada_pela_autora" ou "gerada_pelo_agente"
    papel: str                 # ex: "protagonista", "mentor", "guia sábio"


class LivroState(TypedDict, total=False):
    # --- Entrada (fornecida pela Erica) ---
    colecao: str                       # ex: "Pequenas Histórias, Grandes Lições"
    titulo: str
    emocao_central: str
    aprendizado_cristao: str
    versiculo_referencia: str          # ex: "Salmo 27:14"
    idioma_original: str               # ex: "pt-BR"
    idiomas_alvo: list[str]            # lista de idiomas para tradução
    paginas_minimas: int               # padrão 24, nunca abaixo disso
    trim_largura_in: float             # largura do livro físico, em polegadas (padrão 8.5)
    trim_altura_in: float              # altura do livro físico, em polegadas (padrão 8.5)

    # --- Curador de Tema (opcional) ---
    _entrada_tema_livre: str           # tema/resumo livre, se a Erica não
                                        # quiser preencher os campos acima
                                        # manualmente
    _justificativa_curadoria: str      # por que o versículo sugerido combina

    # --- Personagens ---
    personagens: dict[str, PersonagemDNA]

    # --- Roteirista ---
    sinopse_poetica: str
    cenas_texto: list[CenaTexto]
    licao_final: str

    # --- Revisor ---
    revisao_aprovada: bool
    notas_revisor: list[str]

    # --- Ilustrador ---
    cenas_imagem: list[CenaImagem]

    # --- Capa e Contracapa (arquivos SEPARADOS do miolo, formatos diferentes) ---
    capa_ebook: str                    # arquivo só com a arte frontal (eBook)
    capa_fisica_wrap: str              # arquivo único: contracapa + lombada + capa (livro físico)
    capa_fisica_dimensoes: dict        # medidas usadas (lombada, largura/altura total, DPI) - ver kdp_rules

    # --- Atividades para Colorir ---
    paginas_colorir: list[CenaImagem]  # 3 cenas-chave em versão line-art

    # --- Audiobook ---
    roteiro_audiobook: list[dict]      # [{"numero": 1, "texto_narrado": "...", "marcacoes": "..."}]
    audio_gerado: list[dict]           # [{"numero": 1, "caminho_arquivo": "saida_audio/cena_1.mp3"}]

    # --- Dedicatória Dinâmica ---
    lista_dedicatoria: list[dict]      # [{"pessoa": "Sedinei", "relacao": "mãe"}, ...]
    dedicatoria_texto: str

    # --- Sinopse de vendas ---
    sinopse_vendas_curta: str          # descrição de produto KDP
    sinopse_contracapa: str            # texto impresso na contracapa

    # --- Tradutor ---
    traducoes: dict[str, dict]         # {"en": {"cenas_texto": [...], "dedicatoria": "...", ...}}

    # --- Diagramador / KDP ---
    layout_paginas: list[dict]         # ordem final página a página (texto/imagem alternando lado)
    pacote_pronto: bool
    checklist_kdp: dict[str, bool]

    # --- Atividades para Colorir ---
    paginas_colorir: list[dict]        # [{"cena_numero": int, "caminho_arquivo": str}, ...]
