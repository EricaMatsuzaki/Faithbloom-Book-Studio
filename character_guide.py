"""FaithBloom — Character Guide, Looks, Scene Director e Prompt Livre.

Camada de criação visual sobre Character Universe + Asset Library.
Princípios:
- Character DNA/Identity Lock nunca é alterado silenciosamente.
- figurino, acessórios, pose, emoção, cenário e estação são variáveis controladas;
- psicologia das cores atua no ambiente/iluminação, não recolore identidade canônica;
- toda geração nasce como candidata; Master exige promoção humana explícita;
- assets aprovados continuam sendo o MESMO asset, sem cópia;
- versões derivadas preservam parent_asset_id/version_group quando há asset-base.
"""
from __future__ import annotations

import os
import time
from copy import deepcopy
from typing import Any

from armazenamento import salvar_na_galeria
from asset_library import create_version, get_asset, get_asset_by_uri, update_asset
from character_universe import (
    atualizar_personagem_oficial,
    carregar_personagem_oficial,
    criar_personagem_oficial,
    normalizar_dna,
    personagem_para_prompt,
)
from openrouter_client import chamar_llm, gerar_imagem
from storage_backend import is_storage_uri, materializar, persistir_arquivo

GUIDE_VERSION = 1
TEXT_POLICY = "NO_GENERATED_TEXT"
VARIATION_STATUS = "VARIATION_CANDIDATE"
MASTER_STATUS = "MASTER_CANDIDATE"

USAGE_LABELS = {
    "story": "📖 História",
    "coloring": "🖍️ Colorir",
    "activity": "🧩 Atividades",
    "cover": "📕 Capa",
    "marketing": "📣 Marketing",
    "printable": "🖨️ Printable",
}

USAGE_CONTEXT_FALLBACK = {"marketing": "cover", "printable": "activity"}

NO_GENERATED_TEXT_INSTRUCTION = (
    "TEXT POLICY: NO_GENERATED_TEXT. Generate artwork with zero text, letters, words, titles, subtitles, logos, "
    "captions, speech bubbles, watermarks, or readable/pseudo-readable decorative typography. REFERENCE IMAGES MAY "
    "CONTAIN TYPOGRAPHY OR BOOK TITLES. Use them ONLY for character/style/visual identity. DO NOT copy, imitate, "
    "reproduce or invent any letters, words, titles, logos or typography visible in reference images."
)


def _now() -> int:
    return int(time.time())


def character_identity_summary(character: dict) -> dict:
    dna = normalizar_dna(character.get("dna"))
    locked = dna.get("campos_bloqueados") or {}
    if not locked and dna.get("caracteristicas_bloqueadas"):
        locked = {"descricao": dna.get("caracteristicas_bloqueadas")}
    controlled = list(dna.get("variaveis_permitidas") or [])
    scene_free = [x for x in ("cenario", "acao", "pose", "emocao", "expressao", "iluminacao") if x in controlled or x == "iluminacao"]
    return {
        "descricao": dna.get("descricao_master") or dna.get("caracteristicas_bloqueadas") or "",
        "locked": locked,
        "controlled": controlled,
        "scene_free": scene_free,
    }


def list_looks(character: dict) -> list[dict]:
    return [deepcopy(x) for x in ((character.get("metadata") or {}).get("looks") or []) if isinstance(x, dict)]


