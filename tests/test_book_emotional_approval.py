"""Legacy/new image generation both require an exact reviewed scene color map."""
from copy import deepcopy
from pathlib import Path
from unittest.mock import Mock

import pytest
from PIL import Image
from streamlit.testing.v1 import AppTest

import agents.ilustrador as illustrator
import armazenamento
import storage_backend as storage
import orchestrator_visual as ov
from emotional_visual_binding import (
    approve_book_emotional_map, prepare_book_emotional_map, require_book_emotional_map,
    persist_book_emotional_map, book_emotional_review_key,
    require_book_source_current,
)


def story():
    return {"titulo": "Mesmo título", "colecao": "Coleção", "book_id": "work-exact-A",
            "personagens": {"Mel": {"nome": "Mel", "papel": "protagonista", "descricao_fixa": "Olhos verdes com estrelas e brilho; pelagem creme.",
                                     "imagem_referencia": "approved-master.png", "aparencia_aprovada": True}},
            "cenas_texto": [{"numero": 7, "texto": "Mel observa o vaso vazio.", "personagem_principal": "Mel", "emocao": "tristeza", "emocao_secundaria": "frustracao",
                             "intensidade_emocional": 2, "transicao_emocional": "tristeza → esperança", "instrucao_emocional": "Azul frio somente no cenário."},
                            {"numero": 11, "texto": "Mel planta uma semente.", "personagem_principal": "Mel", "emocao": "esperanca"}],
            "cenas_imagem": []}


@pytest.fixture
def durable(tmp_path, monkeypatch):
    backend = storage.LocalStorageBackend(str(tmp_path / "data"))
    monkeypatch.setattr(storage, "BACKEND", backend)
    monkeypatch.setattr(armazenamento, "BACKEND", backend)
    cache = tmp_path / "cache"
    cache.mkdir()
    monkeypatch.setattr(storage, "CACHE_DIR", cache)
    return backend


def test_legacy_flags_do_not_approve_and_preparation_never_spends_or_approves():
    state = story()
    state["cenas_texto"][0]["mapa_emocional_aprovado"] = True
    draft = prepare_book_emotional_map(state)
    assert draft["emotional_book_binding"]["approval"] is None
    provider = Mock(return_value="unexpected.png")
    for callback in (lambda: illustrator.ilustrador_node(draft, provider),
                     lambda: illustrator.gerar_cena_unica(draft, 7, provider),
                     lambda: illustrator.criar_variacao_cena(draft, 7, provider)):
        with pytest.raises(PermissionError, match="mapa emocional"):
            callback()
    provider.assert_not_called()
    assert state["cenas_imagem"] == []


def test_reviewed_map_reaches_batch_single_and_variation_without_forced_golden_light(monkeypatch):
    state = approve_book_emotional_map(story(), reviewed=True, reviewer="Erica")
    monkeypatch.setattr(illustrator, "persist_generation_snapshot", lambda *_a, **_kw: None)
    provider = Mock(return_value="candidate.png")
    illustrator.ilustrador_node(state, provider)
    assert provider.call_count == 2
    first = provider.call_args_list[0].kwargs["prompt"]
    for token in ("azul-claro", "Intensidade 2/5", "frustracao", "tristeza → esperança", "Azul frio somente no cenário.", "Olhos verdes com estrelas e brilho"):
        assert token in first
    assert "atmosfera de conto de fadas. Luz dourada e acolhedora." not in first
    original = deepcopy(state["personagens"])
    illustrator.gerar_cena_unica(state, 7, provider, "Mudar o ângulo.")
    illustrator.criar_variacao_cena(state, 7, provider, "Mover só a câmera.")
    assert state["personagens"] == original
    assert "Intensidade 2/5" in provider.call_args.kwargs["prompt"]
    assert state["historico_imagens_cenas"]["7"]


@pytest.mark.parametrize("change", ["story", "identity", "dna", "style", "map", "scene_emotion", "reference"])
def test_any_relevant_revision_invalidates_before_first_provider(change):
    state = approve_book_emotional_map(story(), reviewed=True, reviewer="Erica")
    if change == "story": state["cenas_texto"][0]["texto"] = "Outra narrativa."
    elif change == "identity": state["book_id"] = "work-exact-B"
    elif change == "dna": state["personagens"]["Mel"]["descricao_fixa"] = "Outro DNA"
    elif change == "style": state["style_dna_id"] = "another-style"
    elif change == "map": state["mapa_emocional"][0]["direcao"]["intensidade"] = 5
    elif change == "reference": state["personagens"]["Mel"]["imagem_referencia"] = "another-master.png"
    else: state["cenas_texto"][0]["emocao"] = "alegria"
    provider = Mock()
    with pytest.raises(PermissionError): illustrator.ilustrador_node(state, provider)
    provider.assert_not_called()


