"""FaithBloom — categoria Histórias Inspiradas em Experiências Reais."""
from __future__ import annotations

import streamlit as st

from age_profiles import normalizar_faixa_etaria, opcoes_faixa_etaria
from agents.curador_tema import curador_tema_node
from estilo import aplicar_estilo, hero
from openrouter_client import chamar_llm
from real_experience_story import (
    FIDELITY_FAITHFUL,
    FIDELITY_MODES,
    PRIVACY_FICTIONALIZE,
    PRIVACY_MODES,
    REAL_EXPERIENCE_CATEGORY_LABEL,
    RELATION_OPTIONS,
    apply_real_experience_to_state,
)
from state import LivroState
from storage_backend import backend_status

st.set_page_config(page_title="Histórias Reais", page_icon="🌿", layout="wide")
aplicar_estilo()
hero(
    "🌿 Histórias inspiradas em experiências reais",
    "Transforme memórias e vivências verdadeiras em literatura infantil emocionalmente rica, preservando dignidade, consentimento, privacidade e o coração dos fatos.",
    "Origem da história — não estilo narrativo",
)

if "state" not in st.session_state:
    st.session_state.state = LivroState(paginas_minimas=24, idiomas_alvo=[], personagens={})
s = st.session_state.state
s.setdefault("paginas_minimas", 24)
s.setdefault("idiomas_alvo", [])
s.setdefault("personagens", {})
s.setdefault("faixa_etaria", "3-8")
s["faixa_etaria"] = normalizar_faixa_etaria(s.get("faixa_etaria"))
s["age_profile_id"] = s["faixa_etaria"]

st.info(
    "Esta categoria pode depois ser contada como 📖 Aventura, 🎵 Poético/Rimado, 🌿 Fábula, ✨ Misto, ⭐ Versão do Roteirista, estilos adicionais ou pela 🤖 IA externa. A experiência real define a ORIGEM; o estilo define COMO ela será contada."
)

storage = backend_status()
if not storage.get("persistente_cloud"):
    st.warning(
        "⚠️ Seu storage ainda é local. Você pode preparar o relato e testar o fluxo, mas um reboot/redeploy pode apagar o projeto até o Supabase estar configurado."
    )

st.subheader("1. Projeto")
s["colecao"] = st.text_input(
    "Coleção",
    value=str(s.get("colecao") or ""),
    placeholder="Ex.: Histórias que Florescem da Vida",
).strip()
s["titulo"] = st.text_input(
    "Título provisório (opcional)",
    value=str(s.get("titulo") or ""),
    placeholder="Pode deixar em branco e decidir depois",
).strip()

age_options = opcoes_faixa_etaria()
age_ids = [x[0] for x in age_options]
age_labels = {x[0]: x[1] for x in age_options}
current_age = normalizar_faixa_etaria(s.get("faixa_etaria"))
s["faixa_etaria"] = st.selectbox(
    "Faixa etária",
    age_ids,
    index=age_ids.index(current_age) if current_age in age_ids else 0,
    format_func=lambda x: age_labels[x],
)
s["age_profile_id"] = s["faixa_etaria"]

st.subheader("2. Conte a experiência real")
existing_real = s.get("real_experience") or {}
account = st.text_area(
    "Relato / memória / experiência",
    value=str(existing_real.get("original_account") or ""),
    height=300,
    placeholder=(
        "Conte do seu jeito. Pode ser um relato curto ou detalhado. Ex.: uma mudança de país, dificuldade na escola, uma amizade, uma perda, uma conquista, uma experiência de fé, uma situação engraçada..."
    ),
)

relation_keys = list(RELATION_OPTIONS)
existing_relation = existing_real.get("relation") if existing_real.get("relation") in RELATION_OPTIONS else "propria"
relation = st.selectbox(
    "De quem é principalmente esta experiência?",
    relation_keys,
    index=relation_keys.index(existing_relation),
    format_func=lambda x: RELATION_OPTIONS[x],
)

