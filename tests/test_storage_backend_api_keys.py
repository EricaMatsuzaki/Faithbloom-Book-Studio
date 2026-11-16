from __future__ import annotations

import os

import storage_backend as sb


def test_supabase_secret_key_uses_apikey_only():
    backend = sb.SupabaseStorageBackend(
        "https://example.supabase.co",
        "sb_secret_example",
        "faithbloom",
    )
    assert backend.key_kind == "secret"
    assert backend.headers == {"apikey": "sb_secret_example"}


def test_legacy_service_role_keeps_bearer_header():
    legacy = "eyJlegacy.service.role"
    backend = sb.SupabaseStorageBackend(
        "https://example.supabase.co",
        legacy,
        "faithbloom",
    )
    assert backend.key_kind == "legacy_service_role"
    assert backend.headers["apikey"] == legacy
    assert backend.headers["Authorization"] == f"Bearer {legacy}"


def test_get_backend_prefers_new_secret_key(monkeypatch):
    monkeypatch.setenv("FAITHBLOOM_STORAGE_MODE", "supabase")
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "sb_secret_new")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "eyJlegacy")
    monkeypatch.setenv("FAITHBLOOM_SUPABASE_BUCKET", "faithbloom")

    backend = sb.get_backend()
    assert isinstance(backend, sb.SupabaseStorageBackend)
    assert backend.key == "sb_secret_new"
    assert backend.key_kind == "secret"


def test_get_backend_accepts_legacy_key(monkeypatch):
    monkeypatch.setenv("FAITHBLOOM_STORAGE_MODE", "supabase")
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.delenv("SUPABASE_SECRET_KEY", raising=False)
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "eyJlegacy")

    backend = sb.get_backend()
    assert isinstance(backend, sb.SupabaseStorageBackend)
    assert backend.key == "eyJlegacy"
    assert backend.key_kind == "legacy_service_role"


def test_long_prompt_text_is_not_treated_as_local_file_path():
    long_prompt = "MEL VISUAL DNA — " + ("detalhe canônico dos olhos e blush " * 300)
    payload = {
        "dna": {
            "visual_prompt_master": long_prompt,
            "descricao_master": long_prompt,
        }
    }

    persisted = sb.persistir_assets_em_objeto(payload, "assets/test")

    assert persisted == payload


def test_long_text_ending_with_asset_extension_does_not_raise_oserror():
    fake_prompt = ("texto editorial muito longo " * 400) + ".png"

    assert sb.persistir_assets_em_objeto(fake_prompt, "assets/test") == fake_prompt
