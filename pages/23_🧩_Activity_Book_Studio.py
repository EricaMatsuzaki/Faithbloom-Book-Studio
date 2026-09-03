"""Refinamento 08 — Activity Book Studio: Kids, Teens & Adults."""
from __future__ import annotations
import json
import os
import streamlit as st
import streamlit.components.v1 as components

from estilo import aplicar_estilo, hero, section_title, callout
from activity_studio import (
    AUDIENCE_PRESETS, DIFFICULTY_PROFILES, CONTENT_THEMES, ACTIVITY_CATALOG,
    available_activity_types, create_activity_page, revise_activity_page,
    attach_qa, approve_activity_page, reject_activity_page,
    create_activity_project, save_activity_project, load_activity_project,
    list_activity_projects, add_page_to_project, replace_page_in_project,
    project_readiness, story_to_activity_suggestions, build_activity_prompt,
    generation_prompt, normalize_llm_activity_result, render_activity_svg,
)
from armazenamento import listar_livros, carregar_livro
from character_universe import listar_personagens_oficiais, carregar_personagem_oficial, personagem_para_prompt

st.set_page_config(page_title="Activity Book Studio · FaithBloom", page_icon="🧩", layout="wide")
aplicar_estilo()
hero("Activity Book Studio", "Crie e revise folhas de atividades para crianças, adolescentes, adultos e terceira idade — com QA objetivo, gabarito e sua aprovação página por página.", "Refinamento 08 · Kids, Teens & Adults")
callout("Você mantém o controle editorial", "Nenhuma folha entra no livro só porque foi gerada. O fluxo é Rascunho → QA → sua revisão → Aprovar / Modificar somente isto / Variação B/C.", "✅")

# ---- Project
section_title("1 · Projeto & público", "A faixa/público muda instrução, tipografia, densidade visual e tipos sugeridos. A dificuldade é independente da idade.", "Audience Engine")
projects=list_activity_projects()
mode=st.radio("Projeto",["Criar novo","Abrir existente"],horizontal=True)
project=None
if mode=="Abrir existente" and projects:
    pid=st.selectbox("Projeto salvo",[p["id"] for p in projects],format_func=lambda x: next((p["title"] for p in projects if p["id"]==x),x))
    project=load_activity_project(pid)
elif mode=="Abrir existente":
    st.info("Ainda não há Activity Books salvos. Crie o primeiro projeto.")
else:
    c1,c2,c3=st.columns(3)
    title=c1.text_input("Título do Activity Book",placeholder="Ex.: Aventuras e Atividades com Mel")
    audience=c2.selectbox("Público / faixa",list(AUDIENCE_PRESETS),format_func=lambda x:AUDIENCE_PRESETS[x]["label"])
    difficulty=c3.selectbox("Complexidade",list(DIFFICULTY_PROFILES),index=1,format_func=lambda x:DIFFICULTY_PROFILES[x]["label"])
    c4,c5=st.columns(2)
    theme=c4.selectbox("Linha de conteúdo",CONTENT_THEMES)
    collection=c5.text_input("Coleção / universo",placeholder="Pequenas Histórias, Grandes Lições")
    if st.button("🧩 Criar Activity Book",type="primary",disabled=not title.strip()):
        project=create_activity_project(title,audience,difficulty,theme,collection)
        st.session_state.r08_project_id=project["id"]; st.success("Projeto criado."); st.rerun()
    if st.session_state.get("r08_project_id"):
        project=load_activity_project(st.session_state.r08_project_id)

if not project:
    st.stop()

st.session_state.r08_project_id=project["id"]
preset=AUDIENCE_PRESETS[project["audience_id"]]
a,b,c,d=st.columns(4)
a.metric("Público",preset["label"]); b.metric("Complexidade",DIFFICULTY_PROFILES[project["difficulty"]]["label"]); c.metric("Fonte mínima",f"{preset['min_font_pt']} pt"); d.metric("Folhas",len(project.get("pages",[])))
st.caption(f"Perfil de leitura: {preset['reading']} · densidade visual: {preset['visual_density']}")

