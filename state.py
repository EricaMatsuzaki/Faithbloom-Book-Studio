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
    origem: str                 # "gerada_pelo_agente" ou "enviada_pela_autora"


class PersonagemDNA(TypedDict, total=False):
    nome: str
    descricao_fixa: str        # tudo que NUNCA muda: espécie/idade aparente, cor dos olhos, proporção, marcas
    imagem_referencia: str     # caminho da imagem "modelo" usada como referência em toda geração
    origem_referencia: str     # "enviada_pela_autora" ou "gerada_pelo_agente"
    papel: str                 # ex: "protagonista", "mentor", "guia sábio"
    variacoes_visuais: list[dict]      # opções preservadas; pedir outra nunca apaga a anterior
    variacao_selecionada_id: str       # opção atualmente selecionada na etapa de aprovação
    aparencia_aprovada: bool           # True somente após confirmação explícita da autora
    dna_visual_travado: bool            # protege identidade visual nas cenas seguintes
    character_universe_id: str          # vínculo opcional com personagem oficial
    usos_permitidos: list[str]          # story/coloring/activity/cover
    presets_visuais: dict               # roupas/cenários/estações/festividades/emoções salvos


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
    cenas_bloqueadas: list[int]           # cenas aprovadas pela autora que não devem ser alteradas automaticamente
    historico_cenas: dict[int, list[dict]] # versões anteriores por cena, para poder voltar sem perder uma versão boa
    mapa_emocional: list[dict]             # Emotional & Color Director, aprovado antes da geração em lote
    paleta_emocional_preset: str           # preset editorial do livro/coleção
    style_dna_id: str                      # Style DNA oficial aplicado ao projeto

    # --- Revisor ---
    revisao_aprovada: bool
    notas_revisor: list[str]

    # --- Ilustrador ---
    cenas_imagem: list[CenaImagem]
    imagens_cenas_enviadas: dict[int, str]  # {numero_da_cena: caminho_arquivo} - preenchido pela autora ANTES do Ilustrador rodar, pra pular a geração dessas cenas específicas
    historico_imagens_cenas: dict[int, list[dict]]  # versões anteriores preservadas por cena
    instrucoes_imagens_cenas: dict[int, str]        # pedido livre da autora por cena
    cenas_imagem_aprovadas: list[int]               # imagens aprovadas/travadas para finalização

    # --- Capa e Contracapa (arquivos SEPARADOS do miolo, formatos diferentes) ---
    capa_ebook: str                    # arquivo só com a arte frontal (eBook)
    capa_fisica_wrap: str              # arquivo único: contracapa + lombada + capa (livro físico)
    capa_fisica_dimensoes: dict        # medidas usadas (lombada, largura/altura total, DPI) - ver kdp_rules
    arte_capa_frontal: str             # arte sem tipografia; pode vir da IA ou da autora
    arte_contracapa: str               # arte sem tipografia; pode vir da IA ou da autora
    capa_fisica_preview: str           # PNG com guias, apenas para revisão interna
    capa_fisica_pdf: str               # PDF final de 1 página: verso+lombada+frente
    capa_fisica_preflight: dict        # valida tamanho/estrutura do PDF da capa
    autora: str                         # campo legado/snapshot para renderizadores antigos; derivado da autoria estruturada
    authorship: dict                     # Author & Contributor Profiles: autores/coautores/contribuidores + snapshots
    cover_author_credit: str             # override opcional de crédito de capa; vazio usa authorship
    subtitulo: str                      # subtítulo opcional
    tipo_papel_capa: str               # branco/creme/cor_padrao/cor_premium

    # --- Atividades para Colorir ---
    paginas_colorir: list[CenaImagem]  # 3 cenas-chave em versão line-art

    # --- Audiobook ---
    roteiro_audiobook: list[dict]      # pipeline legado; Refinamento 09 mantém compatibilidade
    audio_gerado: list[dict]           # pipeline legado
    audiobook_projects: dict[str, dict] # projetos do Audiobook Studio por locale
    audiobook_voice_profiles: dict[str, dict] # perfis de voz vinculados ao livro
    audiobook_pronunciations: list[dict] # dicionário de pronúncia aprovado
    audiobook_script_versions: dict[str, list[dict]] # versões A/B/C do roteiro de performance
    audiobook_audio_versions: dict[str, list[dict]] # versões A/B/C por segmento
    audiobook_approved_audio: dict[str, str] # unit_id -> audio version id aprovada
    audiobook_final_mix: str           # arquivo completo após aprovação/QA
    audiobook_final_qa: dict           # QA técnico do mix final

    # --- Quality Guardian (Refinamento 10) ---
    quality_guardian_report_id: str     # último relatório final independente associado à obra
    quality_guardian_run: int           # número do último rerun
    quality_guardian_decisions: dict    # decisões explícitas da autora por alerta
    guardian_specialist_reviews: dict   # revisões independentes adicionais (editorial/readability/bíblico/multimodal)
    quality_guardian_certificate: dict  # certificado INTERNO; nunca substitui validação da plataforma

    # --- Dedicatória Dinâmica ---
    lista_dedicatoria: list[dict]      # [{"pessoa": "Sedinei", "relacao": "mãe"}, ...]
    dedicatoria_texto: str

    # --- Sinopse de vendas ---
    sinopse_vendas_curta: str          # descrição de produto KDP
    sinopse_contracapa: str            # texto impresso na contracapa

    # --- Pesquisa de Mercado (ver agents/pesquisa_mercado.py) ---
    palavras_chave_kdp: list[str]      # 7 frases-chave sugeridas
    categorias_sugeridas: list[str]    # caminhos de categoria da árvore KDP
    market_evidence: list[dict]         # evidências observadas com fonte/data/mercado; separadas de inferência da IA
    market_suggestions_provenance: dict # model_inference_only vs observed_evidence
    market_intelligence_brief: dict     # brief baseado somente em evidências válidas + hipóteses rotuladas

    # --- Agent Skills & Bestseller Readiness (Refinamento 21) ---
    agent_skill_audit: dict              # integridade do registry de skills/handoffs
    bestseller_readiness_report: dict    # fatores controláveis; nunca probabilidade de best-seller
    bible_reference_candidate: dict      # referência sugerida pela IA, ainda não validada
    bible_reference_validation: dict     # fonte/contexto/aprovação humana da referência

    # --- Marketing de Lançamento (ver agents/marketing.py) ---
    material_lancamento: dict          # legenda_instagram, descricao_pinterest, email_lancamento, pedido_avaliacao

    # --- Translation & Localization Studio (Refinamento 06) ---
    traducoes: dict[str, dict]         # versões localizadas por locale, ex. en-US / en-GB
    translation_profiles: dict[str, dict] # modo, idade, intensidade de onomatopeias e instruções por locale
    translation_mode: str              # fiel | natural_infantil | localizacao_cultural
    glossario_colecao: dict[str, str]  # termos/nomenclatura oficial da série
    bible_records: dict[str, dict]      # texto bíblico aprovado + versão/fonte; IA nunca traduz livremente
    linguistic_reviews: dict[str, dict] # revisão estrutural/linguística por locale
    translation_versions: dict[str, list[dict]] # histórico A/B/C por locale
    onomatopoeia_intensity: str         # baixa | equilibrada | expressiva
    sound_library_colecao: dict[str, dict] # sons aprovados por evento/locale

    # --- Diagramador / KDP ---
    layout_paginas: list[dict]         # ordem final página a página (texto/imagem alternando lado)
    pacote_pronto: bool
    checklist_kdp: dict
    preflight_impressao: dict          # pixels/PPI/bleed/margens e bloqueios antes da publicação
    pdf_miolo_print_ready: str         # preenchido pelo futuro renderizador PDF após preflight

    # --- Atividades para Colorir ---
    paginas_colorir: list[dict]        # [{"cena_numero": int, "caminho_arquivo": str}, ...]
