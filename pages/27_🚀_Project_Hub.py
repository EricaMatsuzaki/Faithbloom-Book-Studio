"""FaithBloom Refinamento 12 — Production Release & Project Hub."""
from __future__ import annotations

import streamlit as st

from armazenamento import listar_livros, carregar_livro
from estilo import aplicar_estilo, hero, section_title, callout
from translation_localization import listar_projetos_traducao, carregar_projeto_traducao
from activity_studio import list_activity_projects, load_activity_project
from audiobook_studio import list_audiobook_projects, load_audiobook_project
from quality_guardian import list_guardian_reports, load_guardian_report
from publishing_distribution import list_distribution_plans, load_distribution_plan
from project_hub import same_project, build_project_overview, build_edition_matrix, build_project_snapshot
from integration_ux import make_project_context
from author_profiles import authorship_summary

st.set_page_config(page_title="Project Hub", page_icon="🚀", layout="wide")
aplicar_estilo()
hero(
    "🚀 Production Release & Project Hub",
    "Abra uma obra e veja em um único painel o que está pronto, o que precisa de decisão e quais edições existem — sem substituir as aprovações detalhadas de cada Studio.",
    "Refinamento 12 · Single-project command center",
)

livros = listar_livros()
if not livros:
    st.info("Nenhum Book Master salvo ainda. Crie ou salve uma obra para usar o Project Hub.")
    st.stop()

section_title("1. Escolha o projeto", "O Hub lê evidências já salvas nos outros módulos; ele não inventa qualidade nem aprova conteúdo sozinho.", "Project")
options = {f"{x.get('titulo','(sem título)')} · {x.get('colecao','')}": x for x in livros}
selected = st.selectbox("Book Master", list(options))
info = options[selected]
state = carregar_livro(info.get("colecao", ""), info.get("storage_path") or info["arquivo"])
st.session_state["faithbloom_active_project"] = make_project_context(info, state)
title, collection = state.get("titulo", ""), state.get("colecao", "")

# Reúne somente registros que realmente correspondem ao projeto.
translations=[]
for card in listar_projetos_traducao():
    if same_project(title, collection, card.get("titulo"), card.get("colecao")):
        translations.append(carregar_projeto_traducao(card["id"]))

activities=[]
for card in list_activity_projects():
    p=load_activity_project(card["id"])
    source=p.get("source_book") or {}
    if same_project(title, collection, p.get("title"), p.get("collection")) or same_project(title, collection, source.get("titulo") or source.get("title"), source.get("colecao") or source.get("collection")):
        activities.append(p)

audiobooks=[]
for card in list_audiobook_projects():
    p=load_audiobook_project(card["id"])
    if same_project(title, collection, p.get("title"), p.get("collection")):
        audiobooks.append(p)

guardians=[]
for card in list_guardian_reports():
    if same_project(title, collection, card.get("project_title"), ""):
        guardians.append(load_guardian_report(card["id"]))

distributions=[]
for card in list_distribution_plans():
    if same_project(title, collection, card.get("title"), ""):
        distributions.append(load_distribution_plan(card["id"]))

overview=build_project_overview(state, translations=translations, activities=activities, audiobooks=audiobooks, guardian_reports=guardians, distribution_plans=distributions)
matrix=build_edition_matrix(state, translations=translations, distribution_plans=distributions, audiobooks=audiobooks)

auth = authorship_summary(state)
if auth["has_primary_author"]:
    st.caption(f"✍️ Autoria: {auth['author_display']} · {len(auth['contributors'])} colaborador(es) adicional(is)")
else:
    st.warning("✍️ Este projeto ainda não possui autoria estruturada. Defina antes da publicação.")
    st.page_link("pages/32_✍️_Autores_e_Colaboradores.py", label="Configurar autoria →", use_container_width=True)

m1,m2,m3,m4=st.columns(4)
m1.metric("Etapas acompanhadas", overview["counts"]["tracked"])
m2.metric("Concluídas", overview["counts"]["complete"])
m3.metric("Bloqueadas", overview["counts"]["blocked"])
m4.metric("Edições Live", overview["distribution"].get("live",0))

if overview["release"]["ready_for_channel_packages"]:
    st.success("🚀 Release operacional: Quality Gate vigente e edições do plano atual sem bloqueios internos. Isso não significa aceitação automática pelas lojas.")
else:
    st.warning("🚦 Release operacional ainda não liberada: " + overview["release"]["reason"])

next_action=overview["next_action"]
callout("Próxima ação recomendada", f"{next_action['title']}: {next_action['message']}", "🧭")
if next_action.get("page"):
    st.page_link(next_action["page"], label=f"Abrir {next_action['title']} →", use_container_width=True)

section_title("2. Pipeline da obra", "Status baseado somente no que está registrado. Azul significa opcional, não erro.", "Workflow")
for stage in overview["stages"]:
    with st.container(border=True):
        c1,c2=st.columns([4,1])
        with c1:
            st.markdown(f"### {stage['icon']} {stage['title']} · {stage['status_label']}")
            st.write(stage["detail"])
            for ev in stage.get("evidence") or []:
                st.caption(ev)
        with c2:
            if stage.get("action_page"):
                st.page_link(stage["action_page"], label=stage.get("action_label") or "Abrir", use_container_width=True)

section_title("3. Edições & mercados", "Uma linha por locale. Tradução aprovada, audiobook e distribuição continuam sendo estados separados.", "Editions")
if matrix:
    st.dataframe(matrix, use_container_width=True, hide_index=True)
else:
    st.caption("Nenhuma edição derivada encontrada.")

c1,c2,c3=st.columns(3)
with c1:
    st.page_link("pages/21_Translation_Localization_Studio.py", label="🌍 Traduções", use_container_width=True)
with c2:
    st.page_link("pages/22_📐_Publishing_Platform_Engine.py", label="📐 Formatos por plataforma", use_container_width=True)
with c3:
    st.page_link("pages/26_🌐_Publishing_Distribution_Center.py", label="🌐 Distribuição", use_container_width=True)

st.page_link("pages/33_🧭_Integration_UX_Center.py", label="🧭 Abrir Integration & UX Center →", use_container_width=True)

section_title("4. Produtos derivados", "O Hub mostra o que existe; Activity Book e Audiobook continuam opcionais e independentes.", "Products")
p1,p2,p3=st.columns(3)
p1.metric("Projetos de tradução", overview["translations"]["projects"])
p2.metric("Activity Books", overview["activities"]["projects"])
p3.metric("Audiobooks", overview["audiobooks"]["projects"])
st.caption(f"Traduções aprovadas: {overview['translations']['approved_locales']} locale(s) · Folhas de atividade aprovadas: {overview['activities']['approved_pages']} · Audiobooks finais aprovados: {overview['audiobooks']['approved_projects']}")

section_title("5. Release snapshot", "Exporte um manifesto de acompanhamento desta versão. Ele não substitui os arquivos de publicação nem o certificado do Quality Guardian.", "Audit")
snapshot=build_project_snapshot(state, overview, matrix)
st.download_button("⬇️ Baixar snapshot do Project Hub", data=snapshot, file_name="faithbloom-project-hub-snapshot.json", mime="application/json", use_container_width=True)
st.caption(f"Fingerprint atual: {overview['project_fingerprint']}")

callout(
    "O Hub não muda o Book Master",
    "Esta tela agrega e navega. Correções, aprovações, traduções, áudio e status de loja continuam sendo feitos nos Studios responsáveis, preservando histórico e decisões humanas registradas.",
    "🔒",
)
