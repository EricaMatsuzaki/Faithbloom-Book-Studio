"""FaithBloom Agent Skills Registry.

Formaliza competências, critérios de excelência, limites e handoffs de cada
papel especializado. Todos os agentes compartilham a mesma filosofia editorial,
mas preservam escopo profissional próprio. O registry não promete vendas;
ele aumenta consistência, auditabilidade e bestseller-readiness verificável.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, asdict
from pathlib import Path
import json
import ast
from functools import lru_cache

SCHEMA = "faithbloom.agent-skills.v4"

COMMON_FORBIDDEN = [
    "prometer best-seller, ranking, vendas ou aprovação por plataforma",
    "inventar evidência de mercado, métricas, fontes ou validação humana",
    "alterar conteúdo aprovado fora do escopo do agente sem autorização",
    "tratar sugestão de IA como fato observado",
    "copiar voz autoral, bordões, personagens, refrões, cenas ou identidade visual distintiva de obras existentes",
]

# ---------------------------------------------------------------------------
# FaithBloom Literary Excellence Charter — camada compartilhada por TODOS.
# Cada agente conhece estes princípios; somente executa o que pertence ao seu
# papel profissional. Isso evita agentes generalistas e mantém handoffs claros.
# ---------------------------------------------------------------------------
FAITHBLOOM_EDITORIAL_DNA = [
    "encantar antes de ensinar",
    "história precisa funcionar como história, não como sermão",
    "emoções concretas, verdadeiras e adequadas à faixa etária",
    "transformação vivida por escolhas, tentativas, consequências e relações",
    "fé integrada de modo natural, amoroso e não coercitivo",
    "lição de moral clara sem sacrificar diversão, ritmo ou personagem",
    "humor, surpresa, musicalidade ou curiosidade quando combinarem com a obra",
    "ação e leitura visualmente imaginável",
    "prazer de leitura, participação, identificação ou releitura",
    "originalidade de voz, personagens, situações, refrões e soluções",
    "continuidade de personagem, coleção e universo",
    "acessibilidade e clareza compatíveis com a idade",
]

FAITHBLOOM_HEART_ARC = [
    "encantamento",
    "emoção",
    "experiência",
    "descoberta",
    "transformação",
    "fé",
]

HEART_ARC_PRINCIPLES = [
    "aventura/diversão por fora, transformação emocional por dentro e uma verdade de fé no coração",
    "a criança não deve receber a moral antes de viver a história",
    "a emoção precisa nascer de uma causa concreta e produzir comportamento/consequência",
    "a descoberta espiritual deve emergir organicamente da jornada",
    "a fé nunca usa medo excessivo, culpa religiosa, ameaça ou manipulação",
    "o final deve oferecer recompensa emocional, gratidão, reconciliação, paz, coragem, alegria ou outro fechamento coerente",
]

BESTSELLER_READINESS_PRINCIPLES = [
    "forte promessa de leitura e gancho apropriado ao público",
    "personagens memoráveis e emocionalmente reconhecíveis",
    "clareza de público/faixa etária e adequação real da linguagem",
    "ritmo, page-turn, humor, curiosidade ou participação que favoreçam continuidade e releitura",
    "diferenciação e originalidade editorial",
    "potencial visual e experiência de página coerentes com o formato",
    "título, capa, sinopse e metadados fiéis e comercialmente claros",
    "potencial de coleção/série quando fizer sentido, sem repetição artificial",
    "qualidade técnica de publicação e experiência do leitor",
    "decisões de mercado baseadas em evidência quando houver alegações de demanda/competição",
]

# Quem transforma diretamente o Heart Arc e quem deve protegê-lo sem reescrever.
HEART_ARC_EXECUTORS = {
    "idea_generator", "theme_curator", "storyteller", "story_editor",
    "character_creator", "illustrator", "sales_synopsis", "translator_localizer",
    "audiobook_director", "marketing_launch", "cover_specialist",
}
HEART_ARC_GUARDIANS = {
    "story_reviewer", "diagrammer", "narrator", "market_keywords",
    "market_categories", "coloring_activity_creator", "coloring_layout",
    "line_art_specialist", "coloring_idea_generator", "photo_to_character",
    "character_variations",
}


def _heart_arc_mode(role_id: str) -> str:
    if role_id in HEART_ARC_EXECUTORS:
        return "execute_or_preserve"
    if role_id in HEART_ARC_GUARDIANS:
        return "protect_and_verify"
    return "aware"


def _p(role_id, module, name, mission, skills, criteria, handoffs, forbidden=None, evidence=None, execution="llm"):
    return {
        "schema": SCHEMA,
        "role_id": role_id,
        "module": module,
        "name": name,
        "mission": mission,
        "skills": list(skills),
        "quality_criteria": list(criteria),
        "required_handoffs": list(handoffs),
        "forbidden": list(COMMON_FORBIDDEN + list(forbidden or [])),
        "evidence_requirements": list(evidence or []),
        "execution": execution,
        "shared_editorial_dna": list(FAITHBLOOM_EDITORIAL_DNA),
        "heart_arc": list(FAITHBLOOM_HEART_ARC),
        "heart_arc_principles": list(HEART_ARC_PRINCIPLES),
        "heart_arc_mode": _heart_arc_mode(role_id),
        "bestseller_readiness_principles": list(BESTSELLER_READINESS_PRINCIPLES),
    }


AGENT_PROFILES = {
    "idea_generator": _p(
        "idea_generator", "gerador_ideias.py", "Gerador de Ideias",
        "Criar conceitos originais e comercialmente diferenciáveis sem repetir temas da coleção.",
        ["ideação infantil", "promessa de leitura", "variedade temática", "potencial de série", "adequação etária", "originalidade", "Heart Arc seed", "releitura e identificação"],
        ["ideia clara em uma frase", "conflito compreensível", "emoção concreta", "oportunidade visual", "lição não forçada", "gancho que desperta curiosidade"],
        ["theme_curator", "storyteller"],
        evidence=["temas já usados na coleção"],
    ),
    "theme_curator": _p(
        "theme_curator", "curador_tema.py", "Curador de Tema",
        "Transformar uma ideia em emoção, aprendizado cristão e referência bíblica candidata sem transformar a história em sermão.",
        ["curadoria temática", "arco emocional", "valores cristãos", "coerência tema-lição", "referência bíblica candidata", "Heart Arc", "fé orgânica"],
        ["emoção válida", "lição infantil concreta", "transformação vivível", "referência marcada como candidata até validação", "integração espiritual leve e coerente"],
        ["biblical_reference_validator", "storyteller"],
        forbidden=["afirmar que a referência bíblica está validada sem fonte/contexto aprovados", "fornecer tradução livre de versículo"],
    ),
    "storyteller": _p(
        "storyteller", "roteirista.py", "Roteirista",
        "Escrever história infantil memorável, viva, emocional, visual e agradável para leitura em voz alta, com fé integrada organicamente.",
        ["storytelling infantil", "gancho inicial", "page-turn structure", "read-aloud rhythm", "arco emocional", "ação visual", "repetição suave", "integração cristã natural", "continuidade de série", "FaithBloom Heart Arc", "humor e surpresa", "releitura", "recompensa emocional"],
        ["gancho nas cenas iniciais", "uma ação visual por cena", "emoções concretas", "progressão emocional causal", "transformação vivida e não explicada", "fé orgânica", "fechamento memorável", "história divertida mesmo antes da moral"],
        ["story_reviewer", "emotional_color_director", "illustrator"],
    ),
    "story_editor": _p(
        "story_editor", "editor_historia.py", "Editor de História",
        "Editar apenas o trecho solicitado preservando continuidade, aprovações e o coração emocional/espiritual da obra.",
        ["edição cena a cena", "clareza infantil", "ritmo", "continuidade", "redução de redundância", "preservação de intenção", "Heart Arc preservation", "voz narrativa"],
        ["escopo da edição respeitado", "nenhuma mudança colateral", "voz e idade preservadas", "transformação e fé não achatadas pela edição"],
        ["story_reviewer", "biblical_reference_validator"],
        forbidden=["trocar versículo sem aprovação explícita"],
    ),
    "story_reviewer": _p(
        "story_reviewer", "revisor.py", "Revisor Editorial",
        "Revisar história independentemente do Roteirista e devolver problemas rastreáveis por cena, incluindo Heart Arc e prazer de leitura.",
        ["continuidade", "gramática", "child readability", "read-aloud", "repetição intencional", "densidade por cena", "coerência de arco", "Heart Arc audit", "releitura", "integração cristã não-pregadora"],
        ["notas localizadas", "sem reescrita silenciosa", "aprovação somente quando critérios centrais passam", "história funciona sem depender da moral explicada", "transformação é vivida", "fé emerge naturalmente"],
        ["storyteller", "quality_guardian"],
    ),
    "character_creator": _p(
        "character_creator", "criador_personagem.py", "Criador de Personagem",
        "Criar Character DNA distintivo, reproduzível, expressivo e adequado ao universo visual/emocional.",
        ["design de personagem", "silhueta", "paleta canônica", "proporções", "marcas permanentes", "expressividade", "potencial de série", "acting emocional", "memorabilidade"],
        ["DNA fixo separado de variáveis", "descrição reproduzível", "identidade visual diferenciável", "expressões capazes de sustentar o arco emocional"],
        ["character_universe", "character_variations", "illustrator"],
    ),
    "photo_to_character": _p(
        "photo_to_character", "foto_para_personagem.py", "Foto → Personagem",
        "Converter referência enviada em personagem estilizado preservando atributos solicitados e privacidade.",
        ["image-to-image", "preservação de atributos", "simplificação visual", "consistência estilística", "controle de referência"],
        ["referência de origem registrada", "resultado não tratado como identidade oficial sem aprovação"],
        ["character_universe", "character_variations"],
    ),
    "character_variations": _p(
        "character_variations", "personagens_variacoes.py", "Variações de Personagem",
        "Criar alternativas sem destruir o Character Master nem mudar identidade fixa.",
        ["variações controladas", "pose", "roupa", "expressão", "temporada", "festividade", "versionamento", "acting visual"],
        ["DNA travado preservado", "base da variação registrada", "A/B/C preservadas", "expressão coerente com emoção sem alterar identidade"],
        ["character_universe", "character_consistency"],
    ),
    "illustrator": _p(
        "illustrator", "ilustrador.py", "Ilustrador",
        "Produzir cenas coerentes com Character Master, Style DNA, emoção, Heart Arc, narrativa e requisitos de impressão.",
        ["composição infantil", "character consistency", "story-image alignment", "direção emocional", "luz e cor", "continuidade visual", "safe area", "referência multimodal", "visual storytelling", "humor visual", "recompensa emocional"],
        ["sem texto embutido", "identidade canônica preservada", "ação da cena representada", "imagem revisável antes da aprovação", "imagem aprofunda a emoção sem tornar a cena monocromática", "detalhes visuais apoiam releitura"],
        ["character_consistency", "quality_guardian", "asset_library"],
    ),
    "coloring_idea_generator": _p(
        "coloring_idea_generator", "gerador_ideias_colorir.py", "Gerador de Ideias de Coloring",
        "Criar conceitos de coloring book claros, diferenciáveis e adequados ao público escolhido.",
        ["conceito de coloring book", "coerência temática", "variedade de páginas", "faixa etária", "potencial de coleção", "engajamento infantil"],
        ["tema consistente", "variedade sem repetição", "complexidade apropriada", "atividade convidativa"],
        ["line_art_specialist", "coloring_layout"],
    ),
    "line_art_specialist": _p(
        "line_art_specialist", "line_art_colorir.py", "Especialista em Line Art",
        "Gerar line art limpa, imprimível e adequada à complexidade/idade selecionada.",
        ["line art", "espessura de traço", "áreas fechadas", "simplicidade por idade", "margens", "printability", "conversão referência→line art", "expressividade"],
        ["sem cinza indesejado", "contornos legíveis", "não cortar elementos", "personagem consistente", "emoção da cena ainda reconhecível"],
        ["coloring_doctor", "print_preflight"],
    ),
    "coloring_activity_creator": _p(
        "coloring_activity_creator", "atividades_colorir.py", "Atividades para Colorir",
        "Selecionar cenas adequadas e criar derivadas de colorir sem deformar personagens nem perder significado emocional.",
        ["seleção de cenas", "simplificação", "line art", "continuidade de personagem", "adequação infantil", "seleção de momentos memoráveis"],
        ["cenas distintas", "line art reutilizável", "referência do personagem preservada", "momentos escolhidos representam a jornada"],
        ["coloring_doctor", "asset_library"],
    ),
    "coloring_layout": _p(
        "coloring_layout", "diagramador_colorir.py", "Diagramador de Coloring",
        "Organizar miolo de coloring book com páginas técnicas e alternância segura para impressão.",
        ["paginação", "verso em branco", "margens", "ordem editorial", "páginas opcionais", "print layout", "ritmo visual"],
        ["ordem consistente", "frentes/versos intencionais", "sem elemento crítico fora da safe area", "experiência fluida"],
        ["print_preflight", "cover_specialist"], execution="deterministic",
    ),
    "sales_synopsis": _p(
        "sales_synopsis", "sinopse.py", "Sinopse de Vendas",
        "Converter a essência emocional e a promessa de leitura do livro em descrição clara, curiosa e fiel, sem promessas enganosas.",
        ["copy editorial", "benefit framing", "clareza", "curiosidade", "adequação ao público", "contracapa", "emotional hook", "Heart Arc distillation"],
        ["não entregar o final desnecessariamente", "lição e público claros", "sem alegações falsas", "preservar encanto antes de explicar a moral"],
        ["market_keywords", "marketing_launch", "cover_specialist"],
    ),
    "market_keywords": _p(
        "market_keywords", "pesquisa_mercado.py", "Especialista de Keywords",
        "Sugerir keywords relevantes e separar inferência de IA de evidência observada de mercado.",
        ["search intent", "long-tail keywords", "metadata compliance", "relevância", "market evidence literacy", "reader intent"],
        ["sem volume inventado", "sem ranking inventado", "proveniência marcada", "keywords relevantes ao conteúdo", "descoberta não sacrifica fidelidade editorial"],
        ["market_bestseller_intelligence", "publishing_engine"],
        forbidden=["afirmar volume de busca, competição ou demanda sem fonte observada"],
        evidence=["evidência externa quando houver alegação de demanda/competição"],
    ),
    "market_categories": _p(
        "market_categories", "pesquisa_mercado.py", "Especialista de Categorias",
        "Sugerir categorias relevantes sem usar nichos irrelevantes apenas para buscar selo de ranking.",
        ["category fit", "metadata taxonomy", "marketplace awareness", "compliance", "relevância comercial", "reader fit"],
        ["categoria coerente com conteúdo", "marketplace explicitado", "árvore tratada como mutável", "nenhuma distorção do livro para encaixar categoria"],
        ["market_bestseller_intelligence", "publishing_engine"],
        forbidden=["recomendar categoria irrelevante para manipular ranking"],
    ),
    "marketing_launch": _p(
        "marketing_launch", "marketing.py", "Marketing de Lançamento",
        "Preparar materiais de lançamento éticos, emocionais e consistentes com a obra e o público.",
        ["launch messaging", "social copy", "Pinterest discoverability", "email", "CTA", "review request compliance", "campaign consistency", "emotional positioning", "reader promise"],
        ["mensagens fiéis ao livro", "CTA claro", "sem incentivo indevido a review", "sem promessa de ranking", "comunicar valor emocional sem transformar fé em clickbait"],
        ["launch_strategy", "publishing_distribution"],
        forbidden=["pedir avaliação positiva em troca de benefício", "afirmar que reviews garantem ranking"],
    ),
    "cover_specialist": _p(
        "cover_specialist", "capa.py", "Especialista de Capa",
        "Criar arte de capa coerente com o livro e preparar composição técnica com forte promessa visual para cada formato/plataforma.",
        ["cover concept", "thumbnail readability", "visual hierarchy", "character identity", "genre fit", "back cover breathing room", "print wrap", "emotional hook", "distinctiveness"],
        ["arte sem texto gerado pela IA", "foco reconhecível em thumbnail", "Master separado da tipografia", "wrap calculado", "capa comunica emoção/promessa sem enganar"],
        ["cover_master", "print_preflight", "bestseller_readiness"],
    ),
    "diagrammer": _p(
        "diagrammer", "diagramador.py", "Diagramador",
        "Transformar conteúdo aprovado em sequência editorial coerente, emocionalmente ritmada e tecnicamente preparada.",
        ["page sequencing", "text-image alternation", "front matter", "safe areas", "readability", "print structure", "page-turn rhythm", "visual pacing"],
        ["ordem reproduzível", "sem conteúdo órfão", "layout compatível com preflight", "viradas de página preservam surpresa/emoção quando possível"],
        ["print_preflight", "quality_guardian"], execution="deterministic",
    ),
    "dedication": _p(
        "dedication", "dedicatoria.py", "Dedicatória",
        "Criar dedicatória curta, respeitosa e fiel às relações fornecidas, sem inventar biografia.",
        ["escrita afetiva", "tom infantil/familiar", "personalização", "privacidade", "não-invenção", "coerência de voz"],
        ["somente pessoas fornecidas", "relações respeitadas", "texto proporcional ao livro", "tom coerente com a obra"],
        ["diagrammer"],
    ),
    "translator_localizer": _p(
        "translator_localizer", "tradutor.py", "Tradutor & Localizador",
        "Localizar o livro para idioma e mercado preservando significado, idade, voz, humor, Heart Arc, onomatopeias e Bible Guard.",
        ["translation", "localization", "child language", "locale variants", "onomatopoeia localization", "glossary consistency", "cultural sensitivity", "Bible Guard", "humor localization", "Heart Arc preservation"],
        ["nenhuma omissão/invenção", "nomes protegidos", "naturalidade infantil", "mercado explícito", "versículo protegido", "emoção e transformação equivalentes no idioma-alvo"],
        ["linguistic_reviewer", "audiobook_director"],
        forbidden=["traduzir texto bíblico livremente"],
    ),
    "audiobook_director": _p(
        "audiobook_director", "audiobook.py", "Diretor de Audiobook",
        "Transformar texto aprovado em direção de performance que amplifique humor, emoção e Heart Arc sem reescrever a obra.",
        ["read-aloud direction", "pacing", "pause design", "emotion", "pronunciation planning", "character voices", "TTS portability", "comic timing", "emotional performance"],
        ["texto semanticamente idêntico", "pausas intencionais", "emoção coerente", "Bible Guard preservado", "clímax e recompensa emocional audíveis sem exagero melodramático"],
        ["narrator", "audio_qa"],
    ),
    "narrator": _p(
        "narrator", "audiobook.py", "Narrador/TTS",
        "Renderizar o roteiro aprovado em áudio versionado, expressivo e verificável.",
        ["TTS rendering", "segment naming", "pronunciation execution", "version preservation", "audio file integrity", "pacing fidelity", "emotional fidelity"],
        ["segmentos rastreáveis", "nenhuma substituição silenciosa", "mix exige escuta humana", "direção emocional preservada"],
        ["audio_qa", "quality_guardian"], execution="tool",
    ),
}

# Profiles outside the original narrative pipeline are equally auditable.
AGENT_PROFILES["pedagogical_editor"] = _p(
    "pedagogical_editor", "complementos_editoriais.py", "Editor Pedagógico",
    "Derivar complementos fiéis à história e ao mapa emocional aprovados.",
    ["leitura integral do manuscrito", "adequação etária", "mediação de leitura", "perguntas abertas por idade", "psicologia das cores editorial", "fidelidade à moral", "Bible Guard", "validação de campos e quantidades"],
    ["perguntas ligadas à história", "quantidade conforme perfil etário", "nenhum dado pedagógico inventado", "referência bíblica preservada"],
    ["story_reviewer", "diagrammer"],
)
AGENT_PROFILES["scene_director"] = _p(
    "scene_director", "character_guide.py", "Diretor de Cena",
    "Propor três cenas distintas e ilustráveis, fiéis ao trecho, idade e universo aprovado.",
    ["composição", "enquadramento", "acting e poses", "continuidade visual", "Character DNA", "Style DNA", "World Masters", "cor e iluminação", "adequação etária", "espaço para texto editorial", "opções A/B/C", "originalidade visual"],
    ["três propostas completas e distintas", "ação fiel ao trecho", "identidade preservada", "paleta atua no ambiente", "não gerar imagem nesta etapa"],
    ["illustrator", "character_consistency", "emotional_color_director"],
)
AGENT_PROFILES["scene_director"]["module_directory"] = ""

# Technical profiles reuse their canonical domains; no second skill list to drift.
from agents import engenheiro_saas_automacao as _saas
from agents import engenheiro_code_review_profundo as _deep
from agents import governanca_ia as _gov_ai
from agents import governanca_dados as _gov_data
from agents import governanca_ti as _gov_it
from agents import ciberseguranca as _cyber
for _engineer in (_saas, _deep):
    _profile = _p(
        _engineer.ROLE_ID, Path(_engineer.__file__).name, _engineer.NAME,
        _engineer.MISSION, _engineer.all_skills(),
        ["diagnóstico vinculado a evidência", "plano não equivale a correção", "teste de regressão e validação de runtime quando aplicável"],
        ["quality_guardian"], execution="hybrid" if _engineer is _deep else "deterministic",
        evidence=["fontes inspecionadas", "resultado de testes", "evidência de runtime quando aplicável"],
    )
    _profile["scope"] = "technical"
    _profile["forbidden"] = ["declarar correção, deploy ou teste executado sem evidência", "executar código retornado por IA"]
    _profile["operating_rules"] = list(_engineer.NON_NEGOTIABLES)
    for _field in ("shared_editorial_dna", "heart_arc", "heart_arc_principles", "bestseller_readiness_principles"):
        _profile[_field] = []
    _profile["heart_arc_mode"] = "not_applicable"
    AGENT_PROFILES[_engineer.ROLE_ID] = _profile

# Governança é executável e determinística. Contratos não constituem certificação.
GOVERNANCE_AGENTS = (_gov_ai, _gov_data, _gov_it, _cyber)
for _governor in GOVERNANCE_AGENTS:
    _profile = _p(
        _governor.ROLE_ID, Path(_governor.__file__).name, _governor.NAME,
        _governor.MISSION, _governor.all_skills(),
        ["achados com fonte e escopo", "UNKNOWN quando não há evidência", "nenhuma alteração destrutiva automática"],
        ["saas_automation_engineer", "deep_code_review_engineer", "quality_guardian"],
        evidence=["fontes locais inspecionadas", "evidência observada e rastreável de execução"],
        execution="deterministic",
    )
    _profile["scope"] = "technical"
    _profile["forbidden"] = list(_governor.NON_NEGOTIABLES)
    _profile["operating_rules"] = list(_governor.NON_NEGOTIABLES)
    for _field in ("shared_editorial_dna", "heart_arc", "heart_arc_principles", "bestseller_readiness_principles"):
        _profile[_field] = []
    _profile["heart_arc_mode"] = "not_applicable"
    AGENT_PROFILES[_governor.ROLE_ID] = _profile

TECHNICAL_AGENTS = (_saas, _deep, *GOVERNANCE_AGENTS)

INHERITED_MODULE_PROFILES = {
    "estilos_narrativos.py": ["storyteller"],
    "roteirista_autoral.py": ["storyteller"],
    "formato_quadrinhos.py": ["storyteller"],
}
# Handoffs to deterministic services do not need fictional LLM profiles.
HANDOFF_SERVICES = {
    "asset_library": "asset_library.py", "audio_qa": "audiobook_studio.py",
    "bestseller_readiness": "bestseller_readiness.py",
    "biblical_reference_validator": "biblical_reference_validator.py",
    "character_consistency": "character_consistency.py", "character_universe": "character_universe.py",
    "coloring_doctor": "coloring_book_doctor.py", "cover_master": "cover_master.py",
    "emotional_color_director": "emotional_color_director.py",
    "launch_strategy": "agents/marketing.py", "linguistic_reviewer": "translation_localization.py",
    "market_bestseller_intelligence": "market_intelligence.py",
    "print_preflight": "qualidade_impressao.py", "publishing_distribution": "publishing_distribution.py",
    "publishing_engine": "platform_registry.py", "quality_guardian": "quality_guardian.py",
}

# Operational requirements are maintained separately from the editable profile.
# Removing a skill, an executor or a required handoff must not silently turn the
# remaining text into a "valid" profile. These are local contracts, not claims
# that an LLM has mastered a discipline or that an external provider is ready.
# role: (real entrypoints, indispensable skills, input context, reviewable output)
ROLE_EXECUTION_REQUIREMENTS = {
    "idea_generator": (("gerador_ideias_node",), ("ideação infantil", "adequação etária", "originalidade"), ("quantidade", "temas_usados", "faixa_etaria"), ("ideias originais com título, conflito e promessa de leitura",)),
    "theme_curator": (("curador_tema_node",), ("curadoria temática", "arco emocional", "referência bíblica candidata"), ("ideia ou tema livre", "faixa_etaria"), ("emoção, aprendizado e referência candidata não validada",)),
    "storyteller": (("roteirista_node", "montar_prompt"), ("storytelling infantil", "arco emocional", "FaithBloom Heart Arc"), ("tema e faixa etária", "personagens e DNA", "lição e referência aprovadas"), ("cenas numeradas, resolução, celebração e lição final",)),
    "story_editor": (("editar_cena", "sugerir_versiculos", "sugerir_licoes"), ("edição cena a cena", "continuidade", "preservação de intenção"), ("cena e manuscrito", "instrução delimitada", "faixa_etaria"), ("cena editada ou sugestões sem substituir aprovações",)),
    "story_reviewer": (("revisor_node",), ("continuidade", "gramática", "Heart Arc audit"), ("manuscrito completo", "faixa_etaria", "referência e moral"), ("revisao_aprovada e notas rastreáveis por cena",)),
    "character_creator": (("criar_personagem_a_partir_de_ideia",), ("design de personagem", "paleta canônica", "marcas permanentes"), ("ideia e estilo", "idade e contexto do universo"), ("DNA e referência candidata sujeita à aprovação",)),
    "photo_to_character": (("gerar_personagem_a_partir_de_foto",), ("image-to-image", "preservação de atributos", "controle de referência"), ("foto autorizada", "instruções e estilo"), ("imagem derivada revisável sem aprovação automática",)),
    "character_variations": (("gerar_primeira_referencia", "gerar_variacao", "aprovar_variacao"), ("variações controladas", "expressão", "versionamento"), ("personagem e DNA fixo", "referência-base e variáveis autorizadas"), ("variações versionadas e aprovação explícita",)),
    "illustrator": (("prompt_cena", "ilustrador_node", "gerar_cena_unica"), ("character consistency", "direção emocional", "luz e cor"), ("cena e mapa emocional", "Character Master e Style DNA", "referências autorizadas"), ("imagem e prompt rastreáveis, histórico e aprovação separados",)),
    "coloring_idea_generator": (("gerador_ideias_colorir_node",), ("conceito de coloring book", "variedade de páginas", "faixa etária"), ("quantidade", "temas_usados"), ("conceitos distintos de coloring book",)),
    "line_art_specialist": (("prompt_pagina_colorir", "gerar_pagina_colorir", "gerar_variacao_line_art"), ("line art", "espessura de traço", "áreas fechadas"), ("descrição da página", "idade e complexidade", "DNA e referência quando vinculados"), ("line art revisável com traços, margens e identidade verificáveis",)),
    "coloring_activity_creator": (("atividades_colorir_node",), ("seleção de cenas", "simplificação", "continuidade de personagem"), ("cenas da história", "DNA e referências autorizadas"), ("páginas de colorir derivadas sem substituir os Masters",)),
    "coloring_layout": (("montar_layout_colorir", "diagramador_colorir_node"), ("paginação", "verso em branco", "margens"), ("páginas de colorir e opções editoriais",), ("sequência física com alternância e versos em branco",)),
    "sales_synopsis": (("sinopse_node",), ("copy editorial", "adequação ao público", "emotional hook"), ("história completa", "público e aprendizado"), ("sinopse curta e longa fiéis à obra",)),
    "market_keywords": (("pesquisa_palavras_chave_node",), ("search intent", "metadata compliance", "market evidence literacy"), ("título e sinopse", "mercado e evidência externa quando disponível"), ("keywords e proveniência sem métricas inventadas",)),
    "market_categories": (("pesquisa_categorias_node",), ("category fit", "metadata taxonomy", "compliance"), ("livro e mercado-alvo", "evidência de categorias quando disponível"), ("categorias candidatas relevantes e proveniência",)),
    "marketing_launch": (("marketing_lancamento_node",), ("launch messaging", "review request compliance", "campaign consistency"), ("livro, público e sinopse",), ("materiais candidatos sem envio nem promessa de vendas",)),
    "cover_specialist": (("prompt_arte_capa_frontal", "gerar_artes_capa", "montar_capa_fisica"), ("character identity", "print wrap", "thumbnail readability"), ("história e Masters", "formato, páginas e especificação da plataforma"), ("arte sem texto e composição técnica separada revisáveis",)),
    "diagrammer": (("montar_layout", "diagramador_node"), ("page sequencing", "safe areas", "print structure"), ("conteúdo e imagens aprovados", "perfil etário e formato"), ("layout página a página, contagem e preflight",)),
    "dedication": (("dedicatoria_node",), ("personalização", "privacidade", "não-invenção"), ("pessoas e relações fornecidas", "tom da obra"), ("dedicatória sem inventar biografia",)),
    "translator_localizer": (("tradutor_node", "localizar_livro"), ("translation", "localization", "Bible Guard"), ("Master aprovado", "locale e glossário", "registro bíblico do idioma"), ("tradução derivada com fonte preservada e revisão separada",)),
    "audiobook_director": (("audiobook_node",), ("read-aloud direction", "pause design", "TTS portability"), ("texto aprovado", "idioma, público e emoções"), ("roteiro de performance semanticamente idêntico",)),
    "narrator": (("narracao_node",), ("TTS rendering", "version preservation", "audio file integrity"), ("roteiro aprovado e segmentos numerados", "executor TTS configurado"), ("arquivos de áudio rastreáveis preservando versões",)),
    "pedagogical_editor": (("gerar_complementos_editoriais", "validar_complementos", "aplicar_complementos"), ("leitura integral do manuscrito", "perguntas abertas por idade", "Bible Guard"), ("história e mapa emocional", "idade, moral e referência aprovadas"), ("complementos validados antes de substituir o conteúdo salvo",)),
    "scene_director": (("suggest_scene_concepts", "validate_scene_concepts", "compose_scene_prompt"), ("Character DNA", "World Masters", "cor e iluminação"), ("trecho e história completa", "Masters, DNA e mapa emocional", "idade e enquadramento"), ("três propostas A/B/C distintas sem gerar imagens",)),
    "saas_automation_engineer": (("handle_saas_request", "run_diagnostic", "automation_safety_gate"), ("full-stack application development", "integration testing", "human approval gates"), ("pedido e fontes locais selecionadas", "evidência de execução quando fornecida"), ("plano e diagnóstico, nunca patch ou deploy executado por IA",)),
    "deep_code_review_engineer": (("review_sources", "build_deep_review_plan", "correction_gate"), ("line-by-line review",), ("pedido e fontes selecionadas", "evidência rastreável dos achados"), ("revisão com citações verificadas sem executar o código proposto",)),
    "ai_governance": (("run_diagnostic", "check_generation_action"), ("inventário de modelos", "guardas de custos", "aprovação humana"), ("fontes, metadados e contexto da ação",), ("achados sanitizados e decisão pré-ação, UNKNOWN sem evidência",)),
    "data_governance": (("run_diagnostic", "check_data_action"), ("classificação de dados", "consentimento", "linhagem"), ("metadados e contexto de privacidade",), ("achados sobre consentimento, retenção e escopo sem expor manuscrito",)),
    "it_governance": (("run_diagnostic", "check_it_action"), ("gestão de mudanças", "CI e regressão", "release e rollback"), ("fontes e evidências operacionais fornecidas",), ("achados técnicos e limites de prontidão sem deploy automático",)),
    "cybersecurity": (("run_diagnostic", "check_security_action"), ("proteção de segredos", "autenticação e autorização", "auditoria sanitizada"), ("fontes selecionadas e contexto de autorização",), ("achados sanitizados; sem ataque, alteração ou certificação fictícia",)),
}

# Services retain their actual deterministic/tool implementation; a handoff is
# validated as an executable function, never as a path string alone.
HANDOFF_SERVICE_CONTRACTS = {
    "asset_library": ("get_asset", "register_usage"),
    "audio_qa": ("qa_audio_clip", "audio_readiness"),
    "bestseller_readiness": ("evaluate_bestseller_readiness",),
    "biblical_reference_validator": ("create_reference_candidate", "reference_gate"),
    "character_consistency": ("auditar_caracteristicas",),
    "character_universe": ("carregar_personagem_oficial", "personagem_para_prompt"),
    "coloring_doctor": ("analisar_line_art_avancada", "auditar_lote_colorir"),
    "cover_master": ("carregar_cover_master", "preflight_cover_master"),
    "emotional_color_director": ("construir_mapa_emocional", "prompt_direcao_visual"),
    "launch_strategy": ("marketing_lancamento_node",),
    "linguistic_reviewer": ("revisar_localizacao_estrutural", "revisar_localizacao_com_llm"),
    "market_bestseller_intelligence": ("validate_market_evidence", "build_market_brief"),
    "print_preflight": ("preflight_livro", "analisar_pdf_miolo"),
    "publishing_distribution": ("create_distribution_plan", "build_channel_package"),
    "publishing_engine": ("get_platform", "verification_state"),
    "quality_guardian": ("run_quality_guardian", "register_author_final_approval"),
}

# Preserve the required graph independently of the mutable exported document.
_REQUIRED_ROLE_HANDOFFS = {role: tuple(profile["required_handoffs"]) for role, profile in AGENT_PROFILES.items()}
for _rid, (_entrypoints, _skills, _inputs, _outputs) in ROLE_EXECUTION_REQUIREMENTS.items():
    AGENT_PROFILES[_rid]["runtime_contract"] = {
        "entrypoints": list(_entrypoints), "essential_skills": list(_skills),
        "inputs": list(_inputs), "outputs": list(_outputs),
        "handoff_mode": "explicit workflow or human-approved transition; registry is not an automatic dispatcher",
        "quality_boundary": "configuration verified; output quality and live integrations require independent evidence",
    }
    if not AGENT_PROFILES[_rid]["evidence_requirements"]:
        AGENT_PROFILES[_rid]["evidence_requirements"] = [
            "entradas aprovadas ou fornecidas, identificáveis no projeto",
            "saída revisável: " + "; ".join(_outputs),
        ]


def profile_module_path(profile: dict, root: Path | None = None) -> Path:
    return (root or Path(__file__).resolve().parent) / profile.get("module_directory", "agents") / profile["module"]


class SkillReadinessError(ValueError):
    """A role is not configured for its declared job; no provider should run."""


@lru_cache(maxsize=512)
def _function_names(path: str, modified_ns: int, size: int) -> frozenset[str]:
    # Stat identity invalidates this cache when local code changes. Parse only:
    # importing a handoff here could perform I/O or create a circular import.
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    def implemented(node):
        body = [item for item in node.body if not isinstance(item, ast.Pass)
                and not (isinstance(item, ast.Expr) and isinstance(item.value, ast.Constant))]
        return bool(body) and not (len(body) == 1 and isinstance(body[0], ast.Raise)
                                  and "NotImplementedError" in ast.unparse(body[0]))
    return frozenset(node.name for node in tree.body
                     if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and implemented(node))


def _consumed_contract_roles(tree: ast.AST) -> set[str]:
    parents = {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
    roles = set()
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "skill_contract" and node.args
                and isinstance(node.args[0], ast.Constant)):
            continue
        # A detached call has no effect on a prompt. Constants and comments at
        # module scope are not evidence of an active agent either.
        if isinstance(parents.get(node), ast.Expr):
            continue
        ancestor = parents.get(node)
        while ancestor is not None and not isinstance(ancestor, (ast.FunctionDef, ast.AsyncFunctionDef)):
            ancestor = parents.get(ancestor)
        if ancestor is not None:
            roles.add(node.args[0].value)
    return roles


def _entrypoint_errors(path: Path, entrypoints, label: str) -> list[str]:
    if not path.is_file():
        return [f"{label}: executor ausente {path.name}"]
    try:
        stat = path.stat()
        names = _function_names(str(path.resolve()), stat.st_mtime_ns, stat.st_size)
    except (OSError, SyntaxError, UnicodeError):
        return [f"{label}: executor ilegível ou com sintaxe inválida {path.name}"]
    return [f"{label}: entrypoint ausente {name} em {path.name}" for name in entrypoints if name not in names]


def _role_configuration_errors(role_id: str, root: Path) -> list[str]:
    profile = AGENT_PROFILES.get(role_id)
    spec = ROLE_EXECUTION_REQUIREMENTS.get(role_id)
    if not profile or not spec:
        return [f"{role_id}: contrato operacional ausente"]
    entrypoints, essential_skills, inputs, outputs = spec
    errors = []
    if profile.get("role_id") != role_id:
        errors.append(f"{role_id}: role_id divergente")
    declared = profile.get("skills") or []
    for skill in essential_skills:
        if skill not in declared:
            errors.append(f"{role_id}: skill essencial ausente: {skill}")
    contract = profile.get("runtime_contract") or {}
    for field, expected in (("entrypoints", entrypoints), ("essential_skills", essential_skills), ("inputs", inputs), ("outputs", outputs)):
        if contract.get(field) != list(expected):
            errors.append(f"{role_id}: contrato operacional divergente: {field}")
    for target in _REQUIRED_ROLE_HANDOFFS.get(role_id, ()):
        if target not in (profile.get("required_handoffs") or []):
            errors.append(f"{role_id}: handoff obrigatório removido: {target}")
    try:
        errors.extend(_entrypoint_errors(profile_module_path(profile, root), entrypoints, role_id))
    except (KeyError, TypeError):
        errors.append(f"{role_id}: módulo de execução inválido")
    return errors


def role_readiness(role_id: str, *, root: Path | None = None) -> dict:
    """Verify local capability configuration without executing external work.

    This checks the role and its direct handoff executors. It does not infer
    that an LLM output, credentials, customer isolation or production is ready.
    """
    folder = Path(root or Path(__file__).resolve().parent)
    errors = _role_configuration_errors(role_id, folder)
    for target in (AGENT_PROFILES.get(role_id, {}).get("required_handoffs") or []):
        if target in AGENT_PROFILES:
            errors.extend(_role_configuration_errors(target, folder))
        elif target in HANDOFF_SERVICES:
            entrypoints = HANDOFF_SERVICE_CONTRACTS.get(target)
            if not entrypoints:
                errors.append(f"{role_id}: handoff sem contrato executável: {target}")
            else:
                errors.extend(_entrypoint_errors(folder / HANDOFF_SERVICES[target], entrypoints, target))
        else:
            errors.append(f"{role_id}: handoff desconhecido: {target}")
    return {"role_id": role_id, "ok": not errors,
            "status": "configured_for_execution" if not errors else "blocked_configuration",
            "quality_validated": False, "production_validated": False,
            "errors": list(dict.fromkeys(errors))}


def require_role_ready(role_id: str, *, root: Path | None = None) -> dict:
    """Fail before provider/tool execution if the job contract is incomplete."""
    report = role_readiness(role_id, root=root)
    if not report["ok"]:
        raise SkillReadinessError("Agente indisponível: " + "; ".join(report["errors"]))
    return report


def agent_capability_inventory(root: Path | None = None, *, runtime_evidence: dict | None = None) -> dict:
    """Evidence-aware inventory for the Agent Skills UI and engineering report.

    A function found in source is not a callable tested in a live process. The
    caller can attach scoped test evidence, which remains separate from static
    configuration, provider checks and qualitative acceptance.
    """
    folder = Path(root or Path(__file__).resolve().parent)
    supplied = runtime_evidence or {}
    rows = []
    for role_id in sorted(AGENT_PROFILES):
        profile = get_agent_profile(role_id)
        path = profile_module_path(profile, folder)
        source = path.read_text(encoding="utf-8") if path.is_file() else ""
        try:
            tree = ast.parse(source)
            functions = {node.name: node.lineno for node in tree.body
                         if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
            injected = role_id in _consumed_contract_roles(tree)
            gates = [node.lineno for node in ast.walk(tree)
                     if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                     and node.func.id == "require_role_ready" and node.args
                     and isinstance(node.args[0], ast.Constant) and node.args[0].value == role_id]
        except SyntaxError:
            functions, injected, gates = {}, False, []
        entrypoints = profile["runtime_contract"]["entrypoints"]
        rows.append({
            "role_id": role_id, "name": profile["name"], "kind": "registered_role",
            "execution": profile["execution"], "module": str(path.relative_to(folder)),
            "skills_declared": profile["skills"],
            "essential_skills": profile["runtime_contract"]["essential_skills"],
            "inputs": profile["runtime_contract"]["inputs"], "outputs": profile["runtime_contract"]["outputs"],
            "quality_criteria": profile["quality_criteria"], "required_handoffs": profile["required_handoffs"],
            "configuration": role_readiness(role_id, root=folder),
            "contract_injected_in_source": injected,
            "deterministic_gate_source_lines": gates,
            "entrypoint_static_presence": {name: name in functions for name in entrypoints},
            "source_evidence": [f"{path.relative_to(folder)}:{functions[name]}" for name in entrypoints if name in functions],
            "provided_runtime_evidence": deepcopy(supplied.get(role_id, [])),
            "imported_callable_verified_by_inventory": False,
            "output_quality_verified_by_inventory": False,
            "external_limits": (["provedor e resultado em produção não testados por este inventário"]
                                if profile["execution"] in {"llm", "hybrid", "tool"}
                                else ["análise local não comprova produção, certificação ou execução de correções"]),
        })
    return {
        "schema": "faithbloom.agent-capability-inventory.v1", "roles": rows,
        "role_count": len(rows),
        "inherited_modules": deepcopy(INHERITED_MODULE_PROFILES),
        "services": [{"service_id": key, "kind": "service_not_llm_role", "module": value,
                      "entrypoints": list(HANDOFF_SERVICE_CONTRACTS.get(key, ())),
                      "static_errors": _entrypoint_errors(folder / value, HANDOFF_SERVICE_CONTRACTS.get(key, ()), key),
                      "provided_runtime_evidence": deepcopy(supplied.get(key, [])),
                      "execution_verified_by_inventory": False}
                     for key, value in sorted(HANDOFF_SERVICES.items())],
        "caveats": ["skills declaradas não medem excelência profissional", "AST verifica configuração, não execução",
                    "handoffs são contratos de destinos; o registro não executa um pipeline automaticamente",
                    "validar cada saída, aprovações e integrações externas no contexto de uso"],
    }


MODULE_TO_ROLES = {}
for _rid, _profile in AGENT_PROFILES.items():
    MODULE_TO_ROLES.setdefault(_profile["module"], []).append(_rid)


def all_agent_profiles() -> list[dict]:
    return [deepcopy(AGENT_PROFILES[k]) for k in sorted(AGENT_PROFILES)]


def get_agent_profile(role_id: str) -> dict:
    if role_id not in AGENT_PROFILES:
        raise KeyError(f"Skill profile desconhecido: {role_id}")
    return deepcopy(AGENT_PROFILES[role_id])


def roles_for_module(module_name: str) -> list[str]:
    name = Path(module_name).name
    return list(MODULE_TO_ROLES.get(name, INHERITED_MODULE_PROFILES.get(name, [])))


def shared_literary_contract(*, compact: bool = False) -> str:
    """Contrato transversal: todos conhecem; cada agente só executa dentro do próprio escopo."""
    if compact:
        return (
            "FaithBloom DNA: encante antes de ensinar; transformação vivida; fé orgânica; "
            "emoção adequada à idade; originalidade; prazer de leitura/releitura; "
            "bestseller-readiness sem promessa de vendas."
        )
    return (
        "\n=== FAITHBLOOM LITERARY EXCELLENCE CHARTER ===\n"
        f"DNA EDITORIAL: {'; '.join(FAITHBLOOM_EDITORIAL_DNA)}.\n"
        f"HEART ARC: {' → '.join(FAITHBLOOM_HEART_ARC)}.\n"
        f"PRINCÍPIOS HEART ARC: {'; '.join(HEART_ARC_PRINCIPLES)}.\n"
        f"BESTSELLER READINESS: {'; '.join(BESTSELLER_READINESS_PRINCIPLES)}.\n"
        "IMPORTANTE: bestseller-readiness significa maximizar qualidade, descoberta e adequação; nunca prometer ranking ou vendas.\n"
    )


def skill_contract(role_id: str, *, compact: bool = False) -> str:
    require_role_ready(role_id)
    p = get_agent_profile(role_id)
    operational = p["runtime_contract"]
    io_contract = (f"Entradas necessárias: {'; '.join(operational['inputs'])}.\n"
                   f"Saídas esperadas: {'; '.join(operational['outputs'])}.\n")
    shared = ("REGRAS TÉCNICAS: " + "; ".join(p.get("operating_rules", []))
              if p.get("scope") == "technical" else shared_literary_contract(compact=compact))
    if compact:
        return (
            f"\n[FAITHBLOOM SKILL CONTRACT: {p['name']}]\n"
            f"Missão: {p['mission']}\n"
            f"{io_contract}"
            f"Skills obrigatórias: {', '.join(p['skills'])}.\n"
            f"Critérios: {'; '.join(p['quality_criteria'])}.\n"
            f"Evidências necessárias: {'; '.join(p['evidence_requirements']) or 'resultado revisável'}.\n"
            f"Handoffs esperados: {', '.join(p['required_handoffs']) or 'nenhum'}.\n"
            f"Heart Arc mode: {p['heart_arc_mode']}.\n"
            f"Limites: {'; '.join(p['forbidden'])}.\n"
            f"{shared}\n"
        )
    return (
        f"\n\n=== FAITHBLOOM SKILL CONTRACT · {p['name']} ===\n"
        f"MISSÃO: {p['mission']}\n"
        f"{io_contract}"
        f"SKILLS OBRIGATÓRIAS: {', '.join(p['skills'])}.\n"
        f"QUALITY CRITERIA: {'; '.join(p['quality_criteria'])}.\n"
        f"HEART ARC MODE: {p['heart_arc_mode']}.\n"
        f"NÃO FAÇA: {'; '.join(p['forbidden'])}.\n"
        f"EVIDÊNCIAS NECESSÁRIAS: {'; '.join(p['evidence_requirements']) or 'resultado revisável'}.\n"
        f"HANDOFFS ESPERADOS: {', '.join(p['required_handoffs']) or 'nenhum'}.\n"
        "Ao responder, não declare que critérios foram validados se você não recebeu evidência suficiente.\n"
        f"{shared}\n"
    )


def validate_registry(root: Path | None = None, *, check_export: bool = True) -> dict:
    root = Path(root or Path(__file__).resolve().parent)
    errors = []
    modules = {}
    required = {
        "role_id", "module", "name", "mission", "skills", "quality_criteria",
        "required_handoffs", "forbidden", "evidence_requirements", "execution",
        "shared_editorial_dna", "heart_arc", "heart_arc_principles",
        "heart_arc_mode", "bestseller_readiness_principles",
        "runtime_contract",
    }
    for rid, p in AGENT_PROFILES.items():
        errors.extend(role_readiness(rid, root=root)["errors"])
        missing = sorted(required - set(p))
        if missing:
            errors.append(f"{rid}: campos ausentes {missing}")
        if p.get("role_id") != rid:
            errors.append(f"{rid}: role_id divergente")
        if len(p.get("skills") or []) < 3:
            errors.append(f"{rid}: skills insuficientes")
        if len(p.get("quality_criteria") or []) < 2:
            errors.append(f"{rid}: critérios insuficientes")
        if p.get("scope") != "technical" and p.get("heart_arc") != FAITHBLOOM_HEART_ARC:
            errors.append(f"{rid}: Heart Arc divergente do contrato compartilhado")
        if p.get("scope") != "technical" and not p.get("bestseller_readiness_principles"):
            errors.append(f"{rid}: bestseller-readiness ausente")
        modules.setdefault(p.get("module"), 0)
        modules[p.get("module")] += 1
        module_path = profile_module_path(p, root)
        if not module_path.exists():
            errors.append(f"{rid}: módulo {p.get('module')} não existe")
        else:
            source = module_path.read_text(encoding="utf-8", errors="ignore")
            if rid not in source:
                errors.append(f"{rid}: papel não declarado no módulo {p.get('module')}")
    covered = {p["module"] for p in AGENT_PROFILES.values() if p.get("module_directory", "agents") == "agents"} | set(INHERITED_MODULE_PROFILES)
    for path in (root / "agents").glob("*.py"):
        if path.name != "__init__.py" and path.name not in covered:
            errors.append(f"Agente sem perfil: {path.name}")
    for module, roles in INHERITED_MODULE_PROFILES.items():
        if not (root / "agents" / module).is_file():
            errors.append(f"Módulo herdado ausente: {module}")
        for role in roles:
            if role not in AGENT_PROFILES:
                errors.append(f"Perfil herdado desconhecido: {role}")
    for rid, p in AGENT_PROFILES.items():
        for target in p["required_handoffs"]:
            if target not in AGENT_PROFILES and target not in HANDOFF_SERVICES:
                errors.append(f"{rid}: handoff desconhecido {target}")
    for target, module in HANDOFF_SERVICES.items():
        if not (root / module).is_file():
            errors.append(f"{target}: serviço ausente {module}")
    # Inspect syntax, not a string that could occur only in a comment.
    consumers = [(profile_module_path(p, root), rid) for rid, p in AGENT_PROFILES.items() if p["execution"] in {"llm", "hybrid"}]
    consumers += [(root / "agents" / module, rid) for module, roles in INHERITED_MODULE_PROFILES.items() for rid in roles]
    for path, rid in consumers:
        if not path.is_file():
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
            contracts = _consumed_contract_roles(tree)
            if rid not in contracts:
                errors.append(f"{path.name}: contrato de {rid} não utilizado")
        except SyntaxError:
            errors.append(f"{path.name}: sintaxe inválida")
    if check_export:
        try:
            saved = json.loads((root / "skills" / "agent_profiles.json").read_text(encoding="utf-8"))
            if saved != registry_document():
                errors.append("skills/agent_profiles.json desatualizado")
        except (OSError, ValueError):
            errors.append("skills/agent_profiles.json ausente ou inválido")
        for role in (agent.ROLE_ID for agent in TECHNICAL_AGENTS):
            try:
                saved = json.loads((root / "skills" / (role + ".json")).read_text(encoding="utf-8"))
                if saved != technical_profile_document(role):
                    errors.append(f"skills/{role}.json desatualizado")
            except (OSError, ValueError):
                errors.append(f"skills/{role}.json ausente ou inválido")
    return {
        "schema": SCHEMA,
        "ok": not errors,
        "role_count": len(AGENT_PROFILES),
        "module_count": len(modules),
        "errors": list(dict.fromkeys(errors)),
        "modules": modules,
    }


def technical_profile_document(role_id: str) -> dict:
    engineer = {agent.ROLE_ID: agent for agent in TECHNICAL_AGENTS}[role_id]
    is_governance = engineer in GOVERNANCE_AGENTS
    return {
        "schema": "faithbloom.technical-agent-skills.v2",
        "role_id": role_id, "name": engineer.NAME, "mission": engineer.MISSION,
        "module": "agents/" + Path(engineer.__file__).name,
        "skill_domains": {key: list(values) for key, values in engineer.SKILL_DOMAINS.items()},
        "runtime_contract": deepcopy(AGENT_PROFILES[role_id]["runtime_contract"]),
        "quality_criteria": list(AGENT_PROFILES[role_id]["quality_criteria"]),
        "evidence_requirements": list(AGENT_PROFILES[role_id]["evidence_requirements"]),
        "non_negotiables": list(engineer.NON_NEGOTIABLES),
        "runtime_entrypoints": ["run_diagnostic"] if is_governance else ["run_diagnostic", "handle_saas_request"] if engineer is _saas else ["review_sources", "build_deep_review_plan"],
        "activation": "Governança / Agent Skills; diagnóstico determinístico" if is_governance else "Jarvis / Agent Skills / Engenharia; contrato técnico aplicado pelo executor autorizado",
        "execution_boundary": "Diagnóstico local e guardas pré-ação; nenhum dado, Master, provedor ou deploy é modificado automaticamente." if is_governance else "Diagnóstico local e revisão de fontes; nenhum patch, teste ou deploy é executado por uma resposta da IA.",
    }


def export_all_profiles(directory: str | Path) -> None:
    folder = Path(directory)
    export_registry_json(folder / "agent_profiles.json")
    for role in (agent.ROLE_ID for agent in TECHNICAL_AGENTS):
        (folder / (role + ".json")).write_text(json.dumps(technical_profile_document(role), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def registry_document() -> dict:
    return {
        "schema": SCHEMA,
        "shared_editorial_dna": FAITHBLOOM_EDITORIAL_DNA,
        "heart_arc": FAITHBLOOM_HEART_ARC,
        "heart_arc_principles": HEART_ARC_PRINCIPLES,
        "bestseller_readiness_principles": BESTSELLER_READINESS_PRINCIPLES,
        "profiles": all_agent_profiles(),
        "inherited_modules": INHERITED_MODULE_PROFILES,
        "handoff_services": HANDOFF_SERVICES,
        "handoff_service_contracts": {key: list(value) for key, value in HANDOFF_SERVICE_CONTRACTS.items()},
    }


def export_registry_json(path: str | Path) -> str:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps(
            registry_document(),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return str(p)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Conferir ou exportar contratos de agentes.")
    parser.add_argument("--export", action="store_true")
    args = parser.parse_args()
    if args.export:
        export_all_profiles(Path(__file__).resolve().parent / "skills")
    report = validate_registry()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report["ok"] else 1)

