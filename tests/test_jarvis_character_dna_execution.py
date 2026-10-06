import copy

import jarvis_character_actions as actions
import jarvis_dialogue as dialogue


REQUEST = "Complete o DNA visual do Téo usando o Color Master e as referências já cadastradas."


def _teo_character():
    return {
        "id": "teo-1",
        "nome": "Téo",
        "colecao": "Pequenas Histórias, Grandes Lições",
        "status": "oficial",
        "dna": {
            "descricao_master": "",
            "campos_bloqueados": {
                "olhos": "azuis grandes e brilhantes",
                "especie": "",
                "paleta_base": "",
            },
            "caracteristicas_bloqueadas": "",
            "visual_prompt_master": "",
            "variaveis_permitidas": [],
        },
        "color_master": "fb://teo-master.png",
        "reference_pack": [
            {"id": f"ref-{i}", "asset": f"fb://teo-{i}.png", "metadata": {"asset_library_id": f"asset-{i}"}}
            for i in range(4)
        ],
        "metadata": {
            "current_master_asset_ids": {"color_master": "asset-master-teo"},
            "master_history": [],
        },
        "variacoes": [],
        "versoes": [],
    }


def test_teo_fill_reuses_same_character_master_refs_and_color_master(monkeypatch):
    before = _teo_character()
    state = copy.deepcopy(before)
    calls = []

    monkeypatch.setattr(
        actions,
        "buscar_personagens_por_nome",
        lambda name, incluir_arquivados=False: [
            {"id": "teo-1", "nome": "Téo", "colecao": "Pequenas Histórias, Grandes Lições", "status": "oficial"}
        ],
    )
    monkeypatch.setattr(actions, "carregar_personagem_oficial", lambda pid: copy.deepcopy(state))

    def fake_autofill(pid, *, preferred_asset_id=""):
        calls.append((pid, preferred_asset_id))
        state["dna"]["campos_bloqueados"]["especie"] = "passarinho azul"
        state["dna"]["campos_bloqueados"]["paleta_base"] = "azul celeste, branco e coral suave"
        return copy.deepcopy(state)

    monkeypatch.setattr(actions, "autofill_visual_dna_from_saved_references", fake_autofill)

    result = actions.execute_missing_dna_fill(REQUEST)

    assert calls == [("teo-1", "asset-master-teo")]
    assert result["character_id"] == "teo-1"
    assert result["character_preserved"] is True
    assert result["color_master_preserved"] is True
    assert result["references_preserved"] is True
    assert result["reference_count"] == 4
    assert "especie" in result["filled_fields"]
    assert "paleta_base" in result["filled_fields"]
    assert state["dna"]["campos_bloqueados"]["olhos"] == "azuis grandes e brilhantes"
    assert state["color_master"] == before["color_master"]
    assert state["metadata"]["current_master_asset_ids"]["color_master"] == "asset-master-teo"
    assert state["reference_pack"] == before["reference_pack"]
    assert not hasattr(actions, "criar_personagem_oficial")


def test_teo_fill_fails_closed_when_same_name_is_ambiguous(monkeypatch):
    monkeypatch.setattr(
        actions,
        "buscar_personagens_por_nome",
        lambda name, incluir_arquivados=False: [
            {"id": "teo-1", "nome": "Téo", "colecao": "Coleção A", "status": "oficial"},
            {"id": "teo-2", "nome": "Téo", "colecao": "Coleção B", "status": "oficial"},
        ],
    )
    monkeypatch.setattr(
        actions,
        "autofill_visual_dna_from_saved_references",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("autofill must not run for ambiguous character")),
    )

    try:
        actions.execute_missing_dna_fill(REQUEST)
    except ValueError as exc:
        assert "mais de um Character Master" in str(exc)
    else:
        raise AssertionError("Ambiguous Téo must fail closed")


def test_teo_fill_rejects_any_attempt_to_change_approved_dna(monkeypatch):
    before = _teo_character()
    state = copy.deepcopy(before)

    monkeypatch.setattr(
        actions,
        "buscar_personagens_por_nome",
        lambda name, incluir_arquivados=False: [
            {"id": "teo-1", "nome": "Téo", "colecao": "Pequenas Histórias, Grandes Lições", "status": "oficial"}
        ],
    )
    monkeypatch.setattr(actions, "carregar_personagem_oficial", lambda pid: copy.deepcopy(state))

    def bad_autofill(pid, *, preferred_asset_id=""):
        state["dna"]["campos_bloqueados"]["olhos"] = "verdes"
        state["dna"]["campos_bloqueados"]["especie"] = "passarinho azul"
        return copy.deepcopy(state)

    monkeypatch.setattr(actions, "autofill_visual_dna_from_saved_references", bad_autofill)

    try:
        actions.execute_missing_dna_fill(REQUEST)
    except RuntimeError as exc:
        assert "já aprovado 'olhos' foi alterado" in str(exc)
    else:
        raise AssertionError("Changing approved DNA must be blocked")


def test_jarvis_executes_explicit_teo_fill_without_generic_dialogue_model(monkeypatch):
    result = {
        "status": "completed",
        "character_id": "teo-1",
        "character_name": "Téo",
        "collection": "Pequenas Histórias, Grandes Lições",
        "filled_fields": ["especie", "paleta_base"],
        "remaining_missing_fields": [],
        "reference_count": 4,
        "color_master_preserved": True,
        "references_preserved": True,
        "character_preserved": True,
    }
    monkeypatch.setattr(dialogue, "execute_missing_dna_fill", lambda text: result)
    monkeypatch.setattr(
        dialogue,
        "_post_com_retry",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("generic dialogue model must not run")),
    )

    reply = dialogue.build_natural_reply(
        REQUEST,
        history=[],
        route_result={"project_type": "character_universe"},
    )

    folded = reply.casefold()
    assert "atualizei o dna visual de téo" in folded
    assert "4 referências" in folded
    assert "character master" in folded
    assert "color master" in folded


def test_status_question_does_not_execute_dna_fill(monkeypatch):
    monkeypatch.setattr(
        dialogue,
        "execute_missing_dna_fill",
        lambda text: (_ for _ in ()).throw(AssertionError("status question must not mutate character")),
    )
    reply = dialogue.build_natural_reply(
        "Você já criou o DNA do Téo?",
        history=[],
        route_result={"project_type": "character_universe"},
    )
    assert "não posso afirmar" in reply.casefold()