# ---- Story source
section_title("2 · Da história para atividades", "Opcional: use um Story Book salvo para sugerir atividades coerentes com personagens, moral e tema — sem inventar texto bíblico.", "Story → Activities")
books=listar_livros()
if books:
    labels={f"{b.get('titulo')} · {b.get('colecao','')}":b for b in books}
    chosen=st.selectbox("Livro-base (opcional)",["— nenhum —"]+list(labels))
    if chosen!="— nenhum —":
        b=labels[chosen]; story=carregar_livro(b.get("colecao",""),b.get("storage_path") or b.get("arquivo"))
        suggestions=story_to_activity_suggestions(story,project["audience_id"],8)
        st.dataframe([{"atividade":ACTIVITY_CATALOG[s["activity_type"]]["label"],"objetivo":s["objective"],"referência bíblica":s.get("bible_reference_only","")} for s in suggestions],use_container_width=True,hide_index=True)
        st.caption("Quando houver versículo, esta etapa usa somente a referência. O Bible Guard do FaithBloom continua valendo.")
else:
    st.caption("Nenhum Story Book salvo ainda; você pode criar atividades independentes normalmente.")

# ---- Page composer
section_title("3 · Criar uma folha", "Escolha o tipo e monte a estrutura. O QA só declara prontidão quando existe evidência verificável.", "Activity Composer")
types=available_activity_types(project["audience_id"])
c1,c2=st.columns(2)
atype=c1.selectbox("Tipo de atividade",types,format_func=lambda x:ACTIVITY_CATALOG[x]["label"])
objective=c2.text_input("Objetivo",placeholder="Ex.: atenção + contagem / vocabulário / lógica")
instruction=st.text_input("Instrução da folha",placeholder="Ex.: Ajude Mel a encontrar o caminho até Téo.")

# character links
chars=listar_personagens_oficiais(project.get("collection") or None)
char_ids=st.multiselect("Personagens oficiais",[x["id"] for x in chars],format_func=lambda x:next((c["nome"] for c in chars if c["id"]==x),x)) if chars else []
if chars: st.caption("Personagens são vinculados em contexto Activity; DNA bloqueado continua protegido.")

st.markdown("#### Estrutura verificável / gabarito")
st.caption("Cole JSON estruturado quando quiser que o Activity QA valide automaticamente. Há exemplos abaixo; você também pode salvar rascunho e completar depois.")
examples={
 "maze":{"grid":[[0,1,0],[0,0,0],[1,1,0]],"start":[0,0],"end":[2,2]},
 "word_search":{"grid":[list("MELXX"),list("ATEOX"),list("FLORE"),list("XXXXX"),list("XXXXX")],"words":["MEL","TEO"]},
 "spot_difference":{"declared_count":3,"differences":["laço","flor","nuvem"]},
 "connect_dots":{"points":[{"n":1,"x":10,"y":10},{"n":2,"x":20,"y":20},{"n":3,"x":30,"y":10}]},
 "matching":{"pairs":[{"left":"Mel","right":"gatinha"},{"left":"Téo","right":"passarinho"}]},
 "match_pairs":{"pairs":[{"left":"A","right":"A"},{"left":"B","right":"B"}]},
 "patterns":{"sequence":[1,2,1,2],"answer":1}, "simple_patterns":{"sequence":["⭐","🌷","⭐","🌷"],"answer":"⭐"},
 "math":{"items":[{"expression":"2+3","answer":5}]}, "simple_math":{"items":[{"expression":"2+1","answer":3}]},
 "count":{"items":["flor","flor","flor"],"answer":3},
 "crossword":{"entries":[{"answer":"MEL","clue":"Gatinha protagonista","row":0,"col":0,"direction":"across"},{"answer":"LUZ","clue":"Brilha","row":0,"col":2,"direction":"down"}]},
 "sudoku":{"board":[[1,0,3,0],[0,4,0,2],[2,0,4,0],[0,3,0,1]]},
 "cryptogram":{"encoded":"ABC","decoded":"MEL","mapping":{"A":"M","B":"E","C":"L"}},
 "trivia":{"questions":[{"question":"Quem é a gatinha?","answer":"Mel"}]},
 "reading_qa":{"questions":[{"question":"O que Mel aprendeu?","answer":"A esperar com fé."}]},
 "journaling":{"prompts":["Escreva uma coisa pela qual você é grato hoje."]},
 "bible_study":{"prompts":["O que esta passagem ensina para a sua vida?"]},
 "bible_activity":{"prompt":"Atividade baseada apenas na referência aprovada; não inserir tradução bíblica automática."},
}
default_json=json.dumps(examples.get(atype,{}),ensure_ascii=False,indent=2)
ai_key=f"r08_ai_{atype}"
if os.environ.get("OPENROUTER_API_KEY"):
    if st.button("✨ Sugerir estrutura com IA",key=f"ai_generate_{atype}"):
        try:
            from openrouter_client import chamar_llm
            sys_prompt,user_prompt=generation_prompt(atype,project["audience_id"],project["difficulty"],project.get("theme",""),objective,{})
            suggestion=normalize_llm_activity_result(chamar_llm(sys_prompt,user_prompt))
            st.session_state[ai_key]=suggestion
            st.success("Sugestão criada como rascunho. Revise antes de salvar e rode o Activity QA.")
        except Exception as exc: st.error(f"Não foi possível gerar a sugestão: {exc}")
