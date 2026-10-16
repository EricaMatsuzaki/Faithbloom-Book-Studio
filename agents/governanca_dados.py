"""Governança de dados com verificação local e privacidade por padrão."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from governance import build_report, finding, inspect_source, preflight_action, verify_control

ROLE_ID = "data_governance"
NAME = "Agente de Governança de Dados"
MISSION = "Verificar persistência, linhagem, acesso, consentimento, retenção e recuperação sem alterar dados ou originais."
SKILL_DOMAINS = {
    "lifecycle": ("classificação de dados", "minimização", "retenção", "consentimento"),
    "integrity": ("linhagem", "identidade de projeto", "versionamento", "backup e restauração"),
    "access": ("isolamento de tenant", "controle de acesso", "armazenamento privado", "evidências de exposição"),
}
NON_NEGOTIABLES = (
    "não ler bibliotecas pessoais completas durante diagnóstico",
    "não expor manuscritos, documentos, fotos, tokens ou identidades no relatório",
    "não apagar dados nem alterar Masters ou originais",
    "backup declarado não equivale a restauração testada",
    "isolamento de dados exige evidência; configuração desconhecida permanece UNKNOWN",
)


def all_skills() -> list[str]:
    return [skill for domain in SKILL_DOMAINS.values() for skill in domain]


def check_data_action(action: str, **kwargs: Any) -> dict:
    return preflight_action(action, **kwargs)


def run_diagnostic(root: str | Path | None = None, *, state: dict | None = None, context: dict | None = None) -> dict:
    root = Path(root or Path(__file__).resolve().parents[1])
    context = dict(context or {})
    findings = []
    for code, path, symbol, title in (
        ("data_storage_backend", "storage_backend.py", "get_backend", "Backend persistente implementado"),
        ("data_atomic_local_write", "storage_backend.py", "LocalStorageBackend.put_bytes", "Implementação de gravação local presente"),
        ("data_generation_snapshot", "generation_autosave.py", "persist_generation_snapshot", "Checkpoints de geração implementados"),
        ("data_master_history", "character_universe.py", "adicionar_variacao", "Histórico de variações implementado"),
    ):
        evidence = inspect_source(root, path, symbol)
        findings.append(finding(code, "PASS" if evidence else "FAIL", title, evidence,
            "Existência do mecanismo não comprova integridade da biblioteca nem recuperação em produção."))
    for name, title in (
        ("persistent_storage_live", "Persistência após reinício do aplicativo"),
        ("tenant_isolation", "Isolamento entre clientes/workspaces"),
        ("private_storage", "Privacidade de objetos e acesso ao bucket"),
        ("restore_tested", "Restauração de backup testada"),
        ("retention_policy", "Política de retenção aplicada"),
        ("personal_data_consent", "Consentimento e finalidade de dados pessoais"),
        ("lineage_verified", "Linhagem de traduções, áudio e derivados"),
    ):
        status, evidence = verify_control(context, name)
        findings.append(finding(name, status, title, evidence,
            "Conferir o controle em uma execução autorizada e registrar a evidência, sem anexar dados pessoais ao relatório."))
    if state is not None:
        identity = bool(state.get("project_id") or state.get("storage_path") or state.get("id"))
        findings.append(finding("data_project_identity", "PASS" if identity else "WARN",
            "Identidade persistente do projeto", ["project:identity-fields (valores omitidos)"],
            "Vincular derivados à identidade estável do original, não somente ao título."))
        has_derivatives = any(state.get(key) for key in ("translation_versions", "translations", "audiobook", "derived_outputs"))
        has_lineage = bool(state.get("source_ref") or state.get("source_fingerprint") or state.get("origin_project_id"))
        if has_derivatives:
            findings.append(finding("data_derivative_source", "PASS" if has_lineage else "WARN",
                "Vínculo da origem nos metadados do projeto", ["project:source-fields (valores omitidos)"],
                "Validar referências e fingerprints de cada derivado. Ausência no projeto não prova ausência em registros separados."))
        if state.get("origem") == "real_experience" or state.get("origin") == "real_experience":
            status, evidence = verify_control(context, "real_experience_privacy")
            findings.append(finding("real_experience_privacy", status, "Privacidade da experiência real", evidence,
                "Conferir consentimento e anonimização antes de compartilhar ou enviar dados a provedores."))
    return build_report(ROLE_ID, NAME, findings, scope="Dados: fontes locais e metadados do projeto selecionado")