def test_existing_images_remain_readable_without_retroactive_map_approval():
    state = story()
    state["cenas_imagem"] = [{"numero": n, "caminho_arquivo": f"existing-{n}.png", "aprovado": True} for n in (7, 11)]
    before = deepcopy(state)
    illustrator.ilustrador_node(state, Mock(side_effect=AssertionError("no new provider")))
    assert state == before


def test_approval_cannot_be_inferred_from_boolean_or_unidentified_reviewer():
    for options in ({"reviewed": False, "reviewer": "Erica"}, {"reviewed": True, "reviewer": ""}):
        with pytest.raises(PermissionError): approve_book_emotional_map(story(), **options)
    state = approve_book_emotional_map(story(), reviewed=True, reviewer="Erica")
    assert [row["numero"] for row in state["mapa_emocional"]] == [7, 11]
    assert state["cenas_texto"][0]["mapa_emocional_aprovado"] is True
    assert require_book_emotional_map(state)["book_id"] == "work-exact-A"


@pytest.mark.parametrize("mismatch", ["book", "saved_reference"])
def test_approval_from_another_same_title_book_never_authorizes_a_provider(mismatch):
    original = story()
    original["storage_path"] = "fb://livros/colecao/exact-A.json"
    state = approve_book_emotional_map(original, reviewed=True, reviewer="Erica")
    if mismatch == "book":
        state["book_id"] = "work-exact-B"
    else:
        state["storage_path"] = "fb://livros/colecao/exact-B.json"
    provider = Mock(return_value="unexpected.png")
    for callback in (lambda: illustrator.ilustrador_node(state, provider),
                     lambda: illustrator.gerar_cena_unica(state, 7, provider),
                     lambda: illustrator.criar_variacao_cena(state, 7, provider)):
        with pytest.raises(PermissionError):
            callback()
    provider.assert_not_called()


def test_private_story_requires_current_separate_consent(monkeypatch):
    state = story()
    state["real_experience"] = {"consent_confirmed": True}
    state = approve_book_emotional_map(state, reviewed=True, reviewer="Erica")
    monkeypatch.setattr(illustrator, "persist_generation_snapshot", lambda *_a, **_kw: None)
    provider = Mock(return_value="candidate.png")
    with pytest.raises(PermissionError, match="consentimento atual"):
        illustrator.ilustrador_node(state, provider)
    provider.assert_not_called()
    illustrator.gerar_cena_unica(state, 7, provider, consent_confirmed=True)
    provider.assert_called_once()
    with pytest.raises(PermissionError): illustrator.criar_variacao_cena(state, 7, provider)
    assert provider.call_count == 1


@pytest.mark.parametrize("marker", [{"contains_personal_data": True}, {"source_data": {"uses_personal_data": True}}, {"origin": "real_life_story"}])
def test_legacy_illustrator_respects_nested_personal_classification(marker):
    state = story()
    state.update(marker)
    state = approve_book_emotional_map(state, reviewed=True, reviewer="Erica")
    provider = Mock(return_value="unexpected.png")
    for callback in (lambda: illustrator.ilustrador_node(state, provider),
                     lambda: illustrator.gerar_cena_unica(state, 7, provider),
                     lambda: illustrator.criar_variacao_cena(state, 7, provider)):
        with pytest.raises(PermissionError, match="consentimento atual"):
            callback()
    provider.assert_not_called()