def save_look(pid: str, name: str, *, figurino: str = "", acessorios_temporarios: str = "", estacao: str = "", festividade: str = "", emocao: str = "", cenario: str = "", observacoes: str = "", usos: list[str] | None = None) -> dict:
    character = carregar_personagem_oficial(pid)
    if not character:
        raise KeyError(pid)
    name = str(name or "").strip()
    if not name:
        raise ValueError("Nome do Look é obrigatório.")
    meta = deepcopy(character.get("metadata") or {})
    looks = list(meta.get("looks") or [])
    now = _now()
    payload = {
        "id": "", "nome": name, "figurino": figurino.strip(),
        "acessorios_temporarios": acessorios_temporarios.strip(), "estacao": estacao.strip(),
        "festividade": festividade.strip(), "emocao": emocao.strip(), "cenario": cenario.strip(),
        "observacoes": observacoes.strip(), "usos": sorted({x for x in (usos or []) if x}),
        "atualizado_em": now,
    }
    existing = next((x for x in looks if str(x.get("nome", "")).strip().lower() == name.lower()), None)
    if existing:
        payload["id"] = existing.get("id") or f"look-{now}"
        payload["criado_em"] = existing.get("criado_em") or now
        looks[looks.index(existing)] = payload
    else:
        payload["id"] = f"look-{pid[:8]}-{now}"
        payload["criado_em"] = now
        looks.append(payload)
    meta["looks"] = looks
    atualizar_personagem_oficial(pid, {"metadata": meta})
    return payload


def delete_look(pid: str, look_id: str) -> bool:
    character = carregar_personagem_oficial(pid)
    if not character:
        raise KeyError(pid)
    meta = deepcopy(character.get("metadata") or {})
    before = list(meta.get("looks") or [])
    after = [x for x in before if x.get("id") != look_id]
    if len(after) == len(before):
        return False
    meta["looks"] = after
    atualizar_personagem_oficial(pid, {"metadata": meta})
    return True


def _materialize_if_possible(value: str) -> str:
    if not value:
        return ""
    if os.path.exists(value):
        return value
    if is_storage_uri(value):
        try:
            return materializar(value)
        except Exception:
            return ""
    return ""


def _reference_path_and_metadata(ref: dict | str) -> tuple[str, dict]:
    if isinstance(ref, str):
        value, ref_meta, aid = ref, {}, ""
    else:
        ref_meta = dict(ref.get("metadata") or {})
        aid = str(ref_meta.get("asset_library_id") or ref.get("asset_library_id") or "")
        value = str(ref.get("asset") or ref.get("storage_uri") or ref.get("caminho_arquivo") or "")
    asset = get_asset(aid) if aid else get_asset_by_uri(value)
    meta = {**((asset or {}).get("metadata") or {}), **ref_meta}
    if asset:
        value = str(asset.get("caminho_arquivo") or value)
        meta.setdefault("tipo", asset.get("tipo", ""))
        meta.setdefault("asset_role", (asset.get("metadata") or {}).get("asset_role", ""))
    return _materialize_if_possible(value), meta


def _safe_identity_reference(meta: dict) -> bool:
    explicit = bool(meta.get("allow_identity_reference")) or meta.get("reference_purpose") == "identity_explicit"
    text_bearing = bool(meta.get("contains_text"))
    cover_like = meta.get("asset_role") == "cover_art" or meta.get("usage") == "cover" or meta.get("tipo") in {"cover", "capa"}
    return explicit or not (text_bearing or cover_like)


def character_reference_paths(character: dict, limit: int = 8) -> list[str]:
    """Prioriza referências limpas e nunca usa capa/texto sem opt-in explícito."""
    candidates: list[tuple[str, dict]] = []
    if character.get("color_master"):
        candidates.append(_reference_path_and_metadata(str(character["color_master"])))
    for ref in character.get("reference_pack") or []:
        aid = (ref.get("metadata") or {}).get("asset_library_id") or ref.get("asset_library_id")
        candidates.append(_reference_path_and_metadata({**ref, "asset_library_id": aid or ref.get("asset_library_id")}))
    out: list[str] = []
    for path, meta in candidates:
        if path and _safe_identity_reference(meta) and path not in out:
            out.append(path)
        if len(out) >= limit:
            break
    return out


def _context_for(character: dict, usage: str) -> str:
    allowed = list((character.get("metadata") or {}).get("usos_permitidos") or [])
    if usage in allowed:
        return usage
    fallback = USAGE_CONTEXT_FALLBACK.get(usage)
    if fallback and fallback in allowed:
        return fallback
    if "story" in allowed:
        return "story"
    return allowed[0] if allowed else "story"


