from copy import deepcopy
from pathlib import Path
from unittest.mock import Mock

from PIL import Image
import pytest

import armazenamento
import character_universe
import orchestrator_visual as ov
import storage_backend as storage
import visual_execution as ve
from asset_library import get_asset, update_asset
from emotional_visual_binding import prepare_emotional_binding, approve_emotional_binding


def image_file(tmp_path, name, color):
    path = tmp_path / name
    Image.new("RGB", (40, 30), color).save(path)
    return str(path)


def concepts():
    return {"ideas": [{"id": key, "titulo": f"Ideia {key}", "cenario": f"jardim {key}", "acao": f"Mel brinca {key}",
                       "poses": {"Mel": "sentada"}, "emocao": "curiosa", "psicologia_cores": "pastel verde",
                       "iluminacao": "manhã", "camera": f"ângulo {key}", "por_que_funciona": "leitura clara"} for key in "ABC"]}


@pytest.fixture
def project(tmp_path, monkeypatch):
    backend = storage.LocalStorageBackend(str(tmp_path / "durable"))
    monkeypatch.setattr(storage, "BACKEND", backend)
    monkeypatch.setattr(armazenamento, "BACKEND", backend)
    cache = tmp_path / "cache"
    cache.mkdir()
    monkeypatch.setattr(storage, "CACHE_DIR", cache)
    monkeypatch.setattr(ve.client.gemini_client, "GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(ve.client, "OPENROUTER_API_KEY", None)
    monkeypatch.setattr(ve.client, "PROVEDOR_TEXTO", "auto")
    monkeypatch.setattr(ve, "validar_orcamento", lambda _amount: None)
    master_file = image_file(tmp_path, "master.png", "green")
    asset = armazenamento.salvar_na_galeria(master_file, "Mel original", metadata={"character_id": "unused"})
    update_asset(asset["id"], approved=True, visual_status="COLOR_MASTER", metadata={"character_id": ""})
    character = character_universe.criar_personagem_oficial("Coleção", "Mel", {
        "descricao_master": "Gatinha com olhos verdes brilhantes e estrelas na íris",
        "campos_bloqueados": {"olhos": "verde com brilho e estrelas", "pelagem": "creme"},
        "variaveis_permitidas": ["pose", "acao", "emocao", "cenario"]}, color_master=asset["storage_uri"],
        metadata={"usos_permitidos": ["story"]})
    background = image_file(tmp_path, "world.png", "pink")
    background_asset = armazenamento.salvar_na_galeria(background, "World original", tipo="cenario")
    world = ov.create_world_master("Coleção", "Jardim", "Jardim com fonte e flores", [background_asset["storage_uri"]])
    world = ov.approve_world_master(world["id"])
    plan = ov.create_visual_plan("project-1", "Livro", "Mel brinca no jardim.\n\nMel busca sementes.",
                                 characters=[{"id": "mel", "name": "Mel"}], locations=[{"id": "garden", "name": "Jardim"}],
                                 generation_mode="economy", budget_limit_usd=3)
    plan = ov.approve_story(plan)
    plan = ov.approve_character_candidate(plan, "mel", f"official:{character['id']}", asset["storage_uri"])
    plan = ov.link_location_approval(plan, "garden", world["id"])
    plan = ov.approve_style(plan, {"name": "3D suave com luz delicada"})
    prepared = prepare_emotional_binding(plan)
    plan = ov.save_visual_plan(approve_emotional_binding(plan, prepared["emotional_binding"]["scenes"], reviewed=True, reviewer="Erica"))
    monkeypatch.setattr(ve.client, "chamar_llm", Mock(return_value=concepts()))
    outputs = [image_file(tmp_path, f"generated-{i}.png", (i * 30, 40, 180)) for i in range(8)]
    monkeypatch.setattr(ve.client, "gerar_imagem", Mock(side_effect=outputs))
    return {"plan": plan, "world": world, "character": character, "master": master_file, "master_asset": asset,
            "backend": backend, "outputs": outputs, "tmp_path": tmp_path}


def choose_scene(project, key="1"):
    plan_id = project["plan"]["id"]
    stored = ov.load_visual_plan(plan_id)
    number = 7 if stored.get("source_ref") else int(key)
    op = ve.generate_scene_options(plan_id, key, "Mel observa a fonte.", confirmed=True, source_scene_number=number)
    ve.select_scene_option(plan_id, key, "B", adjustment="Preserve o brilho verde dos olhos.")
    return op


def test_world_abc_real_persistence_candidates_require_explicit_selection(project):
    world = ov.create_world_master("Coleção", "Casa", "Casa de madeira")
    op = ve.generate_world_candidates(project["plan"]["id"], world["id"], confirmed=True)
    stored = ov.load_world_master(world["id"])
    assert len(op["results"]) == len(stored["candidates"]) == 3
    assert stored["status"] == "draft" and stored["reference_assets"] == []
    assert all(not get_asset(x["asset_id"])["approved"] for x in op["results"])
    selected = ve.select_world_candidate(world["id"], op["results"][1]["asset_id"])
    assert selected["status"] == "approved"
    assert selected["reference_assets"] == [op["results"][1]["storage_uri"]]
    assert selected["versions"][-1]["snapshot"]["reference_assets"] == []
    assert len(selected["candidates"]) == 3
    assert ov.load_visual_plan(project["plan"]["id"])["budget_spent_usd"] == pytest.approx(.24)


@pytest.mark.parametrize("failed_write", [1, 4])
def test_failed_governance_snapshot_blocks_visual_provider_and_reservation(project, monkeypatch, failed_write):
    import governance
    from governance_runtime import GovernanceBlocked
    real_save = governance.save_report
    writes = 0
    def save(*args, **kwargs):
        nonlocal writes
        writes += 1
        if writes == failed_write:
            raise OSError("evidence unavailable")
        return real_save(*args, **kwargs)
    monkeypatch.setattr(governance, "save_report", save)
    with pytest.raises(GovernanceBlocked):
        ve.generate_world_candidates(project["plan"]["id"], project["world"]["id"], confirmed=True)
    ve.client.gerar_imagem.assert_not_called()
    assert ve.list_visual_operations(project["plan"]["id"]) == []


def test_visual_completed_operation_retains_four_specialist_snapshots(project):
    import governance
    operation = ve.generate_world_candidates(project["plan"]["id"], project["world"]["id"], confirmed=True)
    receipt = operation["governance_receipt"]
    reports = [governance.load_report(path, workspace_id="pilot")
               for path in receipt["specialist_refs"]]
    assert {item["role_id"] for item in reports} == {
        "ai_governance", "data_governance", "it_governance", "cybersecurity"}
    policy = governance.load_report(receipt["policy_ref"], workspace_id="pilot")
    assert policy["metadata"]["action"] == "visual.world_candidates"
    assert policy["metadata"]["execution_decision"]["allowed"] is True
    assert policy["metadata"]["execution_decision"]["customer_ready"] is False


def test_world_reselection_preserves_original_reference_history(project):
    op = ve.generate_world_candidates(project["plan"]["id"], project["world"]["id"], confirmed=True)
    selected = ve.select_world_candidate(project["world"]["id"], op["results"][0]["asset_id"])
    assert selected["versions"][-1]["snapshot"]["reference_assets"] == project["world"]["reference_assets"]
    assert Path(storage.materializar(project["world"]["reference_assets"][0])).exists()


def test_scene_options_selection_actual_image_reference_and_dna(project):
    choose_scene(project)
    original = Path(project["master"]).read_bytes()
    op = ve.generate_selected_scene(project["plan"]["id"], "1", confirmed=True)
    assert op["status"] == "complete" and len(op["results"]) == 1
    args, kwargs = ve.client.gerar_imagem.call_args
    assert "verde com brilho e estrelas" in args[0]
    assert "3D suave com luz delicada" in args[0]
    assert "jardim B" in args[0]
    assert "Preserve o brilho verde" in args[0]
    assert Path(kwargs["imagem_base"]).read_bytes() == original
    assert len(kwargs["imagens_referencia"]) == 1
    assert kwargs["no_paid_fallback"] and kwargs["no_retries"]
    assert kwargs["strict_provider"] == "gemini"
    assert character_universe.carregar_personagem_oficial(project["character"]["id"])["dna"] == project["character"]["dna"]
    assert get_asset(project["master_asset"]["id"])["visual_status"] == "COLOR_MASTER"
    assert Path(project["master"]).read_bytes() == original
    saved = ov.load_visual_plan(project["plan"]["id"])
    assert len(saved["scene_execution"]["1"]["assets"]) == 1
    assert saved["budget_spent_usd"] == pytest.approx(.11)
    assert saved["budget_actual_usd"] is None


def test_default_repeat_reuses_operation_no_cost_no_generation(project):
    choose_scene(project)
    first = ve.generate_selected_scene(project["plan"]["id"], "1", confirmed=True)
    second = ve.generate_selected_scene(project["plan"]["id"], "1", confirmed=False)
    assert first["id"] == second["id"]
    assert first["results"] == second["results"]
    assert ve.client.gerar_imagem.call_count == 1
    assert second["budget"]["estimated_spent_usd"] == pytest.approx(.11)


def test_batch_blocks_every_call_until_every_scene_selected(project):
    choose_scene(project, "1")
    ve.generate_scene_options(project["plan"]["id"], "2", "Mel busca sementes.", confirmed=True)
    with pytest.raises(PermissionError, match="Escolha e aprove"):
        ve.generate_scene_batch(project["plan"]["id"], ["1", "2"], confirmed=True)
    ve.client.gerar_imagem.assert_not_called()


def test_batch_two_scenes_and_saved_each_asset(project):
    choose_scene(project, "1")
    choose_scene(project, "2")
    op = ve.generate_scene_batch(project["plan"]["id"], ["1", "2"], confirmed=True)
    assert [x["scene_key"] for x in op["results"]] == ["1", "2"]
    stored = ov.load_visual_plan(project["plan"]["id"])
    assert len(stored["scene_execution"]["1"]["assets"]) == 1
    assert len(stored["scene_execution"]["2"]["assets"]) == 1


def test_partial_world_failure_keeps_success_and_uncertain_reservation(project, monkeypatch):
    ve.client.gerar_imagem.side_effect = [project["outputs"][0], RuntimeError("timeout")]
    world = ov.create_world_master("Coleção", "Casa", "Casa de madeira")
    with pytest.raises(ve.VisualExecutionError) as failure:
        ve.generate_world_candidates(project["plan"]["id"], world["id"], confirmed=True)
    op = failure.value.operation
    assert len(op["results"]) == 1
    assert op["items"][1]["state"] == "uncertain"
    assert not op["items"][2]["reserved"]
    assert len(ov.load_world_master(world["id"])["candidates"]) == 1
    assert op["budget"]["estimated_spent_usd"] == pytest.approx(.08)
    assert op["budget"]["reserved_usd"] == pytest.approx(.08)
    # The in-memory lock is irrelevant: the checkpoint alone prevents retry.
    with pytest.raises(ve.VisualExecutionError, match="pode ter chegado"):
        ve.generate_world_candidates(project["plan"]["id"], world["id"], confirmed=True)
    assert ve.client.gerar_imagem.call_count == 2
    reconciled = ve.reconcile_visual_attempt(project["plan"]["id"], op["id"], 1, actual_cost_usd=0, confirmed=True)
    assert reconciled["budget"]["reserved_usd"] == 0
    ve.client.gerar_imagem.side_effect = [project["outputs"][1]]
    resumed = ve.generate_world_candidates(project["plan"]["id"], world["id"], confirmed=True)
    assert len(resumed["results"]) == 2
    assert ve.client.gerar_imagem.call_count == 3  # Only the third, never-sent candidate.


def test_storage_failure_after_provider_resumes_without_calling_again(project, monkeypatch):
    choose_scene(project)
    real_persist = ve._persist_candidate
    attempts = 0

    def unavailable(*args, **kwargs):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise storage.StorageError("temporarily offline")
        return real_persist(*args, **kwargs)

    monkeypatch.setattr(ve, "_persist_candidate", unavailable)
    with pytest.raises(ve.VisualExecutionError) as failure:
        ve.generate_selected_scene(project["plan"]["id"], "1", confirmed=True)
    assert failure.value.operation["items"][0]["state"] == "raw"
    restored = ve.generate_selected_scene(project["plan"]["id"], "1", confirmed=True)
    assert restored["status"] == "complete"
    assert ve.client.gerar_imagem.call_count == 1
    assert restored["budget"]["estimated_spent_usd"] == pytest.approx(.11)


def test_catalog_saved_but_plan_save_failed_reuses_asset(project, monkeypatch):
    choose_scene(project)
    original_save = ov.save_visual_plan
    failures = 0

    def save_failure(plan):
        nonlocal failures
        if plan.get("scene_execution", {}).get("1", {}).get("assets") and failures == 0:
            failures += 1
            raise storage.StorageError("plan write failed")
        return original_save(plan)

    monkeypatch.setattr(ov, "save_visual_plan", save_failure)
    with pytest.raises(ve.VisualExecutionError):
        ve.generate_selected_scene(project["plan"]["id"], "1", confirmed=True)
    restored = ve.generate_selected_scene(project["plan"]["id"], "1", confirmed=True)
    assert len(restored["results"]) == 1
    assert ve.client.gerar_imagem.call_count == 1


def test_echoed_original_bytes_never_demotes_original_master(project):
    choose_scene(project)
    ve.client.gerar_imagem.side_effect = None
    ve.client.gerar_imagem.return_value = project["master"]
    op = ve.generate_selected_scene(project["plan"]["id"], "1", confirmed=True)
    original = get_asset(project["master_asset"]["id"])
    candidate = get_asset(op["results"][0]["asset_id"])
    assert candidate["id"] != original["id"]
    assert candidate["parent_asset_id"] == original["id"]
    assert original["approved"] and original["visual_status"] == "COLOR_MASTER"
    assert not candidate["approved"]


def test_story_style_or_character_approval_gate_precedes_provider(project):
    plan = ov.approve_story(project["plan"], False)
    with pytest.raises(PermissionError, match="história não aprovada"):
        ve.generate_scene_options(plan["id"], "1", "Mel brinca.", confirmed=True)
    ve.client.chamar_llm.assert_not_called()


def test_unavailable_approved_reference_stops_before_provider(project):
    plan = deepcopy(project["plan"])
    plan["approvals"]["characters"]["mel"]["asset_uri"] = "/missing/master.png"
    ov.save_visual_plan(plan)
    with pytest.raises((ValueError, PermissionError), match="referência|mapa"):
        ve.generate_scene_options(plan["id"], "1", "Mel brinca.", confirmed=True)
    ve.client.chamar_llm.assert_not_called()


def test_changed_style_invalidates_selected_scene(project):
    choose_scene(project)
    ov.approve_style(ov.load_visual_plan(project["plan"]["id"]), {"name": "aquarela"})
    with pytest.raises(PermissionError, match="desatualizada|mapa|estilo"):
        ve.generate_selected_scene(project["plan"]["id"], "1", confirmed=True)
    ve.client.gerar_imagem.assert_not_called()


def test_missing_world_image_blocks_scene_but_can_generate_world_abc(project):
    world = ov.create_world_master("Coleção", "Casa", "Casa de madeira")
    world = ov.approve_world_master(world["id"])
    plan = ov.link_location_approval(project["plan"], "garden", world["id"])
    plan = ov.save_visual_plan(approve_emotional_binding(plan, prepare_emotional_binding(plan)["emotional_binding"]["scenes"], reviewed=True, reviewer="Erica"))
    with pytest.raises(PermissionError, match="ainda não tem imagem"):
        ve.generate_scene_options(plan["id"], "1", "Mel brinca.", confirmed=True)
    ve.client.chamar_llm.assert_not_called()
    assert len(ve.generate_world_candidates(plan["id"], world["id"], confirmed=True)["results"]) == 3


def test_confirmation_budget_and_free_first_do_not_reach_provider(project):
    with pytest.raises(PermissionError, match="Confirme"):
        ve.generate_world_candidates(project["plan"]["id"], project["world"]["id"])
    plan = ov.load_visual_plan(project["plan"]["id"])
    plan["budget_limit_usd"] = .1
    ov.save_visual_plan(plan)
    with pytest.raises(PermissionError, match="ultrapassa"):
        ve.generate_world_candidates(plan["id"], project["world"]["id"], confirmed=True)
    plan["generation_mode"] = "free_first"
    ov.save_visual_plan(plan)
    with pytest.raises(PermissionError, match="certificada como gratuita"):
        ve.generate_world_candidates(plan["id"], project["world"]["id"], confirmed=True)
    ve.client.gerar_imagem.assert_not_called()


def test_project_budget_shared_across_visual_plans(project):
    ve.generate_world_candidates(project["plan"]["id"], project["world"]["id"], confirmed=True)
    second = ov.create_visual_plan("project-1", "Mesmo projeto", "Uma cena aprovada.", generation_mode="economy", budget_limit_usd=.25)
    second = ov.approve_story(second)
    second = ov.approve_style(second, {"name": "3D suave"})
    second = ov.save_visual_plan(approve_emotional_binding(second, prepare_emotional_binding(second)["emotional_binding"]["scenes"], reviewed=True, reviewer="Erica"))
    estimate = ve.estimate_visual_operation(second["id"], quantity=1)
    assert estimate["estimated_spent_usd"] == pytest.approx(.24)
    assert estimate["over_budget"]
    with pytest.raises(PermissionError, match="ultrapassa"):
        ve.generate_world_candidates(second["id"], project["world"]["id"], confirmed=True)
    assert ve.client.gerar_imagem.call_count == 3


def test_reservation_write_failure_prevents_any_provider_call(project, monkeypatch):
    original = ov._save_json

    def broken(path, value):
        if "visual_budgets" in path:
            raise storage.StorageError("ledger unavailable")
        return original(path, value)

    monkeypatch.setattr(ov, "_save_json", broken)
    with pytest.raises(storage.StorageError):
        ve.generate_world_candidates(project["plan"]["id"], project["world"]["id"], confirmed=True)
    ve.client.gerar_imagem.assert_not_called()


def test_budget_read_error_is_not_an_empty_budget(project, monkeypatch):
    original = project["backend"].get_bytes

    def broken(path):
        if "visual_budgets" in path:
            raise storage.StorageError("offline")
        return original(path)

    monkeypatch.setattr(project["backend"], "get_bytes", broken)
    with pytest.raises(ve.VisualExecutionError, match="ler o orçamento"):
        ve.generate_world_candidates(project["plan"]["id"], project["world"]["id"], confirmed=True)
    ve.client.gerar_imagem.assert_not_called()


def test_element_lock_unavailable_never_generates_new_image(project):
    result = ve.execute_element_lock(project["plan"]["id"], "Trocar somente o fundo", mask="mask.png")
    assert not result["available"] and "máscara" in result["reason"]
    ve.client.gerar_imagem.assert_not_called()


def test_lot_limit_is_enforced_before_any_call(project):
    with pytest.raises(Exception, match="Limite de segurança"):
        ve.generate_scene_batch(project["plan"]["id"], [str(i) for i in range(6)], confirmed=True)
    ve.client.gerar_imagem.assert_not_called()


@pytest.mark.parametrize("invalid", [float("nan"), float("inf"), -1])
def test_invalid_project_budget_cannot_bypass_gate(invalid):
    with pytest.raises(ValueError, match="finito"):
        ov.create_visual_plan("test", "Test", budget_limit_usd=invalid)


def test_premium_selects_only_configured_route_and_does_not_claim_actual_price(project, monkeypatch):
    plan = ov.load_visual_plan(project["plan"]["id"])
    plan["generation_mode"] = "premium"
    ov.save_visual_plan(plan)
    estimate = ve.estimate_visual_operation(plan["id"], quantity=3)
    assert estimate["provider"] == "gemini" and estimate["actual_usd"] is None
    monkeypatch.setattr(ve.client, "OPENROUTER_API_KEY", "test-router-key")
    estimate = ve.estimate_visual_operation(plan["id"], quantity=3)
    assert estimate["provider"] == "openrouter" and estimate["resolution"] == "2K"
    assert estimate["estimated_usd"] == pytest.approx(.48)


def bind_book(project, *, same_title=True):
    from editorial_dispatch import content_fingerprint
    old_image = image_file(project["tmp_path"], "old-scene.png", "yellow")
    book = {"titulo": "Livro" if same_title else "Outra obra", "colecao": "Coleção", "book_id": "source-book-1",
            "cenas_texto": [{"numero": 7, "texto": "Mel observa a fonte.", "emocao": "curiosidade"}],
            "cenas_imagem": [{"numero": 7, "caminho_arquivo": old_image, "aprovado": True}], "cenas_imagem_aprovadas": [7]}
    reference = armazenamento.salvar_livro(book)
    book["storage_path"] = reference
    armazenamento.atualizar_livro_salvo(reference, book)
    raw = project["backend"].get_json(reference.removeprefix("fb://"))
    plan = ov.load_visual_plan(project["plan"]["id"])
    plan.update(source_ref=reference, source_fingerprint=content_fingerprint(raw), source_book_id="source-book-1", story_text="Mel observa a fonte.")
    ov.save_visual_plan(plan)
    return raw, reference


def test_apply_author_selected_asset_to_exact_book_preserves_previous_image(project):
    book, reference = bind_book(project)
    plan = ov.load_visual_plan(project["plan"]["id"])
    ov.save_visual_plan(approve_emotional_binding(plan, prepare_emotional_binding(plan)["emotional_binding"]["scenes"], reviewed=True, reviewer="Erica"))
    choose_scene(project)
    op = ve.generate_selected_scene(project["plan"]["id"], "1", confirmed=True)
    original_image = book["cenas_imagem"][0]["caminho_arquivo"]
    before = project["backend"].list("livros")
    applied = ve.apply_scene_asset(project["plan"]["id"], "1", op["results"][0]["asset_id"], scene_number=7, confirmed=True, state=book)
    stored = project["backend"].get_json(reference.removeprefix("fb://"))
    assert project["backend"].list("livros") == before
    assert applied["storage_path"] == reference
    assert stored["cenas_imagem"][0]["numero"] == 7
    assert stored["cenas_imagem"][0]["visual_asset_id"] == op["results"][0]["asset_id"]
    assert stored["cenas_imagem"][0]["aprovado"]
    assert stored["historico_imagens_cenas"]["7"][0]["caminho_arquivo"] == original_image
    assert Path(storage.materializar(original_image)).exists()
    assert get_asset(project["master_asset"]["id"])["visual_status"] == "COLOR_MASTER"
    assert ve.client.gerar_imagem.call_count == 1
    repeated = ve.apply_scene_asset(project["plan"]["id"], "1", op["results"][0]["asset_id"], scene_number=7, confirmed=True)
    assert len(repeated["state"]["historico_imagens_cenas"]["7"]) == 1


def test_apply_rejects_other_open_book_even_with_same_title(project):
    book, reference = bind_book(project)
    plan = ov.load_visual_plan(project["plan"]["id"])
    ov.save_visual_plan(approve_emotional_binding(plan, prepare_emotional_binding(plan)["emotional_binding"]["scenes"], reviewed=True, reviewer="Erica"))
    choose_scene(project)
    op = ve.generate_selected_scene(project["plan"]["id"], "1", confirmed=True)
    other = deepcopy(book)
    other["storage_path"] = armazenamento.salvar_livro(other)
    before = project["backend"].get_bytes(reference.removeprefix("fb://"))
    with pytest.raises(PermissionError, match="outro livro"):
        ve.apply_scene_asset(project["plan"]["id"], "1", op["results"][0]["asset_id"], scene_number=7, confirmed=True, state=other)
    assert project["backend"].get_bytes(reference.removeprefix("fb://")) == before


def test_apply_rejects_changed_saved_source_and_does_not_overwrite(project):
    book, reference = bind_book(project)
    plan = ov.load_visual_plan(project["plan"]["id"])
    ov.save_visual_plan(approve_emotional_binding(plan, prepare_emotional_binding(plan)["emotional_binding"]["scenes"], reviewed=True, reviewer="Erica"))
    choose_scene(project)
    op = ve.generate_selected_scene(project["plan"]["id"], "1", confirmed=True)
    book["cenas_texto"][0]["texto"] = "História revisada pela autora."
    armazenamento.atualizar_livro_salvo(reference, book)
    before = project["backend"].get_bytes(reference.removeprefix("fb://"))
    with pytest.raises(PermissionError, match="conteúdo/DNA"):
        ve.apply_scene_asset(project["plan"]["id"], "1", op["results"][0]["asset_id"], scene_number=7, confirmed=True)
    assert project["backend"].get_bytes(reference.removeprefix("fb://")) == before


def test_apply_requires_explicit_source_number_and_confirmation(project):
    choose_scene(project)
    op = ve.generate_selected_scene(project["plan"]["id"], "1", confirmed=True)
    aid = op["results"][0]["asset_id"]
    with pytest.raises(PermissionError, match="Confirme"):
        ve.apply_scene_asset(project["plan"]["id"], "1", aid, scene_number=7)
    with pytest.raises(PermissionError, match="Vincule"):
        ve.apply_scene_asset(project["plan"]["id"], "1", aid, scene_number=7, confirmed=True)
    bind_book(project)
    with pytest.raises(ValueError, match="exatamente uma cena"):
        ve.apply_scene_asset(project["plan"]["id"], "1", aid, scene_number=1, confirmed=True)


def test_apply_stale_session_never_overwrites_newer_disk_metadata(project):
    book, reference = bind_book(project)
    plan = ov.load_visual_plan(project["plan"]["id"])
    ov.save_visual_plan(approve_emotional_binding(plan, prepare_emotional_binding(plan)["emotional_binding"]["scenes"], reviewed=True, reviewer="Erica"))
    choose_scene(project)
    op = ve.generate_selected_scene(project["plan"]["id"], "1", confirmed=True)
    newer = deepcopy(book)
    newer["editorial_notes"] = "Mudança salva por outra tela."
    armazenamento.atualizar_livro_salvo(reference, newer)
    applied = ve.apply_scene_asset(project["plan"]["id"], "1", op["results"][0]["asset_id"], scene_number=7, confirmed=True, state=book)
    assert applied["state"]["editorial_notes"] == "Mudança salva por outra tela."


def test_different_operation_key_cannot_bypass_uncertain_provider_call(project):
    ve.client.gerar_imagem.side_effect = RuntimeError("timeout")
    with pytest.raises(ve.VisualExecutionError):
        ve.generate_world_candidates(project["plan"]["id"], project["world"]["id"], confirmed=True, operation_key="first")
    with pytest.raises(ve.VisualExecutionError, match="Alterar a chave"):
        ve.generate_world_candidates(project["plan"]["id"], project["world"]["id"], confirmed=True, operation_key="second")
    assert ve.client.gerar_imagem.call_count == 1


def test_reselecting_same_scene_option_does_not_repeat_default_generation(project):
    choose_scene(project)
    ve.generate_selected_scene(project["plan"]["id"], "1", confirmed=True)
    ve.select_scene_option(project["plan"]["id"], "1", "B", adjustment="Preserve o brilho verde dos olhos.")
    ve.generate_selected_scene(project["plan"]["id"], "1", confirmed=True)
    assert ve.client.gerar_imagem.call_count == 1