def test_exact_persistence_reopens_approval_and_does_not_overwrite_same_title_book(durable):
    state = story()
    state["cenas_texto"][0]["emocao_travada"] = True
    state["cenas_texto"][1]["emocao_travada"] = False
    state["storage_path"] = armazenamento.salvar_livro(state)
    other = deepcopy(state)
    other["book_id"] = "work-exact-B"
    other["storage_path"] = armazenamento.salvar_livro(other)
    before = durable.get_bytes(other["storage_path"].removeprefix("fb://"))
    state = approve_book_emotional_map(state, reviewed=True, reviewer="Erica")
    updated = durable.get_json(state["storage_path"].removeprefix("fb://"))
    updated["editorial_notes"] = "Preservar nova nota de outra tela."
    durable.put_json(state["storage_path"].removeprefix("fb://"), updated)
    saved = persist_book_emotional_map(state)
    reopened = durable.get_json(saved["storage_path"].removeprefix("fb://"))
    reopened["storage_path"] = saved["storage_path"]
    assert require_book_emotional_map(reopened)["approval"]["reviewer"] == "Erica"
    assert reopened["editorial_notes"] == updated["editorial_notes"]
    assert [row["emocao_travada"] for row in reopened["cenas_texto"]] == [True, False]
    assert durable.get_bytes(other["storage_path"].removeprefix("fb://")) == before


@pytest.mark.parametrize("approval", [False, None, "yes"])
@pytest.mark.parametrize("operation", ["batch", "single", "variation"])
def test_every_new_generation_requires_explicit_approved_master(approval, operation):
    state = story()
    if approval is None:
        state["personagens"]["Mel"].pop("aparencia_aprovada")
    else:
        state["personagens"]["Mel"]["aparencia_aprovada"] = approval
    state = approve_book_emotional_map(state, reviewed=True, reviewer="Erica")
    if operation == "variation":
        state["cenas_imagem"] = [{"numero": 7, "caminho_arquivo": "current.png", "aprovado": True}]
    before = deepcopy(state)
    provider = Mock(return_value="must-not-exist.png")
    with pytest.raises(ValueError, match="referência"):
        if operation == "batch":
            illustrator.ilustrador_node(state, provider)
        elif operation == "single":
            illustrator.gerar_cena_unica(state, 7, provider)
        else:
            illustrator.criar_variacao_cena(state, 7, provider)
    provider.assert_not_called()
    assert state == before


def test_mutated_original_master_bytes_invalidate_after_reopen(durable, tmp_path):
    image = tmp_path / "master.png"
    Image.new("RGB", (12, 12), "green").save(image)
    state = story()
    state["personagens"]["Mel"]["imagem_referencia"] = str(image)
    state = approve_book_emotional_map(state, reviewed=True, reviewer="Erica")
    saved = persist_book_emotional_map(state)
    reopened = armazenamento.carregar_livro("", saved["storage_path"].removeprefix("fb://"))
    reopened["storage_path"] = saved["storage_path"]
    require_book_emotional_map(reopened)
    # Alter the actual referenced media bytes, rather than a display/cache label.
    reference = reopened["personagens"]["Mel"]["imagem_referencia"]
    Image.new("RGB", (12, 12), "blue").save(reference)
    with pytest.raises(PermissionError): require_book_emotional_map(reopened)


def test_emotional_master_fingerprint_respects_local_tenant_boundary(tmp_path, monkeypatch):
    import saas_access as access
    master = tmp_path / "outside-tenant.png"
    Image.new("RGB", (12, 12), "green").save(master)
    state = story()
    state["personagens"]["Mel"]["imagem_referencia"] = str(master)
    state = approve_book_emotional_map(state, reviewed=True, reviewer="Erica")
    monkeypatch.setenv("FAITHBLOOM_ACCESS_MODE", "multi_tenant")
    monkeypatch.setenv("FAITHBLOOM_OIDC_ISSUERS", "https://identity.example")
    monkeypatch.delenv("FAITHBLOOM_ACCESS_ROLES", raising=False)
    actor = access.actor_from_trusted_claims({"authenticated": True, "iss": "https://identity.example", "sub": "emotional-account-a"})
    provider = Mock(return_value="unexpected.png")
    with access.access_context(actor):
        with pytest.raises(access.AccessDenied, match="fora da conta"):
            illustrator.gerar_cena_unica(state, 7, provider)
    provider.assert_not_called()


