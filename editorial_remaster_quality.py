"""Quality gate do Full Editorial Remaster.

Reutiliza Restoration Studio e Quality Guardian. Antes do QA final, cada asset
visual associado às páginas da história precisa ter uma decisão explícita:
manter o original ou aprovar uma versão derivada. Nada é considerado concluído
apenas porque uma imagem foi gerada.
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from book_doctor import sha256
from character_universe import carregar_personagem_oficial
from quality_guardian import run_quality_guardian
from restoration_studio import carregar_plano_restauracao, resumo_restauracao


def visual_completion_gate(projeto: dict) -> dict:
    plan = carregar_plano_restauracao(projeto)
    handoff = plan.get("editorial_remaster_handoff") or {}
    cenas = handoff.get("cenas") or []
    assets = plan.get("assets_detectados") or []
    decisions = plan.get("decisoes") or []
    versions = plan.get("versoes_assets") or []

    if not handoff:
        return {"ok": False, "pendentes": [{"motivo": "handoff_visual_ausente"}], "resolvidos": []}

    approved_by_origin = {
        str(v.get("origem") or "")
        for v in versions
        if v.get("aprovada") and str(v.get("origem") or "")
    }
    keep_asset_ids = {
        str(d.get("asset_id") or "")
        for d in decisions
        if d.get("acao") == "manter_original"
    }

    required_pages = sorted({int(c.get("pagina_origem")) for c in cenas if c.get("pagina_origem") is not None})
    pendentes = []
    resolvidos = []
    for page in required_pages:
        page_assets = [a for a in assets if a.get("pagina") is not None and int(a.get("pagina")) == page]
        if not page_assets:
            pendentes.append({"pagina": page, "motivo": "nenhum_asset_visual_detectado"})
            continue
        for asset in page_assets:
            asset_id = str(asset.get("id") or "")
            origem = str(asset.get("arquivo") or "")
            if asset_id in keep_asset_ids:
                resolvidos.append({"pagina": page, "asset_id": asset_id, "resolucao": "manter_original"})
            elif origem and origem in approved_by_origin:
                resolvidos.append({"pagina": page, "asset_id": asset_id, "resolucao": "versao_remastered_aprovada"})
            else:
                pendentes.append({"pagina": page, "asset_id": asset_id, "motivo": "sem_decisao_visual_aprovada"})

    return {
        "ok": not pendentes and bool(required_pages),
        "paginas_historia": required_pages,
        "pendentes": pendentes,
        "resolvidos": resolvidos,
        "assets_resolvidos": len(resolvidos),
        "assets_pendentes": len(pendentes),
    }


def montar_estado_quality_remaster(state: dict, projeto: dict) -> dict:
    original = state.get("original") or {}
    path = str(original.get("arquivo") or "")
    expected = str(original.get("sha256") or "")
    if not path or not expected or sha256(path) != expected:
        raise ValueError("Integridade do original não confirmada.")
    if not state.get("revisao_aprovada"):
        raise ValueError("Texto remasterizado ainda não está aprovado.")
    if not state.get("metadata_emocional_confirmada"):
        raise ValueError("Mapa emocional ainda não está confirmado.")

    visual = visual_completion_gate(projeto)
    if not visual["ok"]:
        raise ValueError("Revisão visual ainda possui páginas/assets pendentes.")

    plan = carregar_plano_restauracao(projeto)
    out = deepcopy(state)
    personagens = {}
    for link in (plan.get("vinculos") or {}).get("characters") or []:
        cid = str(link.get("character_id") or "")
        if not cid:
            continue
        ch = carregar_personagem_oficial(cid)
        if ch:
            personagens[ch.get("nome") or cid] = deepcopy(ch)
    if personagens:
        out["personagens"] = personagens

    cenas_imagem = []
    for version in plan.get("versoes_assets") or []:
        if version.get("aprovada"):
            cenas_imagem.append({
                "origem": version.get("origem"),
                "arquivo": version.get("derivado"),
                "operacao": version.get("operacao"),
                "aprovada": True,
                "metadata": deepcopy(version.get("metadata") or {}),
            })
    out["cenas_imagem"] = cenas_imagem
    out["restoration_summary"] = resumo_restauracao(projeto)
    out["visual_completion_gate"] = visual
    out["full_editorial_remaster"] = True
    return out


def rodar_quality_remaster(state: dict, projeto: dict, previous_report: dict | None = None) -> dict:
    qa_state = montar_estado_quality_remaster(state, projeto)
    report = run_quality_guardian(
        qa_state,
        previous_report=previous_report,
        project_type="story",
    )
    raw = str(state.get("arquivo_estado") or "")
    if raw:
        path = Path(raw).parent / "quality_guardian_remaster.json"
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        report["arquivo_relatorio"] = str(path)
    return report


def carregar_quality_remaster(state: dict) -> dict:
    raw = str(state.get("arquivo_estado") or "")
    if not raw:
        return {}
    path = Path(raw).parent / "quality_guardian_remaster.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}
