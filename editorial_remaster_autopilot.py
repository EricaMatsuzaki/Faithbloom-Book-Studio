"""FaithBloom Full Editorial Remaster Autopilot.

Orquestra os módulos canônicos do Remaster sem duplicar especialistas. O clique
inicial da autora autoriza alterações editoriais somente na versão DERIVADA; o
PDF original, Character Masters, Color Masters e Style DNA oficiais nunca são
promovidos/alterados silenciosamente. Aprovação final da edição continua humana.

Falhas transitórias podem ser repetidas automaticamente. Falhas técnicas são
classificadas e recebem um plano do agente de Engenharia/Full-Stack; o run fica
persistido e pode ser retomado do último checkpoint após a correção/deploy. Este
módulo deliberadamente NÃO autoedita nem autodeploya o próprio código do SaaS.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256 as _sha256
import json
from pathlib import Path
import time
import uuid
from typing import Any, Callable

from book_doctor import sha256

SCHEMA = "faithbloom.editorial-remaster-autopilot.v1"
RUN_STATUSES = {"pending", "running", "completed", "failed", "blocked", "needs_author_review"}
STAGES = [
    "remaster_import",
    "story_page_mapping",
    "editorial_dossier",
    "storyteller_enrichment",
    "final_text_revision",
    "style_and_character_resolution",
    "visual_handoff",
    "visual_preflight",
    "quality_preflight",
    "final_review_package",
]
TRANSIENT_MARKERS = (
    "429", "rate limit", "timeout", "timed out", "temporar", "502", "503", "504",
    "connection reset", "connection error", "provider", "try again", "tente novamente",
)
FULLSTACK_MARKERS = (
    "streamlit", "session_state", "widget", "button", "page_link", "switch_page",
    "frontend", "ui", "ux", "form", "navigation", "navega",
)
EDITORIAL_MARKERS = (
    "lição de moral", "licao de moral", "mensagem bíblica", "mensagem biblica",
    "bible", "versículo", "versiculo", "storyteller", "revisor", "prompt-mestre",
    "prompt mestre", "heart arc", "faixa etária", "faixa etaria",
)


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _fingerprint(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return _sha256(raw).hexdigest()


def _run_dir(project: dict, run_id: str) -> Path:
    root = Path(str(project.get("pasta") or ""))
    if not root:
        raise ValueError("Projeto Book Doctor sem pasta persistente.")
    path = root / "remastered" / "autopilot" / run_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def _run_path(project: dict, run_id: str) -> Path:
    return _run_dir(project, run_id) / "autopilot_state.json"


def _verify_original_from_remaster(state: dict) -> None:
    original = state.get("original") or {}
    path = str(original.get("arquivo") or "")
    expected = str(original.get("sha256") or "")
    if not path or not expected or not Path(path).exists():
        raise ValueError("Original preservado não está disponível para o Autopilot.")
    if sha256(path) != expected:
        raise ValueError("SHA-256 do original divergiu. Autopilot bloqueado por segurança.")


def new_run(
    project: dict,
    *,
    report: dict | None = None,
    settings: dict | None = None,
) -> dict:
    if str(project.get("tipo_projeto") or "story") != "story":
        raise ValueError("Autopilot Editorial Remaster está disponível para Story Book.")
    run_id = uuid.uuid4().hex[:12]
    cfg = {
        "faixa_etaria": "3-8",
        "versiculo_referencia": "",
        "licao_final": "",
        "aprendizado_cristao": "",
        "emocao_central": "",
        "auto_apply_safe_editorial_changes": True,
        "allow_paid_image_generation": False,
        "max_transient_retries": 2,
        "final_human_approval_required": True,
    }
    cfg.update(settings or {})
    run = {
        "schema": SCHEMA,
        "run_id": run_id,
        "project_id": project.get("id", ""),
        "title": project.get("titulo", ""),
        "collection": project.get("colecao", ""),
        "status": "pending",
        "created_at": _now(),
        "updated_at": _now(),
        "settings": cfg,
        "book_doctor_report": deepcopy(report or {}),
        "remaster_state": {},
        "stages": {
            name: {
                "status": "pending", "attempts": 0, "input_fingerprint": "",
                "started_at": "", "completed_at": "", "result": {}, "error": "",
                "incident_ids": [],
            }
            for name in STAGES
        },
        "incidents": [],
        "audit_trail": [{"at": _now(), "event": "autopilot_authorized", "scope": "derived_remaster_only"}],
        "final_review_package": {},
        "author_final_approval": False,
        "master_promotion_allowed": False,
        "auto_publish": False,
    }
    save_run(project, run)
    return run


def save_run(project: dict, run: dict) -> dict:
    payload = deepcopy(run)
    payload["updated_at"] = _now()
    _run_path(project, payload["run_id"]).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return payload


def load_run(project: dict, run_id: str) -> dict:
    path = _run_path(project, run_id)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def list_runs(project: dict) -> list[dict]:
    root = Path(str(project.get("pasta") or "")) / "remastered" / "autopilot"
    if not root.exists():
        return []
    out = []
    for path in root.glob("*/autopilot_state.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(data, dict):
            out.append(data)
    return sorted(out, key=lambda x: str(x.get("updated_at") or ""), reverse=True)


def classify_failure(exc: BaseException, stage: str = "") -> dict:
    text = f"{type(exc).__name__}: {exc}".casefold()
    if any(marker in text for marker in TRANSIENT_MARKERS):
        owner, action = "runtime_retry", "retry"
    elif any(marker in text for marker in FULLSTACK_MARKERS):
        owner, action = "fullstack_developer", "engineering_repair"
    elif any(marker in text for marker in EDITORIAL_MARKERS) or stage in {
        "editorial_dossier", "storyteller_enrichment", "final_text_revision"
    }:
        owner, action = "editorial_specialist", "editorial_remediation"
    else:
        owner, action = "saas_automation_engineer", "engineering_repair"
    return {"owner": owner, "action": action, "message": str(exc), "exception": type(exc).__name__}


def _engineering_plan(stage: str, failure: dict, context: dict | None = None) -> dict:
    if failure.get("owner") not in {"saas_automation_engineer", "fullstack_developer"}:
        return {}
    try:
        from agents.engenheiro_saas_automacao import build_execution_plan
        request = (
            f"Falha no Autopilot Editorial Remaster na etapa {stage}. "
            f"Responsável sugerido: {failure.get('owner')}. Erro: {failure.get('message')}. "
            "Preserve checkpoints, original e retome do estágio que falhou após a correção."
        )
        plan = build_execution_plan(request, existing_components=[
            "editorial_remaster_autopilot", "editorial_remaster", "restoration_studio",
            "quality_guardian", "Streamlit",
        ])
        from agents.engenheiro_code_review_profundo import escalation_required, build_deep_review_plan
        if escalation_required(context):
            plan["deep_review_plan"] = build_deep_review_plan(stage, symptom=failure.get("message", ""))
        plan["diagnostic_page"] = "pages/37_🧠_Agent_Skills_Bestseller_Readiness.py"
        return plan
    except Exception as exc:
        return {"status": "plan_generation_failed", "error": str(exc)}


def record_incident(project: dict, run: dict, stage: str, exc: BaseException) -> dict:
    failure = classify_failure(exc, stage)
    incident = {
        "id": uuid.uuid4().hex[:12],
        "stage": stage,
        "created_at": _now(),
        "status": "retrying" if failure["action"] == "retry" else "queued_for_repair",
        **failure,
        "engineering_plan": _engineering_plan(stage, failure, {"runtime_failure_persists": any(x.get("stage") == stage for x in run.get("incidents", []))}),
        "resume_from": stage,
        "self_code_patch": False,
        "note": (
            "O runtime pode repetir falhas transitórias e retomar checkpoints. "
            "Defeitos de código exigem correção/deploy por uma integração de engenharia autorizada; "
            "o SaaS não altera o próprio código silenciosamente."
        ),
    }
    run.setdefault("incidents", []).append(incident)
    run["stages"][stage].setdefault("incident_ids", []).append(incident["id"])
    run.setdefault("audit_trail", []).append({
        "at": _now(), "event": "incident_routed", "stage": stage,
        "incident_id": incident["id"], "owner": incident["owner"],
    })
    save_run(project, run)
    return incident


def _page_mapping_with_llm(state: dict, chamar_llm: Callable) -> tuple[list[int], dict]:
    pages = [
        {"pagina": int(x.get("pagina") or 0), "texto": str(x.get("texto_extraido") or "")[:6000]}
        for x in (state.get("paginas_texto_extraido") or [])
        if str(x.get("texto_extraido") or "").strip()
    ]
    if not pages:
        raise ValueError("O PDF não possui texto extraível para mapear a história automaticamente.")
    result = chamar_llm(
        sistema=(
            "Você é o classificador editorial do FaithBloom. Identifique somente páginas que pertencem "
            "à narrativa principal do livro infantil. Exclua capa, folha de rosto, copyright, dedicatória, "
            "sumário, mensagens editoriais, atividades e contracapa. Não reescreva o texto."
        ),
        instrucao=(
            "Classifique as páginas a seguir. Retorne JSON com paginas_historia (lista de inteiros), "
            "classificacao (lista com pagina, tipo, confianca 0-1, motivo) e ambiguas (lista). "
            "Use somente páginas fornecidas: " + json.dumps(pages, ensure_ascii=False)
        ),
    )
    if not isinstance(result, dict):
        raise RuntimeError("Classificador de páginas não retornou JSON estruturado.")
    allowed = {x["pagina"] for x in pages}
    selected = []
    for raw in result.get("paginas_historia") or []:
        try:
            number = int(raw)
        except (TypeError, ValueError):
            continue
        if number in allowed and number not in selected:
            selected.append(number)
    if not selected:
        raise RuntimeError("Nenhuma página narrativa foi classificada com segurança.")
    return sorted(selected), result


def _resolve_visual_identity(project: dict, report: dict | None = None) -> dict:
    from character_universe import listar_personagens_oficiais
    from restoration_studio import (
        carregar_plano_restauracao, criar_plano_restauracao, salvar_vinculos,
        vincular_character, vincular_style,
    )
    from style_dna import carregar_style, listar_styles

    plan = carregar_plano_restauracao(project) or criar_plano_restauracao(
        project, report, "story", project.get("status_publicacao"), project.get("colecao", "")
    )
    collection = str(project.get("colecao") or plan.get("colecao") or "")
    style_cards = listar_styles(collection or None)
    story_styles = []
    for card in style_cards:
        style = carregar_style(card.get("id", ""))
        if not style:
            continue
        uses = style.get("usos_permitidos") or []
        if not uses or "story" in uses:
            story_styles.append(style)

    linked_style = str((plan.get("vinculos") or {}).get("style_id") or "")
    chosen_style = next((x for x in story_styles if x.get("id") == linked_style), None)
    if chosen_style is None and len(story_styles) == 1:
        chosen_style = story_styles[0]
        plan = vincular_style(plan, chosen_style["id"])
    elif chosen_style is None and len(story_styles) > 1:
        raise RuntimeError("Há mais de um Style DNA oficial compatível com Story; escolha canônica ambígua.")
    elif chosen_style is None:
        raise RuntimeError("Nenhum Style DNA oficial ativo para Story nesta coleção.")

    characters = listar_personagens_oficiais(collection or None)
    for character in characters:
        plan = vincular_character(plan, character.get("id", ""), papel="autopilot_collection_official")
    plan = salvar_vinculos(project, plan)
    return {
        "style": {"id": chosen_style.get("id"), "nome": chosen_style.get("nome")},
        "characters": [{"id": x.get("id"), "nome": x.get("nome")} for x in characters],
        "restoration_plan_id": plan.get("id", ""),
    }


def _quality_preflight(state: dict, project: dict) -> dict:
    from editorial_remaster_quality import visual_completion_gate
    visual = visual_completion_gate(project)
    return {
        "text_approved": bool(state.get("revisao_aprovada")),
        "prompt_master_ok": bool((state.get("prompt_master_compliance_remaster") or {}).get("ok_para_finalizar")),
        "bible_gate": deepcopy(state.get("bible_reference_gate_remaster") or {}),
        "emotional_map_ready": bool(state.get("metadata_emocional_confirmada")),
        "visual": visual,
        "ready_for_final_quality_guardian": bool(
            state.get("revisao_aprovada")
            and (state.get("prompt_master_compliance_remaster") or {}).get("ok_para_finalizar")
            and state.get("metadata_emocional_confirmada")
            and visual.get("ok")
        ),
    }


def build_final_review_package(run: dict, state: dict, project: dict) -> dict:
    from restoration_studio import carregar_plano_restauracao
    plan = carregar_plano_restauracao(project)
    storyteller_stage = (run.get("stages") or {}).get("storyteller_enrichment") or {}
    quality_stage = (run.get("stages") or {}).get("quality_preflight") or {}
    return {
        "schema": "faithbloom.editorial-remaster-final-review.v1",
        "run_id": run.get("run_id"),
        "remaster_id": state.get("remaster_id"),
        "titulo": state.get("titulo"),
        "colecao": state.get("colecao"),
        "original": deepcopy(state.get("original") or {}),
        "original_preservado": True,
        "cenas_remastered": deepcopy(state.get("cenas_texto") or []),
        "storyteller": deepcopy(storyteller_stage.get("result") or {}),
        "licao_de_moral": state.get("licao_final", ""),
        "aprendizado_cristao": state.get("aprendizado_cristao", ""),
        "referencia_biblica": state.get("versiculo_referencia", ""),
        "bible_guard": deepcopy(state.get("bible_reference_gate_remaster") or {}),
        "prompt_master": deepcopy(state.get("prompt_master_compliance_remaster") or {}),
        "mapa_emocional": deepcopy(state.get("mapa_emocional") or []),
        "style_dna": deepcopy(((run.get("stages") or {}).get("style_and_character_resolution") or {}).get("result", {}).get("style") or {}),
        "character_masters": deepcopy(((run.get("stages") or {}).get("style_and_character_resolution") or {}).get("result", {}).get("characters") or []),
        "visual_versions": [deepcopy(x) for x in (plan.get("versoes_assets") or []) if not x.get("aprovada")],
        "visual_decisions": deepcopy(plan.get("decisoes") or []),
        "quality_preflight": deepcopy(quality_stage.get("result") or {}),
        "incidents_and_recovery": deepcopy(run.get("incidents") or []),
        "audit_trail": deepcopy(run.get("audit_trail") or []),
        "requires_final_human_approval": True,
        "master_promotion_allowed": False,
        "auto_publish": False,
        "generated_at": _now(),
    }


def _stage_input(run: dict, stage: str) -> dict:
    state = run.get("remaster_state") or {}
    base = {
        "stage": stage,
        "project_id": run.get("project_id"),
        "original_sha": (state.get("original") or {}).get("sha256"),
        "scenes": state.get("cenas_texto") or [],
        "settings": run.get("settings") or {},
    }
    if stage in {"remaster_import", "story_page_mapping"}:
        base["report"] = run.get("book_doctor_report") or {}
    return base


def _execute_stage(
    stage: str,
    run: dict,
    project: dict,
    chamar_llm: Callable,
) -> dict:
    settings = run.get("settings") or {}
    state = deepcopy(run.get("remaster_state") or {})

    if stage == "remaster_import":
        if state:
            _verify_original_from_remaster(state)
            return {"state": state, "result": {"reused": True, "remaster_id": state.get("remaster_id")}}
        from editorial_remaster import criar_rascunho_remaster_editorial
        state = criar_rascunho_remaster_editorial(
            project, run.get("book_doctor_report") or {},
            faixa_etaria=settings.get("faixa_etaria", "3-8"),
            versiculo_referencia=settings.get("versiculo_referencia", ""),
            licao_final=settings.get("licao_final", ""),
            aprendizado_cristao=settings.get("aprendizado_cristao", ""),
            emocao_central=settings.get("emocao_central", ""),
        )
        state["autopilot_authorization"] = {
            "authorized_at": _now(),
            "scope": "safe_derived_editorial_changes_until_final_review",
            "final_human_approval_required": True,
        }
        return {"state": state, "result": {"remaster_id": state.get("remaster_id")}}

    _verify_original_from_remaster(state)

    if stage == "story_page_mapping":
        if state.get("mapeamento_cenas_confirmado") and state.get("cenas_texto"):
            return {"state": state, "result": {"reused": True, "pages": [x.get("pagina_origem") for x in state.get("cenas_texto") or []]}}
        from editorial_remaster import confirmar_mapeamento_cenas
        pages, evidence = _page_mapping_with_llm(state, chamar_llm)
        state = confirmar_mapeamento_cenas(state, pages)
        from editorial_remaster_revision import salvar_estado_remaster
        state = salvar_estado_remaster(state)
        return {"state": state, "result": {"pages": pages, "classification": evidence}}

    if stage == "editorial_dossier":
        from editorial_remaster import gerar_dossie_revisao
        from editorial_remaster_revision import aprovar_dossie_para_edicao, carregar_dossie
        dossier = carregar_dossie(state)
        if not dossier:
            dossier = gerar_dossie_revisao(state, chamar_llm)
        state = aprovar_dossie_para_edicao(state, dossier, aprovado=True)
        return {"state": state, "result": {"dossier": dossier, "authorized_by": "autopilot_start_consent"}}

    if stage == "storyteller_enrichment":
        from editorial_remaster_storyteller import (
            aplicar_proposta_enriquecimento_roteirista,
            gerar_proposta_enriquecimento_roteirista,
        )
        proposal = gerar_proposta_enriquecimento_roteirista(state, chamar_llm)
        auto_apply = bool(settings.get("auto_apply_safe_editorial_changes", True))
        if proposal.get("ganho_editorial") and auto_apply:
            state = aplicar_proposta_enriquecimento_roteirista(state, proposal, aprovado=True)
        return {
            "state": state,
            "result": {
                "ganho_editorial": bool(proposal.get("ganho_editorial")),
                "auto_applied_to_derived": bool(proposal.get("ganho_editorial") and auto_apply),
                "analysis": deepcopy(proposal.get("analise") or {}),
                "new_scenes": deepcopy((proposal.get("analise") or {}).get("novas_cenas_adicionadas") or []),
            },
        }

    if stage == "final_text_revision":
        from editorial_remaster_revision import rodar_revisao_final_textual
        result = rodar_revisao_final_textual(state, chamar_llm)
        state = result["estado"]
        if not result.get("pronto_para_visual"):
            raise RuntimeError("Revisor final ou Prompt-Mestre ainda encontrou pendências editoriais.")
        return {"state": state, "result": {k: deepcopy(v) for k, v in result.items() if k != "estado"}}

    if stage == "style_and_character_resolution":
        result = _resolve_visual_identity(project, run.get("book_doctor_report") or {})
        return {"state": state, "result": result}

    if stage == "visual_handoff":
        from editorial_visual_handoff import preparar_handoff_visual
        result = preparar_handoff_visual(state, project)
        return {"state": state, "result": {"fingerprint": (result.get("handoff") or {}).get("fingerprint"), "scenes": len((result.get("handoff") or {}).get("cenas") or [])}}

    if stage == "visual_preflight":
        from restoration_studio import carregar_plano_restauracao
        plan = carregar_plano_restauracao(project)
        assets = [x for x in (plan.get("assets_detectados") or []) if str(x.get("arquivo") or "").strip()]
        pending = [x for x in (plan.get("assets_detectados") or []) if not str(x.get("arquivo") or "").strip()]
        return {
            "state": state,
            "result": {
                "assets_available": len(assets),
                "assets_without_extracted_file": len(pending),
                "paid_generation_authorized": bool(settings.get("allow_paid_image_generation")),
                "visual_candidates_auto_approved": False,
                "note": (
                    "O Autopilot prepara identidade, direção emocional e handoff. Imagens geradas permanecem candidatas; "
                    "nenhuma versão visual é aprovada ou promovida a Master automaticamente."
                ),
            },
        }

    if stage == "quality_preflight":
        result = _quality_preflight(state, project)
        return {"state": state, "result": result}

    if stage == "final_review_package":
        package = build_final_review_package(run, state, project)
        return {"state": state, "result": {"ready": True}, "final_package": package}

    raise KeyError(f"Etapa desconhecida: {stage}")


def run_autopilot(
    project: dict,
    run: dict,
    chamar_llm: Callable,
    *,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> dict:
    """Executa/retoma do primeiro checkpoint ainda não concluído.

    Checkpoints concluídos com a mesma impressão de entrada são reutilizados.
    Falhas transitórias respeitam max_transient_retries. Falhas de código ficam
    persistidas para retomada após correção/deploy, sem apagar trabalho anterior.
    """
    current = deepcopy(run)
    if current.get("status") == "completed":
        return current
    current["status"] = "running"
    current = save_run(project, current)
    max_retries = max(0, int((current.get("settings") or {}).get("max_transient_retries", 2)))

    for stage in STAGES:
        checkpoint = current["stages"][stage]
        input_fp = _fingerprint(_stage_input(current, stage))
        if checkpoint.get("status") == "completed" and checkpoint.get("input_fingerprint") == input_fp:
            continue
        checkpoint.update({
            "status": "running", "input_fingerprint": input_fp, "started_at": _now(),
            "completed_at": "", "error": "",
        })
        current = save_run(project, current)

        while True:
            checkpoint = current["stages"][stage]
            checkpoint["attempts"] = int(checkpoint.get("attempts") or 0) + 1
            current = save_run(project, current)
            try:
                out = _execute_stage(stage, current, project, chamar_llm)
                current["remaster_state"] = deepcopy(out.get("state") or current.get("remaster_state") or {})
                checkpoint = current["stages"][stage]
                checkpoint["status"] = "completed"
                checkpoint["result"] = deepcopy(out.get("result") or {})
                checkpoint["completed_at"] = _now()
                checkpoint["error"] = ""
                if out.get("final_package"):
                    current["final_review_package"] = deepcopy(out["final_package"])
                current.setdefault("audit_trail", []).append({"at": _now(), "event": "stage_completed", "stage": stage})
                current = save_run(project, current)
                break
            except Exception as exc:
                incident = record_incident(project, current, stage, exc)
                current = load_run(project, current["run_id"]) or current
                checkpoint = current["stages"][stage]
                retryable = incident.get("action") == "retry" and checkpoint.get("attempts", 0) <= max_retries
                if retryable:
                    checkpoint["status"] = "pending"
                    checkpoint["error"] = str(exc)
                    current = save_run(project, current)
                    sleep_fn(min(4.0, float(checkpoint.get("attempts") or 1)))
                    continue
                checkpoint["status"] = "blocked" if incident.get("action") in {"engineering_repair", "editorial_remediation"} else "failed"
                checkpoint["error"] = str(exc)
                current["status"] = "blocked" if checkpoint["status"] == "blocked" else "failed"
                current = save_run(project, current)
                return current

    current["status"] = "needs_author_review"
    current.setdefault("audit_trail", []).append({"at": _now(), "event": "final_review_ready"})
    return save_run(project, current)


def approve_final_remaster(project: dict, run: dict, *, approved: bool) -> dict:
    """Registra decisão final sem promover Master nem publicar automaticamente."""
    current = deepcopy(run)
    if current.get("status") not in {"needs_author_review", "completed"}:
        raise ValueError("O Autopilot ainda não chegou ao pacote final de revisão.")
    current["author_final_approval"] = bool(approved)
    current["author_final_decided_at"] = _now()
    current["status"] = "completed" if approved else "needs_author_review"
    current.setdefault("audit_trail", []).append({
        "at": _now(), "event": "author_final_decision", "approved": bool(approved),
    })
    current["master_promotion_allowed"] = False
    current["auto_publish"] = False
    return save_run(project, current)