@pytest.mark.parametrize("operation", ["batch", "single", "variation"])
@pytest.mark.parametrize("changed", ["story", "dna", "style", "map", "approval"])
def test_durable_book_revision_blocks_legacy_generation_and_autosave(durable, monkeypatch, operation, changed):
    state = persist_book_emotional_map(approve_book_emotional_map(story(), reviewed=True, reviewer="Erica"))
    if operation == "variation":
        state["cenas_imagem"] = [{"numero": 7, "caminho_arquivo": "existing.png", "aprovado": True}]
    path = state["storage_path"].removeprefix("fb://")
    saved = durable.get_json(path)
    if changed == "story": saved["cenas_texto"][0]["texto"] = "Uma narrativa nova salva em outra tela."
    elif changed == "dna": saved["personagens"]["Mel"]["descricao_fixa"] = "DNA aprovado novo"
    elif changed == "style": saved["style_dna"] = {"nome": "Outro estilo", "status": "oficial", "regras": {"rendering": "aquarela"}}
    elif changed == "map": saved["mapa_emocional"][0]["direcao"]["intensidade"] = 5
    else: saved.pop("emotional_book_binding")
    durable.put_json(path, saved)
    before = durable.get_bytes(path)
    snapshot = Mock()
    monkeypatch.setattr(illustrator, "persist_generation_snapshot", snapshot)
    provider = Mock(return_value="must-not-exist.png")
    with pytest.raises(PermissionError):
        if operation == "batch": illustrator.ilustrador_node(state, provider)
        elif operation == "single": illustrator.gerar_cena_unica(state, 7, provider)
        else: illustrator.criar_variacao_cena(state, 7, provider)
    provider.assert_not_called()
    snapshot.assert_not_called()
    assert durable.get_bytes(path) == before


def test_source_freshness_ignores_image_checkpoints_but_not_book_identity(durable, monkeypatch):
    state = persist_book_emotional_map(approve_book_emotional_map(story(), reviewed=True, reviewer="Erica"))
    path = state["storage_path"].removeprefix("fb://")
    saved = durable.get_json(path)
    saved["historico_imagens_cenas"] = {"7": [{"caminho_arquivo": "old-candidate.png"}]}
    saved["autosave_last_reason"] = "checkpoint-only"
    durable.put_json(path, saved)
    require_book_source_current(state, require_saved=True)
    provider = Mock(return_value="candidate.png")
    snapshots = []
    monkeypatch.setattr(illustrator, "persist_generation_snapshot", lambda value, **_kw: snapshots.append(deepcopy(value)))
    illustrator.ilustrador_node(state, provider)
    assert provider.call_count == 2 and len(snapshots) == 2
    require_book_source_current(state)
    saved["book_id"] = "other-book"
    durable.put_json(path, saved)
    with pytest.raises(PermissionError): require_book_source_current(state)


@pytest.mark.parametrize("operation", ["batch", "single", "variation"])
def test_actual_approved_style_dna_replaces_default_2d_in_provider_prompt(monkeypatch, operation):
    state = story()
    state["style_dna"] = {"nome": "FaithBloom 3D aprovado", "status": "oficial", "regras": {"rendering": "renderização tridimensional 3D com material acetinado"}}
    state = approve_book_emotional_map(state, reviewed=True, reviewer="Erica")
    if operation == "variation":
        state["cenas_imagem"] = [{"numero": 7, "caminho_arquivo": "existing.png", "aprovado": True}]
    monkeypatch.setattr(illustrator, "persist_generation_snapshot", lambda *_a, **_kw: None)
    provider = Mock(return_value="candidate.png")
    if operation == "batch": illustrator.ilustrador_node(state, provider)
    elif operation == "single": illustrator.gerar_cena_unica(state, 7, provider)
    else: illustrator.criar_variacao_cena(state, 7, provider)
    for call in provider.call_args_list:
        prompt = call.kwargs["prompt"]
        assert "FaithBloom 3D aprovado" in prompt and "renderização tridimensional 3D com material acetinado" in prompt
        assert "Ilustração digital 2D" not in prompt
        assert any(row["direcao"]["cor_principal"] in prompt for row in state["mapa_emocional"])
        assert "estrelas" in prompt


def test_canonical_style_id_is_resolved_and_later_rule_changes_require_new_review(durable):
    style = {"id": "style-approved", "nome": "3D Oficial", "status": "oficial", "usos_permitidos": ["story"], "regras": {"rendering": "3D acetinado"}}
    durable.put_json("style_dna/style-approved.json", style)
    state = story()
    state["style_dna_id"] = style["id"]
    state = approve_book_emotional_map(state, reviewed=True, reviewer="Erica")
    provider = Mock(return_value="candidate.png")
    illustrator.gerar_cena_unica(state, 7, provider)
    assert "3D Oficial" in provider.call_args.kwargs["prompt"]
    assert "3D acetinado" in provider.call_args.kwargs["prompt"]
    style["regras"]["rendering"] = "Novo rendering de aquarela"
    durable.put_json("style_dna/style-approved.json", style)
    with pytest.raises(PermissionError): illustrator.gerar_cena_unica(state, 7, provider)
    assert provider.call_count == 1


