import io

import pytest
from PIL import Image

import visual_master_manager as manager
import asset_library
import character_universe as universe
from character_universe import adicionar_referencia, deduplicar_reference_pack, normalizar_dna
from scene_color_controls import build_restoration_prompt, identity_lock
from storage_backend import is_storage_uri, storage_uri
from visual_image_audit import audit_image


def image_bytes(fmt="PNG"):
    out = io.BytesIO()
    Image.new("RGBA", (640, 800), (20, 180, 90, 180)).save(out, fmt)
    return out.getvalue()


def test_objective_audit_separates_identity_and_print_quality():
    result = audit_image(image_bytes(), "mel.png")
    assert result["width_px"] == 640
    assert result["has_alpha"] is True
    assert result["sha256"]
    assert "identity_reference_quality" in result
    assert "final_print_quality" in result
    assert result["ppi"] is None
    assert result["print_readiness"] == "not_assessed"
    assert "tamanho físico final não informado" in result["final_print_quality"]
    assert "%" not in str(result)


def test_identity_lock_and_color_never_change_canonical_traits():
    dna = {"campos_bloqueados": {"olhos": "verdes", "especie": "gatinha"}}
    prompt = build_restoration_prompt("replace_scene", dna=dna, scene="Inverno", color="Mais vibrante")
    assert identity_lock(dna)["enabled"] is True
    assert "olhos" in prompt and "verdes" in prompt
    assert "troque somente o cenario" in prompt
    assert "Nao altere traits canonicos" in prompt


def test_modify_only_has_explicit_preservation_instruction():
    prompt = build_restoration_prompt("modify_only", request="Deixe somente o fundo mais claro")
    for value in ("rosto", "olhos", "pose", "expressao", "enquadramento", "composicao"):
        assert value in prompt


def test_legacy_dna_still_loads_with_safe_defaults():
    dna = normalizar_dna("gatinha creme com olhos verdes")
    assert dna["descricao_master"]
    assert "cenario" in dna["variaveis_permitidas"]


def test_legacy_materialized_master_uri_resolves_asset(monkeypatch):
    import hashlib
    storage_path = "assets/galeria/master-v1.png"
    cache_name = hashlib.sha256(storage_path.encode("utf-8")).hexdigest()[:24] + ".png"
    legacy = {"id": "v1", "storage_uri": f"fb://{storage_path}"}
    monkeypatch.setattr(asset_library, "_all_assets", lambda: [legacy])
    monkeypatch.setattr(asset_library, "get_asset", lambda aid, materialize_file=False: legacy if aid == "v1" else None)
    assert asset_library.get_asset_by_uri(f"/cache/{cache_name}")["id"] == "v1"


def test_storage_uri_compatibility_and_no_secret_constants():
    assert is_storage_uri(storage_uri("assets/mel.png"))
    source = open("visual_master_manager.py", encoding="utf-8").read()
    assert ("s" + "k" + "-") not in source


def test_upload_is_reference_not_master(monkeypatch):
    monkeypatch.setattr(manager, "carregar_personagem_oficial", lambda _pid: {"nome": "Mel", "colecao": "C"})
    monkeypatch.setattr(manager, "salvar_na_galeria", lambda *a, **k: {"id": "original", "storage_uri": "fb://original.png"})
    monkeypatch.setattr(manager, "_set_visual", lambda aid, status, **meta: {"id": aid, "visual_status": status, "approved": False})
    monkeypatch.setattr(manager, "adicionar_referencia", lambda *a, **k: {})
    monkeypatch.setattr(manager, "get_asset", lambda *a, **k: {"id": "original", "visual_status": "REFERENCE", "approved": False, "master_roles": []})
    result = manager.register_upload("mel", "mel.png", image_bytes())
    assert result["visual_status"] == "REFERENCE"
    assert not result["approved"] and not result["master_roles"]


def test_multiple_uploads_keep_independent_categories(monkeypatch):
    recorded = []
    monkeypatch.setattr(manager, "carregar_personagem_oficial", lambda _pid: {"nome": "Mel", "colecao": "C"})
    monkeypatch.setattr(manager, "salvar_na_galeria", lambda *a, **k: {"id": str(len(recorded)), "storage_uri": f"fb://{len(recorded)}.png"})
    monkeypatch.setattr(manager, "_set_visual", lambda *a, **k: {})
    monkeypatch.setattr(manager, "adicionar_referencia", lambda pid, asset, category, *rest: recorded.append(category))
    monkeypatch.setattr(manager, "get_asset", lambda aid, **k: {"id": aid, "visual_status": "REFERENCE"})
    manager.register_upload("mel", "mel_frente.png", image_bytes(), "frente")
    manager.register_upload("mel", "mel_perfil.png", image_bytes(), "perfil")
    manager.register_upload("mel", "mel_corpo.png", image_bytes(), "corpo inteiro")
    assert recorded == ["frente", "perfil", "corpo inteiro"]