def _identity_block(character: dict, variables: dict | None, usage: str) -> str:
    return personagem_para_prompt(character, modo="color", variaveis=variables or {}, contexto=_context_for(character, usage))


def artwork_text_policy(usage: str = "story", reserve_title_space: str = "none") -> str:
    policy = NO_GENERATED_TEXT_INSTRUCTION
    if usage == "cover":
        position = reserve_title_space if reserve_title_space in {"top", "center", "bottom"} else "none"
        policy += f" COVER ART ONLY; never render the book title. reserve_title_space={position}."
        if position != "none":
            policy += f" Leave intentional negative space at the {position} for later editorial typography."
    return policy


def build_character_free_prompt(character: dict, request: str, *, usage: str = "story", variables: dict | None = None, look: dict | None = None, neutral_base: bool = False, reserve_title_space: str = "none") -> str:
    request = str(request or "").strip()
    merged = {k: v for k, v in (look or {}).items() if k in {"figurino", "acessorios_temporarios", "estacao", "festividade", "emocao", "cenario"} and v not in (None, "")}
    merged.update({k: v for k, v in (variables or {}).items() if v not in (None, "")})
    identity = _identity_block(character, merged, usage)
    color_rule = (
        "PSICOLOGIA DAS CORES E EMOÇÕES: use cor, contraste, saturação e iluminação para apoiar a emoção da cena, "
        "MAS nunca altere as cores canônicas do rosto, olhos, pele/pelagem, cabelo ou marcas permanentes do Character DNA."
    )
    if neutral_base:
        direction = (
            "Crie uma BASE OFICIAL NEUTRA candidata: personagem sozinho, corpo inteiro bem enquadrado, pose natural e amigável, "
            "expressão-base, fundo neutro claro e limpo, iluminação de estúdio suave, sem cenário narrativo, sem texto, sem logotipo "
            "e sem acessórios temporários não solicitados. Esta saída é apenas MASTER_CANDIDATE; não é Master até aprovação/promoção humana."
        )
    else:
        direction = (
            f"PEDIDO LIVRE DA AUTORA: {request or 'Crie uma variação coerente e reutilizável.'} "
            "Altere somente o que foi explicitamente pedido/autorizado. Sem texto, letras, balões ou marcas d'água."
        )
    cover_rule = ""
    if usage == "cover":
        position = reserve_title_space if reserve_title_space in {"top", "center", "bottom"} else "none"
        cover_rule = (
            f"\nCAPA: gere somente COVER ART, sem título. reserve_title_space={position}. "
            + (f"Reserve espaço negativo na região {position} para tipografia editorial aplicada depois." if position != "none" else "Não renderize tipografia; o título será aplicado pelo pipeline editorial.")
        )
    return f"{identity}\n{color_rule}\n{direction}\n{artwork_text_policy(usage, reserve_title_space)}\nUso pretendido: {USAGE_LABELS.get(usage, usage)}.{cover_rule}"


def build_neutral_base_prompt(character: dict) -> str:
    return build_character_free_prompt(character, "", usage="story", neutral_base=True)


