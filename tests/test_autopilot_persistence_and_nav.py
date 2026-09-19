from pathlib import Path

import book_doctor
import editorial_autopilot_storage as runtime_storage


class FakeBackend:
    name = "fake"

    def __init__(self):
        self.data = {}

    def put_bytes(self, path, data, content_type=None):
        self.data[path] = bytes(data)
        return path

    def get_bytes(self, path):
        return self.data[path]

    def put_json(self, path, value):
        import json
        self.data[path] = json.dumps(value, ensure_ascii=False).encode("utf-8")
        return path

    def get_json(self, path, default=None):
        import json
        raw = self.data.get(path)
        return default if raw is None else json.loads(raw.decode("utf-8"))

    def list(self, prefix=""):
        p = prefix.strip("/")
        return sorted(k for k in self.data if k == p or k.startswith(p + "/"))


def test_autopilot_is_exposed_in_custom_sidebar():
    root = Path(__file__).resolve().parents[1]
    source = (root / "estilo.py").read_text(encoding="utf-8")
    assert 'pages/52_✨_Autopilot_Editorial_Remaster.py' in source
    assert '✨ Autopilot Editorial Remaster' in source


def test_runtime_tree_roundtrip(monkeypatch, tmp_path):
    fake = FakeBackend()
    monkeypatch.setattr(runtime_storage, "BACKEND", fake)
    project = {"id": "abc123", "pasta": str(tmp_path / "project")}
    run_file = Path(project["pasta"]) / "remastered" / "autopilot" / "run1" / "autopilot_state.json"
    plan_file = Path(project["pasta"]) / "planos" / "restoration_plan.json"
    run_file.parent.mkdir(parents=True, exist_ok=True)
    plan_file.parent.mkdir(parents=True, exist_ok=True)
    run_file.write_text('{"run_id":"run1","status":"blocked"}', encoding="utf-8")
    plan_file.write_text('{"id":"plan1"}', encoding="utf-8")

    result = runtime_storage.sync_runtime_tree(project)
    assert result["synced"] == 2

    import shutil
    shutil.rmtree(Path(project["pasta"]) / "remastered")
    shutil.rmtree(Path(project["pasta"]) / "planos")

    restored = runtime_storage.restore_runtime_tree(project)
    assert restored["restored"] == 2
    assert run_file.exists()
    assert plan_file.exists()


def test_book_doctor_project_and_original_rehydrate(monkeypatch, tmp_path):
    fake = FakeBackend()
    monkeypatch.setattr(book_doctor, "BACKEND", fake)
    monkeypatch.setattr(book_doctor, "ROOT", tmp_path / "book_doctor_projects")
    monkeypatch.setattr(book_doctor, "backend_status", lambda: {"modo": "fake"})

    src = tmp_path / "sample.pdf"
    src.write_bytes(b"%PDF-test")
    project = book_doctor.criar_projeto("Livro Teste", colecao="Coleção")
    preserved = Path(book_doctor.preservar_original(project, str(src), "miolo"))
    report = {"projeto_id": project["id"], "miolo": {"modo_auditoria": "rapida"}}
    local_report = Path(project["pasta"]) / "relatorios" / "book_doctor_report.json"
    local_report.parent.mkdir(parents=True, exist_ok=True)
    import json
    local_report.write_text(json.dumps(report), encoding="utf-8")
    book_doctor._persist_json(project, "relatorios/book_doctor_report.json", report)

    import shutil
    shutil.rmtree(book_doctor.ROOT)

    projects = book_doctor.listar_projetos()
    assert len(projects) == 1
    restored_project = projects[0]
    restored_report = book_doctor.carregar_relatorio(restored_project)
    assert restored_report["projeto_id"] == project["id"]
    manifest = Path(restored_project["pasta"]) / "originais" / "manifest.json"
    assert manifest.exists()
    entries = json.loads(manifest.read_text(encoding="utf-8"))
    assert Path(entries[-1]["arquivo"]).exists()
    assert preserved.name == Path(entries[-1]["arquivo"]).name
