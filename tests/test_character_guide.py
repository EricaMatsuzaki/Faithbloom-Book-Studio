from copy import deepcopy

import character_guide as guide


def _character():
    return {
        "id": "mel-1",
        "nome": "Mel",
        "colecao": "Pequenas Histórias, Grandes Lições",
        "dna": {
            "descricao_master": "gatinha filhote creme/pêssego, olhos verdes grandes, identidade infantil",
            "campos_bloqueados": {"especie": "gatinha filhote", "olhos": "verdes grandes", "paleta_base": "creme/pêssego"},
            "variaveis_permitidas": ["pose", "acao", "expressao", "emocao", "figurino", "acessorios_temporarios", "cenario", "estacao", "festividade"],
        },
        "metadata": {"usos_permitidos": ["story", "coloring", "activity", "cover"], "looks": []},
        "reference_pack": [],
        "color_master": "",
    }


def test_free_prompt_preserves_identity_and_limits_color_psychology():
    p = _character()
    prompt = guide.build_character_free_prompt(
        p,
        "Natal com cachecol vermelho e laço vermelho, sorrindo na neve.",
        usage="story",
        variables={"figurino": "cachecol vermelho", "acessorios_temporarios": "laço vermelho", "cenario": "rua nevada", "emocao": "alegre"},
    )
    assert "CHARACTER DNA BLOQUEADO" in prompt
    assert "cachecol vermelho" in prompt
    assert "rua nevada" in prompt
    assert "nunca altere as cores canônicas" in prompt
    assert "Sem texto" in prompt


def test_neutral_base_is_candidate_not_automatic_master():
    prompt = guide.build_neutral_base_prompt(_character())
    assert "BASE OFICIAL NEUTRA candidata" in prompt
    assert "MASTER_CANDIDATE" in prompt
    assert "não é Master" in prompt


def test_scene_ideas_normalize_three_concepts():
    raw = {"ideas": [
        {"id": "A", "titulo": "Curiosa", "cenario": "jardim", "acao": "Mel olha o vaso", "poses": {"Mel": "ajoelhada"}, "emocao": "curiosidade", "psicologia_cores": "amarelo e verde"},
        {"id": "B", "titulo": "Cinematográfica", "cenario": "jardim ao amanhecer", "pose": "deitada"},
        {"id": "C", "titulo": "Humor", "cenario": "canteiro", "pose": "Téo escutando junto"},
    ]}
    ideas = guide._normalize_scene_ideas(raw, 3)
    assert [x["id"] for x in ideas] == ["A", "B", "C"]
    assert ideas[0]["poses"]["Mel"] == "ajoelhada"
    assert ideas[1]["poses"]["geral"] == "deitada"


def test_save_look_upserts_by_name(monkeypatch):
    state = _character()

    def load(_pid):
        return deepcopy(state)

    def update(_pid, changes):
        if "metadata" in changes:
            state["metadata"] = deepcopy(changes["metadata"])
        return deepcopy(state)

    monkeypatch.setattr(guide, "carregar_personagem_oficial", load)
    monkeypatch.setattr(guide, "atualizar_personagem_oficial", update)

    first = guide.save_look("mel-1", "Natal — Inverno", figurino="cachecol vermelho", acessorios_temporarios="laço vermelho", estacao="Inverno", festividade="Natal", usos=["story", "cover"])
    second = guide.save_look("mel-1", "Natal — Inverno", figurino="cachecol vermelho mais grosso", acessorios_temporarios="laço vermelho", estacao="Inverno", festividade="Natal", usos=["story"])

    assert first["id"] == second["id"]
    assert len(state["metadata"]["looks"]) == 1
    assert state["metadata"]["looks"][0]["figurino"] == "cachecol vermelho mais grosso"


def test_approve_variation_is_in_place(monkeypatch):
    asset = {"id": "asset-1", "visual_status": guide.VARIATION_STATUS, "approved": False, "storage_uri": "fb://assets/example.png", "metadata": {}}
    updated = {}
    monkeypatch.setattr(guide, "get_asset", lambda _aid, materialize_file=False: deepcopy(asset))

    def update(_aid, **changes):
        updated.update(changes)
        out = deepcopy(asset)
        out.update(changes)
        return out

    monkeypatch.setattr(guide, "update_asset", update)
    result = guide.approve_asset_as_variation("asset-1")
    assert result["id"] == "asset-1"
    assert result["visual_status"] == "APPROVED_VARIATION"
    assert result["approved"] is True
    assert updated["metadata"]["approval"] == "human"
