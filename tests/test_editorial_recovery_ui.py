"""Real author controls recover the exact saved product without paid retries."""
from copy import deepcopy
import json
import os
from pathlib import Path
import socket
from unittest.mock import Mock

import pytest
from streamlit.testing.v1 import AppTest

import ai_provider_router
import armazenamento
import editorial_dispatch as dispatch
import editorial_generation_runtime as runtime
import editorial_products as studio
import painel_visual
import saas_access as access
import storage_backend as storage

ROOT = Path(__file__).resolve().parents[1]


def response(**_kwargs):
    return {"title": "Observar e cuidar", "objectives": ["Praticar o cuidado com uma flor"],
            "source_refs": [], "blocks": [{"label": "Abertura", "text": "Observe uma flor e conte como você cuidaria dela."}]}


@pytest.fixture
def saved(tmp_path, monkeypatch):
    backend = storage.LocalStorageBackend(str(tmp_path / "durable"))
    monkeypatch.setattr(storage, "BACKEND", backend)
    monkeypatch.setattr(armazenamento, "BACKEND", backend)
    cache = tmp_path / "cache"
    cache.mkdir()
    monkeypatch.setattr(storage, "CACHE_DIR", cache)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(painel_visual, "_sidebar_page_link", lambda *_a, **_k: None)
    monkeypatch.setattr(ai_provider_router, "provider_status", lambda **_: {"gemini": True, "groq": False, "openrouter": False})
    paid = Mock(side_effect=response)
    monkeypatch.setattr(ai_provider_router, "chamar_llm", paid)
    monkeypatch.setattr(dispatch, "_strict_llm", paid)
    run = dispatch.initialize_specialist(dispatch.create_editorial_run("other", "Livro para conferir", "Cuidar das flores",
        custom_blocks=["Abertura"], unit_count=1)["id"])
    return {"backend": backend, "run": run, "source": studio.load_product(run["source_ref"]), "paid": paid}


def widget(app, kind, label):
    return next(item for item in getattr(app, kind) if item.label == label)


def app_for(saved, target):
    if target == "native":
        app = AppTest.from_file(str(ROOT / "pages/55_📚_Produtos_Editoriais.py"))
        app.session_state["editorial_product_id"] = saved["run"]["source_ref"]
    else:
        app = AppTest.from_string("from orchestrator_editorial import build_editorial_route\n"
            "from orchestrator_execution_ui import render_editorial_execution\n"
            "render_editorial_execution(build_editorial_route('other'))")
        app.session_state["editorial_run_id"] = saved["run"]["id"]
    app.run(timeout=15)
    assert not app.exception
    return app


def generation_label(target):
    return "Gerar / retomar unidades" if target == "native" else "Gerar unidades pendentes"


def paid_confirmation(target):
    return "Autorizo a geração das unidades pendentes e o custo do provedor" if target == "native" else "Confirmo gerar o conteúdo com IA e consumir os créditos do provedor configurado"


def interrupted(saved):
    with pytest.raises(RuntimeError):
        studio.generate_product(saved["source"], Mock(side_effect=RuntimeError("provider response unknown")), confirmed=True)
    return runtime.generation_status(saved["run"]["source_ref"])


@pytest.mark.parametrize("target", ["central", "native"])
def test_uncertain_call_blocks_generation_and_requires_separate_provider_evidence(saved, target):
    execution = interrupted(saved)
    token = execution["attempts"][-1]["token"]
    app = app_for(saved, target)
    widget(app, "checkbox", paid_confirmation(target)).check().run()
    assert widget(app, "button", generation_label(target)).disabled
    assert widget(app, "button", "Salvar conferência desta chamada").disabled
    widget(app, "selectbox", "Resultado conferido no provedor").set_value("not_sent").run()
    widget(app, "text_area", "Evidência ou justificativa da conferência").set_value("O painel do provedor confirma que não houve envio.")
    widget(app, "checkbox", "Conferi este resultado no provedor e autorizo registrar a conferência").check().run()
    widget(app, "button", "Salvar conferência desta chamada").click().run()
    assert not app.exception
    current = runtime.generation_status(saved["run"]["source_ref"])
    attempt = next(item for item in current["attempts"] if item["token"] == token)
    assert attempt["state"] == "reconciled_failed"
    saved["paid"].assert_not_called()
    if target == "central":
        widget(app, "checkbox", "Revisei o rascunho e confirmo retomar a execução interrompida").check().run()
    assert not widget(app, "button", generation_label(target)).disabled


