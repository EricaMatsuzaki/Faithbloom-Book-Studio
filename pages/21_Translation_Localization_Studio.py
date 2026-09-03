"""Refinamento 06 — Translation & Localization Studio."""
from __future__ import annotations

import json
import string
import tempfile
from pathlib import Path
import streamlit as st

from estilo import aplicar_estilo, hero, section_title, callout
from armazenamento import listar_livros, carregar_livro
from openrouter_client import chamar_llm
from translation_localization import (
    LOCALIZACOES, MODOS, INTENSIDADE_SONS, SOUND_LIBRARY,
    criar_registro_biblico, validar_registro_biblico, texto_biblico_para_exportacao,
    sugerir_onomatopeias, construir_prompt_localizacao, localizar_livro,
    revisar_localizacao_estrutural, revisar_localizacao_com_llm,
    criar_projeto_traducao, listar_projetos_traducao, carregar_projeto_traducao,
    salvar_projeto_traducao, adicionar_versao_localizada, aprovar_versao_localizada,
    extrair_texto_pdf_localizacao, construir_prompt_revisor_linguistico,
)

st.set_page_config(page_title="Translation & Localization Studio", page_icon="🌍", layout="wide")
aplicar_estilo()
hero(
    "🌍 Translation & Localization Studio",
    "Localize livros infantis por idioma e mercado, preserve a voz da coleção, use onomatopeias com equilíbrio e mantenha versículos bíblicos protegidos.",
    "FaithBloom · Refinamento 06",
)

callout(
    "Regra bíblica protegida",
    "O FaithBloom não traduz versículos por conta própria. O texto bíblico só entra na edição quando você fornece/seleciona um texto aprovado e registra versão/fonte. Sem isso, a edição usa apenas a referência.",
    "🔒",
)

livros=listar_livros()
if not livros:
    st.info("Salve um Story Book primeiro para abrir uma tradução vinculada ao Master.")
    st.stop()

opcoes={f"{x['titulo']} · {x.get('colecao','')}":x for x in livros}
label=st.selectbox("📚 Livro Master",list(opcoes))
info=opcoes[label]
master=carregar_livro(info.get("colecao",""),info["arquivo"])

section_title("1. Mercado e estilo de localização", "O mesmo idioma pode ter variantes editoriais diferentes.", "Locale")
c1,c2,c3,c4=st.columns(4)
with c1:
    locale=st.selectbox("Idioma + mercado",list(LOCALIZACOES),index=list(LOCALIZACOES).index("en-US") if "en-US" in LOCALIZACOES else 0)
with c2:
    modo=st.selectbox("Modo",list(MODOS),format_func=lambda x:{"fiel":"Fiel","natural_infantil":"Natural Infantil ⭐","localizacao_cultural":"Localização Cultural"}[x],index=1)
with c3:
    idade=st.selectbox("Faixa de leitura",["3–5","3–8","6–8","9–10","Personalizado"],index=1)
with c4:
    sons=st.selectbox("Onomatopeias",list(INTENSIDADE_SONS),format_func=lambda x:x.capitalize(),index=1)

loc=LOCALIZACOES[locale]
st.caption(f"Destino: {loc['idioma']} · {loc['mercado']} · {loc['ortografia']}")

section_title("2. Glossário protegido", "Nomes e termos recorrentes ficam consistentes entre livros e edições.", "Series Memory")
if "r06_glossary" not in st.session_state: st.session_state.r06_glossary={}
g1,g2,g3=st.columns([1,1,.45])
termo=g1.text_input("Termo Master",placeholder="ex.: Pequenas Histórias, Grandes Lições")
alvo=g2.text_input("Forma aprovada neste locale",placeholder="ex.: Little Stories, Big Lessons")
if g3.button("Adicionar",use_container_width=True,disabled=not termo.strip()):
    st.session_state.r06_glossary[termo.strip()]=alvo.strip() or termo.strip(); st.rerun()
if st.session_state.r06_glossary:
    st.json(st.session_state.r06_glossary,expanded=False)

section_title("3. Onomatopeias & sons", "Sugestões são locais e editáveis. A autora decide o que entra no texto, na arte e depois no audiobook.", "Sound Localization")
evento=st.selectbox("Evento sonoro",list(SOUND_LIBRARY),format_func=lambda x:x.replace('_',' ').title())
opcoes_som=sugerir_onomatopeias(evento,locale)
st.write("Sugestões para este mercado:", " · ".join(opcoes_som) if opcoes_som else "Sem preset; escolha manualmente.")
st.caption("O nível Equilibrado é o padrão: mais energia em humor/ação e menos efeitos em oração, reflexão ou cenas emocionais delicadas.")