def _normalize_scene_ideas(raw: Any, count: int = 3) -> list[dict]:
    if isinstance(raw, dict):
        ideas = raw.get("ideas") or raw.get("ideias") or raw.get("scenes") or raw.get("cenas") or []
    elif isinstance(raw, list):
        ideas = raw
    else:
        ideas = []
    normalized = []
    for idx, idea in enumerate(ideas):
        if not isinstance(idea, dict):
            continue
        poses = idea.get("poses") or idea.get("pose") or {}
        if isinstance(poses, str):
            poses = {"geral": poses}
        normalized.append({
            "id": str(idea.get("id") or chr(65 + idx)),
            "titulo": str(idea.get("titulo") or idea.get("title") or f"Ideia {idx + 1}"),
            "cenario": str(idea.get("cenario") or idea.get("setting") or ""),
            "acao": str(idea.get("acao") or idea.get("action") or ""),
            "poses": poses if isinstance(poses, dict) else {},
            "emocao": str(idea.get("emocao") or idea.get("emotion") or ""),
            "psicologia_cores": str(idea.get("psicologia_cores") or idea.get("colors") or ""),
            "iluminacao": str(idea.get("iluminacao") or idea.get("lighting") or ""),
            "camera": str(idea.get("camera") or idea.get("enquadramento") or ""),
            "figurino_acessorios": str(idea.get("figurino_acessorios") or idea.get("wardrobe") or ""),
            "objetos": str(idea.get("objetos") or idea.get("props") or ""),
            "por_que_funciona": str(idea.get("por_que_funciona") or idea.get("why") or ""),
        })
    if len(normalized) < count:
        raise ValueError("O Scene Director não retornou 3 ideias completas. Tente novamente.")
    return normalized[:count]


def suggest_scene_concepts(story_excerpt: str, characters: list[dict], count: int = 3) -> list[dict]:
    excerpt = str(story_excerpt or "").strip()
    if not excerpt:
        raise ValueError("Cole um trecho da história primeiro.")
    if not characters:
        raise ValueError("Selecione ao menos um personagem oficial.")
    char_context = []
    for p in characters:
        summary = character_identity_summary(p)
        char_context.append({"nome": p.get("nome"), "dna": summary["descricao"], "locked": summary["locked"], "variaveis_permitidas": summary["controlled"]})
    system = (
        "Você é o Scene Director do FaithBloom Book Studio, especialista em direção de arte para livros infantis. "
        "Receba um trecho de história e personagens oficiais. Proponha exatamente 3 direções visuais DISTINTAS. Não gere imagens. "
        "Não altere o Character DNA. A psicologia das cores deve reforçar emoção, mas nunca recolorir identidade canônica. "
        "As ideias devem ser práticas para ilustração editorial, com composição clara, movimento, leitura visual infantil e reaproveitamento futuro. "
        f"Responda apenas JSON válido. Toda direção deve respeitar {TEXT_POLICY}: nenhuma tipografia na arte."
    )
    instruction = {
        "trecho": excerpt,
        "personagens": char_context,
        "quantidade": count,
        "saida_obrigatoria": {"ideas": [{
            "id": "A", "titulo": "nome curto", "cenario": "descrição do ambiente", "acao": "ação principal",
            "poses": {"Nome do personagem": "pose e linguagem corporal"}, "emocao": "emoção dominante",
            "psicologia_cores": "paleta/contraste e função emocional", "iluminacao": "direção da luz",
            "camera": "enquadramento/ângulo", "figurino_acessorios": "mudanças coerentes com tema/estação",
            "objetos": "props essenciais", "por_que_funciona": "1 frase"
        }]}
    }
    raw = chamar_llm(system, str(instruction))
    return _normalize_scene_ideas(raw, count=count)


def compose_scene_prompt(concept: dict, characters: list[dict], *, usage: str = "story", adjustment: str = "") -> str:
    if not characters:
        raise ValueError("Selecione ao menos um personagem.")
    blocks = []
    for p in characters:
        name = p.get("nome", "Personagem")
        variables = {"pose": (concept.get("poses") or {}).get(name, ""), "acao": concept.get("acao", ""), "emocao": concept.get("emocao", ""), "cenario": concept.get("cenario", "")}
        blocks.append(_identity_block(p, variables, usage))
    return "\n".join(blocks) + (
        "\nDIREÇÃO DE CENA APROVADA PELA AUTORA:\n"
        f"Cenário: {concept.get('cenario','')}\nAção: {concept.get('acao','')}\nPoses: {concept.get('poses',{})}\n"
        f"Emoção: {concept.get('emocao','')}\nPsicologia das cores: {concept.get('psicologia_cores','')}\n"
        f"Iluminação: {concept.get('iluminacao','')}\nCâmera/enquadramento: {concept.get('camera','')}\n"
        f"Figurino/acessórios: {concept.get('figurino_acessorios','')}\nObjetos essenciais: {concept.get('objetos','')}\n"
        f"Ajuste adicional da autora: {adjustment.strip() or 'nenhum'}\n"
        "REGRAS: preserve rigorosamente a identidade de TODOS os personagens. A psicologia das cores atua no ambiente/iluminação "
        f"e não altera olhos, cabelo, pele/pelagem ou marcas canônicas. {artwork_text_policy(usage)}"
    )