@pytest.mark.parametrize("target", ["central", "native"])
def test_alive_local_worker_cannot_be_released_by_recovery_controls(saved, target):
    source = saved["source"]
    def active(product):
        product["editorial_product"]["execution"].update(status="running",
            claim={"token": "live-local-owner", "host": socket.gethostname(), "pid": os.getpid(), "owner_active": True})
        return product
    saved["backend"].update_json(runtime._path(source["storage_path"]), active)
    runtime._ACTIVE.add("live-local-owner")
    try:
        before = saved["backend"].get_bytes(runtime._path(source["storage_path"]))
        app = app_for(saved, target)
        widget(app, "checkbox", paid_confirmation(target)).check().run()
        assert widget(app, "button", generation_label(target)).disabled
        widget(app, "text_area", "Como foi confirmado o encerramento da execução?").set_value("Tentativa de confirmar um worker que ainda está trabalhando.")
        widget(app, "checkbox", "Confirmei que a execução foi encerrada").check().run()
        widget(app, "button", "Registrar encerramento e conferir tentativas").click().run()
        assert not app.exception
        assert any("ainda está ativo" in error.value for error in app.error)
        assert saved["backend"].get_bytes(runtime._path(source["storage_path"])) == before
        saved["paid"].assert_not_called()
    finally:
        runtime._ACTIVE.discard("live-local-owner")


@pytest.mark.parametrize("target", ["central", "native"])
def test_legacy_draft_requires_shutdown_review_then_separate_provider_reconciliation(saved, target):
    source = deepcopy(saved["source"])
    meta = source["editorial_product"]
    meta.pop("execution")
    meta["draft"] = {"id": "legacy-ui-draft", "units": [], "spec_fingerprint": studio._spec_fingerprint(source)}
    saved["backend"].put_json(runtime._path(source["storage_path"]), source)
    app = app_for(saved, target)
    widget(app, "checkbox", paid_confirmation(target)).check().run()
    assert widget(app, "button", generation_label(target)).disabled
    assert widget(app, "button", "Registrar encerramento e conferir tentativas").disabled
    widget(app, "text_area", "Como foi confirmado o encerramento da execução?").set_value("Todos os workers antigos foram encerrados antes da atualização.")
    widget(app, "checkbox", "Confirmei que a execução foi encerrada").check().run()
    widget(app, "button", "Registrar encerramento e conferir tentativas").click().run()
    assert not app.exception
    execution = runtime.generation_status(source["storage_path"])
    assert execution["attempts"][-1]["state"] == "uncertain"
    assert widget(app, "button", generation_label(target)).disabled
    assert any(item.label == "Salvar conferência desta chamada" for item in app.button)
    saved["paid"].assert_not_called()


