"""Refinamento 13 — Stable Release Hardening."""
from __future__ import annotations

import json
import streamlit as st

from armazenamento import listar_livros, carregar_livro
from estilo import aplicar_estilo, hero, section_title, callout
from stable_hardening import (
    CURRENT_DATA_SCHEMA, ROLE_PERMISSIONS, can, create_recovery_point,
    environment_diagnostics, identity_from_environment, list_audit_events,
    list_recovery_points, load_recovery_point, load_settings, migration_preview,
    migrate_project_state, onboarding_status, permission_matrix,
    prepare_restore_working_copy, run_offline_stable_smoke, save_settings,
    stable_release_gate, storage_roundtrip_probe,
)

st.set_page_config(page_title="Stable Release Hardening", page_icon="🧱", layout="wide")
aplicar_estilo()
hero(
    "Stable Release Hardening",
    "Migração segura, recovery, onboarding, configuração, permissões e readiness operacional antes da tag Stable.",
    "Refinamento 13 · sem chamadas de IA",
)

identity = identity_from_environment()
settings = load_settings()

callout(
    "Papéis não são autenticação",
    "Owner/Editor/Reviewer/Viewer definem permissões internas. Em produção multiusuário, o Stable Gate exige um provedor real de autenticação (OIDC/external); trocar um papel na interface não equivale a login seguro.",
    "🔐",
)

t1, t2, t3, t4, t5, t6 = st.tabs(["👋 Onboarding", "🩺 Ambiente", "🧬 Migração", "🛟 Recovery", "🔐 Acesso", "🚦 Stable Gate"])

with t1:
    section_title("Configurações do estúdio", "Secrets nunca são gravados nesta tela.", "Onboarding")
    with st.form("stable_settings"):
        author = st.text_input("Nome editorial padrão (legado)", value=settings.get("author_name", ""))
        locale = st.text_input("Locale padrão", value=settings.get("default_locale", "pt-BR"))
        age = st.selectbox("Faixa padrão", ["3-5", "3-8", "6-8", "9-10", "adulto", "personalizado"], index=max(0, ["3-5", "3-8", "6-8", "9-10", "adulto", "personalizado"].index(settings.get("default_age_profile", "3-8")) if settings.get("default_age_profile", "3-8") in ["3-5", "3-8", "6-8", "9-10", "adulto", "personalizado"] else 1))
        trim = st.text_input("Trim Master padrão", value=settings.get("default_trim", "8.5x8.5"))
        autosave = st.checkbox("Autosave habilitado", value=bool(settings.get("autosave_enabled", True)))
        recovery = st.checkbox("Criar recovery point antes de mudanças importantes", value=bool(settings.get("recovery_before_major_change", True)))
        st.checkbox("Bible Guard obrigatório", value=True, disabled=True)
        if st.form_submit_button("Salvar configurações"):
            if not can(identity["role"], "change_settings"):
                st.error("Seu papel atual não pode alterar configurações.")
            else:
                settings = save_settings({**settings, "author_name": author, "default_locale": locale, "default_age_profile": age, "default_trim": trim, "autosave_enabled": autosave, "recovery_before_major_change": recovery, "bible_guard_required": True}, actor=identity["name"])
                st.success("Configurações salvas. Bible Guard permanece obrigatório.")
                st.caption("Para múltiplos autores e colaboradores, use a área ✍️ Autores & Colaboradores.")
    ob = onboarding_status(settings)
    st.progress(ob["done"] / max(1, ob["total"]))
    for item in ob["items"]:
        st.write(("✅ " if item["done"] else "⬜ ") + item["label"])

with t2:
    d = environment_diagnostics()
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Modo", d["deployment_mode"])
    c2.metric("Storage", d["storage"].get("modo", "?"))
    c3.metric("Auth", d["auth_mode"])
    c4.metric("Produção", "OK" if d["ok_for_production"] else "Bloqueada")
    for x in d["checks"]:
        icon = "✅" if x["ok"] else ("🔴" if x["level"] == "blocker" else "🟡")
        st.write(f"{icon} **{x['id']}** — {x['detail']}")
    if st.button("Testar leitura/escrita do storage"):
        p = storage_roundtrip_probe()
        (st.success if p["ok"] else st.error)(p["detail"])