else:
    st.caption("🔐 Sem OPENROUTER_API_KEY nesta sessão: exemplos estruturados e edição manual continuam disponíveis sem custo.")
ai=st.session_state.get(ai_key) or {}
if ai.get("designer_notes"): st.info("Designer IA: "+ai["designer_notes"])
if ai.get("instruction") and not instruction: instruction=ai["instruction"]
content_default=json.dumps(ai.get("content") if ai.get("content") else examples.get(atype,{}),ensure_ascii=False,indent=2)
content_text=st.text_area("Conteúdo estruturado (JSON)",value=content_default,height=220,key=f"r08_content_{atype}")
answer_text=st.text_area("Gabarito adicional (JSON opcional)",value=json.dumps(ai.get("answer_key"),ensure_ascii=False,indent=2) if ai.get("answer_key") is not None else "null",height=100,key=f"r08_answer_{atype}")
if st.button("➕ Adicionar folha como rascunho",use_container_width=True):
    try:
        content=json.loads(content_text or "{}"); answer=json.loads(answer_text or "null")
        page=create_activity_page(atype,project["audience_id"],project["difficulty"],instruction=instruction,objective=objective,theme=project.get("theme",""),content=content,answer_key=answer,character_ids=char_ids)
        project=add_page_to_project(project,page); save_activity_project(project); st.success("Folha A salva como rascunho."); st.rerun()
    except Exception as exc: st.error(f"Não foi possível criar a folha: {exc}")

# ---- review queue
section_title("4 · Revisar, modificar e aprovar", "Cada folha tem histórico A/B/C. 'Modificar somente isto' preserva explicitamente os campos que você não quer mexer.", "Author Review")
pages=project.get("pages",[])
if not pages:
    st.info("Crie a primeira folha para iniciar o fluxo de revisão.")
