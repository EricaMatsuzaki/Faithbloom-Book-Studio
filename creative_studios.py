"""FaithBloom Creative Studios — arquitetura multimídia extensível.

Esta camada registra capacidades futuras de animação, vídeo, música e cofre de
ideias sem acoplar o produto a um provedor específico. Ela não gera mídia por
si só: define contratos, especialistas, checkpoints e reaproveitamento dos
Masters já aprovados no FaithBloom.
"""
from __future__ import annotations

from copy import deepcopy

SCHEMA = "faithbloom.creative-studios.v1"
STATUS_FOUNDATION = "foundation_ready"
STATUS_PROVIDER_PENDING = "provider_integration_pending"

SHARED_GUARDRAILS = [
    "preservar Character Master, Character DNA, Color Master e Reference Pack aprovados",
    "preservar World/Location Masters e Style Master aprovados quando aplicáveis",
    "não promover candidata, frame, voz, música ou asset a Master automaticamente",
    "exigir aprovação humana antes de lotes caros ou publicação/distribuição",
    "aplicar Cost Gate antes de operações pagas",
    "registrar origem e versão dos assets derivados",
    "não copiar personagens, cenas distintivas, letras, melodias, vozes ou identidade visual de terceiros",
]

STUDIOS = {
    "idea_vault": {
        "name": "💡 Idea Vault",
        "status": STATUS_FOUNDATION,
        "mission": "Capturar uma inspiração rapidamente e preservá-la antes de decidir o formato final.",
        "specialists": ["idea_curator", "format_suggester", "originality_guard"],
        "inputs": ["texto", "tema", "emoção", "versículo/referência", "imagem", "documento", "nota de voz futura"],
        "outputs": ["idea_master", "possíveis formatos", "próximos passos"],
        "approval_gates": ["nenhuma ideia é descartada ou transformada em produção cara sem escolha da autora"],
    },
    "animation_video": {
        "name": "🎬 Animation & Video Studio",
        "status": STATUS_PROVIDER_PENDING,
        "mission": "Adaptar histórias e ideias aprovadas para desenhos animados, curtas e filminhos mantendo continuidade do universo.",
        "specialists": [
            "animation_director", "book_to_screen_adapter", "storyboard_director",
            "scene_director", "character_continuity_guardian", "world_scenario_director",
            "motion_animation_director", "voice_dialogue_director", "sound_effects_director",
            "color_lighting_director", "video_quality_guardian",
        ],
        "inputs": ["Book/Story Master", "idea_master", "Character Masters", "World Masters", "Style Master", "áudio aprovado"],
        "outputs": ["screenplay", "storyboard", "shot_plan", "animatic", "video_master"],
        "approval_gates": ["roteiro audiovisual", "storyboard", "personagens/cenários", "voz", "música", "render final"],
    },
    "music": {
        "name": "🎵 Music Studio",
        "status": STATUS_PROVIDER_PENDING,
        "mission": "Criar canções e trilhas originais para livros, animações, personagens e universos FaithBloom.",
        "specialists": [
            "composer", "lyricist", "arranger", "childrens_music_director",
            "christian_music_director", "film_score_composer", "singing_voice_director",
            "mix_master_engineer", "music_originality_guard", "music_quality_guardian",
        ],
        "inputs": ["tema", "história", "Heart Arc", "personagens", "público", "briefing musical"],
        "outputs": ["music_brief", "lyrics_draft", "composition_plan", "song_master", "instrumental_score"],
        "approval_gates": ["conceito", "letra quando houver", "demo", "voz/interpretação", "mix/master final"],
    },
}

DERIVATIVE_PATHS = {
    "book_to_animation": ["Book Master", "screenplay", "storyboard", "animatic", "animation", "video QA", "Video Master"],
    "book_to_song": ["Book/Story Master", "music brief", "composition", "demo", "music QA", "Music Master"],
    "idea_to_universe": ["Idea Vault", "idea_master", "format proposal", "author choice", "project pipeline"],
}


def get_studio(studio_id: str) -> dict:
    if studio_id not in STUDIOS:
        raise KeyError(f"Creative Studio desconhecido: {studio_id}")
    out = deepcopy(STUDIOS[studio_id])
    out["id"] = studio_id
    out["schema"] = SCHEMA
    out["shared_guardrails"] = list(SHARED_GUARDRAILS)
    return out


def list_studios() -> list[dict]:
    return [get_studio(studio_id) for studio_id in STUDIOS]


def build_derivative_plan(path_id: str, *, source_id: str, title: str = "", approved_masters: dict | None = None) -> dict:
    if path_id not in DERIVATIVE_PATHS:
        raise KeyError(f"Fluxo derivado desconhecido: {path_id}")
    return {
        "schema": SCHEMA,
        "path_id": path_id,
        "source_id": source_id,
        "title": title,
        "stages": list(DERIVATIVE_PATHS[path_id]),
        "approved_masters": deepcopy(approved_masters or {}),
        "auto_publish": False,
        "auto_promote_master": False,
        "requires_human_approval": True,
        "provider_bound": False,
        "guardrails": list(SHARED_GUARDRAILS),
    }


def provider_readiness(studio_id: str) -> dict:
    studio = get_studio(studio_id)
    ready = studio["status"] != STATUS_PROVIDER_PENDING
    return {
        "studio_id": studio_id,
        "architecture_ready": True,
        "provider_connected": ready if studio_id == "idea_vault" else False,
        "can_generate_final_media": False if studio_id in {"animation_video", "music"} else None,
        "status": studio["status"],
    }
