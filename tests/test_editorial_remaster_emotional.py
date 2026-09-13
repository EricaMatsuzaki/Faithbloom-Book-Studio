from pathlib import Path
import json

from pypdf import PdfWriter

import book_doctor
import editorial_remaster_emotional as emotional


def _state(tmp_path: Path):
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
        "original": {"arquivo": original, "sha256": manifest[-1]["sha256"], "imutavel": True},
        "cenas_texto": [
            {"numero": 1, "texto": "Mel olhou para a terra."},
            {"numero": 2, "texto": "Mel decidiu esperar."},
        ],
    }


def test_emotional_metadata_stays_pending_until_every_scene_is_confirmed(tmp_path):
    state = _state(tmp_path)
    assert emotional.metadata_emocional_completa(state)["ok"] is False

    state = emotional.atualizar_metadata_emocional_cena(
        state, 1, emocao="curiosidade", intensidade=2,
        emocao_secundaria="", transicao_emocional="", expressao="curiosa",
    )
    assert state["metadata_emocional_confirmada"] is False
    assert state["mapa_emocional"] == []

    state = emotional.atualizar_metadata_emocional_cena(
        state, 2, emocao="esperanca", intensidade=4,
        emocao_secundaria="gratidao", transicao_emocional="impaciência → esperança", expressao="serena",
    )
    assert state["metadata_emocional_confirmada"] is True
    assert len(state["mapa_emocional"]) == 2
    assert state["mapa_emocional"][0]["direcao"]["emocao_narrativa"] == "curiosidade"


def test_invalid_emotion_is_rejected(tmp_path):
    state = _state(tmp_path)
    try:
        emotional.atualizar_metadata_emocional_cena(state, 1, emocao="qualquer_coisa", intensidade=3)
    except ValueError as exc:
        assert "Emoção" in str(exc)
    else:
        raise AssertionError("Emoção fora da taxonomia deveria ser bloqueada")