def test_declared_missing_style_never_falls_back_to_generic_2d(durable):
    state = story()
    state["style_dna_id"] = "missing-official-style"
    with pytest.raises(PermissionError, match="Style DNA"):
        approve_book_emotional_map(state, reviewed=True, reviewer="Erica")


def test_empty_story_cannot_be_approved_but_false_can_clear_legacy_state():
    with pytest.raises(ValueError, match="texto da história"):
        ov.approve_story({"id": "empty", "story_text": " "})


def test_page17_requires_explicit_review_and_keeps_nonsequential_scene_identity(durable, monkeypatch):
    import painel_visual
    monkeypatch.setattr(painel_visual, "_sidebar_page_link", lambda *_a, **_kw: None)
    state = story()
    state["storage_path"] = armazenamento.salvar_livro(state)
    root = Path(__file__).resolve().parents[1]
    app = AppTest.from_file(root / "pages/17_🎭_Emotional_Color_Director.py")
    app.session_state["state"] = state
    app.run(timeout=15)
    assert not app.exception
    scene_labels = [item.value for item in app.markdown if item.value.startswith("### Cena ")]
    assert scene_labels == ["### Cena 07", "### Cena 11"]
    save = next(x for x in app.button if x.label == "💾 Aplicar e salvar este mapa no livro ativo")
    assert save.disabled
    next(x for x in app.text_input if x.label == "Responsável pela revisão emocional").set_value("Erica")
    next(x for x in app.checkbox if x.label == "Revisei todas as cenas, a direção emocional e a preservação dos Masters").check().run(timeout=15)
    next(x for x in app.button if x.label == "💾 Aplicar e salvar este mapa no livro ativo").click().run(timeout=15)
    assert not app.exception and not app.error
    saved = app.session_state["state"]
    assert [row["numero"] for row in saved["cenas_texto"]] == [7, 11]
    require_book_emotional_map(saved)


@pytest.mark.parametrize("changed_target", [False, True])
def test_page17_review_handoff_updates_only_exact_return_book(durable, monkeypatch, changed_target):
    import painel_visual
    from emotional_review_ui import begin_emotional_review
    monkeypatch.setattr(painel_visual, "_sidebar_page_link", lambda *_a, **_kw: None)
    state = story()
    state["storage_path"] = armazenamento.salvar_livro(state)
    original_saved = durable.get_bytes(state["storage_path"].removeprefix("fb://"))
    other = {"book_id": "another-open-work", "titulo": "Outro livro", "cenas_texto": [{"numero": 1, "texto": "Outro texto."}]}
    session = {"resume_book": state, "state": deepcopy(other)}
    begin_emotional_review(session, "resume_book", "pages/2_📚_Retomar_Livro.py")
    root = Path(__file__).resolve().parents[1]
    app = AppTest.from_file(root / "pages/17_🎭_Emotional_Color_Director.py")
    for key, value in session.items():
        app.session_state[key] = value
    app.run(timeout=15)
    assert not app.exception
    next(x for x in app.text_input if x.label == "Responsável pela revisão emocional").set_value("Erica")
    next(x for x in app.checkbox if x.label == "Revisei todas as cenas, a direção emocional e a preservação dos Masters").check().run(timeout=15)
    if changed_target:
        app.session_state["resume_book"] = deepcopy(other)
    next(x for x in app.button if x.label == "💾 Aplicar e salvar este mapa no livro ativo").click().run(timeout=15)
    assert not app.exception
    assert app.session_state["state"] == other
    if changed_target:
        assert app.error
        assert durable.get_bytes(state["storage_path"].removeprefix("fb://")) == original_saved
        assert app.session_state["resume_book"] == other
    else:
        assert not app.error
        approved = app.session_state["resume_book"]
        require_book_emotional_map(approved)
        assert approved["book_id"] == state["book_id"]
        assert approved["storage_path"] == state["storage_path"]