with t3:
    st.caption(f"Schema atual do FaithBloom: v{CURRENT_DATA_SCHEMA}. A migração trabalha em cópia e não sobrescreve o projeto salvo automaticamente.")
    books = listar_livros()
    if not books:
        st.info("Nenhum Story Book salvo no storage atual.")
    else:
        labels = [f"{b.get('titulo')} · {b.get('colecao') or 'sem coleção'} · {b.get('arquivo')}" for b in books]
        idx = st.selectbox("Projeto", range(len(books)), format_func=lambda i: labels[i], key="migration_book")
        book = books[idx]
        state = carregar_livro(book.get("colecao", ""), book.get("storage_path") or book.get("arquivo"))
        preview = migration_preview(state)
        st.json(preview)
        if preview.get("changed"):
            if st.button("Preparar cópia migrada"):
                r = migrate_project_state(state)
                st.session_state["stable_migrated_working_copy"] = r["state"]
                st.success("Cópia migrada criada em memória. O projeto salvo não foi sobrescrito.")
                st.download_button("Baixar cópia migrada (.json)", json.dumps(r["state"], ensure_ascii=False, indent=2), file_name=f"{book.get('titulo','projeto')}-schema-v{CURRENT_DATA_SCHEMA}.json", mime="application/json")
        else:
            st.success("Projeto já está no schema atual; migração idempotente não altera o conteúdo.")

with t4:
    books = listar_livros()
    if not books:
        st.info("Salve um Story Book para usar recovery points.")
    else:
        labels = [f"{b.get('titulo')} · {b.get('colecao') or 'sem coleção'}" for b in books]
        idx = st.selectbox("Projeto para recovery", range(len(books)), format_func=lambda i: labels[i], key="recovery_book")
        book = books[idx]
        state = carregar_livro(book.get("colecao", ""), book.get("storage_path") or book.get("arquivo"))
        label = st.text_input("Rótulo do recovery point", value="antes-de-mudanca-importante")
        if st.button("Criar recovery point"):
            if not can(identity["role"], "restore_backup"):
                st.error("Seu papel atual não possui permissão de recovery.")
            else:
                rp = create_recovery_point(state, label=label, actor=identity["name"], role=identity["role"])
                st.success(f"Recovery point criado: {rp['recovery_id']}")
        points = list_recovery_points(book.get("titulo", ""), book.get("colecao", ""))
        if points:
            pidx = st.selectbox("Recovery points", range(len(points)), format_func=lambda i: f"{points[i].get('created_at')} · {points[i].get('label')} · {points[i].get('recovery_id')}")
            rp = points[pidx]
            st.caption("Restaurar aqui significa preparar uma cópia de trabalho. O estado atual não é apagado.")
            if st.button("Preparar cópia de trabalho deste recovery"):
                result = prepare_restore_working_copy(state, load_recovery_point(rp["storage_path"]))
                st.session_state["stable_recovery_working_copy"] = result["working_copy"]
                st.success(result["notice"])
                st.download_button("Baixar cópia restaurada (.json)", json.dumps(result["working_copy"], ensure_ascii=False, indent=2), file_name="faithbloom-recovery-working-copy.json", mime="application/json")
        else:
            st.info("Ainda não há recovery points para este projeto.")

with t5:
    st.write(f"Perfil atual: **{identity['name']} · {identity['role']}**")
    st.caption(f"Auth mode: {identity['auth_mode']} · authenticated flag: {identity['authenticated']}. Em produção, configure autenticação real fora desta matriz de papéis.")
    st.dataframe(permission_matrix(), use_container_width=True, hide_index=True)
    st.markdown("**Últimos eventos de auditoria**")
    events = list_audit_events(30)
    if events:
        st.dataframe([{"quando":e.get("at"), "ator":e.get("actor"), "papel":e.get("role"), "acao":e.get("action"), "status":e.get("status")} for e in events], use_container_width=True, hide_index=True)
    else:
        st.info("Nenhum evento registrado ainda.")

with t6:
    if st.button("Rodar smoke test offline"):
        r = run_offline_stable_smoke()
        (st.success if r["ok"] else st.error)("Smoke test offline aprovado." if r["ok"] else "Smoke test offline encontrou falhas.")
        st.json(r)
    probe = st.checkbox("Incluir teste real de write/read/delete do storage no Stable Gate", value=False)
    gate = stable_release_gate(settings=settings, include_storage_probe=probe)
    if gate["ready_for_stable_tag"]:
        st.success("✅ Stable Gate interno: PASS")
    else:
        st.error("🔴 Stable Gate interno: BLOCKED")
    for x in gate["checks"]:
        icon = "✅" if x["ok"] else ("🔴" if x["level"] == "blocker" else "🟡")
        st.write(f"{icon} **{x['id']}** — {x['detail']}")
    st.info(gate["notice"])