@pytest.mark.parametrize("target", ["central", "native"])
def test_lost_raw_save_keeps_downloadable_session_response_and_recovers_without_repaying(saved, target, monkeypatch):
    original = saved["backend"].update_json
    failed = False
    def fail_raw(path, callback, default=None, **kwargs):
        nonlocal failed
        def checked(current):
            nonlocal failed
            value = callback(current)
            if path == runtime._path(saved["run"]["source_ref"]) and not failed:
                attempts = value["editorial_product"]["execution"]["attempts"]
                if attempts and attempts[-1]["state"] == "raw":
                    failed = True
                    raise storage.StorageUnavailable("raw receipt unavailable")
            return value
        return original(path, checked, default, **kwargs)
    monkeypatch.setattr(saved["backend"], "update_json", fail_raw)
    app = app_for(saved, target)
    widget(app, "checkbox", paid_confirmation(target)).check().run()
    widget(app, "button", generation_label(target)).click().run()
    assert not app.exception and failed
    saved["paid"].assert_called_once()
    cache = app.session_state["editorial_received_responses"]
    assert len(cache) == 1 and next(iter(cache.values())) == response()
    widget(app, "button", "Atualizar estado da geração").click().run()
    assert not app.exception
    assert app.get("download_button")
    assert widget(app, "button", generation_label(target)).disabled
    widget(app, "selectbox", "Resultado conferido no provedor").set_value("succeeded").run()
    widget(app, "text_area", "Evidência ou justificativa da conferência").set_value("Resposta recebida e conferida no registro do provedor.")
    widget(app, "checkbox", "Conferi este resultado no provedor e autorizo registrar a conferência").check().run()
    widget(app, "button", "Salvar conferência desta chamada").click().run()
    assert not app.exception
    widget(app, "checkbox", "Confirmo recuperar as respostas recebidas sem nova chamada à IA").check().run()
    if target == "central":
        widget(app, "checkbox", "Revisei o rascunho e confirmo retomar a execução interrompida").check().run()
    widget(app, "button", generation_label(target)).click().run()
    assert not app.exception
    saved["paid"].assert_called_once()
    current = studio.load_product(saved["run"]["source_ref"])
    assert len(current["editorial_product"]["units"]) == 1


@pytest.mark.parametrize("target", ["central", "native"])
def test_unreadable_attempt_ledger_disables_generation_instead_of_assuming_zero(saved, target, monkeypatch):
    monkeypatch.setattr(runtime, "generation_status", Mock(side_effect=storage.StorageUnavailable("temporary read failure")))
    app = app_for(saved, target)
    if target == "central":
        widget(app, "checkbox", paid_confirmation(target)).check().run()
        assert widget(app, "button", generation_label(target)).disabled
    else:
        assert not any(button.label == generation_label(target) for button in app.button)
    assert any("conferir as tentativas salvas" in error.value for error in app.error)
    saved["paid"].assert_not_called()


def test_native_stale_copy_requires_reload_before_approval_and_manual_save(saved):
    source = saved["source"]
    studio.generate_product(source, response, confirmed=True)
    app = app_for(saved, "native")
    current = studio.load_product(source["storage_path"])
    current["editorial_notes"] = "Anotação atual de outra sessão."
    studio.save_product(current)
    app.run()
    assert not app.exception
    assert widget(app, "button", "Salvar estado atual").disabled
    assert widget(app, "button", "Aprovar esta versão").disabled
    assert widget(app, "button", "Preparar arquivo").disabled
    widget(app, "button", "Reabrir conteúdo salvo deste produto").click().run()
    assert app.session_state["editorial_product_state"]["editorial_notes"] == current["editorial_notes"]
    assert not widget(app, "button", "Salvar estado atual").disabled


@pytest.mark.parametrize("target", ["central", "native"])
def test_raw_only_recovery_needs_no_provider_configuration_or_new_budget(saved, target, monkeypatch):
    execution = interrupted(saved)
    runtime.reconcile_attempt(saved["run"]["source_ref"], attempt_token=execution["attempts"][-1]["token"],
        provider_outcome="succeeded", note="Resposta recebida e conferida antes de remover o provedor.",
        confirmed=True, recovered_response=response())
    monkeypatch.setattr(ai_provider_router, "provider_status", lambda **_: {"gemini": False, "groq": False, "openrouter": False})
    import controle_geracao
    monkeypatch.setattr(controle_geracao, "validar_orcamento", lambda *_a: pytest.fail("Saving a received response cannot buy a new unit"))
    app = app_for(saved, target)
    widget(app, "checkbox", "Confirmo recuperar as respostas recebidas sem nova chamada à IA").check().run()
    if target == "central":
        widget(app, "checkbox", "Revisei o rascunho e confirmo retomar a execução interrompida").check().run()
    else:
        assert any("próximas chamadas: 0" in item.value for item in app.caption)
    assert not widget(app, "button", generation_label(target)).disabled
    widget(app, "button", generation_label(target)).click().run()
    assert not app.exception
    assert len(studio.load_product(saved["run"]["source_ref"])["editorial_product"]["units"]) == 1
    saved["paid"].assert_not_called()


