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
        "titulo": "Quando Mel Aprendeu a Esperar",
        "faixa_etaria": "3–8",
        "cenas_texto": [
            {"numero": 1, "texto": "Mel olhou para a terra."},
            {"numero": 2, "texto": "Mel decidiu esperar."},
        ],
    }


def test_emotional_metadata_manual_override_remains_available(tmp_path):
    state = _state(tmp_path)
    assert emotional.metadata_emocional_completa(state)["ok"] is False

    state = emotional.atualizar_metadata_emocional_cena(
        state, 1, emocao="curiosidade", intensidade=2,
        emocao_secundaria="", transicao_emocional="", expressao="curiosa",
    )
    assert state["metadata_emocional_confirmada"] is False
    assert state["mapa_emocional"] == []
    assert state["cenas_texto"][0]["emocao_travada"] is True

    state = emotional.atualizar_metadata_emocional_cena(
        state, 2, emocao="esperanca", intensidade=4,
        emocao_secundaria="gratidao", transicao_emocional="impaciência → esperança", expressao="serena",
    )
    assert state["metadata_emocional_confirmada"] is True
    assert len(state["mapa_emocional"]) == 2
    assert state["mapa_emocional"][0]["direcao"]["emocao_narrativa"] == "curiosidade"


def test_automatic_specialist_analyzes_story_and_color_engine_maps_environment(tmp_path):
    state = _state(tmp_path)

    def fake_llm(system, instruction):
        assert "NÃO escolha cores" in system
        assert "Quando Mel Aprendeu a Esperar" in instruction
        return {
            "cenas": [
                {"numero": 1, "emocao": "curiosidade", "emocao_secundaria": "", "intensidade": 2, "transicao_emocional": "", "expressao": "curiosa", "justificativa_curta": "Mel observa e tenta entender o que acontece."},
                {"numero": 2, "emocao": "esperanca", "emocao_secundaria": "gratidao", "intensidade": 4, "transicao_emocional": "curiosidade → esperança", "expressao": "serena", "justificativa_curta": "A decisão de esperar muda a emoção da cena."},
            ],
            "resumo_arco": "curiosidade → esperança",
        }

    out = emotional.analisar_emocoes_automaticamente(state, fake_llm)
    assert out["metadata_emocional_confirmada"] is True
    assert out["metadata_emocional_modo"] == "automatico_com_override_humano"
    assert out["cenas_texto"][0]["emocao_origem"] == "especialista_automatico"
    assert out["mapa_emocional"][0]["direcao"]["emocao_narrativa"] == "curiosidade"
    assert out["mapa_emocional"][0]["direcao"]["cor_principal"]
    assert out["mapa_emocional"][1]["direcao"]["emocao_narrativa"] == "esperanca"
    assert out["analise_emocional_automatica"]["cores_por_motor_canonico"] is True
    assert out["analise_emocional_automatica"]["personagem_recolorido"] is False


def test_automatic_specialist_preserves_locked_author_emotion(tmp_path):
    state = _state(tmp_path)
    state["cenas_texto"][0].update({
        "emocao": "alegria",
        "intensidade_emocional": 3,
        "emocao_travada": True,
        "emocao_origem": "override_autora",
    })

    def fake_llm(system, instruction):
        return {
            "cenas": [
                {"numero": 1, "emocao": "tristeza", "emocao_secundaria": "", "intensidade": 5, "transicao_emocional": "", "expressao": "triste"},
                {"numero": 2, "emocao": "esperanca", "emocao_secundaria": "", "intensidade": 4, "transicao_emocional": "", "expressao": "serena"},
            ],
            "resumo_arco": "alegria → esperança",
        }

    out = emotional.analisar_emocoes_automaticamente(state, fake_llm)
    assert out["cenas_texto"][0]["emocao"] == "alegria"
    assert out["cenas_texto"][0]["intensidade_emocional"] == 3
    assert out["mapa_emocional"][0]["direcao"]["emocao_narrativa"] == "alegria"


def test_invalid_emotion_is_rejected(tmp_path):
    state = _state(tmp_path)
    try:
        emotional.atualizar_metadata_emocional_cena(state, 1, emocao="qualquer_coisa", intensidade=3)
    except ValueError as exc:
        assert "Emoção" in str(exc)
    else:
        raise AssertionError("Emoção fora da taxonomia deveria ser bloqueada")
