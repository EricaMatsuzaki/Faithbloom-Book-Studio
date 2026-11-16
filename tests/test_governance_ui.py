"""Exercise the governance page action and persistent history in an isolated store."""
from pathlib import Path

from streamlit.testing.v1 import AppTest

import storage_backend

ROOT = Path(__file__).resolve().parents[1]


def test_governance_runs_only_on_click_and_history_preserves_original(tmp_path, monkeypatch):
    # AppTest loads this page as its entry point; global multipage navigation is
    # tested by the application smoke suite and is excluded from this page test.
    monkeypatch.setattr("estilo.render_sidebar_navigation", lambda: None)
    monkeypatch.setenv("FAITHBLOOM_ACCESS_MODE", "pilot")
    backend = storage_backend.LocalStorageBackend(str(tmp_path))
    monkeypatch.setattr(storage_backend, "BACKEND", backend)
    backend.put_bytes("masters/original.png", b"ORIGINAL-BYTES")
    page = AppTest.from_file(str(ROOT / "pages/54_🛡️_Governanca.py"), default_timeout=20).run()
    assert not page.exception
    assert not page.subheader
    assert backend.list() == ["masters/original.png"]
    next(button for button in page.button if button.label == "Verificar agora").click().run()
    assert not page.exception
    assert len(page.subheader) == 4
    assert backend.list() == ["masters/original.png"]
    next(button for button in page.button if button.label == "Salvar relatório no histórico").click().run()
    assert not page.exception
    saved = [path for path in backend.list() if path.startswith("governance/")]
    assert len(saved) == 1
    assert backend.get_bytes("masters/original.png") == b"ORIGINAL-BYTES"
    next(button for button in page.button if button.label == "Consultar histórico").click().run()
    assert not page.exception
    assert len(page.session_state["governance_history"]) == 1
    next(button for button in page.button if button.label == "Abrir relatório selecionado").click().run()
    assert not page.exception
    assert len(page.subheader) == 1