section_title("4. Bíblia — conteúdo protegido", "O texto do versículo é tratado fora do tradutor de IA.", "Bible Guard")
ref=master.get("versiculo_referencia","")
b1,b2=st.columns(2)
with b1:
    st.text_input("Referência bíblica",value=ref,disabled=True)
    bible_mode=st.radio("Nesta edição",["Somente referência","Usar texto bíblico aprovado"],horizontal=True)
with b2:
    versao=st.text_input("Versão bíblica",placeholder="Nome exato da versão utilizada",disabled=bible_mode=="Somente referência")
    fonte=st.text_input("Fonte/licença/observação",placeholder="Fonte ou nota de licença",disabled=bible_mode=="Somente referência")
texto_biblico=st.text_area("Texto exato do versículo aprovado",height=110,disabled=bible_mode=="Somente referência",help="Cole aqui o texto da versão bíblica escolhida. O FaithBloom não o reescreve nem o traduz.")
aprovado=st.checkbox("Confirmo que este é o texto bíblico que desejo usar nesta edição",disabled=bible_mode=="Somente referência")
bible=criar_registro_biblico(ref,locale,versao=versao,texto_aprovado=texto_biblico,fonte=fonte,aprovado=aprovado) if bible_mode!="Somente referência" else criar_registro_biblico(ref,locale)
erros_biblia=validar_registro_biblico(bible)
if erros_biblia and bible_mode!="Somente referência": st.warning(" · ".join(erros_biblia))
else:
    exp=texto_biblico_para_exportacao(bible)
    st.success("🔒 Bible Guard ativo. " + ("Texto aprovado poderá ser inserido na exportação." if exp["pode_exportar_texto"] else "Somente a referência será inserida."))

section_title("5. Gerar e revisar", "A tradução vira uma nova versão; o Master nunca é sobrescrito.", "A/B/C Versions")
instrucoes=st.text_area("Instruções adicionais para este mercado",placeholder="Ex.: manter o humor do Max suave; evitar gírias muito regionais.")

with st.expander("🔎 Ver regras que serão enviadas ao tradutor",expanded=False):
    prompt,payload=construir_prompt_localizacao(master,locale,modo=modo,faixa_etaria=idade,intensidade_sons=sons,glossario=st.session_state.r06_glossary,instrucoes=instrucoes)
    st.code(prompt,language="text")
    st.json(payload,expanded=False)

if st.button("🌍 Gerar localização",type="primary",use_container_width=True):
    with st.spinner("Localizando o livro sem tocar no Master..."):
        traducao=localizar_livro(master,chamar_llm,locale,modo=modo,faixa_etaria=idade,intensidade_sons=sons,glossario=st.session_state.r06_glossary,bible_record=bible,instrucoes=instrucoes)
    st.session_state.r06_translation=traducao
    st.session_state.r06_review=revisar_localizacao_estrutural(master,traducao,bible_record=bible,glossario=st.session_state.r06_glossary)

