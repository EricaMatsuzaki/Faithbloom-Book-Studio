from pathlib import Path
import json

from pypdf import PdfWriter

import book_doctor
import editorial_visual_handoff as handoff


def _pdf(path: Path) -> None:
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    with path.open("wb") as f:
        writer.write(f)


def _fixture(tmp_path: Path):
    root = tmp_path / "book"
    (root / "originais").mkdir(parents=True)
    source = tmp_path / "miolo.pdf"
    _pdf(source)
    project = {
        "id": "mel123",
        "titulo": "Quando Mel Aprendeu a Esperar",
        "pasta": str(root),
        "tipo_projeto": "story",
        "status_publicacao": "publicado",
        "colecao": "Pequenas Histórias, Grandes Lições",
    }
    original = book_doctor.preservar_original(project, str(source), "miolo")
    manifest = json.loads((root / "originais" / "manifest.json").read_text(encoding="utf-8"))
    state = {
        "remaster_id": "r1",
        "projeto_book_doctor_id": "mel123",
        "titulo": project["titulo"],
        "colecao": project["colecao"],
        "faixa_etaria": "3-8",
        "versiculo_referencia": "Eclesiastes 3:1",
        "licao_final": "Há um tempo certo para cada coisa.",
        "original": {"arquivo": original, "sha256": manifest[-1]["sha256"], "imutavel": True},
        "revisao_aprovada": True,
        "prompt_master_compliance_remaster": {"ok_para_finalizar": True},
        "cenas_texto": [
            {"numero": 1, "pagina_origem": 4, "texto": "Mel esperou perto do vaso.", "emocao": "esperanca", "intensidade_emocional": 3},
        ],
        "mapa_emocional": [
            {"numero": 1, "emocao_narrativa": "esperanca", "cor_principal": "amarelo"},
        ],
    }
    return project, state


def test_handoff_requires_approved_text(tmp_path):
    project, state = _fixture(tmp_path)
    state["revisao_aprovada"] = False
    try:
        handoff.preparar_handoff_visual(state, project)
    except ValueError as exc:
        assert "Revisor Editorial" in str(exc)
    else:
        raise AssertionError("handoff visual deveria bloquear texto ainda não aprovado")


def test_handoff_preserves_existing_restoration_history(tmp_path):
    project, state = _fixture(tmp_path)
    from restoration_studio import criar_plano_restauracao, salvar_vinculos, carregar_plano_restauracao

    plan = criar_plano_restauracao(project)
    plan["decisoes"] = [{"id": "old", "acao": "manter_original"}]
    plan["versoes_assets"] = [{"id": "v1", "aprovada": True}]
    salvar_vinculos(project, plan)

    out = handoff.preparar_handoff_visual(state, project)
    updated = out["restoration_plan"]
    assert updated["decisoes"] == [{"id": "old", "acao": "manter_original"}]
    assert updated["versoes_assets"] == [{"id": "v1", "aprovada": True}]
    assert updated["editorial_remaster_handoff"]["remaster_id"] == "r1"
    assert updated["editorial_remaster_handoff"]["cenas"][0]["pagina_origem"] == 4
    assert handoff.contexto_cena_para_asset(carregar_plano_restauracao(project), 4)["texto_revisado"] == "Mel esperou perto do vaso."


def test_changed_handoff_is_versioned(tmp_path):
    project, state = _fixture(tmp_path)
    first = handoff.preparar_handoff_visual(state, project)
    state2 = dict(state)
    state2["cenas_texto"] = [{**state["cenas_texto"][0], "texto": "Mel sorriu e esperou."}]
    second = handoff.preparar_handoff_visual(state2, project)
    assert first["handoff"]["fingerprint"] != second["handoff"]["fingerprint"]
    assert len(second["restoration_plan"].get("editorial_remaster_handoff_history") or []) == 1