def test_candidate_versions_preserve_original_and_group(monkeypatch):
    base = {"id": "original", "version_group": "group", "storage_uri": "fb://original.png"}
    created = []
    monkeypatch.setattr(manager, "persistir_arquivo", lambda path, prefix: f"fb://{path}")
    def fake_version(asset_id, **kwargs):
        item = {"id": f"v{len(created)}", "parent_asset_id": asset_id, "version_group": "group", "storage_uri": kwargs["storage_uri_value"]}
        created.append(item); return item
    monkeypatch.setattr(manager, "create_version", fake_version)
    monkeypatch.setattr(manager, "_set_visual", lambda aid, status, **meta: {**next(x for x in created if x["id"] == aid), "visual_status": status})
    results = manager.create_abc(base["id"], ["a.png", "b.png", "c.png"], transformation="light", prompt="locked")
    assert len(results) == 3
    assert all(x["parent_asset_id"] == "original" and x["version_group"] == "group" for x in results)
    assert base["storage_uri"] == "fb://original.png"


def test_master_and_lineart_require_human_approval(monkeypatch):
    monkeypatch.setattr(manager, "get_asset", lambda *a, **k: {"id": "candidate", "approved": False})
    with pytest.raises(PermissionError):
        manager.promote_master("mel", "candidate", "color_master", confirmed=False)
    with pytest.raises(PermissionError):
        manager.promote_master("mel", "candidate", "line_art_master", confirmed=True)


def test_reference_pack_does_not_promote_master(monkeypatch):
    calls = []
    monkeypatch.setattr(manager, "carregar_personagem_oficial", lambda _pid: {"nome": "Mel", "colecao": "C"})
    monkeypatch.setattr(manager, "salvar_na_galeria", lambda *a, **k: {"id": "ref", "storage_uri": "fb://ref.png"})
    monkeypatch.setattr(manager, "_set_visual", lambda *a, **k: {})
    monkeypatch.setattr(manager, "adicionar_referencia", lambda *a, **k: calls.append(a))
    monkeypatch.setattr(manager, "get_asset", lambda *a, **k: {"id": "ref", "master_roles": []})
    manager.register_upload("mel", "mel.png", image_bytes())
    assert calls and manager.promote_master not in calls


def test_new_master_keeps_old_history(monkeypatch):
    saved = {}
    monkeypatch.setattr(manager, "get_asset", lambda *a, **k: {"id": "new", "approved": True, "storage_uri": "fb://new.png"})
    monkeypatch.setattr(manager, "carregar_personagem_oficial", lambda _pid: {"color_master": "fb://old.png", "metadata": {}})
    monkeypatch.setattr(manager, "get_asset_by_uri", lambda *a, **k: {"id": "old", "storage_uri": "fb://old.png"})
    monkeypatch.setattr(manager, "atualizar_personagem_oficial", lambda pid, value: saved.update(value) or value)
    monkeypatch.setattr(manager, "set_master_role", lambda *a, **k: {})
    monkeypatch.setattr(manager, "update_asset", lambda *a, **k: k)
    manager.promote_master("mel", "new", "color_master", confirmed=True)
    assert saved["color_master"] == "fb://new.png"
    assert saved["metadata"]["master_history"][0]["asset"] == "fb://old.png"


def test_only_new_asset_keeps_current_master_role(monkeypatch):
    roles = {"v1": {"color_master"}, "v2": set()}
    monkeypatch.setattr(manager, "get_asset", lambda aid, **k: {"id": aid, "approved": True, "storage_uri": f"fb://{aid}.png"})
    monkeypatch.setattr(manager, "get_asset_by_uri", lambda *a, **k: None)
    monkeypatch.setattr(manager, "carregar_personagem_oficial", lambda _pid: {
        "color_master": "fb://v1.png", "metadata": {"current_master_asset_ids": {"color_master": "v1"}}
    })
    saved = {}
    monkeypatch.setattr(manager, "atualizar_personagem_oficial", lambda pid, value: saved.update(value) or value)
    monkeypatch.setattr(manager, "set_master_role", lambda aid, role, enabled: roles[aid].add(role) if enabled else roles[aid].discard(role))
    monkeypatch.setattr(manager, "update_asset", lambda aid, **changes: {"id": aid, **changes})
    manager.promote_master("mel", "v2", "color_master", confirmed=True)
    assert "color_master" not in roles["v1"]
    assert roles["v2"] == {"color_master"}
    assert saved["metadata"]["master_history"][0]["asset_id"] == "v1"
    assert saved["metadata"]["current_master_asset_ids"]["color_master"] == "v2"


