"""FaithBloom — IA externa por Prompt/Ideia, sem créditos OpenRouter."""
from __future__ import annotations

import streamlit as st

from age_profiles import normalizar_faixa_etaria, opcoes_faixa_etaria
from armazenamento import listar_livros, carregar_livro
from estilo import aplicar_estilo, hero
from external_ai_bridge import (
    EXTERNAL_AI_LABEL,
    SOURCE_IDEA,
    SOURCE_PROMPT,
    activate_external_version,
    build_external_authoring_prompt,
    parse_external_story_response,
    prompt_originality_preflight,
    register_external_version,
)
from state import LivroState
from storage_backend import backend_status

st.set_page_config(page_title="IA externa sem OpenRouter", page_icon="🤖", layout="wide")
aplicar_estilo()
hero(
    "🤖 IA externa — Prompt ou 💡 Ideia",
    "Prepare um prompt FaithBloom completo, use manualmente no ChatGPT Plus ou em outra IA que você já tenha e importe a história de volta — sem chamar OpenRouter.",
    "Zero chamadas OpenRouter nesta página",
)

if "state" not in st.session_state:
    st.session_state.state = LivroState(paginas_minimas=24, idiomas_alvo=[], personagens={})
s = st.session_state.state
s.setdefault("paginas_minimas", 24)
s.setdefault("idiomas_alvo", [])
s.setdefault("personagens", {})
s.setdefault("versoes_narrativas_salvas", {})
s.setdefault("faixa_etaria", "3-8")
s["faixa_etaria"] = normalizar_faixa_etaria(s.get("faixa_etaria"))
s["age_profile_id"] = s["faixa_etaria"]

st.info(
    "Esta página NÃO usa `chamar_llm` e não faz chamada automática à OpenRouter. O FaithBloom monta o prompt; você usa a IA externa manualmente e depois cola a resposta JSON aqui."
)

storage = backend_status()
if not storage.get("persistente_cloud"):
    st.warning(
        "⚠️ O storage atual ainda é local. Você pode testar o prompt sem custo, mas NÃO importe uma versão importante antes de configurar o Supabase, pois um reboot pode apagar o projeto salvo."
    )
else:
    st.success(f"☁️ Storage persistente ativo: {storage.get('modo')} · bucket {storage.get('bucket')}")

# --------------------------------------------------------------- PROJETO
st.subheader("1. Projeto / contexto")
livros = listar_livros()
if livros:
    choices = {f"{x.get('titulo','(sem título)')} · {x.get('colecao','')}": x for x in livros}
    selected = st.selectbox("Opcional: carregar um Book Master salvo", ["— manter contexto atual —", *choices])
    if selected != "— manter contexto atual —" and st.button("📖 Carregar este Book Master"):
        info = choices[selected]
        loaded = carregar_livro(info.get("colecao", ""), info.get("storage_path") or info.get("arquivo", ""))
        st.session_state.state = LivroState(**loaded)
        st.rerun()

s["colecao"] = st.text_input("Coleção", value=str(s.get("colecao") or "")).strip()
s["titulo"] = st.text_input("Título / título provisório", value=str(s.get("titulo") or "")).strip()

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

s["_entrada_tema_livre"] = st.text_area(
    "💡 Ideia / premissa",
    value=str(s.get("_entrada_tema_livre") or ""),
    height=130,
    placeholder="Ex.: Mel percebe que esperar é difícil quando quer ver uma sementinha nascer...",
).strip()
s["personagens_historia_brief"] = st.text_area(
    "Personagens narrativos",
    value=str(s.get("personagens_historia_brief") or ""),
    height=120,
    placeholder="Mel — protagonista curiosa...\nManu — amiga...",
).strip()
s["emocao_central"] = st.text_input("Emoção central", value=str(s.get("emocao_central") or "")).strip()
s["aprendizado_cristao"] = st.text_area(
    "Lição cristã",
    value=str(s.get("aprendizado_cristao") or ""),
    height=80,
).strip()
s["versiculo_referencia"] = st.text_input(
    "Referência bíblica (somente referência)",
    value=str(s.get("versiculo_referencia") or ""),
).strip()

# ------------------------------------------------------------- MODO
st.subheader("2. Escolha como a IA externa deve começar")
source_mode = st.radio(
    "Modo de criação",
    options=[SOURCE_IDEA, SOURCE_PROMPT],
    horizontal=True,
    format_func=lambda x: "💡 Escrever a partir da ideia" if x == SOURCE_IDEA else "🪄 Escrever a partir do meu prompt",
)

author_prompt = ""
if source_mode == SOURCE_PROMPT:
    author_prompt = st.text_area(
        "Seu prompt / direção criativa",
        value=str(st.session_state.get("external_author_prompt") or ""),
        height=180,
        placeholder="Ex.: Quero uma nova versão mais emocionante, com humor leve, cenas mais visuais e um final muito memorável...",
    )
    st.session_state.external_author_prompt = author_prompt

