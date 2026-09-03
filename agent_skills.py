"""FaithBloom Refinamento 21 — Agent Skills Registry.

Formaliza competências, critérios de excelência, limites e handoffs de cada
papel especializado. O registry não promete vendas; ele aumenta consistência
e auditabilidade do processo editorial.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, asdict
from pathlib import Path
import json

SCHEMA = "faithbloom.agent-skills.v1"

COMMON_FORBIDDEN = [
    "prometer best-seller, ranking, vendas ou aprovação por plataforma",
    "inventar evidência de mercado, métricas, fontes ou validação humana",
    "alterar conteúdo aprovado fora do escopo do agente sem autorização",
    "tratar sugestão de IA como fato observado",
]


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
    }


AGENT_PROFILES = {
    "idea_generator": _p(
        "idea_generator", "gerador_ideias.py", "Gerador de Ideias",
        "Criar conceitos originais e comercialmente diferenciáveis sem repetir temas da coleção.",
        ["ideação infantil", "promessa de leitura", "variedade temática", "potencial de série", "adequação 3–8", "originalidade"],
        ["ideia clara em uma frase", "conflito compreensível", "emoção concreta", "oportunidade visual", "lição não forçada"],
        ["theme_curator", "storyteller"],
        evidence=["temas já usados na coleção"],
    ),
    "theme_curator": _p(
        "theme_curator", "curador_tema.py", "Curador de Tema",
        "Transformar uma ideia em emoção, aprendizado cristão e referência bíblica candidata.",
        ["curadoria temática", "arco emocional", "valores cristãos", "coerência tema-lição", "referência bíblica candidata"],
        ["emoção válida", "lição infantil concreta", "referência marcada como candidata até validação"],
        ["biblical_reference_validator", "storyteller"],
        forbidden=["afirmar que a referência bíblica está validada sem fonte/contexto aprovados", "fornecer tradução livre de versículo"],
    ),
    "storyteller": _p(
        "storyteller", "roteirista.py", "Roteirista",
        "Escrever história infantil memorável, clara, visual e agradável para leitura em voz alta.",
        ["storytelling infantil", "gancho inicial", "page-turn structure", "read-aloud rhythm", "arco emocional", "ação visual", "repetição suave", "integração cristã natural", "continuidade de série"],
        ["gancho nas cenas iniciais", "uma ação visual por cena", "emoções concretas", "progressão curiosidade→desafio→aprendizado→fé→gratidão", "fechamento memorável"],
        ["story_reviewer", "emotional_color_director", "illustrator"],
    ),
    "story_editor": _p(
        "story_editor", "editor_historia.py", "Editor de História",
        "Editar apenas o trecho solicitado preservando continuidade e aprovações anteriores.",
        ["edição cena a cena", "clareza infantil", "ritmo", "continuidade", "redução de redundância", "preservação de intenção"],
        ["escopo da edição respeitado", "nenhuma mudança colateral", "voz e idade preservadas"],
        ["story_reviewer", "biblical_reference_validator"],
        forbidden=["trocar versículo sem aprovação explícita"],
    ),
    "story_reviewer": _p(
        "story_reviewer", "revisor.py", "Revisor Editorial",
        "Revisar história independentemente do Roteirista e devolver problemas rastreáveis por cena.",
        ["continuidade", "gramática", "child readability", "read-aloud", "repetição intencional", "densidade por cena", "coerência de arco"],
        ["notas localizadas", "sem reescrita silenciosa", "aprovação somente quando critérios centrais passam"],
        ["storyteller", "quality_guardian"],
    ),
    "character_creator": _p(
        "character_creator", "criador_personagem.py", "Criador de Personagem",
        "Criar Character DNA distintivo, reproduzível e adequado ao universo visual.",
        ["design de personagem", "silhueta", "paleta canônica", "proporções", "marcas permanentes", "expressividade", "potencial de série"],
        ["DNA fixo separado de variáveis", "descrição reproduzível", "identidade visual diferenciável"],
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
        ["variações controladas", "pose", "roupa", "expressão", "temporada", "festividade", "versionamento"],
        ["DNA travado preservado", "base da variação registrada", "A/B/C preservadas"],
        ["character_universe", "character_consistency"],
    ),
    "illustrator": _p(
        "illustrator", "ilustrador.py", "Ilustrador",
        "Produzir cenas coerentes com Character Master, Style DNA, emoção, narrativa e requisitos de impressão.",
        ["composição infantil", "character consistency", "story-image alignment", "direção emocional", "luz e cor", "continuidade visual", "safe area", "referência multimodal"],
        ["sem texto embutido", "identidade canônica preservada", "ação da cena representada", "imagem revisável antes da aprovação"],
        ["character_consistency", "quality_guardian", "asset_library"],
    ),
    "coloring_idea_generator": _p(
        "coloring_idea_generator", "gerador_ideias_colorir.py", "Gerador de Ideias de Coloring",
        "Criar conceitos de coloring book claros, diferenciáveis e adequados ao público escolhido.",
        ["conceito de coloring book", "coerência temática", "variedade de páginas", "faixa etária", "potencial de coleção"],
        ["tema consistente", "variedade sem repetição", "complexidade apropriada"],
        ["line_art_specialist", "coloring_layout"],
    ),
    "line_art_specialist": _p(
        "line_art_specialist", "line_art_colorir.py", "Especialista em Line Art",
        "Gerar line art limpa, imprimível e adequada à complexidade/idade selecionada.",
        ["line art", "espessura de traço", "áreas fechadas", "simplicidade por idade", "margens", "printability", "conversão referência→line art"],
        ["sem cinza indesejado", "contornos legíveis", "não cortar elementos", "personagem consistente"],
        ["coloring_doctor", "print_preflight"],
    ),
    "coloring_activity_creator": _p(
        "coloring_activity_creator", "atividades_colorir.py", "Atividades para Colorir",
        "Selecionar cenas adequadas e criar derivadas de colorir sem deformar personagens.",
        ["seleção de cenas", "simplificação", "line art", "continuidade de personagem", "adequação infantil"],
        ["cenas distintas", "line art reutilizável", "referência do personagem preservada"],
        ["coloring_doctor", "asset_library"],
    ),
    "coloring_layout": _p(
        "coloring_layout", "diagramador_colorir.py", "Diagramador de Coloring",
        "Organizar miolo de coloring book com páginas técnicas e alternância segura para impressão.",
        ["paginação", "verso em branco", "margens", "ordem editorial", "páginas opcionais", "print layout"],
        ["ordem consistente", "frentes/versos intencionais", "sem elemento crítico fora da safe area"],
        ["print_preflight", "cover_specialist"], execution="deterministic",
    ),
    "sales_synopsis": _p(
        "sales_synopsis", "sinopse.py", "Sinopse de Vendas",
        "Converter a essência do livro em descrição clara, emocional e fiel, sem promessas enganosas.",
        ["copy editorial", "benefit framing", "clareza", "curiosidade", "adequação ao público", "contracapa"],
        ["não entregar o final desnecessariamente", "lição e público claros", "sem alegações falsas"],
        ["market_keywords", "marketing_launch", "cover_specialist"],
    ),
    "market_keywords": _p(
        "market_keywords", "pesquisa_mercado.py", "Especialista de Keywords",
        "Sugerir keywords relevantes e separar inferência de IA de evidência observada de mercado.",
        ["search intent", "long-tail keywords", "metadata compliance", "relevância", "market evidence literacy"],
        ["sem volume inventado", "sem ranking inventado", "proveniência marcada", "keywords relevantes ao conteúdo"],
        ["market_bestseller_intelligence", "publishing_engine"],
        forbidden=["afirmar volume de busca, competição ou demanda sem fonte observada"],
        evidence=["evidência externa quando houver alegação de demanda/competição"],
    ),
    "market_categories": _p(
        "market_categories", "pesquisa_mercado.py", "Especialista de Categorias",
        "Sugerir categorias relevantes sem usar nichos irrelevantes apenas para buscar selo de ranking.",
        ["category fit", "metadata taxonomy", "marketplace awareness", "compliance", "relevância comercial"],
        ["categoria coerente com conteúdo", "marketplace explicitado", "árvore tratada como mutável"],
        ["market_bestseller_intelligence", "publishing_engine"],
        forbidden=["recomendar categoria irrelevante para manipular ranking"],
    ),
    "marketing_launch": _p(
        "marketing_launch", "marketing.py", "Marketing de Lançamento",
        "Preparar materiais de lançamento éticos e consistentes com a obra e o público.",
        ["launch messaging", "social copy", "Pinterest discoverability", "email", "CTA", "review request compliance", "campaign consistency"],
        ["mensagens fiéis ao livro", "CTA claro", "sem incentivo indevido a review", "sem promessa de ranking"],
        ["launch_strategy", "publishing_distribution"],
        forbidden=["pedir avaliação positiva em troca de benefício", "afirmar que reviews garantem ranking"],
    ),
    "cover_specialist": _p(
        "cover_specialist", "capa.py", "Especialista de Capa",
        "Criar arte de capa coerente com o livro e preparar composição técnica para cada formato/plataforma.",
        ["cover concept", "thumbnail readability", "visual hierarchy", "character identity", "genre fit", "back cover breathing room", "print wrap"],
        ["arte sem texto gerado pela IA", "foco reconhecível em thumbnail", "Master separado da tipografia", "wrap calculado"],
        ["cover_master", "print_preflight", "bestseller_readiness"],
    ),
    "diagrammer": _p(
        "diagrammer", "diagramador.py", "Diagramador",
        "Transformar conteúdo aprovado em sequência editorial coerente e tecnicamente preparada.",
        ["page sequencing", "text-image alternation", "front matter", "safe areas", "readability", "print structure"],
        ["ordem reproduzível", "sem conteúdo órfão", "layout compatível com preflight"],
        ["print_preflight", "quality_guardian"], execution="deterministic",
    ),
    "dedication": _p(
        "dedication", "dedicatoria.py", "Dedicatória",
        "Criar dedicatória curta, respeitosa e fiel às relações fornecidas, sem inventar biografia.",
        ["escrita afetiva", "tom infantil/familiar", "personalização", "privacidade", "não-invenção"],
        ["somente pessoas fornecidas", "relações respeitadas", "texto proporcional ao livro"],
        ["diagrammer"],
    ),
    "translator_localizer": _p(
        "translator_localizer", "tradutor.py", "Tradutor & Localizador",
        "Localizar o livro para idioma e mercado preservando significado, idade, voz, onomatopeias e Bible Guard.",
        ["translation", "localization", "child language", "locale variants", "onomatopoeia localization", "glossary consistency", "cultural sensitivity", "Bible Guard"],
        ["nenhuma omissão/invenção", "nomes protegidos", "naturalidade infantil", "mercado explícito", "versículo protegido"],
        ["linguistic_reviewer", "audiobook_director"],
        forbidden=["traduzir texto bíblico livremente"],
    ),
    "audiobook_director": _p(
        "audiobook_director", "audiobook.py", "Diretor de Audiobook",
        "Transformar texto aprovado em direção de performance sem reescrever a obra.",
        ["read-aloud direction", "pacing", "pause design", "emotion", "pronunciation planning", "character voices", "TTS portability"],
        ["texto semanticamente idêntico", "pausas intencionais", "emoção coerente", "Bible Guard preservado"],
        ["narrator", "audio_qa"],
    ),
    "narrator": _p(
        "narrator", "audiobook.py", "Narrador/TTS",
        "Renderizar o roteiro aprovado em áudio versionado e verificável.",
        ["TTS rendering", "segment naming", "pronunciation execution", "version preservation", "audio file integrity"],
        ["segmentos rastreáveis", "nenhuma substituição silenciosa", "mix exige escuta humana"],
        ["audio_qa", "quality_guardian"], execution="tool",
    ),
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
    return list(MODULE_TO_ROLES.get(Path(module_name).name, []))


def skill_contract(role_id: str, *, compact: bool = False) -> str:
    p = get_agent_profile(role_id)
    if compact:
        return (
            f"\n[FAITHBLOOM SKILL CONTRACT: {p['name']}]\n"
            f"Missão: {p['mission']}\n"
            f"Skills obrigatórias: {', '.join(p['skills'])}.\n"
            f"Critérios: {'; '.join(p['quality_criteria'])}.\n"
            f"Limites: {'; '.join(p['forbidden'])}.\n"
        )
    return (
        f"\n\n=== FAITHBLOOM SKILL CONTRACT · {p['name']} ===\n"
        f"MISSÃO: {p['mission']}\n"
        f"SKILLS OBRIGATÓRIAS: {', '.join(p['skills'])}.\n"
        f"QUALITY CRITERIA: {'; '.join(p['quality_criteria'])}.\n"
        f"NÃO FAÇA: {'; '.join(p['forbidden'])}.\n"
        f"HANDOFFS ESPERADOS: {', '.join(p['required_handoffs']) or 'nenhum'}.\n"
        "Ao responder, não declare que critérios foram validados se você não recebeu evidência suficiente.\n"
    )


def validate_registry() -> dict:
    errors = []
    modules = {}
    required = {"role_id", "module", "name", "mission", "skills", "quality_criteria", "required_handoffs", "forbidden", "evidence_requirements", "execution"}
    for rid, p in AGENT_PROFILES.items():
        missing = sorted(required - set(p))
        if missing:
            errors.append(f"{rid}: campos ausentes {missing}")
        if p.get("role_id") != rid:
            errors.append(f"{rid}: role_id divergente")
        if len(p.get("skills") or []) < 3:
            errors.append(f"{rid}: skills insuficientes")
        if len(p.get("quality_criteria") or []) < 2:
            errors.append(f"{rid}: critérios insuficientes")
        modules.setdefault(p.get("module"), 0); modules[p.get("module")] += 1
        module_path = Path(__file__).resolve().parent / "agents" / str(p.get("module") or "")
        if not module_path.exists():
            errors.append(f"{rid}: módulo {p.get('module')} não existe")
        else:
            source = module_path.read_text(encoding="utf-8", errors="ignore")
            if rid not in source:
                errors.append(f"{rid}: papel não declarado no módulo {p.get('module')}")
    return {
        "schema": SCHEMA,
        "ok": not errors,
        "role_count": len(AGENT_PROFILES),
        "module_count": len(modules),
        "errors": errors,
        "modules": modules,
    }


def export_registry_json(path: str | Path) -> str:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"schema": SCHEMA, "profiles": all_agent_profiles()}, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(p)
