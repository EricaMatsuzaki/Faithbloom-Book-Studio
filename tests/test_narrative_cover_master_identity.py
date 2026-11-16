"""Narrative covers retain canonical identity without contacting an image service."""
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from unittest.mock import Mock

import pytest

from agents.capa import gerar_artes_capa, prompt_arte_capa_frontal, prompt_arte_contracapa


def book(tmp_path):
    lia = tmp_path / "lia-original.png"
    mimi = tmp_path / "mimi-original.png"
    lia.write_bytes(b"original-lia-master")
    mimi.write_bytes(b"original-mimi-master")
    return {"titulo": "Uma semente", "personagens": {
        "MIMI": {"nome": "Mimi", "papel": "amiga", "descricao_fixa": "Gatinha creme com olhos verdes e reflexo de coração.",
                 "imagem_referencia": str(mimi), "aparencia_aprovada": True},
        "LIA": {"nome": "Lia", "papel": "protagonista", "descricao_fixa": "Olhos verdes com estrelas e cabelo castanho.",
                "imagem_referencia": str(lia), "aparencia_aprovada": True,
                "dna": {"campos_bloqueados": {"olhos": "Verde-esmeralda, reflexos em estrela e coração.", "laço": "Rosa"}}},
    }}


def assert_dna(prompt):
    assert "Olhos verdes com estrelas" in prompt
    assert "reflexo de coração" in prompt
    assert "Verde-esmeralda, reflexos em estrela e coração" in prompt
    assert "prevalece sobre proporções e estilo genéricos" in prompt
    assert "posição, número e formato dos brilhos/reflexos" in prompt
    assert "sem recolorir a identidade dos personagens" in prompt


@pytest.mark.parametrize("prompt_builder", [prompt_arte_capa_frontal, prompt_arte_contracapa])
def test_both_cover_prompts_receive_all_canonical_character_identity(tmp_path, prompt_builder):
    state = book(tmp_path)
    before = deepcopy(state)
    prompt = prompt_builder(state)
    assert_dna(prompt)
    assert "Ilustração digital 2D" in prompt
    assert state == before


def test_current_image_callback_receives_all_original_masters_on_both_artworks(tmp_path):
    state = book(tmp_path)
    original_characters = deepcopy(state["personagens"])
    hashes = {p["imagem_referencia"]: sha256(Path(p["imagem_referencia"]).read_bytes()).hexdigest()
              for p in state["personagens"].values()}
    calls = []

    def provider(prompt, imagem_base=None, imagens_referencia=None):
        calls.append((prompt, imagem_base, imagens_referencia))
        return "candidate-front.png" if len(calls) == 1 else "candidate-back.png"

    result = gerar_artes_capa(state, provider)
    assert result["arte_capa_frontal"] == "candidate-front.png"
    assert result["arte_contracapa"] == "candidate-back.png"
    assert len(calls) == 2
    for prompt, primary, additional in calls:
        assert_dna(prompt)
        assert primary == original_characters["LIA"]["imagem_referencia"]
        assert additional == [original_characters["MIMI"]["imagem_referencia"]]
    assert state["personagens"] == original_characters
    assert all(sha256(Path(path).read_bytes()).hexdigest() == digest for path, digest in hashes.items())


def test_legacy_two_argument_callback_keeps_primary_master_and_full_textual_dna(tmp_path):
    state = book(tmp_path)
    before = deepcopy(state["personagens"])
    calls = []

    def legacy(prompt, imagem_base=None):
        calls.append((prompt, imagem_base))
        return "legacy-candidate.png"

    gerar_artes_capa(state, legacy)
    assert len(calls) == 2
    for prompt, original in calls:
        assert_dna(prompt)
        assert original == before["LIA"]["imagem_referencia"]
    assert state["personagens"] == before


def test_provider_type_error_is_not_retried_as_a_different_callback_signature(tmp_path):
    state = book(tmp_path)
    before = deepcopy(state)
    provider = Mock(side_effect=TypeError("Synthetic error after request submission"))
    with pytest.raises(TypeError, match="Synthetic error"):
        gerar_artes_capa(state, provider)
    provider.assert_called_once()
    assert state == before


def test_positional_variadic_argument_is_not_mistaken_for_a_reference_keyword(tmp_path):
    state = book(tmp_path)
    calls = []

    def legacy(prompt, imagem_base=None, *imagens_referencia):
        calls.append((prompt, imagem_base, imagens_referencia))
        return "legacy-candidate.png"

    gerar_artes_capa(state, legacy)
    assert len(calls) == 2
    assert all(call[1] == state["personagens"]["LIA"]["imagem_referencia"] and call[2] == () for call in calls)