def create_character_guide(*, collection: str, name: str, locked_identity: dict, description: str = "", controlled_variables: dict | None = None, usages: list[str] | None = None) -> dict:
    """Cria a entidade canônica no Character Universe (assets não são personagens)."""
    dna = {
        "descricao_master": str(description or "").strip(),
        "campos_bloqueados": {k: str(v).strip() for k, v in locked_identity.items() if str(v).strip()},
        "variaveis_permitidas": list((controlled_variables or {}).keys()) or ["pose", "acao", "expressao", "emocao", "figurino", "acessorios_temporarios", "cenario", "estacao", "festividade"],
    }
    return criar_personagem_oficial(collection.strip(), name.strip(), dna, metadata={"usos_permitidos": usages or list(USAGE_LABELS)})


def update_character_guide(character_id: str, *, collection: str, name: str, locked_identity: dict, description: str = "", controlled_variables: dict | None = None, usages: list[str] | None = None) -> dict:
    current = carregar_personagem_oficial(character_id)
    if not current:
        raise KeyError(character_id)
    dna = normalizar_dna(current.get("dna"))
    dna.update({
        "descricao_master": str(description or "").strip(),
        "campos_bloqueados": {k: str(v).strip() for k, v in locked_identity.items() if str(v).strip()},
        "variaveis_permitidas": list((controlled_variables or {}).keys()) or dna.get("variaveis_permitidas", []),
    })
    meta = deepcopy(current.get("metadata") or {})
    meta["usos_permitidos"] = usages or meta.get("usos_permitidos", list(USAGE_LABELS))
    return atualizar_personagem_oficial(character_id, {"colecao": collection.strip(), "nome": name.strip(), "dna": dna, "metadata": meta})


def select_gallery_asset(state: Any, asset_id: str) -> str:
    """Seleciona o detalhe inline sem exigir navegação entre páginas."""
    state["gallery_open_asset_id"] = asset_id
    return asset_id


def _persist_generated(path: str, *, name: str, characters: list[dict], prompt: str, visual_status: str, usage: str, label: str, origin: str, base_asset_id: str = "", metadata: dict | None = None) -> dict:
    names = [str(p.get("nome", "")).strip() for p in characters if p.get("nome")]
    collection = next((str(p.get("colecao", "")).strip() for p in characters if p.get("colecao")), "")
    meta = {
        "personagem": names[0] if len(names) == 1 else ("Cena multi-personagem" if names else ""),
        "personagens": names, "colecao": collection, "origem": origin, "prompt": prompt,
        "visual_status": visual_status, "usage": usage, "usos": [usage], "scope": "reusable",
        "asset_role": "cover_art" if usage == "cover" else ("scene" if len(names) != 1 else "character_reference"),
        "contains_text": False, "text_policy": TEXT_POLICY, "guide_version": GUIDE_VERSION, **(metadata or {}),
    }
    tags = [x for x in [*names, collection, visual_status, usage, "character-guide"] if x]
    base = get_asset(base_asset_id, materialize_file=False) if base_asset_id else None
    if base:
        uri = persistir_arquivo(path, "assets/character_guide")
        item = create_version(base_asset_id, storage_uri_value=uri, name=name, version_label=label, metadata=meta)
        return update_asset(item["id"], nome=name, tags=sorted(set([*item.get("tags", []), *tags])), approved=False, visual_status=visual_status, metadata=meta)
    item = salvar_na_galeria(path, name, "personagem" if len(names) == 1 else "cena", tags, meta)
    return update_asset(item["id"], approved=False, visual_status=visual_status, version_label=label, metadata=meta) or item