else:
    for idx,p in enumerate(pages,1):
        icon={"approved":"✅","ready_for_author_review":"👀","needs_revision":"🟠","draft":"📝"}.get(p.get("status"),"📝")
        with st.expander(f"{icon} Folha {idx} · {p.get('title')} · versão {p.get('version_label','A')}",expanded=(idx==1)):
            c1,c2,c3,c4=st.columns(4)
            c1.write(f"**Público:** {AUDIENCE_PRESETS[p['audience_id']]['label']}")
            c2.write(f"**Dificuldade:** {DIFFICULTY_PROFILES[p['difficulty']]['label']}")
            c3.write(f"**Status:** {p.get('status')}")
            c4.write(f"**Tipo:** {ACTIVITY_CATALOG[p['activity_type']]['label']}")
            st.write("**Instrução:**",p.get("instruction") or "—")
            svg=render_activity_svg(p)
            with st.expander("📄 Pré-visualizar folha",expanded=True):
                components.html(svg,height=720,scrolling=True)
                st.download_button("⬇️ Baixar preview SVG",data=svg,file_name=f"atividade-{idx}-{p.get('version_label','A')}.svg",mime="image/svg+xml",key=f"svg_{p['id']}")
                st.caption("Preview vetorial para revisão. O arquivo final de publicação ainda passará pelo diagramador/Platform Engine.")
            with st.expander("🧠 Ver estrutura e gabarito",expanded=False):
                st.json({"content":p.get("content"),"answer_key":p.get("answer_key")},expanded=True)
            # prompt protected
            char_prompts=[]
            for cid in p.get("character_ids",[]):
                try: char_prompts.append(personagem_para_prompt(carregar_personagem_oficial(cid),contexto="activity"))
                except Exception: pass
            with st.expander("🎨 Prompt protegido da folha",expanded=False): st.code(build_activity_prompt(p,char_prompts),language=None)
            if st.button("🔬 Rodar Activity QA",key=f"qa_{p['id']}"):
                pp=attach_qa(p); project=replace_page_in_project(project,pp); save_activity_project(project); st.rerun()
            qa=p.get("qa")
            if qa:
                if qa.get("valid"): st.success("QA estrutural passou. Agora depende da sua aprovação editorial/visual.")
                else: st.error(f"{qa.get('blockers',0)} bloqueio(s) precisam ser corrigidos antes da aprovação.")
                for a in qa.get("alerts",[]): st.write(f"- **{a['severity']}** · {a['message']}")
                with st.expander("👁️ Ver gabarito validado",expanded=False): st.json(qa.get("answer_key"),expanded=True)
            st.markdown("##### ✏️ Modificar somente isto")
            change=st.text_input("O que deseja mudar?",placeholder="Ex.: deixe o labirinto mais fácil, sem mudar Mel nem o cenário",key=f"chg_{p['id']}")
            preserve=st.multiselect("Preservar explicitamente",["character_ids","theme","instruction","content","layout","style_id","objective"],default=["character_ids","theme"],key=f"pres_{p['id']}")
            new_instruction=st.text_input("Nova instrução (opcional)",value=p.get("instruction",""),key=f"instr_{p['id']}")
            if st.button("🔄 Criar nova versão",key=f"rev_{p['id']}",disabled=not change.strip()):
                pp=revise_activity_page(p,change_request=change,patch={"instruction":new_instruction},preserve_fields=preserve)
                project=replace_page_in_project(project,pp); save_activity_project(project); st.success(f"Versão {pp['version_label']} criada; anterior preservada no histórico."); st.rerun()
            a1,a2=st.columns(2)
            if a1.button("✅ Aprovar esta folha",key=f"approve_{p['id']}",disabled=not bool(qa and qa.get("valid"))):
                try:
                    pp=approve_activity_page(p); project=replace_page_in_project(project,pp); save_activity_project(project); st.rerun()
                except Exception as exc: st.error(str(exc))
            reason=st.text_input("Motivo para revisão",placeholder="Ex.: letras pequenas / dificuldade alta",key=f"reason_{p['id']}")
            if a2.button("🟠 Solicitar revisão",key=f"reject_{p['id']}"):
                pp=reject_activity_page(p,reason or "Revisão solicitada pela pessoa responsável."); project=replace_page_in_project(project,pp); save_activity_project(project); st.rerun()
            if p.get("revisions"):
                with st.expander(f"🕘 Histórico ({len(p['revisions'])} versão(ões) anteriores)"):
                    for r in reversed(p["revisions"]): st.write(f"**{r['version_label']}** · {r.get('change_request','')}")

# ---- readiness
section_title("5 · Prontidão do Activity Book", "O livro só fica pronto quando todas as folhas passam pelo QA aplicável e são aprovadas por você.", "Quality Gate")
ready=project_readiness(project)
r1,r2,r3=st.columns(3); r1.metric("Folhas",ready["total_pages"]); r2.metric("Aprovadas",ready["approved_pages"]); r3.metric("Com bloqueio QA",ready["qa_blocked_pages"])
if ready["ready"]: st.success("✅ Todas as folhas passaram pelos gates atuais e foram com aprovação humana.")
else: st.info("Ainda não está pronto para montagem final. Continue o ciclo QA → revisão → aprovação.")
st.download_button("⬇️ Exportar projeto JSON",data=json.dumps(project,ensure_ascii=False,indent=2),file_name=f"{project.get('title','activity-book')}.json",mime="application/json")