def test_cached_response_from_another_product_is_not_used_for_reconciliation(saved):
    execution = interrupted(saved)
    token = execution["attempts"][-1]["token"]
    app = app_for(saved, "native")
    app.session_state["editorial_received_responses"] = {("fb://livros/another-product.json", token): response()}
    app.run()
    widget(app, "selectbox", "Resultado conferido no provedor").set_value("succeeded").run()
    assert any(item.label == "Resposta recuperada do provedor (JSON)" for item in app.text_area)
    widget(app, "text_area", "Evidência ou justificativa da conferência").set_value("Ainda preciso fornecer a resposta correta deste produto.")
    widget(app, "checkbox", "Conferi este resultado no provedor e autorizo registrar a conferência").check().run()
    widget(app, "button", "Salvar conferência desta chamada").click().run()
    assert not app.exception
    assert runtime.generation_status(saved["run"]["source_ref"])["attempts"][-1]["state"] == "uncertain"
    assert any("resposta estruturada" in error.value for error in app.error)
    saved["paid"].assert_not_called()


@pytest.mark.parametrize("actor_kind", ["other_account", "no_actor"])
def test_retained_native_session_never_renders_another_tenants_private_source(saved, monkeypatch, actor_kind):
    import estilo
    monkeypatch.setenv("FAITHBLOOM_ACCESS_MODE", "multi_tenant")
    monkeypatch.setenv("FAITHBLOOM_OIDC_ISSUERS", "https://identity.example")
    monkeypatch.delenv("FAITHBLOOM_ACCESS_ROLES", raising=False)
    backend = storage.TenantStorageBackend(saved["backend"])
    monkeypatch.setattr(storage, "BACKEND", backend)
    monkeypatch.setattr(armazenamento, "BACKEND", backend)
    # Exercise this product boundary independently of the separate commercial
    # UI gate, which deliberately remains blocked in the shipped application.
    monkeypatch.setattr(estilo, "aplicar_estilo", lambda: None)
    actor_a = access.actor_from_trusted_claims({"authenticated": True, "iss": "https://identity.example", "sub": "account-a"})
    with access.access_context(actor_a):
        source = studio.create_product("other", "TITULO PRIVADO A", "RELATO PRIVADO A",
            unit_count=1, custom_blocks=["Abertura"])
        studio.save_product(source)
        source_path = storage.uri_to_path(source["storage_path"])
    before = saved["backend"].get_bytes(source_path)
    context_code = ("access.access_context(access.actor_from_trusted_claims({'authenticated': True, 'iss': 'https://identity.example', 'sub': 'account-b'}))"
                    if actor_kind == "other_account" else "nullcontext()")
    page = str(ROOT / "pages/55_📚_Produtos_Editoriais.py")
    app = AppTest.from_string("import saas_access as access\nfrom pathlib import Path\nfrom contextlib import nullcontext\n"
        f"with {context_code}:\n"
        f"    exec(compile(Path({page!r}).read_text(), {page!r}, 'exec'))\n")
    app.session_state["editorial_product_state"] = source
    app.run(timeout=15)
    assert not app.exception
    visible = "\n".join(str(item.value) for kind in ("markdown", "text", "caption", "info", "warning", "error")
                        for item in app.get(kind))
    assert "TITULO PRIVADO A" not in visible and "RELATO PRIVADO A" not in visible
    assert any("conferir as tentativas salvas" in item.value for item in app.error)
    assert not any(button.label == "Gerar / retomar unidades" for button in app.button)
    assert saved["backend"].get_bytes(source_path) == before
    saved["paid"].assert_not_called()
