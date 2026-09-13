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
        "cenas_texto": [{"numero": 1, "texto": "Mel olhou para o vaso.", "pagina_origem": 3}],
        "necessita_intervencao_estrutural_roteirista": True,
        "dossie_editorial_aprovado_para_edicao": True,
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


def test_storyteller_can_propose_enrichment_and_new_scene_without_mutating_active_state(tmp_path):
    state = _state(tmp_path)
    before = json.loads(json.dumps(state["cenas_texto"], ensure_ascii=False))

    def fake_llm(**kwargs):
        assert "ENRIQUECER SEM DESVIAR" in kwargs["sistema"]
        assert "Lição de moral" in kwargs["sistema"]
        assert "Referência bíblica" in kwargs["sistema"]
        return {
            "ganho_editorial": True,
            "diagnostico_geral": "Falta uma tentativa concreta antes da descoberta.",
            "motivos": ["fortalecer experiência e transformação"],
            "heart_arc": "encantamento → emoção → experiência → descoberta → transformação → fé",
            "experiencia": "Mel tenta descobrir se a semente já acordou.",
            "descoberta_transformacao": "Ela aprende a esperar sem desistir.",
            "licao_moral_preservada": True,
            "mensagem_biblica_preservada": True,
            "risco_de_desvio": "baixo",
            "novas_cenas_adicionadas": ["tentativa cuidadosa de Mel"],
            "cenas_texto_propostas": [
                {"numero_origem": 1, "texto": "Mel olhou para o vaso e respirou fundo."},
                {"texto": "No dia seguinte, Mel voltou e percebeu que esperar também era cuidar."},
            ],
        }

    proposal = storyteller.gerar_proposta_enriquecimento_roteirista(state, fake_llm)
    assert state["cenas_texto"] == before
    assert proposal["ganho_editorial"] is True
    assert proposal["status"] == "aguardando_aprovacao"
    assert len(proposal["depois"]) == 2
    assert proposal["depois"][0]["pagina_origem"] == 3
    assert proposal["depois"][1]["pagina_origem"] is None
    assert proposal["analise"]["licao_moral_preservada"] is True
    assert proposal["analise"]["mensagem_biblica_preservada"] is True
    assert Path(proposal["arquivo_proposta"]).exists()
    assert book_doctor.sha256(state["original"]["arquivo"]) == state["original"]["sha256"]


def test_storyteller_enrichment_only_applies_after_human_approval(tmp_path):
    state = _state(tmp_path)

    def fake_llm(**kwargs):
        return {
            "ganho_editorial": True,
            "diagnostico_geral": "Pode enriquecer.",
            "motivos": ["Heart Arc"],
            "heart_arc": "mais completo",
            "experiencia": "tentativa",
            "descoberta_transformacao": "espera confiante",
            "licao_moral_preservada": True,
            "mensagem_biblica_preservada": True,
            "risco_de_desvio": "baixo",
            "novas_cenas_adicionadas": [],
            "cenas_texto_propostas": [
                {"numero_origem": 1, "texto": "Mel cuidou do vaso e esperou com carinho."},
            ],
        }

    proposal = storyteller.gerar_proposta_enriquecimento_roteirista(state, fake_llm)
    rejected = storyteller.aplicar_proposta_enriquecimento_roteirista(state, proposal, aprovado=False)
    assert rejected["cenas_texto"] == state["cenas_texto"]
    assert rejected["storyteller_enrichment_aprovado"] is False

    approved = storyteller.aplicar_proposta_enriquecimento_roteirista(state, proposal, aprovado=True)
    assert approved["cenas_texto"][0]["texto"] == "Mel cuidou do vaso e esperou com carinho."
    assert approved["storyteller_enrichment_aprovado"] is True
    assert approved["status"] == "texto_enriquecido_aguardando_revisao_final"
    assert book_doctor.sha256(state["original"]["arquivo"]) == state["original"]["sha256"]


def test_storyteller_blocks_loss_of_moral_or_biblical_message(tmp_path):
    state = _state(tmp_path)

    def fake_llm(**kwargs):
        return {
            "ganho_editorial": True,
            "licao_moral_preservada": False,
            "mensagem_biblica_preservada": True,
            "risco_de_desvio": "baixo",
            "cenas_texto_propostas": [{"numero_origem": 1, "texto": "Outra história."}],
        }

    try:
        storyteller.gerar_proposta_enriquecimento_roteirista(state, fake_llm)
    except RuntimeError as exc:
        assert "lição de moral" in str(exc)
    else:
        raise AssertionError("Perda da lição de moral deveria bloquear a proposta")