def test_failed_back_art_keeps_completed_front_and_resumes_only_the_back(tmp_path):
    state = book(tmp_path)
    provider = Mock(side_effect=["front-candidate.png", ""])
    with pytest.raises(ValueError, match="contracapa"):
        gerar_artes_capa(state, provider)
    assert state["arte_capa_frontal"] == "front-candidate.png" and "arte_contracapa" not in state
    retry = Mock(return_value="back-candidate.png")
    gerar_artes_capa(state, retry)
    retry.assert_called_once()
    assert_dna(retry.call_args.args[0])
    assert state["arte_capa_frontal"] == "front-candidate.png"
    assert state["arte_contracapa"] == "back-candidate.png"


def test_already_completed_cover_is_not_generated_again(tmp_path):
    state = {**book(tmp_path), "arte_capa_frontal": "reviewed-front.png", "arte_contracapa": "reviewed-back.png"}
    before = deepcopy(state)
    provider = Mock()
    gerar_artes_capa(state, provider)
    provider.assert_not_called()
    assert state == before


def test_second_original_master_is_deduplicated_before_the_provider_call(tmp_path):
    state = book(tmp_path)
    state["personagens"]["DUPLICATE_MIMI"] = deepcopy(state["personagens"]["MIMI"])
    provider = Mock(side_effect=["front.png", "back.png"])
    gerar_artes_capa(state, provider)
    assert all(call.kwargs["imagens_referencia"] == [state["personagens"]["MIMI"]["imagem_referencia"]]
               for call in provider.call_args_list)


def test_approved_inline_3d_style_reaches_both_covers_without_fixed_2d_instructions(tmp_path):
    state = book(tmp_path)
    state["style_dna"] = {"nome": "FaithBloom 3D aprovado", "status": "oficial",
                          "regras": {"rendering": "renderização tridimensional 3D com material acetinado"}}
    before = deepcopy(state)
    provider = Mock(side_effect=["front-3d.png", "back-3d.png"])
    gerar_artes_capa(state, provider)
    assert provider.call_count == 2
    for call in provider.call_args_list:
        prompt = call.args[0]
        assert "FaithBloom 3D aprovado" in prompt
        assert "renderização tridimensional 3D com material acetinado" in prompt
        assert "Ilustração digital 2D" not in prompt
        assert_dna(prompt)
    assert state["style_dna"] == before["style_dna"] and state["personagens"] == before["personagens"]


def test_covers_resolve_and_use_the_exact_persisted_official_style_id(tmp_path, monkeypatch):
    import style_dna
    from storage_backend import LocalStorageBackend
    backend = LocalStorageBackend(str(tmp_path / "style-storage"))
    monkeypatch.setattr(style_dna, "_json", backend.get_json)
    monkeypatch.setattr(style_dna, "_save_json", backend.put_json)
    official = style_dna.criar_style_dna("3D Oficial da coleção", "Jardim",
        {"rendering": "3D acetinado com texturas macias"}, usos=["story", "cover"])
    state = book(tmp_path)
    state["style_dna_id"] = official["id"]
    state["style_dna"] = {"nome": "INLINE NÃO CANÔNICO", "regras": {"rendering": "2D divergente"}}
    provider = Mock(side_effect=["front.png", "back.png"])
    gerar_artes_capa(state, provider)
    assert provider.call_count == 2
    for call in provider.call_args_list:
        assert official["id"] in call.args[0]
        assert "3D Oficial da coleção" in call.args[0] and "3D acetinado com texturas macias" in call.args[0]
        assert "INLINE NÃO CANÔNICO" not in call.args[0] and "Ilustração digital 2D" not in call.args[0]
    assert backend.get_json(f"style_dna/{official['id']}.json") == official


def test_missing_declared_style_never_silently_falls_back_to_inline_or_fixed_2d(tmp_path, monkeypatch):
    import style_dna
    from storage_backend import LocalStorageBackend
    backend = LocalStorageBackend(str(tmp_path / "style-storage"))
    monkeypatch.setattr(style_dna, "_json", backend.get_json)
    state = book(tmp_path)
    state["style_dna_id"] = "missing-official-style"
    state["style_dna"] = {"nome": "Fallback proibido", "status": "oficial", "regras": {"rendering": "3D"}}
    before = deepcopy(state)
    provider = Mock()
    with pytest.raises(PermissionError, match="Style DNA declarado"):
        gerar_artes_capa(state, provider)
    provider.assert_not_called()
    assert state == before