trad=st.session_state.get("r06_translation")
if trad:
    a,b=st.columns(2,gap="large")
    with a:
        st.markdown("#### 🔒 Master")
        st.write(master.get("titulo","")); st.json(master.get("cenas_texto",[])[:4],expanded=False)
    with b:
        st.markdown(f"#### 🌍 {locale} · rascunho")
        st.write(trad.get("titulo",master.get("titulo",""))); st.json(trad.get("cenas_texto",[])[:4],expanded=False)
    review=st.session_state.get("r06_review",{})
    if review.get("ok"): st.success("✅ Verificação estrutural passou. Ainda requer revisão linguística/humana antes de publicar.")
    else: st.error(f"❌ {review.get('bloqueantes',0)} bloqueio(s) estrutural(is).")
    for al in review.get("alertas",[]): st.write(f"- **{al['nivel']}** · {al['mensagem']}")

    if st.button("🧑‍🏫 Rodar Revisor Linguístico Independente"):
        with st.spinner("Comparando Master × localização..."):
            st.session_state.r06_ai_review=revisar_localizacao_com_llm(master,trad,chamar_llm,locale,idade)
    if st.session_state.get("r06_ai_review"):
        st.markdown("#### Parecer do Revisor Linguístico")
        st.json(st.session_state.r06_ai_review)

    st.download_button("⬇️ Baixar rascunho JSON",data=json.dumps(trad,ensure_ascii=False,indent=2),file_name=f"{locale}-translation-draft.json",mime="application/json",use_container_width=True)

    section_title("6. Salvar como versão", "A/B/C ficam preservadas; aprovar uma não apaga as anteriores.", "Version History")
    projetos=listar_projetos_traducao()
    matching=[p for p in projetos if p.get("titulo")==master.get("titulo") and p.get("colecao")==master.get("colecao")]
    if matching:
        proj=carregar_projeto_traducao(matching[0]["id"])
    else:
        if st.button("Criar projeto de tradução para este Master"):
            proj=criar_projeto_traducao(master.get("titulo",""),master.get("colecao",""),master.get("idioma_original","pt-BR"),info.get("storage_path",info.get("arquivo","")))
            st.session_state.r06_project_id=proj["id"]; st.rerun()
        proj=carregar_projeto_traducao(st.session_state.get("r06_project_id","")) if st.session_state.get("r06_project_id") else {}
    if proj:
        label_version=st.selectbox("Rótulo",list(string.ascii_uppercase[:8]))
        if st.button("💾 Salvar esta versão"):
            proj["glossario"]=dict(st.session_state.r06_glossary); proj.setdefault("bible_records",{})[locale]=bible
            proj=salvar_projeto_traducao(proj); proj=adicionar_versao_localizada(proj,locale,trad,label_version)
            st.success(f"Versão {label_version} salva sem apagar as anteriores.")
        ed=(proj.get("edicoes",{}) or {}).get(locale,{})
        versions=ed.get("versoes",[]) or []
        if versions:
            ids={f"{v.get('label','?')} · {v.get('versao_id','')[:8]}":v.get('versao_id') for v in versions}
            sel=st.selectbox("Versões salvas",list(ids))
            if st.button("✅ Aprovar versão selecionada"):
                aprovar_versao_localizada(proj,locale,ids[sel]); st.success("Versão aprovada como edição ativa deste locale."); st.rerun()

section_title("7. Auditar tradução já existente", "Importe uma edição publicada/antiga sem substituir o Master. O FaithBloom usa a camada de texto do PDF e não inventa OCR quando ela não existe.", "Legacy Translation Audit")
existing_pdf=st.file_uploader("PDF da tradução existente",type=["pdf"],key="r06_existing_pdf")
existing_locale=st.selectbox("Locale da edição importada",list(LOCALIZACOES),key="r06_existing_locale")
if existing_pdf is not None:
    suffix=Path(existing_pdf.name).suffix or ".pdf"
    with tempfile.NamedTemporaryFile(delete=False,suffix=suffix) as tmp:
        tmp.write(existing_pdf.getbuffer()); temp_path=tmp.name
    audit=extrair_texto_pdf_localizacao(temp_path)
    st.write(f"Páginas: **{audit['paginas_total']}** · caracteres de texto extraídos: **{audit['caracteres_extraidos']}**")
    if not audit["texto_disponivel"]:
        st.warning("Este PDF não possui camada de texto utilizável. O FaithBloom não fará OCR automaticamente nem inventará uma tradução para comparar.")
    else:
        with st.expander("Ver amostra do texto importado"):
            st.text("\n\n".join(f"[p.{x['pagina']}] {x['texto'][:1200]}" for x in audit['paginas'][:6]))
        if st.button("🧑‍🏫 Auditar edição existente com Revisor Linguístico"):
            imported={"locale":existing_locale,"texto_importado_por_pagina":audit["paginas"],"bible_ai_translation_allowed":False}
            prompt=construir_prompt_revisor_linguistico(master,imported,existing_locale,idade)
            with st.spinner("Comparando a edição existente com o Master..."):
                st.session_state.r06_legacy_review=chamar_llm(sistema=prompt,instrucao="Audite a edição importada. Não gere nem traduza texto bíblico.")
        if st.session_state.get("r06_legacy_review"):
            st.json(st.session_state.r06_legacy_review)

st.divider()
st.caption("FaithBloom 2.0 · Refinamento 06 · Translation & Localization Studio · locale por mercado · onomatopeias equilibradas · Bible Guard · revisão independente · versões A/B/C.")