def generate_character_variations(character: dict, prompt: str, *, quantity: int = 1, usage: str = "story", base_asset_id: str = "", neutral_base: bool = False, metadata: dict | None = None) -> list[dict]:
    quantity = 3 if int(quantity) == 3 else 1
    base_asset = get_asset(base_asset_id) if base_asset_id else None
    base_path = (base_asset or {}).get("caminho_arquivo") or ""
    refs = [x for x in character_reference_paths(character) if x != base_path]
    results = []
    for label in ["A", "B", "C"][:quantity]:
        p = prompt + f"\n{artwork_text_policy(usage)}\nVariação {label}: composição independente, mantendo o mesmo Character DNA."
        generated = gerar_imagem(p, imagem_base=base_path or None, imagens_referencia=refs)
        results.append(_persist_generated(
            generated, name=f"{character.get('nome','Personagem')} — {'Base neutra' if neutral_base else 'Variação'} {label}",
            characters=[character], prompt=p, visual_status=MASTER_STATUS if neutral_base else VARIATION_STATUS,
            usage=usage, label=label, origin="character_guide_neutral_base" if neutral_base else "character_guide_free_prompt",
            base_asset_id=base_asset_id, metadata=metadata,
        ))
    return results


def generate_scene_assets(concept: dict, characters: list[dict], *, quantity: int = 1, usage: str = "story", adjustment: str = "", base_asset_id: str = "", story_excerpt: str = "") -> list[dict]:
    quantity = 3 if int(quantity) == 3 else 1
    prompt = compose_scene_prompt(concept, characters, usage=usage, adjustment=adjustment)
    base_asset = get_asset(base_asset_id) if base_asset_id else None
    base_path = (base_asset or {}).get("caminho_arquivo") or ""
    refs: list[str] = []
    for character in characters:
        for path in character_reference_paths(character):
            if path and path != base_path and path not in refs:
                refs.append(path)
    results = []
    for label in ["A", "B", "C"][:quantity]:
        p = prompt + f"\nResultado {label}: interpretação independente da mesma direção visual."
        generated = gerar_imagem(p, imagem_base=base_path or None, imagens_referencia=refs)
        results.append(_persist_generated(
            generated, name=f"Cena — {concept.get('titulo','Direção')} — {label}", characters=characters,
            prompt=p, visual_status=VARIATION_STATUS, usage=usage, label=label, origin="scene_director",
            base_asset_id=base_asset_id, metadata={"story_excerpt": story_excerpt, "scene_concept": concept,
            "emocao": concept.get("emocao", ""), "cenario": concept.get("cenario", ""), "psicologia_cores": concept.get("psicologia_cores", "")},
        ))
    return results


def approve_asset_as_variation(asset_id: str) -> dict:
    """Aprova IN PLACE. Não duplica arquivo e nunca promove Master."""
    asset = get_asset(asset_id, materialize_file=False)
    if not asset:
        raise KeyError(asset_id)
    if asset.get("visual_status") == "APPROVED_VARIATION":
        return asset
    if asset.get("visual_status") not in {VARIATION_STATUS, MASTER_STATUS, "RESTORATION_CANDIDATE"}:
        raise ValueError("Somente uma candidata visual pode ser aprovada como variação.")
    return update_asset(asset_id, approved=True, visual_status="APPROVED_VARIATION", metadata={"visual_status": "APPROVED_VARIATION", "approved_at": _now(), "approval": "human"})