def test_identity_lock_is_constraint_not_automatic_validation(monkeypatch):
    captured = {}
    monkeypatch.setattr(manager, "persistir_arquivo", lambda *a, **k: "fb://candidate.png")
    monkeypatch.setattr(manager, "create_version", lambda aid, **kwargs: captured.update(kwargs) or {"id": "candidate"})
    monkeypatch.setattr(manager, "_set_visual", lambda aid, status, **meta: {"id": aid, "status": status})
    manager.create_candidate("original", "candidate.png", transformation="light", prompt="IDENTITY LOCK")
    assert captured["metadata"]["visual_identity_validated"] is False
    assert "revisão/aprovação humana" in captured["metadata"]["identity_review_notice"]


def _reference(asset_id, uri=None, **extra):
    value = {
        "id": f"ref-{asset_id}",
        "asset": uri or f"fb://assets/{asset_id}.png",
        "tipo": "outra",
        "metadata": {"asset_library_id": asset_id} if asset_id else {},
    }
    value.update(extra)
    return value


def test_four_unique_references_stay_four_after_repeated_add(monkeypatch):
    document = {"id": "mel", "reference_pack": [], "metadata": {}, "versoes": []}
    monkeypatch.setattr(universe, "_json", lambda path, default: universe.deepcopy(document))
    monkeypatch.setattr(universe, "_save_json", lambda path, value: document.update(universe.deepcopy(value)))
    monkeypatch.setattr(universe, "materializar_assets_em_objeto", lambda value: value)
    def update(_pid, changes):
        document.update(universe.deepcopy(changes))
        return universe.deepcopy(document)
    monkeypatch.setattr(universe, "atualizar_personagem_oficial", update)

    assets = [(f"asset-{index}", f"fb://assets/{index}.png") for index in range(4)]
    for _ in range(2):
        for asset_id, uri in assets:
            adicionar_referencia("mel", uri, metadata={"asset_library_id": asset_id})
    assert len(document["reference_pack"]) == 4


def test_legacy_eleven_entries_normalize_to_four_and_persist(monkeypatch):
    unique = [_reference(str(index)) for index in range(4)]
    legacy = [unique[index % 4] for index in range(11)]
    document = {"id": "mel", "reference_pack": legacy, "metadata": {}}
    saved = []
    monkeypatch.setattr(universe, "_json", lambda path, default: universe.deepcopy(document))
    monkeypatch.setattr(universe, "_save_json", lambda path, value: saved.append(universe.deepcopy(value)))
    monkeypatch.setattr(universe, "materializar_assets_em_objeto", lambda value: value)
    loaded = universe.carregar_personagem_oficial("mel")
    assert len(loaded["reference_pack"]) == 4
    assert len(saved) == 1 and len(saved[0]["reference_pack"]) == 4


def test_reference_dedup_uses_asset_library_id_as_primary_key():
    first = _reference("same", "fb://assets/original.png", origem="upload")
    repeated = _reference("same", "fb://assets/materialized-copy.png", extra_field="useful")
    result = deduplicar_reference_pack([first, repeated])
    assert len(result) == 1
    assert result[0]["asset"] == "fb://assets/original.png"
    assert result[0]["extra_field"] == "useful"


def test_reference_dedup_falls_back_to_storage_uri_for_legacy_entries():
    first = {"storage_uri": "fb://assets/mel.png", "tipo": "frente", "metadata": {}}
    repeated = {"storage_uri": "fb://assets/mel.png", "origem": "legacy", "metadata": {}}
    assert len(deduplicar_reference_pack([first, repeated])) == 1


def test_different_physical_references_are_preserved_and_never_deleted(monkeypatch):
    references = [_reference("a", "fb://assets/a.png"), _reference("b", "fb://assets/b.png")]
    deleted = []
    monkeypatch.setattr(asset_library.BACKEND, "delete", lambda path: deleted.append(path))
    result = deduplicar_reference_pack(references)
    assert len(result) == 2
    assert {item["metadata"]["asset_library_id"] for item in result} == {"a", "b"}
    assert deleted == []
