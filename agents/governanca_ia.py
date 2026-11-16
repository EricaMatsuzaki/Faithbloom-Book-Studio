"""Governança de IA: diagnóstico local, sem gerar conteúdo ou certificar modelos."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from governance import build_report, finding, inspect_source, preflight_action, verify_control

ROLE_ID = "ai_governance"
NAME = "Agente de Governança de IA"
MISSION = "Verificar rastreabilidade da IA, limites de custos, avaliação de resultados e decisões humanas antes de ações de risco."
SKILL_DOMAINS = {
    "model_risk": ("inventário de modelos", "proveniência de resultados", "avaliação de IA", "limites de inferência"),
    "controls": ("aprovação humana", "guardas de custos", "segurança de prompts", "preservação de Masters"),
    "assurance": ("evidências verificáveis", "avaliação por faixa etária", "continuidade editorial", "monitoramento de falhas"),
}
NON_NEGOTIABLES = (
    "não chamar provedores durante o diagnóstico",
    "não confundir modelo configurado com modelo validado",
    "não promover candidatos a Master nem publicar automaticamente",
    "não salvar prompts, manuscritos, credenciais ou dados pessoais no relatório",
    "evidência ausente permanece UNKNOWN; contrato não é certificação",
)


def all_skills() -> list[str]:
    return [skill for domain in SKILL_DOMAINS.values() for skill in domain]


def check_generation_action(action: str = "generate_book", **kwargs: Any) -> dict:
    """Pré-ação reutilizável; nenhuma chamada de IA é realizada aqui."""
    from agent_skills import require_role_ready
    require_role_ready("ai_governance")
    return preflight_action(action, **kwargs)


def run_diagnostic(root: str | Path | None = None, *, state: dict | None = None, context: dict | None = None) -> dict:
    from agent_skills import require_role_ready
    require_role_ready("ai_governance")
    root = Path(root or Path(__file__).resolve().parents[1])
    context = dict(context or {})
    findings = []
    for code, path, symbol, title in (
        ("ai_provider_routing", "ai_provider_router.py", "chamar_llm", "Roteamento textual implementado"),
        ("ai_daily_budget", "controle_geracao.py", "validar_orcamento", "Guarda de orçamento implementada"),
        ("ai_paid_request_log", "controle_geracao.py", "finalizar_requisicao", "Registro de geração implementado"),
        ("ai_master_approval", "character_universe.py", "aprovar_variacao", "Aprovação de variações implementada"),
        ("ai_originality_gate", "originality_guard.py", None, "Camada de revisão de originalidade presente"),
    ):
        evidence = inspect_source(root, path, symbol)
        findings.append(finding(code, "PASS" if evidence else "FAIL", title, evidence,
            "Verificar a aplicação deste controle em cada fluxo; existência do código não comprova cobertura nem qualidade do resultado."))
    configured = sum(bool(os.environ.get(name)) for name in ("GEMINI_API_KEY", "GROQ_API_KEY", "OPENROUTER_API_KEY"))
    findings.append(finding("ai_credentials_presence", "PASS" if configured else "WARN",
        "Credencial textual presente no processo" if configured else "Nenhuma credencial textual identificada neste processo",
        ["runtime:presence-only"], "A presença não comprova acesso, saldo ou geração. Validar uma chamada autorizada sem registrar chaves."))
    for name, title in (
        ("provider_live_test", "Teste real do provedor"),
        ("generation_provenance", "Proveniência modelo/provedor/versionamento"),
        ("cost_metering_coverage", "Cobertura de custos em todos os fluxos"),
        ("human_approval_coverage", "Aplicação das aprovações humanas"),
        ("ai_output_evaluation", "Avaliação editorial e visual dos resultados"),
    ):
        status, evidence = verify_control(context, name)
        findings.append(finding(name, status, title, evidence,
            "Registrar uma execução observada e sua referência de teste; não basta marcar o controle como verdadeiro."))
    if state is not None:
        scenes = [x for x in (state.get("cenas_texto") or []) if isinstance(x, dict)]
        findings.append(finding("project_usable_story", "PASS" if any(str(x.get("texto") or "").strip() for x in scenes) else "WARN",
            "Texto utilizável no projeto selecionado", ["project:cenas_texto (somente presença)"],
            "Revisar qualidade e faixa etária antes de aprovar. O conteúdo não é copiado para o relatório."))
        metadata = state.get("generation_metadata") or state.get("generation_provenance") or {}
        if not isinstance(metadata, dict):
            metadata = {}
        has_trace = bool(metadata.get("provider") and metadata.get("model") and (metadata.get("request_id") or metadata.get("generated_at")))
        findings.append(finding("project_ai_trace", "PASS" if has_trace else "WARN",
            "Campos de rastreabilidade do projeto", ["project:generation_metadata (somente campos)"],
            "Registrar provedor, modelo e execução sem guardar prompts completos nem credenciais."))
    return build_report(ROLE_ID, NAME, findings, scope="IA: fontes locais e evidências de execução fornecidas")
