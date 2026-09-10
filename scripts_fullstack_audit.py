"""Auditoria estrutural completa do FaithBloom sem chamar IA nem gastar créditos.

Objetivo: revisar todos os módulos Python do repositório e apontar falhas ou
inconsistências verificáveis sem alterar conteúdo editorial. O script segue o
princípio FaithBloom: verificar -> reutilizar -> estender -> criar só se faltar.

Uso local:
    python scripts_fullstack_audit.py

Saída:
    FULLSTACK_AUDIT_REPORT.json

Código de saída 1 somente quando há blockers objetivos (ex.: sintaxe inválida,
referência interna quebrada, definição duplicada no mesmo escopo ou segredo literal).
Warnings não bloqueiam CI porque podem representar especializações legítimas.
"""
from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
REPORT_PATH = ROOT / "FULLSTACK_AUDIT_REPORT.json"
EXCLUDED_DIRS = {".git", ".venv", "venv", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
PAGE_REF_RE = re.compile(r"pages/[A-Za-z0-9_\-\.\u0080-\uffff🎙️🤖📖📚🖍️🎯🔍👤🚀🖼️🧪🎄🛡️🏭✅🎭🎨✨🌐📐🧩🎧☁️🏆✍️🧭🏠🪄➕🌿🌸]+\.py")
SECRET_NAME_RE = re.compile(r"(?i)(api[_-]?key|secret|password|token|service[_-]?role)")
PLACEHOLDER_VALUES = {"", "changeme", "change-me", "example", "placeholder", "your-key", "sua-chave", "none"}
REQUEST_METHODS = {"get", "post", "put", "patch", "delete", "request", "head", "options"}


def _py_files() -> list[Path]:
    out = []
    for path in ROOT.rglob("*.py"):
        if any(part in EXCLUDED_DIRS for part in path.parts):
            continue
        out.append(path)
    return sorted(out)


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _module_name(path: Path) -> str:
    rel = path.relative_to(ROOT).with_suffix("")
    return ".".join(rel.parts)


def _definition_duplicates(body: list[ast.stmt], scope: str) -> list[dict[str, Any]]:
    seen: dict[str, int] = {}
    issues = []
    for node in body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.name in seen:
                issues.append({
                    "severity": "blocker",
                    "code": "duplicate_definition",
                    "scope": scope,
                    "name": node.name,
                    "first_line": seen[node.name],
                    "line": node.lineno,
                })
            else:
                seen[node.name] = node.lineno
            if isinstance(node, ast.ClassDef):
                issues.extend(_definition_duplicates(node.body, f"{scope}.{node.name}"))
    return issues


def _literal_secret_issues(tree: ast.AST, rel: str) -> list[dict[str, Any]]:
    issues = []
    for node in ast.walk(tree):
        targets: list[str] = []
        value = None
        if isinstance(node, ast.Assign):
            value = node.value
            for target in node.targets:
                if isinstance(target, ast.Name):
                    targets.append(target.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            targets.append(node.target.id)
            value = node.value
        if not targets or not isinstance(value, ast.Constant) or not isinstance(value.value, str):
            continue
        literal = value.value.strip()
        if not literal or literal.casefold() in PLACEHOLDER_VALUES:
            continue
        for name in targets:
            if SECRET_NAME_RE.search(name):
                # Model IDs and token counters can legitimately contain token in the name.
                lower = name.casefold()
                if "model" in lower or "token_count" in lower or "max_token" in lower:
                    continue
                issues.append({
                    "severity": "blocker",
                    "code": "literal_secret_candidate",
                    "file": rel,
                    "line": getattr(node, "lineno", 0),
                    "name": name,
                    "detail": "Valor sensível aparentemente literal no código; mover para Secrets/variável de ambiente.",
                })
    return issues


def _call_name(node: ast.Call) -> tuple[str, str]:
    func = node.func
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
        return func.value.id, func.attr
    return "", ""


def _quality_issues(tree: ast.AST, rel: str) -> list[dict[str, Any]]:
    issues = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler):
            if node.type is None:
                issues.append({"severity": "warning", "code": "bare_except", "file": rel, "line": node.lineno})
            if len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
                issues.append({"severity": "warning", "code": "silent_exception", "file": rel, "line": node.lineno})
        if isinstance(node, ast.Call):
            base, method = _call_name(node)
            if base == "requests" and method in REQUEST_METHODS:
                if not any(k.arg == "timeout" for k in node.keywords):
                    issues.append({
                        "severity": "warning", "code": "request_without_timeout", "file": rel,
                        "line": node.lineno, "detail": f"requests.{method} sem timeout explícito",
                    })
            if isinstance(node.func, ast.Name) and node.func.id in {"eval", "exec"}:
                issues.append({
                    "severity": "warning", "code": "dynamic_code_execution", "file": rel,
                    "line": node.lineno, "detail": f"Uso de {node.func.id}() requer revisão de segurança.",
                })
            if base == "subprocess" and any(k.arg == "shell" and isinstance(k.value, ast.Constant) and k.value.value is True for k in node.keywords):
                issues.append({
                    "severity": "warning", "code": "subprocess_shell_true", "file": rel,
                    "line": node.lineno,
                })
    return issues


def _imports(tree: ast.AST) -> set[str]:
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def _navigation_refs(tree: ast.AST) -> set[str]:
    refs = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            refs.update(PAGE_REF_RE.findall(node.value))
    return refs


def _local_module_index(files: list[Path]) -> dict[str, str]:
    index = {}
    for path in files:
        rel = _rel(path)
        mod = _module_name(path)
        index[mod] = rel
        if path.parent == ROOT:
            index[path.stem] = rel
    return index


def _import_graph(parsed: dict[str, ast.AST], local_index: dict[str, str]) -> tuple[dict[str, set[str]], list[dict[str, Any]]]:
    graph: dict[str, set[str]] = defaultdict(set)
    issues = []
    for rel, tree in parsed.items():
        source_mod = _module_name(ROOT / rel)
        for name in _imports(tree):
            candidates = [name]
            parts = name.split(".")
            if parts:
                candidates.append(parts[0])
            resolved = next((local_index[c] for c in candidates if c in local_index), None)
            if resolved:
                graph[source_mod].add(_module_name(ROOT / resolved))
                continue
            top = parts[0] if parts else name
            try:
                found = importlib.util.find_spec(top)
            except (ImportError, AttributeError, ValueError):
                found = None
            if found is None and top not in {"__future__"}:
                issues.append({
                    "severity": "warning",
                    "code": "unresolved_import_candidate",
                    "file": rel,
                    "import": name,
                    "detail": "Não foi localizado como módulo interno nem dependência disponível neste ambiente de auditoria.",
                })
    return graph, issues


def _cycles(graph: dict[str, set[str]]) -> list[list[str]]:
    cycles: set[tuple[str, ...]] = set()
    visiting: list[str] = []
    active: set[str] = set()
    done: set[str] = set()

    def visit(node: str) -> None:
        if node in done:
            return
        if node in active:
            try:
                i = visiting.index(node)
                cycle = visiting[i:] + [node]
                core = cycle[:-1]
                rotations = [tuple(core[i:] + core[:i]) for i in range(len(core))]
                canonical = min(rotations) if rotations else tuple()
                if canonical:
                    cycles.add(canonical)
            except ValueError:
                pass
            return
        active.add(node)
        visiting.append(node)
        for dep in sorted(graph.get(node, set())):
            visit(dep)
        visiting.pop()
        active.remove(node)
        done.add(node)

    for node in sorted(graph):
        visit(node)
    return [list(c) for c in sorted(cycles)]


def audit_repository() -> dict[str, Any]:
    files = _py_files()
    parsed: dict[str, ast.AST] = {}
    issues: list[dict[str, Any]] = []
    hashes: dict[str, list[str]] = defaultdict(list)
    stats = {"python_files": len(files), "production_files": 0, "test_files": 0, "pages": 0, "agents": 0}

    for path in files:
        rel = _rel(path)
        if rel.startswith("tests/"):
            stats["test_files"] += 1
        else:
            stats["production_files"] += 1
        if rel.startswith("pages/"):
            stats["pages"] += 1
        if rel.startswith("agents/"):
            stats["agents"] += 1
        raw = path.read_bytes()
        hashes[hashlib.sha256(raw).hexdigest()].append(rel)
        try:
            text = raw.decode("utf-8")
            tree = ast.parse(text, filename=rel)
            parsed[rel] = tree
        except (SyntaxError, UnicodeDecodeError) as exc:
            issues.append({
                "severity": "blocker", "code": "syntax_or_encoding_error", "file": rel,
                "line": getattr(exc, "lineno", 0) or 0, "detail": str(exc),
            })
            continue
        issues.extend({"file": rel, **x} for x in _definition_duplicates(tree.body, rel))
        issues.extend(_literal_secret_issues(tree, rel))
        issues.extend(_quality_issues(tree, rel))
        for ref in _navigation_refs(tree):
            if not (ROOT / ref).exists():
                issues.append({
                    "severity": "blocker", "code": "broken_page_reference", "file": rel,
                    "reference": ref, "detail": "Referência de navegação aponta para página inexistente.",
                })

    # Duplicação exata é warning: wrappers/especializações podem ser legítimos e nunca são removidos automaticamente.
    duplicate_groups = []
    for digest, members in hashes.items():
        prod = [m for m in members if not m.startswith("tests/")]
        if len(prod) > 1:
            duplicate_groups.append({"sha256": digest, "files": prod})
            issues.append({
                "severity": "warning", "code": "exact_duplicate_source", "files": prod,
                "detail": "Conteúdo idêntico detectado; revisar antes de decidir reutilizar, manter especialização ou consolidar.",
            })

    # Prefixos numéricos repetidos nas páginas podem confundir ordem/navegação, mas não são erro por si só.
    prefixes: dict[int, list[str]] = defaultdict(list)
    for rel in parsed:
        if not rel.startswith("pages/"):
            continue
        name = Path(rel).name
        m = re.match(r"^(\d+)_", name)
        if m:
            prefixes[int(m.group(1))].append(rel)
    page_prefix_collisions = []
    for prefix, members in sorted(prefixes.items()):
        if len(members) > 1:
            page_prefix_collisions.append({"prefix": prefix, "files": members})
            issues.append({
                "severity": "warning", "code": "page_prefix_collision", "prefix": prefix, "files": members,
                "detail": "Mais de uma página usa o mesmo prefixo numérico normalizado.",
            })

    local_index = _local_module_index(files)
    graph, import_issues = _import_graph(parsed, local_index)
    issues.extend(import_issues)
    cycles = _cycles(graph)
    for cycle in cycles:
        issues.append({
            "severity": "warning", "code": "circular_import_candidate", "modules": cycle,
            "detail": "Ciclo de imports internos detectado; pode ser legítimo, mas merece revisão arquitetural.",
        })

    blockers = [x for x in issues if x.get("severity") == "blocker"]
    warnings = [x for x in issues if x.get("severity") == "warning"]
    modules_with_direct_tests = []
    test_stems = {Path(rel).stem.removeprefix("test_") for rel in parsed if rel.startswith("tests/")}
    for rel in parsed:
        if rel.startswith("tests/") or rel.startswith("pages/"):
            continue
        if Path(rel).stem in test_stems:
            modules_with_direct_tests.append(rel)

    return {
        "schema": "faithbloom.fullstack-audit.v1",
        "status": "BLOCKED" if blockers else "PASS_WITH_WARNINGS" if warnings else "PASS",
        "policy": {
            "read_only_audit": True,
            "no_ai_calls": True,
            "no_credit_usage": True,
            "warnings_do_not_auto_delete_or_merge": True,
            "anti_duplication": ["verify", "reuse", "extend", "create_if_missing"],
        },
        "stats": stats,
        "summary": {"blockers": len(blockers), "warnings": len(warnings), "issues_total": len(issues)},
        "duplicate_groups": duplicate_groups,
        "page_prefix_collisions": page_prefix_collisions,
        "circular_imports": cycles,
        "modules_with_direct_test_filename": sorted(modules_with_direct_tests),
        "issues": issues,
    }


def main() -> int:
    report = audit_repository()
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    s = report["summary"]
    print(f"FaithBloom Full-Stack Audit: {report['status']}")
    print(f"Python: {report['stats']['python_files']} | produção: {report['stats']['production_files']} | testes: {report['stats']['test_files']}")
    print(f"Blockers: {s['blockers']} | warnings: {s['warnings']} | total: {s['issues_total']}")
    for issue in report["issues"]:
        mark = "FAIL" if issue.get("severity") == "blocker" else "WARN"
        where = issue.get("file") or ", ".join(issue.get("files") or issue.get("modules") or [])
        detail = issue.get("detail") or issue.get("name") or issue.get("import") or issue.get("code")
        print(f"- {mark} {issue.get('code')}: {where} :: {detail}")
    print(f"Relatório: {REPORT_PATH.name}")
    return 1 if s["blockers"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