st.subheader("3. Fidelidade e privacidade")
fidelity_keys = list(FIDELITY_MODES)
existing_fidelity = existing_real.get("fidelity_mode") if existing_real.get("fidelity_mode") in FIDELITY_MODES else FIDELITY_FAITHFUL
fidelity = st.radio(
    "Como a história deve tratar os fatos?",
    fidelity_keys,
    index=fidelity_keys.index(existing_fidelity),
    format_func=lambda x: FIDELITY_MODES[x],
)
if fidelity == FIDELITY_FAITHFUL:
    st.caption("Mantém acontecimentos, relações, cronologia e desfecho principais. A IA melhora ritmo, linguagem, seleção de cenas e emoção sem mudar o que aconteceu.")
else:
    st.caption("Usa a vivência como semente. Pode condensar tempo e ficcionalizar elementos não essenciais, mas não pode atribuir a pessoas reais fatos sensíveis inventados.")

privacy_keys = list(PRIVACY_MODES)
existing_privacy = existing_real.get("privacy_mode") if existing_real.get("privacy_mode") in PRIVACY_MODES else PRIVACY_FICTIONALIZE
privacy = st.radio(
    "Privacidade",
    privacy_keys,
    index=privacy_keys.index(existing_privacy),
    format_func=lambda x: PRIVACY_MODES[x],
)
if privacy == PRIVACY_FICTIONALIZE:
    st.caption("Recomendado para histórias com crianças e terceiros: troca nomes e reduz detalhes identificáveis, preservando o significado emocional.")
else:
    st.caption("Mesmo com nomes autorizados, o FaithBloom não deve acrescentar dados privados nem acontecimentos sensíveis que não foram fornecidos.")

consent = st.checkbox(
    "Confirmo que tenho direito/consentimento adequado para transformar este relato em uma obra e que sou responsável pela autorização de pessoas reais identificáveis.",
    value=False,
)

st.subheader("4. Preparar categoria")
st.caption("Este botão é local: ele NÃO chama OpenRouter e NÃO gasta créditos de IA.")
prepare_disabled = not bool(str(s.get("colecao") or "").strip() and account.strip() and consent)
if st.button("🌱 Preparar história inspirada na vida real — 0 créditos", disabled=prepare_disabled, type="primary", use_container_width=True):
    try:
        prepared = apply_real_experience_to_state(
            dict(s),
            account=account,
            fidelity_mode=fidelity,
            privacy_mode=privacy,
            relation=relation,
            consent_confirmed=consent,
        )
        s.clear()
        s.update(prepared)
        st.success(f"✅ Categoria preparada: {REAL_EXPERIENCE_CATEGORY_LABEL}")
        st.success("✅ O relato agora carrega regras de fidelidade, dignidade, privacidade e adaptação emocional para os Roteiristas.")
    except Exception as exc:
        st.error(str(exc))

if s.get("story_category") == "inspirada_em_experiencia_real":
    st.divider()
    st.subheader("5. Próximo passo")
    st.write(
        "Você pode seguir para o comparador e contar esta mesma experiência em diferentes estilos. O FaithBloom preservará a categoria como origem narrativa."
    )
    col1, col2 = st.columns(2)
    with col1:
        if st.button("✍️ Abrir História em 4 Estilos", use_container_width=True, type="primary"):
            st.switch_page("pages/39_✍️_Historia_4_Estilos.py")
    with col2:
        if st.button("🤖 Usar IA externa / ChatGPT sem OpenRouter", use_container_width=True):
            st.switch_page("pages/41_🤖_IA_Externa_sem_OpenRouter.py")

    with st.expander("🧠 Opcional — Curar título, emoção, lição e referência agora"):
        st.warning("Esta ação CHAMA o modelo configurado no FaithBloom e pode consumir créditos OpenRouter.")
        if st.button("🧠 Curar tema agora (usa IA)", use_container_width=True):
            try:
                updated = curador_tema_node(dict(s), chamar_llm)
                s.clear()
                s.update(updated)
                st.success("Curadoria concluída. Título, emoção, lição e referência permanecem editáveis.")
                st.rerun()
            except Exception as exc:
                st.error(f"Não foi possível concluir a curadoria: {exc}")

st.divider()
st.caption(
    "Regra editorial: o FaithBloom pode dramatizar a forma de contar, mas não deve inventar sofrimento, diagnóstico, abuso, crime, morte ou outro fato sensível para tornar uma memória mais emocionante. A história deve preservar dignidade e separar experiência verdadeira de reconstrução literária."
)
