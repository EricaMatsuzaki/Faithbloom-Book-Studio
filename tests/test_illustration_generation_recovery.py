from copy import deepcopy

import pytest

import agents.ilustrador as illustrator
from emotional_visual_binding import approve_book_emotional_map


def story():
    return {
        "colecao": "Teste de engenharia", "titulo": "Lia e a flor",
        "personagens": {"Lia": {
            "nome": "Lia", "papel": "protagonista",
            "descricao_fixa": "Olhos verdes com brilho e laço rosa.",
            "imagem_referencia": "lia-master.png", "aparencia_aprovada": True,
        }},
        "cenas_texto": [{"numero": 1, "personagem_principal": "Lia", "texto": "Lia rega a flor."}],
        "cenas_imagem": [],
    }


def test_resuming_illustration_preserves_approved_image_without_provider_call():
    state = story()
    image = {"numero": 1, "caminho_arquivo": "approved.png", "aprovado": True, "origem": "enviada_pela_autora", "prompt_final": "original"}
    state["cenas_imagem"] = [deepcopy(image)]
    state["cenas_imagem_aprovadas"] = [1]
    before = deepcopy(state)

    def unexpected_call(**kwargs):
        pytest.fail("A cena existente não deve consumir uma nova geração.")

    illustrator.ilustrador_node(state, unexpected_call)
    assert state == before


def test_character_name_variation_uses_matching_master_and_dna(monkeypatch):
    state = story()
    state["cenas_texto"][0]["personagem_principal"] = " LIA "
    state = approve_book_emotional_map(state, reviewed=True, reviewer="Erica")
    calls = []
    monkeypatch.setattr(illustrator, "persist_generation_snapshot", lambda *a, **k: "fb://livros/teste.json", raising=False)
    illustrator.ilustrador_node(state, lambda **kwargs: calls.append(kwargs) or "new.png")
    assert calls[0]["imagem_base"] == "lia-master.png"
    assert "Olhos verdes com brilho e laço rosa." in calls[0]["prompt"]
    assert state["cenas_imagem"][0]["aprovado"] is False


def test_unknown_named_character_does_not_generate_from_another_master():
    state = story()
    state["cenas_texto"][0]["personagem_principal"] = "João"
    calls = []
    with pytest.raises(ValueError, match="referência"):
        illustrator.ilustrador_node(state, lambda **kwargs: calls.append(kwargs) or "wrong.png")
    assert calls == []


def test_interrupted_batch_keeps_first_image_and_durable_checkpoint(monkeypatch):
    state = story()
    state["cenas_texto"].append({"numero": 2, "personagem_principal": "Lia", "texto": "Lia espera."})
    state = approve_book_emotional_map(state, reviewed=True, reviewer="Erica")
    snapshots = []
    monkeypatch.setattr(illustrator, "persist_generation_snapshot", lambda value, **kwargs: snapshots.append(deepcopy(value)) or "fb://livros/teste.json", raising=False)
    attempts = []

    def generate(**kwargs):
        attempts.append(kwargs)
        if len(attempts) == 2:
            raise RuntimeError("Provedor indisponível")
        return "scene-1.png"

    with pytest.raises(RuntimeError, match="Provedor indisponível"):
        illustrator.ilustrador_node(state, generate)
    assert state["cenas_imagem"][0]["caminho_arquivo"] == "scene-1.png"
    assert snapshots[0]["cenas_imagem"][0]["caminho_arquivo"] == "scene-1.png"
    resumed = []
    illustrator.ilustrador_node(state, lambda **kwargs: resumed.append(kwargs) or "scene-2.png")
    assert len(resumed) == 1
    assert [image["caminho_arquivo"] for image in state["cenas_imagem"]] == ["scene-1.png", "scene-2.png"]


def test_explicit_uploaded_replacement_keeps_previous_image_history(monkeypatch):
    state = story()
    state["cenas_imagem"] = [{"numero": 1, "caminho_arquivo": "old.png", "aprovado": True}]
    state["imagens_cenas_enviadas"] = {"1": "author-new.png"}
    monkeypatch.setattr(illustrator, "persist_generation_snapshot", lambda *a, **k: "fb://livros/teste.json", raising=False)
    illustrator.ilustrador_node(state, lambda **kwargs: pytest.fail("Upload dispensa geração."))
    assert state["cenas_imagem"][0]["caminho_arquivo"] == "author-new.png"
    assert state["cenas_imagem_aprovadas"] == [1]
    assert state["historico_imagens_cenas"]["1"][0]["caminho_arquivo"] == "old.png"


def test_single_scene_requires_reference_before_provider_call():
    state = story()
    state["personagens"]["Lia"]["imagem_referencia"] = ""
    calls = []
    with pytest.raises(ValueError, match="referência"):
        illustrator.gerar_cena_unica(state, 1, lambda **kwargs: calls.append(kwargs) or "wrong.png")
    assert calls == []


def test_missing_character_master_requires_human_reference_review_before_any_provider(monkeypatch):
    state = story()
    state["personagens"]["Lia"].update(imagem_referencia="", aparencia_aprovada=False)
    state = approve_book_emotional_map(state, reviewed=True, reviewer="Erica")
    snapshots = []
    monkeypatch.setattr(illustrator, "persist_generation_snapshot", lambda value, **kwargs: snapshots.append(deepcopy(value)))
    calls = []
    with pytest.raises(ValueError, match="referência aprovada"):
        illustrator.ilustrador_node(state, lambda **kwargs: calls.append(kwargs) or "unexpected.png")
    assert calls == [] and snapshots == []
    assert state["personagens"]["Lia"]["imagem_referencia"] == ""
