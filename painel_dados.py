"""Dados e recomendações locais do painel FaithBloom, sem dependências de UI.

As etapas refletem o estado salvo. Uma imagem disponível não conta como
aprovada, e um pacote pronto não conta como uma publicação na loja.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
import re
import unicodedata


ACTIONS = [
    {"key": "create", "title": "Criar um livro", "description": "Do zero, com a equipe certa para a sua história.", "route": "pages/39_✍️_Historia_4_Estilos.py", "color": "pink", "icon": "book"},
    {"key": "continue", "title": "Continuar / Atualizar", "description": "Melhorar um livro existente ou retomar de onde parou.", "route": "pages/16_🩺_Book_Doctor.py", "color": "blue", "icon": "refresh"},
    {"key": "characters", "title": "Personagens", "description": "Criar, editar e gerenciar os personagens da sua história.", "route": "pages/14_👥_Character_Universe.py", "color": "mint", "icon": "people"},
    {"key": "images", "title": "Imagens & ilustrações", "description": "Organizar imagens, referências e versões das suas ilustrações.", "route": "pages/31_🖼️_Asset_Library_Media_Manager.py", "color": "yellow", "icon": "image"},
    {"key": "text", "title": "Texto & revisão", "description": "Escrever, revisar e ajustar com apoio da IA.", "route": "pages/5_🔍_Analisar_Livro.py", "color": "lilac", "icon": "text"},
    {"key": "publish", "title": "Publicar", "description": "Preparar formatos, pacotes e distribuição para suas plataformas.", "route": "pages/26_🌐_Publishing_Distribution_Center.py", "color": "pink", "icon": "rocket"},
]

NAV_GROUPS = [
    {"label": "CRIAR & TRANSFORMAR", "items": deepcopy(ACTIONS)},
    {"label": "UNIVERSO & BIBLIOTECA", "items": [
        {"title": "Meus projetos", "route": "pages/53_📁_Meus_Projetos.py", "icon": "📁"},
        {"title": "Biblioteca editorial", "route": "pages/15_📚_Biblioteca_Editorial.py", "icon": "📚"},
        {"title": "Universo de personagens", "route": "pages/14_👥_Character_Universe.py", "icon": "👥"},
        {"title": "Galeria de imagens", "route": "pages/31_🖼️_Asset_Library_Media_Manager.py", "icon": "🖼️"},
    ]},
    {"label": "QUALIDADE & PUBLICAÇÃO", "items": [
        {"title": "Revisão final", "route": "pages/25_🛡️_Quality_Guardian.py", "icon": "🛡️"},
        {"title": "Formatos de publicação", "route": "pages/22_📐_Publishing_Platform_Engine.py", "icon": "📐"},
        {"title": "Preparar publicação", "route": "pages/26_🌐_Publishing_Distribution_Center.py", "icon": "🚀"},
    ]},
    {"label": "FERRAMENTAS AVANÇADAS", "items": [
        {"title": "Livros de colorir", "route": "pages/3_🖍️_Livros_de_Colorir.py", "icon": "🖍️"},
        {"title": "Atividades", "route": "pages/23_🧩_Activity_Book_Studio.py", "icon": "🧩"},
        {"title": "Tradução", "route": "pages/21_Translation_Localization_Studio.py", "icon": "🌍"},
        {"title": "Audiobook", "route": "pages/24_🎧_Audiobook_Studio.py", "icon": "🎧"},
        {"title": "Perfis & preferências", "route": "pages/34_🏠_Perfis_e_Dashboard.py", "icon": "⚙️"},
    ]},
]

_KEYWORDS = {
    "create": ("criar", "novo", "nova", "livro", "historia", "comecar", "zero"),
    "continue": ("continuar", "retomar", "atualizar", "existente", "projeto salvo", "parou"),
    "characters": ("personagem", "personagens", "mel", "aparencia", "dna", "referencia", "figurino"),
    "images": ("imagem", "imagens", "ilustracao", "ilustracoes", "restaurar", "desenho", "arte", "foto", "capa"),
    "text": ("texto", "revisao", "revisar", "ortografia", "escrever", "corrigir", "analisar", "sinopse"),
    "publish": ("publicar", "publicacao", "kdp", "amazon", "distribuicao", "diagramar", "diagramacao", "pdf", "epub", "formato", "formatar"),
}


def normalize_text(value) -> str:
    """Normaliza acentos e espaços sem alterar os dados originais."""
    text = unicodedata.normalize("NFKD", str(value or "").casefold())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return " ".join(re.findall(r"\w+", text, flags=re.UNICODE))


def _searchable(value) -> str:
    if isinstance(value, Mapping):
        return " ".join(f"{normalize_text(k)} {_searchable(v)}" for k, v in value.items())
    if isinstance(value, (list, tuple)):
        return " ".join(_searchable(item) for item in value)
    return normalize_text(value)


def _matches(text: str, query: str) -> bool:
    return all(word in text for word in normalize_text(query).split())


def filter_projects(projects, query: str) -> list[dict]:
    """Busca título, coleção, tema e personagens; preserva ordem e dados."""
    fields = ("titulo", "title", "colecao", "collection", "tema_geral", "tema", "aprendizado_cristao", "sinopse_poetica", "personagens", "personagens_nomes", "character_names")
    return [project for project in (projects or [])
            if isinstance(project, Mapping)
            and _matches(" ".join(_searchable(project.get(field)) for field in fields), query)]


def filter_actions(query: str) -> list[dict]:
    """Busca os atalhos pela descrição e pelo vocabulário usado nas tarefas."""
    return [deepcopy(action) for action in ACTIONS if _matches(
        normalize_text(f"{action['title']} {action['description']} {' '.join(_KEYWORDS[action['key']])}"), query)]


def suggest_actions(message: str) -> list[dict]:
    """Sugere até três ferramentas por palavras-chave, sem chamada de IA.

    A UI deve apresentar os resultados como atalhos sugeridos. Esta função
    não gera conteúdo, não executa a tarefa e não modifica projetos.
    """
    words = f" {normalize_text(message)} "
    scored = []
    for index, action in enumerate(ACTIONS):
        score = sum(1 for keyword in _KEYWORDS[action["key"]] if f" {keyword} " in words)
        # 'Livro' e 'história' são contexto; pedidos específicos vêm primeiro.
        if action["key"] == "create":
            score = sum(1 if keyword in {"livro", "historia"} else 3
                        for keyword in _KEYWORDS["create"] if f" {keyword} " in words)
        else:
            score *= 3
        if score:
            scored.append((score, index, action))
    if not scored:
        return deepcopy(ACTIONS[:2])
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [deepcopy(action) for _, _, action in scored[:3]]


def _items(value) -> list[dict]:
    if isinstance(value, Mapping):
        value = list(value.values())
    if not isinstance(value, (list, tuple)):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _approved(item: dict) -> bool:
    flags = [item[key] for key in ("aprovado", "aprovada", "approved") if key in item]
    if flags:
        # Uma recusa explícita prevalece sobre um status legado desatualizado.
        return all(flag is True for flag in flags)
    return item.get("status") in {"aprovado", "aprovada", "approved"}


def _has_image(item: dict) -> bool:
    return bool(item.get("caminho_arquivo") or item.get("storage_uri"))


def _stage(label: str, complete: bool, started: bool, detail: str) -> dict:
    return {"label": label, "status": "concluido" if complete else "em_andamento" if started else "pendente", "detail": detail}


def _publication(state: dict) -> dict:
    raw_status = normalize_text(state.get("status_publicacao") or state.get("status"))
    if state.get("publicado") is True or raw_status in {"published", "publicado"}:
        return _stage("Publicação", True, True, "Publicação registrada explicitamente no projeto.")
    summary = state.get("distribution_summary") or {}
    if not isinstance(summary, Mapping):
        summary = {}
    # O Distribution Center salva este resumo após confirmação externa humana.
    total = summary.get("total", 0)
    live = summary.get("live", 0)
    total = total if isinstance(total, int) and not isinstance(total, bool) else 0
    live = live if isinstance(live, int) and not isinstance(live, bool) else 0
    blocked = summary.get("blocked", 0)
    if state.get("distribution_plan_id") and total > 0 and 0 < live <= total:
        return _stage("Publicação", live == total and blocked == 0, True,
                      f"{live}/{total} edição(ões) com publicação registrada no Distribution Center.")
    started = bool(state.get("pacote_pronto") or state.get("distribution_plan_id") or state.get("checklist_kdp") or state.get("pdf_miolo") or state.get("pdf_miolo_print_ready"))
    return _stage("Publicação", False, started,
                  "Pacote em preparação; a publicação na loja ainda não está registrada." if started else "Prepare os arquivos e registre a publicação na plataforma.")


def production_stages(state: dict | None, kind: str = "story") -> list[dict]:
    """Resume seis etapas a partir de evidências salvas, sem acessar storage.

    Não verifica a existência do arquivo na máquina: os caminhos podem ser
    URIs do storage. A conclusão visual exige arquivo e aprovação registrada.
    """
    state = state if isinstance(state, Mapping) else {}
    layout = _items(state.get("layout_paginas"))
    pdf = bool(state.get("pdf_miolo_print_ready") or state.get("pdf_miolo"))
    layout_stage = _stage("Diagramação", bool(layout and pdf), bool(layout or pdf),
                          "Layout e PDF do miolo salvos." if layout and pdf else "Exporte o PDF do miolo após montar o layout.")
    if kind in {"coloring", "colorir"}:
        pages = _items(state.get("paginas"))
        images = [page for page in pages if _has_image(page)]
        approved = [page for page in pages if _has_image(page) and _approved(page)]
        theme = bool(state.get("tema_geral"))
        configured = bool(pages) and all(page.get("nome") or page.get("cena") or page.get("prompt_livre") for page in pages)
        return [
            _stage("Tema", theme, bool(theme or state.get("titulo")), "Tema do livro de colorir definido." if theme else "Defina o tema do livro de colorir."),
            _stage("Páginas", configured, bool(pages), f"{len(pages)} página(s) planejada(s)." if pages else "Planeje as páginas do livro de colorir."),
            _stage("Line art", bool(pages) and len(approved) == len(pages), bool(images), f"{len(approved)}/{len(pages)} página(s) com imagem e aprovação registradas."),
            _stage("Revisão", bool(pages) and len(approved) == len(pages), bool(images), "Aprovação das páginas registrada." if pages and len(approved) == len(pages) else "Revise e aprove cada página de colorir."),
            layout_stage,
            _publication(state),
        ]

    scenes = _items(state.get("cenas_texto"))
    chars = _items(state.get("personagens"))
    images = _items(state.get("cenas_imagem") or state.get("ilustracoes") or state.get("imagens_cenas"))
    saved_numbers = state.get("cenas_imagem_aprovadas") or []
    approved_numbers = {str(number) for number in saved_numbers} if isinstance(saved_numbers, (list, tuple)) else set()
    approved_images = [image for image in images if _has_image(image) and
                       (_approved(image) or (not any(key in image for key in ("aprovado", "aprovada", "approved", "status")) and str(image.get("numero")) in approved_numbers))]
    approved_chars = [char for char in chars if char.get("imagem_referencia") and char.get("aparencia_aprovada") is True]
    expected_numbers = {str(scene.get("numero")) for scene in scenes if scene.get("numero") is not None}
    image_numbers = {str(image.get("numero")) for image in approved_images if image.get("numero") is not None}
    illustrations_done = bool(images) and len(approved_images) == len(images) and len(images) >= len(scenes) and (not expected_numbers or expected_numbers <= image_numbers)
    text_ready = bool(scenes) and all(str(scene.get("texto") or "").strip() for scene in scenes)
    return [
        _stage("História", text_ready, bool(scenes or state.get("sinopse_poetica") or state.get("titulo")), f"{len(scenes)} cena(s) de texto salva(s)." if scenes else "Comece a história do seu livro."),
        _stage("Personagens", bool(chars) and len(approved_chars) == len(chars), bool(chars), f"{len(approved_chars)}/{len(chars)} referência(s) com aparência aprovada."),
        _stage("Ilustrações", illustrations_done, bool(images or state.get("imagens_cenas_enviadas")), f"{len(approved_images)}/{len(images)} ilustração(ões) com imagem e aprovação registradas."),
        _stage("Revisão", text_ready and state.get("revisao_aprovada") is True, bool(scenes or state.get("notas_revisor")), "Revisão editorial aprovada." if text_ready and state.get("revisao_aprovada") is True else "Revise o texto e registre a aprovação editorial."),
        layout_stage,
        _publication(state),
    ]


def project_status(item: dict, state: dict | None = None) -> tuple[str, str]:
    """Badge do projeto; preparação e aprovação não significam publicação."""
    state = state or {}
    if _publication(state)["status"] == "concluido":
        return "Publicado", "published"
    if state.get("pacote_pronto") is True or item.get("pacote_pronto") is True:
        return "Pacote pronto", "progress"
    raw_status = normalize_text(state.get("status"))
    started = any(state.get(field) for field in ("cenas_texto", "personagens", "paginas", "cenas_imagem", "texto_final", "layout_paginas", "revisao_aprovada"))
    if started or raw_status in {"in progress", "in_progress", "em andamento", "remastering"}:
        return "Em andamento", "progress"
    return "Rascunho", "draft"


def jarvis_project_progress(state: dict | None, kind: str = "story") -> dict:
    """Mantém o contrato de progresso do Jarvis com evidências do livro ativo."""
    state = state or {}
    stages = production_stages(state, kind)
    flags = [stage["status"] == "concluido" for stage in stages]
    package_ready = state.get("pacote_pronto") is True
    if flags[5]:
        next_step, message = "follow_publication", "A publicação está registrada. Podemos acompanhar suas edições."
    elif package_ready:
        next_step, message = "publish_or_distribute", "O pacote está pronto para preparar a distribuição; a publicação na loja ainda precisa ser registrada."
    elif flags[2]:
        next_step, message = "layout_and_qa", "As imagens estão aprovadas. O próximo foco é QA, diagramação e preparação de saída."
    elif flags[3]:
        next_step, message = "visual_preflight", "A revisão está aprovada. Podemos conferir personagens, cenários e o pré-voo visual."
    elif flags[0] and flags[1]:
        next_step, message = "story_review", "Recebi a história e as referências aprovadas. O próximo checkpoint é a revisão editorial."
    elif flags[0]:
        next_step, message = "characters", "A história está salva. O próximo passo é confirmar as referências dos personagens."
    else:
        next_step, message = "story", "Ainda estamos na construção da história."
    if kind in {"coloring", "colorir"} and not package_ready and not flags[5]:
        if flags[2]:
            next_step, message = "layout_and_qa", "As páginas de colorir estão aprovadas. Vamos conferir o layout e preparar a saída."
        else:
            next_step, message = "coloring_pages", "O próximo passo é preparar, revisar e aprovar as páginas de colorir."
    return {
        "title": state.get("titulo") or "Projeto atual", "collection": state.get("colecao") or state.get("tema_geral") or "",
        "story_ready": flags[0], "characters_ready": flags[1], "visuals_ready": flags[2], "review_ready": flags[3],
        "package_ready": package_ready, "published": flags[5], "next_step": next_step, "message": message,
    }


def project_session_updates(project: dict, state: dict) -> dict:
    """Prepara somente mudanças de sessão; não gera conteúdo nem publica."""
    if not state:
        raise ValueError("Não foi possível carregar o projeto salvo.")
    kind = project.get("kind")
    path = str(project.get("storage_path") or project.get("arquivo") or "").removeprefix("fb://").strip("/")
    loaded = deepcopy(state)
    if kind == "coloring":
        loaded.setdefault("paginas", [])
        return {"state": loaded, "state_c": loaded, "etapa_c": "paginas" if loaded["paginas"] else "entrada", "caminho_salvo_c": path}
    if kind != "story":
        raise ValueError("Tipo de projeto desconhecido.")
    for field in ("cenas_texto", "cenas_imagem", "cenas_imagem_aprovadas"):
        loaded.setdefault(field, [])
    for field in ("personagens", "historico_imagens_cenas", "imagens_cenas_enviadas"):
        loaded.setdefault(field, {})
    loaded.setdefault("dedicatoria_texto", "")
    stage = "cenas" if production_stages(loaded)[1]["status"] == "concluido" and loaded["cenas_texto"] else "personagens"
    # A mesma instância mantém o progresso do Jarvis sincronizado com Retomar.
    return {"state": loaded, "state_r": loaded, "etapa_r": stage, "caminho_salvo_r": path}