with st.expander("📖 Opcional — usar texto-base de uma obra MINHA / versão anterior"):
    st.caption(
        "Use somente material que seja seu ou que você tenha direito de reutilizar. Ex.: seu livro anterior da Mel para pedir uma atualização editorial. Este campo não é tratado como referência de terceiros."
    )
    own_reference = st.text_area(
        "Cole aqui o texto/trecho da sua própria obra",
        value=str(st.session_state.get("external_own_reference") or ""),
        height=260,
    )
    st.session_state.external_own_reference = own_reference

# ------------------------------------------------------------- PROMPT
st.subheader("3. Preparar prompt — 0 créditos OpenRouter")
preflight = prompt_originality_preflight(dict(s), author_prompt if source_mode == SOURCE_PROMPT else "")
if preflight.get("status") == "BLOCKED":
    st.error(
        "🛡️ O Originality Guard encontrou linguagem de imitação direta no prompt. Reescreva a referência em termos de mecanismos gerais (ex.: humor cotidiano, profundidade emocional, ritmo, cumulatividade) antes de continuar."
    )
    for finding in preflight.get("blockers") or []:
        st.caption(f"{finding.get('code')}: {finding.get('detail')}")

can_prepare = bool(s.get("colecao")) and (
    bool(s.get("_entrada_tema_livre")) if source_mode == SOURCE_IDEA else bool(str(author_prompt).strip())
) and preflight.get("status") != "BLOCKED"

if st.button("🧩 Preparar prompt FaithBloom", disabled=not can_prepare, use_container_width=True, type="primary"):
    try:
        st.session_state.external_ready_prompt = build_external_authoring_prompt(
            dict(s),
            source_mode=source_mode,
            author_prompt=author_prompt,
            author_owned_reference=own_reference,
        )
    except Exception as exc:
        st.error(str(exc))

ready_prompt = st.session_state.get("external_ready_prompt") or ""
if ready_prompt:
    st.success("✅ Prompt preparado localmente. Nenhum crédito OpenRouter foi usado.")
    st.code(ready_prompt, language=None)
    st.download_button(
        "⬇️ Baixar prompt .txt",
        data=ready_prompt,
        file_name="faithbloom-prompt-ia-externa.txt",
        mime="text/plain",
        use_container_width=True,
    )
    st.link_button("↗️ Abrir ChatGPT", "https://chatgpt.com/", use_container_width=True)
    st.caption(
        "Copie o prompt acima, use no ChatGPT/IA externa e peça a resposta em JSON. Depois volte a esta página e cole o resultado abaixo."
    )

# ------------------------------------------------------------- IMPORTAR
st.subheader("4. Importar a história criada fora do OpenRouter")
raw_response = st.text_area(
    "Cole aqui o JSON retornado pela IA externa",
    value="",
    height=300,
    placeholder='{"titulo":"...","cenas_texto":[...],"licao_final":"..."}',
)

if st.button("✅ Validar e salvar na Biblioteca de Versões", disabled=not bool(raw_response.strip()), use_container_width=True):
    try:
        version = parse_external_story_response(raw_response, dict(s))
        key, path = register_external_version(s, version, source_mode=source_mode)
        st.session_state.external_imported_key = key
        st.success(
            f"✅ {EXTERNAL_AI_LABEL} importada e salva na Biblioteca de Versões. Nenhuma chamada OpenRouter foi feita nesta etapa."
        )
        if not path:
            st.warning("A versão entrou na sessão, mas não houve caminho persistido. Configure o storage antes de confiar em reboot/redeploy.")
    except Exception as exc:
        st.error(f"Não foi possível importar: {exc}")

library = s.get("versoes_narrativas_salvas") or {}
external_items = [(k, v) for k, v in library.items() if isinstance(v, dict) and v.get("origem") == "external_ai_manual"]
if external_items:
    st.divider()
    st.subheader("5. Versões externas importadas")
    for key, version in external_items:
        with st.expander(f"{version.get('label') or EXTERNAL_AI_LABEL} · {version.get('titulo') or 'sem título'}"):
            st.caption(
                f"Origem: manual/externa · modo: {version.get('source_mode','ideia')} · estilo-base recomendado: {version.get('estilo_recomendado','misto')}"
            )
            if version.get("sinopse_poetica"):
                st.write(version["sinopse_poetica"])
            for scene in (version.get("cenas_texto") or [])[:4]:
                if isinstance(scene, dict):
                    st.markdown(f"**Cena {scene.get('numero','')}**")
                    st.write(scene.get("texto", ""))
            if len(version.get("cenas_texto") or []) > 4:
                st.caption(f"+ {len(version.get('cenas_texto') or []) - 4} cena(s) preservada(s) na versão completa.")
            if version.get("licao_final"):
                st.markdown(f"**⭐ Lição de Moral:** {version['licao_final']}")
            if st.button(
                "⭐ Tornar esta versão ativa",
                key=f"activate_external_{key}",
                use_container_width=True,
                disabled=s.get("versao_narrativa_ativa") == key,
            ):
                try:
                    activate_external_version(s, key, version)
                    st.success("Versão externa definida como ativa e preservada no Book Master.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Não foi possível ativar: {exc}")

st.caption(
    "Arquitetura: o FaithBloom prepara/valida/importa de forma determinística; a geração externa acontece fora do SaaS. Assim esta opção não usa créditos OpenRouter e continua respeitando Storyteller Skill, Heart Arc e Originality Guard."
)
