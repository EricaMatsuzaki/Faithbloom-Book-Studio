from pathlib import Path
import json

from pypdf import PdfWriter

import book_doctor
import editorial_remaster_storyteller as storyteller


def _state(tmp_path: Path) -> dict:
    root = tmp_path / "book"
    (root / "originais").mkdir(parents=True)
    source = tmp_path / "miolo.pdf"
    writer = PdfWriter(); writer.add_blank_page(width=612, height=792)
    with source.open("wb") as f: writer.write(f)
    original = book_doctor.preservar_original({"pasta": str(root)}, str(source), "miolo")
    manifest = json.loads((root / "originais" / "manifest.json").read_text(encoding="utf-8"))
    state_path = root / "remastered" / "editorial" / "r1" / "editorial_remaster.json"
    state_path.parent.mkdir(parents=True)
    return {
        "remaster_id": "r1",
        "arquivo_estado": str(state_path),
        "titulo": "Quando Mel Aprendeu a Esperar",
        "colecao": "Pequenas Histórias, Grandes Lições",
        "faixa_etaria": "3-8",
        "emocao_central": "impaciencia",
        "aprendizado_cristao": "confiar no tempo de Deus",
        "licao_final": "Há um tempo certo para cada coisa.",
        "versiculo_referencia": "Eclesiastes 3:1",
        "cenas_texto": [{"numero": 1, "texto": "Mel olhou para o vaso."}],
        "necessita_intervencao_estrutural_roteirista": True,
        "original": {"arquivo": original, "sha256": manifest[-1]["sha256"], "imutavel": True},
    }


def test_storyteller_requires_explicit_authorization(tmp_path):
    state = _state(tmp_path)
    try:
        storyteller.gerar_parecer_estrutural_roteirista(state, lambda **kwargs: {}, autorizado=False)
    except ValueError as exc:
        assert "Autorização" in str(exc)
    else:
        raise AssertionError("Roteirista deveria exigir autorização explícita")


def test_storyteller_returns_advice_without_mutating_scenes(tmp_path):
    state = _state(tmp_path)
    before = json.loads(json.dumps(state["cenas_texto"], ensure_ascii=False))

    def fake_llm(**kwargs):
        return {
            "diagnostico_geral": "Ritmo pode melhorar.",
            "heart_arc": "preservado",
            "manter": [1],
            "ajustes_pontuais": [],
            "ajustes_estruturais": [],
            "cenas_prioritarias": [],
            "risco_de_perder_alma": "baixo",
            "ordem_recomendada": [1],
        }

    out = storyteller.gerar_parecer_estrutural_roteirista(state, fake_llm, autorizado=True)
    assert state["cenas_texto"] == before
    assert out["alteracoes_aplicadas"] is False
    assert out["parecer"]["heart_arc"] == "preservado"
    assert Path(out["arquivo_parecer"]).exists()
    assert book_doctor.sha256(state["original"]["arquivo"]) == state["original"]["sha256"]
