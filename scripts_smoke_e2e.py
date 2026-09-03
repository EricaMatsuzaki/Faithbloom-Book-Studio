"""Rodar no terminal: python scripts_smoke_e2e.py (não gasta créditos)."""
from integracao_e2e import rodar_diagnostico_completo

r=rodar_diagnostico_completo()
print("FaithBloom E2E:", "PASS" if r["ok"] else "FAIL")
for grupo, checks in r["grupos"].items():
    print(f"\n[{grupo}]")
    for c in checks:
        mark="OK" if c["ok"] else ("WARN" if c["nivel"]=="aviso" else "FAIL")
        print(f"- {mark}: {c['nome']} :: {c['detalhe']}")
raise SystemExit(0 if r["ok"] else 1)
