from pathlib import Path

from book_doctor import sha256
import editorial_remaster_revision as revision


def _state(tmp_path: Path) -> dict:
    original = tmp_path / "original.pdf"
    original.write_bytes(b"%PDF-fake-preserved")
    return {
        "remaster_id": "rem-1",
        "titulo": "Livro Teste",
        "faixa_etaria": "3-8",
        "licao_final": "",
        "aprendizado_cristao": "",
        "emocao_central": "",
        "versiculo_referencia": "",
        "original": {"arquivo": str(original), "sha256": sha256(str(original)), "imutavel": True},
        "arquivo_estado": str(tmp_path / "remastered" / "state.json"),
        "cenas_texto": [
            {"numero": 1, "pagina_origem": 4, "texto": "Mel esperou junto do vasinho e aprendeu a ter paciência."},
        ],
        "autopilot_authorization": {
            "final_human_approval_required": True,
            "scope": "safe_derived_editorial_changes_until_final_review",
        },
    }


def test_autopilot_infers_missing_editorial_metadata_without_form(tmp_path):
    state = _state(tmp_path)

    def fake_llm(**kwargs):
        return {
            "licao_final": "Há um tempo certo para cada coisa.",
            "aprendizado_cristao": "Confiar no tempo de Deus com paciência.",
            "emocao_central": "esperança",
            "versiculo_referencia": "Eclesiastes 3:1",
            "confianca": {"licao_final": 0.96, "aprendizado_cristao": 0.94, "emocao_central": 0.93, "versiculo_referencia": 0.99},
            "justificativas": {"licao_final": "derivada da jornada da personagem"},
        }

    updated, info = revision._inferir_metadados_editoriais_faltantes(state, fake_llm)

    assert updated["licao_final"] == "Há um tempo certo para cada coisa."
    assert updated["aprendizado_cristao"]
    assert updated["emocao_central"] == "esperança"
    assert updated["versiculo_referencia"] == "Eclesiastes 3:1"
    assert info["inferred"] is True
    assert "licao_final" in info["fields"]
    assert Path(updated["arquivo_estado"]).exists()


def test_autopilot_repairs_reviewer_notes_in_derived_copy(tmp_path):
    state = _state(tmp_path)
    state["licao_final"] = "Há um tempo certo para cada coisa."
    before_hash = state["original"]["sha256"]
    result = {
        "notas": [{"cena": 1, "problema": "Falta uma reação emocional mais clara."}],
        "prompt_mestre": {"bloqueios": []},
    }

    def fake_llm(**kwargs):
        return {
            "cenas_texto_revisadas": [
                {"numero": 1, "texto": "Mel respirou fundo, sentiu esperança e decidiu esperar mais um pouquinho."},
            ],
            "ajustes_realizados": ["reação emocional explicitada"],
            "invariantes_preservados": True,
        }

    updated, info = revision._reparar_pendencias_editoriais(state, result, fake_llm, 1)

    assert info["changed"] is True
    assert updated["cenas_texto"][0]["pagina_origem"] == 4
    assert "esperança" in updated["cenas_texto"][0]["texto"]
    assert updated["original"]["sha256"] == before_hash
    assert sha256(updated["original"]["arquivo"]) == before_hash
    assert updated["metadata_emocional_confirmada"] is False
