from pathlib import Path
import json

from pypdf import PdfWriter

import book_doctor
import editorial_remaster


def _pdf(path: Path, pages: int = 2) -> None:
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=612, height=792)
    with path.open("wb") as f:
        writer.write(f)


def _project(tmp_path: Path) -> dict:
    project = {
        "id": "mel123",
        "titulo": "Quando Mel Aprendeu a Esperar",
        "idioma": "pt-BR",
        "pasta": str(tmp_path / "book"),
        "tipo_projeto": "story",
        "status_publicacao": "publicado",
        "colecao": "Pequenas Histórias, Grandes Lições",
    }
    (Path(project["pasta"]) / "originais").mkdir(parents=True)
    (Path(project["pasta"]) / "remastered").mkdir(parents=True)
    source = tmp_path / "miolo.pdf"
    _pdf(source)
    original = book_doctor.preservar_original(project, str(source), "miolo")
    return project


def test_remaster_preserves_original_and_fails_closed_before_scene_confirmation(tmp_path):
    project = _project(tmp_path)
    manifest = json.loads((Path(project["pasta"]) / "originais" / "manifest.json").read_text(encoding="utf-8"))
    original = manifest[-1]["arquivo"]
    before = book_doctor.sha256(original)

    draft = editorial_remaster.criar_rascunho_remaster_editorial(project, {"titulo": project["titulo"]})

    assert book_doctor.sha256(original) == before
    assert draft["original"]["sha256"] == before
    assert draft["original"]["imutavel"] is True
    assert draft["cenas_texto"] == []
    assert draft["mapeamento_cenas_confirmado"] is False
    gate = editorial_remaster.gate_revisao_editorial(draft)
    assert gate["ok"] is False
    assert "mapeamento_cenas_nao_confirmado" in gate["bloqueios"]
    assert gate["next_step"] == "aguardar_confirmacao"


def test_remaster_route_reuses_existing_specialists_in_safe_order(tmp_path):
    project = _project(tmp_path)
    draft = editorial_remaster.criar_rascunho_remaster_editorial(project)
    route = draft["rota_editorial"]

    assert route[0] == "book_doctor"
    assert route.index("story_reviewer") < route.index("story_editor")
    assert route.index("story_editor") < route.index("storyteller")
    assert route.index("storyteller") < route.index("character_universe")
    assert route.index("character_universe") < route.index("restoration_studio")
    assert route.index("restoration_studio") < route.index("quality_guardian")
    assert route[-1] == "publishing_distribution_center"
    assert len(route) == len(set(route))
    assert draft["politica_revisao"]["preservar_original"] is True
    assert draft["politica_revisao"]["revisao_textual_antes_visual"] is True
    assert draft["politica_revisao"]["aprovacao_humana_obrigatoria"] is True


def test_sha_mismatch_blocks_remaster(tmp_path):
    project = _project(tmp_path)
    manifest_path = Path(project["pasta"]) / "originais" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    original = Path(manifest[-1]["arquivo"])
    original.write_bytes(original.read_bytes() + b"changed")

    try:
        editorial_remaster.criar_rascunho_remaster_editorial(project)
    except ValueError as exc:
        assert "SHA-256" in str(exc)
    else:
        raise AssertionError("Remaster deveria bloquear original com hash divergente")


def test_non_story_project_is_rejected(tmp_path):
    project = _project(tmp_path)
    project["tipo_projeto"] = "coloring"

    try:
        editorial_remaster.criar_rascunho_remaster_editorial(project)
    except ValueError as exc:
        assert "Story Book" in str(exc)
    else:
        raise AssertionError("Remaster textual não deve aceitar coloring nesta etapa")


def test_confirmed_mapping_builds_only_explicitly_selected_pages():
    draft = {
        "paginas_texto_extraido": [
            {"pagina": 1, "texto_extraido": "Capa", "tem_texto": True},
            {"pagina": 2, "texto_extraido": "Mel olhou para a semente.", "tem_texto": True},
            {"pagina": 3, "texto_extraido": "Ela esperou mais um pouco.", "tem_texto": True},
        ],
        "original": {},
    }
    confirmed = editorial_remaster.confirmar_mapeamento_cenas(draft, [2, 3])

    assert confirmed["mapeamento_cenas_confirmado"] is True
    assert [x["pagina_origem"] for x in confirmed["cenas_texto"]] == [2, 3]
    assert confirmed["cenas_texto"][0]["texto"] == "Mel olhou para a semente."
    assert all(x["origem"] == "book_doctor_pdf" for x in confirmed["cenas_texto"])
