from pathlib import Path

from pypdf import PdfWriter

import real_pilot as rp
import storage_backend
from storage_backend import LocalStorageBackend


def isolated(tmp_path, monkeypatch):
    backend = LocalStorageBackend(str(tmp_path / "data"))
    monkeypatch.setattr(storage_backend, "BACKEND", backend)
    monkeypatch.setattr(rp, "BACKEND", backend)
    return backend


def make_pdf(path: Path, pages=3):
    w = PdfWriter()
    for _ in range(pages):
        w.add_blank_page(width=621, height=630)  # 8.625 x 8.75
    with path.open("wb") as f:
        w.write(f)
    return path


def test_fast_audit_does_not_modify_source(tmp_path):
    p = make_pdf(tmp_path / "book.pdf", 4)
    before = rp._sha256(p)
    r = rp.fast_pdf_audit(p)
    assert r["pages_total"] == 4
    assert r["uniform_page_size"] is True
    assert r["sha256"] == before
    assert rp._sha256(p) == before
    assert r["source_unchanged"] is True


def test_pilot_run_is_saved_and_profile_driven(tmp_path, monkeypatch):
    isolated(tmp_path, monkeypatch)
    p = make_pdf(tmp_path / "book.pdf", 2)
    run = rp.run_pilot(p, "mel_master", save=True)
    assert run["profile_id"] == "mel_master"
    assert "Character Universe" in run["focus_modules"]
    rows = rp.list_pilot_runs()
    assert rows[0]["id"] == run["id"]


def test_bug_requires_retest_evidence_before_verified(tmp_path, monkeypatch):
    isolated(tmp_path, monkeypatch)
    bug = rp.register_bug("Botão não preserva contexto", module="Integration UX", severity="high")
    fixed = rp.update_bug_status(bug["id"], "fixed")
    assert fixed["status"] == "fixed"
    try:
        rp.update_bug_status(bug["id"], "verified")
        assert False, "verified deveria exigir evidência"
    except ValueError:
        pass
    verified = rp.update_bug_status(bug["id"], "verified", evidence="Reteste E2E aprovado")
    assert verified["status"] == "verified"


def test_readiness_requires_all_three_pilots_and_no_high_bugs(tmp_path, monkeypatch):
    isolated(tmp_path, monkeypatch)
    p = make_pdf(tmp_path / "book.pdf", 2)
    assert rp.pilot_readiness()["ready_for_next_candidate"] is False
    for pid in rp.PILOT_PROFILES:
        rp.run_pilot(p, pid, save=True)
    assert rp.pilot_readiness()["ready_for_next_candidate"] is True
    bug = rp.register_bug("Falha crítica", module="Book Doctor", severity="high")
    assert rp.pilot_readiness()["ready_for_next_candidate"] is False
    rp.update_bug_status(bug["id"], "verified", evidence="Reproduzido e corrigido")
    assert rp.pilot_readiness()["ready_for_next_candidate"] is True


def test_profile_catalog_contains_the_three_real_pilots():
    assert set(rp.PILOT_PROFILES) == {"mel_master", "mel_natal", "bolufinhas"}


def test_book_doctor_fast_wrapper_is_compatible(tmp_path):
    from book_doctor import auditar_pdf_rapido
    p = make_pdf(tmp_path / "big-book.pdf", 3)
    r = auditar_pdf_rapido(str(p))
    assert r["modo_auditoria"] == "rapida"
    assert r["paginas_total"] == 3
    assert r["tamanho_uniforme"] is True
    assert "observacao_ppi" in r
    assert "analise_textual_piloto" in r
