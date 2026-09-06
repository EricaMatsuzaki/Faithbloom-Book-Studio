"""
Estado compartilhado do pipeline de geração de livros infantis.

Esse objeto circula entre todos os agentes no LangGraph. Cada agente lê o
que precisa e escreve de volta o que produziu, sem apagar o que os
agentes anteriores já colocaram.
"""

from typing import TypedDict


class CenaTexto(TypedDict):
    numero: int
    texto: str                 # texto narrativo da cena; densidade depende da faixa etária
    emocao: str                # emoção principal canônica de emotion_colors.EMOCOES
    emocao_secundaria: str     # subemoção complementar opcional para nuance emocional/visual
    transicao_emocional: str   # ex.: "tristeza → começando a surgir esperança"
    figurino: str              # o que o personagem principal está vestindo/carregando NESSA cena
    contexto_visual: str       # cenário, hora do dia, clima - herda da cena anterior salvo mudança explícita
    personagem_principal: str  # nome do personagem em foco na cena (chave em state.personagens); default = protagonista
    expressao: str             # expressão/linguagem corporal, variável por cena
    intensidade_emocional: int # 1-5, controla atmosfera sem alterar Character DNA
    paleta_preset: str         # preset do Emotional & Color Director
    instrucao_emocional: str   # ajuste livre da autora somente para esta cena
    emocao_travada: bool       # impede que sugestões de arco substituam a emoção aprovada


class CenaImagem(TypedDict):
    numero: int
    prompt_final: str          # prompt de imagem já com DNA fixo + figurino + paleta de emoção
    caminho_arquivo: str       # onde a imagem gerada foi salva
    aprovado: bool             # marcado True depois de revisão humana ou automática
    origem: str                # "gerada_pelo_agente" ou "enviada_pela_autora"


class PersonagemDNA(TypedDict, total=False):
    nome: str
    descricao_fixa: str        # tudo que NUNCA muda: espécie/idade aparente, cor dos olhos, proporção, marcas
    imagem_referencia: str     # caminho da imagem "modelo" usada como referência em toda geração
    origem_referencia: str     # "enviada_pela_autora" ou "gerada_pelo_agente"
    papel: str                 # ex: "protagonista", "mentor", "guia sábio"
    variacoes_visuais: list[dict]      # opções preservadas; pedir outra nunca apaga a anterior
    variacao_selecionada_id: str       # opção atualmente selecionada na etapa de aprovação
    aparencia_aprovada: bool           # True somente após confirmação explícita da autora
    dna_visual_travado: bool           # protege identidade visual nas cenas seguintes
    character_universe_id: str         # vínculo opcional com personagem oficial
    usos_permitidos: list[str]         # story/coloring/activity/cover
    presets_visuais: dict              # roupas/cenários/estações/festividades/emoções salvos


class LivroState(TypedDict, total=False):
    # --- Entrada / direção editorial ---
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
    faixa_etaria: str                  # 3-5 | 6-8 | 9-12 | 3-8 (compatibilidade)
    age_profile_id: str                # id normalizado pelo Age Profile Engine

    # --- Curador de Tema (opcional) ---
    _entrada_tema_livre: str           # tema/resumo livre, se a autora não quiser preencher tudo manualmente
    _justificativa_curadoria: str      # por que a referência bíblica sugerida combina

    # --- Personagens ---
    personagens: dict[str, PersonagemDNA]

    # --- Roteirista ---
    sinopse_poetica: str
    cenas_texto: list[CenaTexto]
    licao_final: str
    cenas_bloqueadas: list[int]           # cenas aprovadas que não devem ser alteradas automaticamente
    historico_cenas: dict[int, list[dict]] # versões anteriores por cena
    mapa_emocional: list[dict]             # Emotional & Color Director, aprovado antes da geração em lote
    paleta_emocional_preset: str           # preset editorial do livro/coleção
    style_dna_id: str                      # Style DNA oficial aplicado ao projeto

    # --- Revisor ---
    revisao_aprovada: bool
    notas_revisor: list[str]

    # --- Ilustrador ---
    cenas_imagem: list[CenaImagem]
    imagens_cenas_enviadas: dict[int, str]  # arte pronta enviada pela autora; pula geração por IA da cena
    historico_imagens_cenas: dict[int, list[dict]]  # versões anteriores preservadas por cena
    instrucoes_imagens_cenas: dict[int, str]        # pedido livre da autora por cena
    cenas_imagem_aprovadas: list[int]               # imagens aprovadas/travadas para finalização

    # --- Capa e Contracapa (arquivos SEPARADOS do miolo) ---
    capa_ebook: str
    capa_fisica_wrap: str
    capa_fisica_dimensoes: dict
    arte_capa_frontal: str
    arte_contracapa: str
    capa_fisica_preview: str
    capa_fisica_pdf: str
    capa_fisica_preflight: dict
    autora: str                         # campo legado/snapshot; derivado da autoria estruturada
    authorship: dict                    # Author & Contributor Profiles
    cover_author_credit: str            # override opcional de crédito de capa
    subtitulo: str
    tipo_papel_capa: str

    # --- Atividades para Colorir ---
    paginas_colorir: list[dict]         # padrão atual: 3 páginas line-art com cena_numero/caminho_arquivo

    # --- Audiobook ---
    roteiro_audiobook: list[dict]
    audio_gerado: list[dict]
    audiobook_projects: dict[str, dict]
    audiobook_voice_profiles: dict[str, dict]
    audiobook_pronunciations: list[dict]
    audiobook_script_versions: dict[str, list[dict]]
    audiobook_audio_versions: dict[str, list[dict]]
    audiobook_approved_audio: dict[str, str]
    audiobook_final_mix: str
    audiobook_final_qa: dict

    # --- Quality Guardian (Refinamento 10) ---
    quality_guardian_report_id: str
    quality_guardian_run: int
    quality_guardian_decisions: dict
    guardian_specialist_reviews: dict
    quality_guardian_certificate: dict

    # --- Dedicatória Dinâmica ---
    lista_dedicatoria: list[dict]
    dedicatoria_texto: str

    # --- Sinopse de vendas ---
    sinopse_vendas_curta: str
    sinopse_contracapa: str

    # --- Pesquisa de Mercado ---
    palavras_chave_kdp: list[str]
    categorias_sugeridas: list[str]
    market_evidence: list[dict]
    market_suggestions_provenance: dict
    market_intelligence_brief: dict

    # --- Agent Skills & Bestseller Readiness ---
    agent_skill_audit: dict
    bestseller_readiness_report: dict
    bible_reference_candidate: dict
    bible_reference_validation: dict

    # --- Marketing de Lançamento ---
    material_lancamento: dict

    # --- Translation & Localization Studio ---
    traducoes: dict[str, dict]
    translation_profiles: dict[str, dict]
    translation_mode: str
    glossario_colecao: dict[str, str]
    bible_records: dict[str, dict]
    linguistic_reviews: dict[str, dict]
    translation_versions: dict[str, list[dict]]
    onomatopoeia_intensity: str
    sound_library_colecao: dict[str, dict]

    # --- Diagramador / KDP ---
    layout_paginas: list[dict]
    pacote_pronto: bool
    checklist_kdp: dict
    preflight_impressao: dict
    pdf_miolo_print_ready: str         # caminho do PDF físico gerado após diagramação + preflight
