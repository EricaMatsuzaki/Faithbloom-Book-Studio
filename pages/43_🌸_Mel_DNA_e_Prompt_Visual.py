"""FaithBloom — DNA canônico e Prompt Mestre Visual da Mel."""
from __future__ import annotations

import streamlit as st

from armazenamento import listar_colecoes
from character_universe import (
    atualizar_personagem_oficial,
    carregar_personagem_oficial,
    criar_personagem_oficial,
    listar_personagens_oficiais,
    personagem_para_prompt,
)
from estilo import aplicar_estilo, hero
from mel_character_profile import (
    MEL_BOW_SIGNATURE,
    MEL_CHARACTER_NAME,
    MEL_EYE_SIGNATURE,
    MEL_HEART_CHEEK_BLUSH,
    MEL_MASTER_DESCRIPTION,
    MEL_PROFILE_SCHEMA,
    MEL_VISUAL_PROMPT_MASTER,
    mel_character_dna,
    mel_visual_prompt,
)
from storage_backend import backend_status

st.set_page_config(page_title="Mel · DNA Visual", page_icon="🌸", layout="wide")
aplicar_estilo()
hero(
    "🌸 Mel — Character DNA & Prompt Mestre Visual",
    "Central oficial da identidade visual da Mel: olhos, blush em duas camadas, laço contextual e Prompt Mestre reutilizável em novas gerações.",
    "FaithBloom · Canonical Character Identity",
)

st.info(
    "Esta página NÃO gera imagem e NÃO consome créditos. Ela grava/revisa o DNA canônico da Mel no Character Universe e prepara o Prompt Mestre que os fluxos visuais passam a herdar."
)

storage = backend_status()
if not storage.get("persistente_cloud"):
    st.warning(
        "⚠️ O storage está local. Você pode testar o DNA, mas antes de confiar o Color Master definitivo a produção, configure o storage persistente em nuvem."
    )

colecoes = listar_colecoes()
default_collection = "Pequenas Histórias, Grandes Lições"
if default_collection not in colecoes and colecoes:
    default_collection = colecoes[0]

st.subheader("1. Coleção e personagem")
colecao = st.text_input("Coleção da Mel", value=default_collection).strip()
items = listar_personagens_oficiais(colecao) if colecao else []
mel_item = next((x for x in items if str(x.get("nome") or "").strip().casefold() == MEL_CHARACTER_NAME.casefold()), None)
mel_saved = carregar_personagem_oficial(mel_item["id"]) if mel_item else None

if mel_saved:
    st.success("✅ A Mel já existe como personagem oficial nesta coleção. O botão abaixo atualiza somente o DNA/prompt e preserva Color Master, referências, variações e histórico.")
    c1, c2, c3 = st.columns(3)
    c1.metric("Color Master", "✅" if mel_saved.get("color_master") else "Ainda não")
    c2.metric("Reference Pack", len(mel_saved.get("reference_pack") or []))
    c3.metric("Versões preservadas", len(mel_saved.get("versoes") or []))
else:
    st.info("A Mel ainda não está cadastrada nesta coleção. Você pode criar o Character Master oficial com o DNA aprovado abaixo.")

st.subheader("2. Assinaturas faciais canônicas")
left, right = st.columns(2)
with left:
    st.markdown("### 👁️ Mel Eye Signature™")
    st.write(MEL_EYE_SIGNATURE)
with right:
    st.markdown("### 💗 Heart Cheek Blush™")
    st.write(MEL_HEART_CHEEK_BLUSH)

st.markdown("### 🎀 Bow Signature™")
st.write(MEL_BOW_SIGNATURE)
st.caption("A presença, formato geral e posição do laço são identidade. A COR é variável contextual: rosa como padrão; vermelho no Natal quando solicitado.")

with st.expander("🧬 Descrição Master completa", expanded=False):
    st.write(MEL_MASTER_DESCRIPTION)

st.subheader("3. Prompt Mestre Visual Oficial")
st.caption(
    "Quando uma imagem Color Master estiver cadastrada, ela continua sendo a referência visual primária para microdetalhes. O prompt abaixo funciona como Identity Lock complementar."
)

bow_options = ["Padrão da Mel (rosa)", "Vermelho — Natal", "Outra cor autorizada"]
bow_choice = st.selectbox("Cor contextual do laço para visualizar o prompt", bow_options)
if bow_choice == "Padrão da Mel (rosa)":
    bow_color = "rosa, cor-base canônica"
elif bow_choice == "Vermelho — Natal":
    bow_color = "vermelho, autorizado para história de Natal"
else:
    bow_color = st.text_input("Cor autorizada do laço", value="").strip()
scene_direction = st.text_area(
    "Direção de cena opcional",
    value="",
    placeholder="Ex.: Mel sentada ao lado de um vaso no jardim, curiosa e esperançosa.",
    height=90,
)
preview_prompt = mel_visual_prompt(bow_color=bow_color, scene_direction=scene_direction)
st.code(preview_prompt, language=None)

st.subheader("4. Gravar no Character Universe")
confirm = st.checkbox(
    "Confirmo que este é o DNA visual oficial da Mel e que olhos, blush e formato/posição do laço devem ser protegidos como identidade canônica."
)
button_label = "🌸 Atualizar DNA oficial da Mel" if mel_saved else "🌸 Criar Mel como Character Master oficial"
if st.button(button_label, type="primary", use_container_width=True, disabled=not bool(confirm and colecao)):
    dna = mel_character_dna()
    if mel_saved:
        meta = dict(mel_saved.get("metadata") or {})
        meta["canonical_profile_schema"] = MEL_PROFILE_SCHEMA
        atualizar_personagem_oficial(mel_saved["id"], {"dna": dna, "metadata": meta})
        st.success("✅ DNA e Prompt Mestre Visual da Mel atualizados. Assets, Color Master, Reference Pack, variações e histórico foram preservados.")
    else:
        criar_personagem_oficial(
            colecao,
            MEL_CHARACTER_NAME,
            dna,
            metadata={
                "usos_permitidos": ["story", "coloring", "activity", "cover"],
                "canonical_profile_schema": MEL_PROFILE_SCHEMA,
            },
        )
        st.success("✅ Mel criada como personagem oficial com DNA e Prompt Mestre Visual canônicos.")
    st.rerun()

if mel_saved:
    st.divider()
    st.subheader("5. Verificação do prompt que o pipeline recebe")
    generated_lock = personagem_para_prompt(
        mel_saved,
        modo="color",
        variaveis={"cor_acessorio_identitario": bow_color} if bow_color else {},
        contexto="story",
    )
    with st.expander("🔒 Identity Lock final enviado aos fluxos visuais", expanded=False):
        st.code(generated_lock, language=None)

    st.markdown("### 🖼️ Próximo passo com a nova imagem linda da Mel")
    st.write(
        "Abra o Character Universe, faça upload dessa imagem no Reference Pack e, depois de revisá-la, use **⭐ Definir como Color Master**. O FaithBloom não promove uma imagem automaticamente: a aprovação humana continua obrigatória."
    )
    st.page_link("pages/14_👥_Character_Universe.py", label="👥 Abrir Character Universe →", use_container_width=True)

st.divider()
st.caption(
    "Regra canônica da Mel: imagem Color Master aprovada = fonte visual primária; Prompt Mestre = trava textual complementar. A cor do laço pode variar com a narrativa, mas olhos, blush em duas camadas e identidade facial não devem derivar."
)
