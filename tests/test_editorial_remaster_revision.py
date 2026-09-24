from pathlib import Path
import json

from pypdf import PdfWriter

import book_doctor
import editorial_remaster_revision as revision


def _pdf(path: Path) -> None:
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    with path.open("wb") as f:
        writer.write(f)


def _state(tmp_path: Path) -> dict:
    root = tmp_path / "book"
    (root / "originais").mkdir(parents=True)
    (root / "remastered" / "editorial" / "r1").mkdir(parents=True)
    source = tmp_path / "miolo.pdf"
    _pdf(source)
    project = {"pasta": str(root)}
    original = book_doctor.preservar_original(project, str(source), "miolo")
    manifest = json.loads((root / "originais" / "manifest.json").read_text(encoding="utf-8"))
    state_path = root / "remastered" / "editorial" / "r1" / "editorial_remaster.json"
    state = {
        "remaster_id": "r1",
        "titulo": "Quando Mel Aprendeu a Esperar",
        "faixa_etaria": "3-8",
        "versiculo_referencia": "Eclesiastes 3:1",
        "licao_final": "Há um tempo certo para cada coisa.",
        "aprendizado_cristao": "aprender a esperar e confiar em Deus",
        "emocao_central": "impaciencia",
        "original": {"arquivo": original, "sha256": manifest[-1]["sha256"], "imutavel": True},
        "arquivo_estado": str(state_path),
        "mapeamento_cenas_confirmado": True,
        "cenas_texto": [
            {"numero": 1, "pagina_origem": 4, "origem": "book_doctor_pdf", "texto": "Mel olhou para o vaso."},
        ],
        "revisao_aprovada": False,
    }
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    return state


def test_dossier_approval_required_before_editor(tmp_path):
    state = _state(tmp_path)

    def fake_llm(*args, **kwargs):
        return {"texto": "Mel esperou perto do vaso."}

    try:
        revision.gerar_proposta_edicao_cena(state, 1, "melhore", fake_llm)
    except ValueError as exc:
        assert "Dossiê" in str(exc)
    else:
        raise AssertionError("Editor deveria permanecer bloqueado antes da aprovação do dossiê")


def test_proposal_is_non_destructive_until_explicit_approval(tmp_path, monkeypatch):
    state = _state(tmp_path)
    dossier = {"remaster_id": "r1", "revisor": {"status": "REVISAR"}}
    state = revision.aprovar_dossie_para_edicao(state, dossier, aprovado=True)

    monkeypatch.setattr(
        "agents.editor_historia.editar_cena",
        lambda cena, instrucao, state, chamar_llm: {**cena, "texto": "Mel respirou e esperou perto do vaso."},
    )
    proposal = revision.gerar_proposta_edicao_cena(state, 1, "melhore o ritmo", lambda **kwargs: {})

    assert state["cenas_texto"][0]["texto"] == "Mel olhou para o vaso."
    rejected = revision.aplicar_proposta_edicao(state, proposal, aprovado=False)
    assert rejected["cenas_texto"][0]["texto"] == "Mel olhou para o vaso."

    approved = revision.aplicar_proposta_edicao(state, proposal, aprovado=True)
    assert approved["cenas_texto"][0]["texto"] == "Mel respirou e esperou perto do vaso."
    assert approved["cenas_texto"][0]["pagina_origem"] == 4
    assert approved["original"]["sha256"] == state["original"]["sha256"]
    assert book_doctor.sha256(approved["original"]["arquivo"]) == state["original"]["sha256"]


def test_stale_proposal_is_blocked(tmp_path, monkeypatch):
    state = _state(tmp_path)
    state = revision.aprovar_dossie_para_edicao(state, {"remaster_id": "r1"}, aprovado=True)
    monkeypatch.setattr(
        "agents.editor_historia.editar_cena",
        lambda cena, instrucao, state, chamar_llm: {**cena, "texto": "Nova proposta"},
    )
    proposal = revision.gerar_proposta_edicao_cena(state, 1, "melhore", lambda **kwargs: {})
    changed = dict(state)
    changed["cenas_texto"] = [dict(state["cenas_texto"][0], texto="Mudança concorrente")]

    try:
        revision.aplicar_proposta_edicao(changed, proposal, aprovado=True)
    except ValueError as exc:
        assert "mudou" in str(exc)
    else:
        raise AssertionError("Proposta stale deveria ser bloqueada")


def test_final_review_builds_emotional_map_only_after_reviewer_approval(tmp_path, monkeypatch):
    state = _state(tmp_path)
    state = revision.aprovar_dossie_para_edicao(state, {"remaster_id": "r1"}, aprovado=True)

    def fake_reviewer(work, chamar_llm):
        work = dict(work)
        work["revisao_aprovada"] = True
        work["notas_revisor"] = []
        work["cenas_texto"] = [
            {
                **work["cenas_texto"][0],
                "emocao": "esperanca",
                "intensidade_emocional": 3,
                "emocao_secundaria": "curiosidade",
                "transicao_emocional": "impaciência → esperança",
            }
        ]
        return work

    monkeypatch.setattr("agents.revisor.revisor_node", fake_reviewer)
    result = revision.rodar_revisao_final_textual(state, lambda **kwargs: {})

    assert result["aprovado"] is True
    assert len(result["mapa_emocional"]) == 1
    assert result["necessita_roteirista"] is False
    assert result["estado"]["original"]["sha256"] == state["original"]["sha256"]
