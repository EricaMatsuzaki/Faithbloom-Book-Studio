import copy

import jarvis_character_auto_setup as auto


def _file(name="teo.png", marker="a"):
    return {
        "name": name,
        "kind": "image",
        "mime_type": "image/png",
        "data": marker.encode("utf-8"),
        "sha256": marker * 8,
    }


def _analysis(index=0):
    return {
        "descricao_master": "Passarinho azul fofo e infantil.",
        "campos_bloqueados": {
            "especie": "passarinho azul filhote",
            "olhos": "grandes, azuis e brilhantes",
            "paleta_base": "azul claro com ventre mais claro",
        },
        "caracteristicas_bloqueadas": "corpo arredondado, olhos grandes e bico pequeno",
        "visual_prompt_master": "passarinho azul infantil em fundo neutro",
        "variaveis_permitidas": ["pose", "expressao", "cenario"],
        "melhor_referencia_indice": index,
        "melhor_referencia_motivo": "frente limpa e identidade clara",
        "resumo_visual": "Passarinho azul redondinho com olhos grandes.",
    }


def test_infer_character_name_and_known_collection_from_natural_sentence():
    result = auto.infer_character_context(
        "Esse é o personagem Téo da Coleção Pequenas Histórias, Grandes Lições e quero salvar tudo.",
        ["Pequenas Histórias, Grandes Lições", "QA STORAGE"],
    )
    assert result["character_name"] == "Téo"
    assert result["target_collection"] == "Pequenas Histórias, Grandes Lições"


def test_merge_visual_dna_fills_missing_without_overwriting_locked_traits():
    existing = {
        "descricao_master": "Identidade aprovada",
        "campos_bloqueados": {"olhos": "verdes oficiais"},
        "caracteristicas_bloqueadas": "",
        "visual_prompt_master": "",
        "variaveis_permitidas": [],
    }
    merged = auto.merge_visual_dna(existing, _analysis())
    assert merged["descricao_master"] == "Identidade aprovada"
    assert merged["campos_bloqueados"]["olhos"] == "verdes oficiais"
    assert merged["campos_bloqueados"]["especie"] == "passarinho azul filhote"
    assert merged["visual_prompt_master"]
    assert merged["auto_visual_analysis"]["source"] == "jarvis_character_auto_setup"


def test_prepare_auto_setup_reuses_existing_character_and_does_not_duplicate(monkeypatch):
    monkeypatch.setattr(auto, "listar_personagens_oficiais", lambda collection=None, incluir_arquivados=False: [
        {"id": "teo-1", "nome": "Téo", "colecao": "Pequenas Histórias, Grandes Lições", "status": "oficial"}
    ] if collection else [])
    monkeypatch.setattr(auto, "buscar_personagens_por_nome", lambda name, incluir_arquivados=False: [
        {"id": "teo-1", "nome": "Téo", "colecao": "Pequenas Histórias, Grandes Lições", "status": "oficial"}
    ])
    monkeypatch.setattr(auto, "carregar_personagem_oficial", lambda pid: {
        "id": pid,
        "nome": "Téo",
        "colecao": "Pequenas Histórias, Grandes Lições",
        "dna": {},
        "metadata": {},
        "color_master": "",
    })
    monkeypatch.setattr(auto, "analyze_character_images", lambda *args, **kwargs: _analysis())

    plan = auto.prepare_auto_setup(
        {"id": "handoff-1", "request": "Esse é o personagem Téo.", "files": [_file()]},
        character_name="Téo",
        target_collection="Pequenas Histórias, Grandes Lições",
    )

    assert plan["operation"] == "update"
    assert plan["character_id"] == "teo-1"
    assert plan["will_promote_color_master"] is True
    assert plan["reference_count"] == 1


def test_execute_auto_setup_creates_reference_pack_color_master_and_dna(monkeypatch):
    state = {
        "id": "",
        "nome": "",
        "colecao": "",
        "dna": {},
        "metadata": {},
        "color_master": "",
    }

    def create(collection, name, dna, metadata=None, **kwargs):
        state.update({
            "id": "teo-new",
            "nome": name,
            "colecao": collection,
            "dna": copy.deepcopy(dna),
            "metadata": copy.deepcopy(metadata or {}),
            "color_master": "",
        })
        return copy.deepcopy(state)

    def load(pid):
        return copy.deepcopy(state) if pid == "teo-new" else {}

    def update(pid, values):
        state.update(copy.deepcopy(values))
        return copy.deepcopy(state)

    uploaded = []

    def register(pid, filename, data, category="outra"):
        asset = {"id": f"asset-{len(uploaded) + 1}", "storage_uri": f"fb://{filename}"}
        uploaded.append(asset)
        return asset

    def promote(pid, asset_id, confirmed=False):
        assert confirmed is True
        state["color_master"] = f"fb://master/{asset_id}.png"
        return {"id": asset_id}

    monkeypatch.setattr(auto, "criar_personagem_oficial", create)
    monkeypatch.setattr(auto, "carregar_personagem_oficial", load)
    monkeypatch.setattr(auto, "atualizar_personagem_oficial", update)
    monkeypatch.setattr(auto, "register_upload", register)
    monkeypatch.setattr(auto, "promote_reference_color_master", promote)

    plan = {
        "ready": True,
        "handoff_id": "handoff-2",
        "character_name": "Téo",
        "target_collection": "Pequenas Histórias, Grandes Lições",
        "character_id": "",
        "operation": "create",
        "files": [_file("teo-1.png", "a"), _file("teo-2.png", "b")],
        "analysis": _analysis(index=1),
        "dna": auto.merge_visual_dna({}, _analysis(index=1)),
        "best_reference_index": 1,
    }

    result = auto.execute_auto_setup(plan, confirmed=True)

    assert result["character_id"] == "teo-new"
    assert result["references_added"] == 2
    assert result["color_master_asset_id"] == "asset-2"
    assert result["dna_filled"] is True
    assert state["color_master"]
    assert state["dna"]["campos_bloqueados"]["especie"] == "passarinho azul filhote"


def test_execute_auto_setup_requires_single_explicit_approval():
    try:
        auto.execute_auto_setup({"ready": True}, confirmed=False)
    except PermissionError as exc:
        assert "Aprovacao humana" in str(exc)
    else:
        raise AssertionError("Auto-Setup nao pode persistir sem aprovacao humana")
