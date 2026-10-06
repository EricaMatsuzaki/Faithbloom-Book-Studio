from pathlib import Path
import json

from pypdf import PdfWriter

import book_doctor
import editorial_remaster_quality as quality
from restoration_studio import criar_plano_restauracao, salvar_vinculos


def _pdf(path: Path) -> None:
    writer = PdfWriter(); writer.add_blank_page(width=612, height=792)
    with path.open("wb") as f: writer.write(f)


def _fixture(tmp_path: Path):
    root = tmp_path / "book"
    (root / "originais").mkdir(parents=True)
    source = tmp_path / "miolo.pdf"; _pdf(source)
    project = {
        "id": "mel123", "titulo": "Quando Mel Aprendeu a Esperar",
        "pasta": str(root), "tipo_projeto": "story", "status_publicacao": "publicado",
        "colecao": "Pequenas Histórias, Grandes Lições",
    }
    original = book_doctor.preservar_original(project, str(source), "miolo")
    manifest = json.loads((root / "originais" / "manifest.json").read_text(encoding="utf-8"))
    state_path = root / "remastered" / "editorial" / "r1" / "editorial_remaster.json"
    state_path.parent.mkdir(parents=True)
    state = {
        "remaster_id": "r1", "arquivo_estado": str(state_path),
        "titulo": project["titulo"], "colecao": project["colecao"], "faixa_etaria": "3-8",
        "aprendizado_cristao": "confiar no tempo de Deus", "versiculo_referencia": "Eclesiastes 3:1",
        "licao_final": "Há um tempo certo para cada coisa.",
        "original": {"arquivo": original, "sha256": manifest[-1]["sha256"], "imutavel": True},
        "revisao_aprovada": True, "metadata_emocional_confirmada": True,
        "cenas_texto": [{"numero": 1, "pagina_origem": 4, "texto": "Mel esperou.", "emocao": "esperanca", "intensidade_emocional": 3}],
        "mapa_emocional": [{"numero": 1, "emocao_narrativa": "esperanca"}],
    }
    plan = criar_plano_restauracao(project)
    asset_path = tmp_path / "page4.png"; asset_path.write_bytes(b"fake")
    plan["assets_detectados"] = [{"id": "p004-i01", "pagina": 4, "arquivo": str(asset_path)}]
    plan["editorial_remaster_handoff"] = {"cenas": [{"numero": 1, "pagina_origem": 4, "texto_revisado": "Mel esperou."}]}
    salvar_vinculos(project, plan)
    return project, state


def test_visual_gate_blocks_unresolved_asset(tmp_path):
    project, state = _fixture(tmp_path)
    gate = quality.visual_completion_gate(project)
    assert gate["ok"] is False
    assert gate["assets_pendentes"] == 1


def test_visual_gate_accepts_explicit_keep_original(tmp_path):
    project, state = _fixture(tmp_path)
    from restoration_studio import carregar_plano_restauracao
    plan = carregar_plano_restauracao(project)
    plan["decisoes"] = [{"asset_id": "p004-i01", "acao": "manter_original"}]
    salvar_vinculos(project, plan)
    gate = quality.visual_completion_gate(project)
    assert gate["ok"] is True
    assert gate["resolvidos"][0]["resolucao"] == "manter_original"


def test_quality_state_requires_visual_completion(tmp_path):
    project, state = _fixture(tmp_path)
    try:
        quality.montar_estado_quality_remaster(state, project)
    except ValueError as exc:
        assert "visual" in str(exc).lower()
    else:
        raise AssertionError("QA deveria bloquear enquanto houver asset visual pendente")


def test_quality_guardian_runs_after_explicit_visual_decision(tmp_path):
    project, state = _fixture(tmp_path)
    from restoration_studio import carregar_plano_restauracao
    plan = carregar_plano_restauracao(project)
    plan["decisoes"] = [{"asset_id": "p004-i01", "acao": "manter_original"}]
    salvar_vinculos(project, plan)
    report = quality.rodar_quality_remaster(state, project)
    assert report["project_title"] == "Quando Mel Aprendeu a Esperar"
    assert "summary" in report
    assert Path(report["arquivo_relatorio"]).exists()
