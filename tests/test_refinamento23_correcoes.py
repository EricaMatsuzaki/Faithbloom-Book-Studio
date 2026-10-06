from copy import deepcopy

import asset_library
import character_guide as guide


def character():
    return {
        "id": "mel", "nome": "Mel", "colecao": "Jardim",
        "dna": {
            "descricao_master": "gatinha creme",
            "campos_bloqueados": {"especie": "gatinha", "olhos": "verdes"},
            "variaveis_permitidas": ["pose", "acao", "expressao", "emocao", "figurino", "acessorios_temporarios", "cenario", "estacao", "festividade"],
        },
        "metadata": {"usos_permitidos": list(guide.USAGE_LABELS), "looks": []},
        "reference_pack": [], "color_master": "",
    }


def test_character_and_scene_prompts_enforce_no_generated_text():
    free = guide.build_character_free_prompt(character(), "Mel perto do vaso")
    scene = guide.compose_scene_prompt({"poses": {"Mel": "ajoelhada"}}, [character()])
    for prompt in (free, scene):
        assert guide.TEXT_POLICY in prompt
        assert "pseudo-readable" in prompt
        assert "REFERENCE IMAGES MAY CONTAIN TYPOGRAPHY" in prompt


def test_text_and_cover_references_are_skipped_when_clean_exists(monkeypatch):
    assets = {
        "cover": {"id": "cover", "caminho_arquivo": "/tmp/cover.png", "tipo": "capa", "metadata": {"contains_text": True, "usage": "cover"}},
        "clean": {"id": "clean", "caminho_arquivo": "/tmp/clean.png", "tipo": "personagem", "metadata": {"contains_text": False, "asset_role": "character_reference"}},
    }
    monkeypatch.setattr(guide, "get_asset", lambda aid, materialize_file=True: deepcopy(assets.get(aid)))
    monkeypatch.setattr(guide, "get_asset_by_uri", lambda value: None)
    monkeypatch.setattr(guide, "_materialize_if_possible", lambda value: value)
    p = character()
    p["reference_pack"] = [
        {"asset_library_id": "cover", "metadata": {}},
        {"asset_library_id": "clean", "metadata": {}},
    ]
    assert guide.character_reference_paths(p) == ["/tmp/clean.png"]


def test_cover_is_art_and_reserves_space_without_requesting_title():
    prompt = guide.build_character_free_prompt(character(), "jardim de primavera", usage="cover", reserve_title_space="top")
    assert "COVER ART" in prompt
    assert "reserve_title_space=top" in prompt
    assert "never render the book title" in prompt
    assert "Leave intentional negative space" in prompt


def test_gallery_open_selects_inline_asset():
    state = {}
    assert guide.select_gallery_asset(state, "asset-1") == "asset-1"
    assert state["gallery_open_asset_id"] == "asset-1"


def test_atomic_archive_and_restore_preserve_asset_identity(monkeypatch):
    original = {
        "id": "a1", "nome": "Mel", "status": "active", "visual_status": "APPROVED_VARIATION",
        "approved": True, "storage_uri": "fb://assets/a1.png", "version_group": "vg", "parent_asset_id": "p",
        "metadata": {"visual_status": "APPROVED_VARIATION"},
    }
    state = [asset_library.normalize_asset(original)]
    monkeypatch.setattr(asset_library, "_all_assets", lambda write_back=False: deepcopy(state))
    monkeypatch.setattr(asset_library, "_salvar_indice_galeria", lambda items: state.__setitem__(slice(None), deepcopy(items)))
    archived = asset_library.set_archived("a1", True)
    assert archived["status"] == "archived" and archived["visual_status"] == "ARCHIVED"
    for key in ("id", "storage_uri", "version_group", "parent_asset_id"):
        assert archived[key] == original[key]
    restored = asset_library.set_archived("a1", False)
    assert restored["status"] == "active"
    assert restored["visual_status"] == "APPROVED_VARIATION"
    assert len(state) == 1 and restored["id"] == "a1"


def test_character_guide_create_and_edit_use_canonical_entity(monkeypatch):
    state = {}
    def create(collection, name, dna, metadata=None, **kwargs):
        state.update({"id": "same-id", "colecao": collection, "nome": name, "dna": dna, "metadata": metadata or {}, "reference_pack": []})
        return deepcopy(state)
    monkeypatch.setattr(guide, "criar_personagem_oficial", create)
    monkeypatch.setattr(guide, "carregar_personagem_oficial", lambda pid: deepcopy(state) if pid == "same-id" else {})
    monkeypatch.setattr(guide, "atualizar_personagem_oficial", lambda pid, changes: state.update(changes) or deepcopy(state))
    created = guide.create_character_guide(collection="Jardim", name="Mel", locked_identity={"olhos": "verdes"})
    edited = guide.update_character_guide("same-id", collection="Jardim", name="Mel Flor", locked_identity={"olhos": "verdes grandes"})
    assert created["id"] == edited["id"] == "same-id"
    assert edited["nome"] == "Mel Flor"
    assert edited["dna"]["campos_bloqueados"]["olhos"] == "verdes grandes"


def test_looks_and_approval_still_work_after_edit(monkeypatch):
    state = character()
    monkeypatch.setattr(guide, "carregar_personagem_oficial", lambda _pid: deepcopy(state))
    monkeypatch.setattr(guide, "atualizar_personagem_oficial", lambda _pid, changes: state.update(changes) or deepcopy(state))
    look = guide.save_look("mel", "Natal", figurino="cachecol")
    assert look["nome"] == "Natal" and state["metadata"]["looks"]
    candidate = {"id": "candidate", "visual_status": guide.VARIATION_STATUS, "approved": False, "master_roles": []}
    monkeypatch.setattr(guide, "get_asset", lambda *args, **kwargs: deepcopy(candidate))
    monkeypatch.setattr(guide, "update_asset", lambda aid, **changes: {**candidate, **changes})
    approved = guide.approve_asset_as_variation("candidate")
    assert approved["id"] == "candidate"
    assert approved["visual_status"] == "APPROVED_VARIATION"
    assert approved.get("master_roles") == []

