"""Refinamento 09 — Audiobook Studio Professional."""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import streamlit as st

from estilo import aplicar_estilo, hero, section_title, callout
from armazenamento import listar_livros, carregar_livro
from audiobook_studio import (
    STUDIO_MODES, CAST_MODES, VOICE_STYLE_PRESETS, EMOTION_PRESETS,
    create_voice_profile, save_voice_profile, list_voice_profiles,
    create_audiobook_project, save_audiobook_project, load_audiobook_project, list_audiobook_projects,
    upsert_project_voice, assign_voice, add_pronunciation,
    revise_script_scene, approve_script_scene, voice_director_prompt, normalize_voice_director_result,
    build_generation_units, estimate_project_audio, create_audiobook_job, executor_audiobook,
    approve_audio_version, favorite_audio_version, audio_readiness, merge_approved_audio,
    approve_final_mix, distribution_readiness, export_audiobook_package, apply_automatic_direction_project,
)
from fila_producao import listar_jobs, processar_proximo, processar_lote, pausar_job, continuar_job, cancelar_job, resumo_job

st.set_page_config(page_title="Audiobook Studio · FaithBloom", page_icon="🎧", layout="wide")
aplicar_estilo()
hero("Audiobook Studio Professional", "Dirija, escute, revise e aprove o audiobook cena por cena — com narrador único ou elenco, pronúncia, versões, fila e QA técnico.", "Refinamento 09 · Voice Direction + TTS + QA")
callout("Você aprova a performance", "O Voice Director pode sugerir emoção, ritmo e divisão de falas, mas não pode reescrever a história. Nenhum áudio vira final só porque foi gerado.", "🎙️")
callout("Bible Guard permanece ativo", "Versículos não são traduzidos nem inventados pela IA. O audiobook usa apenas a referência ou o texto exato de uma versão bíblica já aprovada pela pessoa responsável.", "🔒")

# ---------------- Project
section_title("1 · Projeto de audiobook", "Abra um projeto existente ou crie uma edição de áudio a partir de um Story Book salvo.", "Audio Project")
projects=list_audiobook_projects()
mode=st.radio("Projeto",["Criar novo","Abrir existente"],horizontal=True)
project=None
if mode=="Abrir existente" and projects:
    pid=st.selectbox("Projeto salvo",[p["id"] for p in projects],format_func=lambda x:next((f"{p.get('title')} · {p.get('locale')}" for p in projects if p["id"]==x),x))
    project=load_audiobook_project(pid)
elif mode=="Abrir existente":
    st.info("Ainda não há projetos de audiobook salvos.")
else:
    books=listar_livros()
    labels={f"{b.get('titulo')} · {b.get('colecao','')}":b for b in books}
    source_label=st.selectbox("Story Book de origem",["— projeto independente —"]+list(labels))
    c1,c2,c3=st.columns(3)
    locale=c1.text_input("Locale",value="pt-BR",help="Ex.: pt-BR, en-US, en-GB, ja-JP")
    studio_mode=c2.selectbox("Modo",list(STUDIO_MODES),format_func=lambda x:STUDIO_MODES[x].split(" — ")[0])
    cast_mode=c3.selectbox("Elenco",list(CAST_MODES),format_func=lambda x:CAST_MODES[x])
    source_state=None; source_ref=""; collection=""
    default_title=""
    if source_label!="— projeto independente —":
        b=labels[source_label]; source_ref=b.get("storage_path") or b.get("arquivo",""); collection=b.get("colecao","")
        source_state=carregar_livro(collection,source_ref); default_title=source_state.get("titulo",b.get("titulo",""))
    title=st.text_input("Título da edição de áudio",value=default_title)
    if st.button("🎧 Criar projeto de audiobook",type="primary",disabled=not title.strip()):
        project=create_audiobook_project(title,locale,collection=collection,source_ref=source_ref,mode=studio_mode,cast_mode=cast_mode,source_state=source_state)
        project=save_audiobook_project(project); st.session_state.r09_project_id=project["id"]; st.success("Projeto criado."); st.rerun()
    if st.session_state.get("r09_project_id"):
        project=load_audiobook_project(st.session_state.r09_project_id)

if not project:
    st.stop()
st.session_state.r09_project_id=project["id"]

m1,m2,m3,m4=st.columns(4)
m1.metric("Locale",project.get("locale","")); m2.metric("Elenco",CAST_MODES.get(project.get("cast_mode"),project.get("cast_mode","")))
m3.metric("Cenas",len(project.get("script_scenes",[]))); m4.metric("Status",project.get("status","draft"))
est=estimate_project_audio(project)
st.caption(f"Estimativa antes da geração: ~{est['estimated_minutes']:.1f} min · {est['segments']} segmentos · ~US${est['estimated_cost_usd']:.2f}. É uma estimativa configurável, não preço oficial do provedor.")

# ---------------- Voice library / casting
section_title("2 · Voice Profiles & elenco", "Salve vozes reutilizáveis. O ID da voz depende do provedor TTS configurado; se ficar vazio, o conector usa a voz padrão.", "Voice Library")
left,right=st.columns([1,1])
with left:
    with st.expander("➕ Criar Voice Profile",expanded=not bool(project.get("voice_profiles"))):
        v1,v2=st.columns(2)
        vname=v1.text_input("Nome do perfil",placeholder="Ex.: Narradora Mel — PT-BR")
        vrole=v2.selectbox("Papel",["narrator","character","guide","other"])
        v3,v4=st.columns(2)
        vstyle=v3.selectbox("Estilo",list(VOICE_STYLE_PRESETS),format_func=lambda x:VOICE_STYLE_PRESETS[x]["label"])
        vprovider=v4.text_input("ID da voz no provedor (opcional)")
        default_pace=VOICE_STYLE_PRESETS[vstyle]["pace_wpm"]
        v5,v6=st.columns(2)
        vpace=v5.slider("Ritmo-base (palavras/min)",75,220,int(default_pace))
        vspeed=v6.slider("Velocidade pós-processada",0.75,1.30,1.0,0.05)
        vnotes=st.text_area("Notas de direção",value=VOICE_STYLE_PRESETS[vstyle]["notes"])
        vfav=st.checkbox("⭐ Favoritar este Voice Profile")
        if st.button("💾 Salvar voz e vincular ao projeto",disabled=not vname.strip()):
            vp=create_voice_profile(vname,project.get("locale","pt-BR"),role=vrole,provider_voice_id=vprovider,style_id=vstyle,pace_wpm=vpace,speed=vspeed,notes=vnotes,favorite=vfav)
            save_voice_profile(vp); project=upsert_project_voice(project,vp); project=save_audiobook_project(project); st.success("Voice Profile salvo."); st.rerun()

    library=list_voice_profiles(project.get("locale"))
    if library:
        attach=st.selectbox("Importar voz da biblioteca",[""]+[x["id"] for x in library],format_func=lambda x:"— selecione —" if not x else next((v["name"] for v in library if v["id"]==x),x))
        if attach and st.button("➕ Vincular Voice Profile existente"):
            vp=next(v for v in library if v["id"]==attach); project=upsert_project_voice(project,vp); project=save_audiobook_project(project); st.rerun()
with right:
    voices=project.get("voice_profiles") or {}
    if not voices:
        st.warning("Crie ou vincule ao menos uma voz antes da geração TTS.")
    else:
        st.markdown("#### Casting")
        speakers=project.get("known_speakers") or ["narrator"]
        if project.get("cast_mode")=="single_narrator": speakers=["narrator"]
        for speaker in speakers:
            current=(project.get("casting") or {}).get(speaker,"")
            options=list(voices)
            idx=options.index(current) if current in options else 0
            chosen=st.selectbox(f"{speaker}",options,index=idx,key=f"cast_{speaker}",format_func=lambda x:voices[x].get("name",x))
            if chosen!=current:
                project=assign_voice(project,speaker,chosen); project=save_audiobook_project(project)
        st.caption("Em elenco múltiplo, a divisão de falas é feita no roteiro de performance; a autora pode corrigir qualquer speaker.")

# ---------------- Pronunciation
section_title("3 · Dicionário de pronúncia", "Corrija nomes, palavras estrangeiras ou termos recorrentes sem alterar o texto editorial exibido.", "Pronunciation")
p1,p2,p3=st.columns([1,1,1])
term=p1.text_input("Termo",placeholder="Téo")
spoken=p2.text_input("Falar como",placeholder="Tê-o")
note=p3.text_input("Nota",placeholder="nome do personagem")
if st.button("➕ Adicionar pronúncia",disabled=not(term.strip() and spoken.strip())):
    project=add_pronunciation(project,term,spoken,locale=project.get("locale"),note=note); project=save_audiobook_project(project); st.rerun()
if project.get("pronunciations"):
    st.dataframe([{k:r.get(k,"") for k in ("term","spoken_as","locale","note")} for r in project["pronunciations"]],use_container_width=True,hide_index=True)

# ---------------- Script direction
section_title("4 · Roteiro de performance", "Texto aprovado fica protegido. Você dirige emoção, ritmo, pausas, ênfases e falas sem precisar reescrever a história.", "Voice Director")
scenes=project.get("script_scenes") or []
if project.get("mode")=="automatic" and scenes:
    if st.button("✨ Aplicar direção automática conservadora às cenas não aprovadas"):
        project=apply_automatic_direction_project(project,only_unapproved=True); project=save_audiobook_project(project); st.success("Direção automática aplicada como rascunho. Revise e aprove cada cena."); st.rerun()
    st.caption("O modo Automático ajusta ritmo/pausas por emoção sem alterar o texto. Para divisão inteligente de falas, use o AI Voice Director na cena e aprove o resultado.")
if not scenes:
    st.info("Este projeto ainda não possui cenas. Para um projeto independente, importe/crie o texto no Story Book Studio antes de produzir o audiobook.")
else:
    nums=[int(s.get("numero",0)) for s in scenes]
    selected=st.selectbox("Cena",nums,format_func=lambda n:next((f"Cena {n} · {s.get('scene_type','story')} · {s.get('status','draft')}" for s in scenes if int(s.get('numero',0))==n),str(n)))
    idx=next(i for i,s in enumerate(scenes) if int(s.get("numero",0))==selected); scene=scenes[idx]
    st.text_area("Texto-fonte protegido",value=scene.get("source_text",""),height=150,disabled=True)
    c1,c2,c3=st.columns(3)
    emotion=c1.selectbox("Emoção",EMOTION_PRESETS,index=EMOTION_PRESETS.index(scene.get("emotion")) if scene.get("emotion") in EMOTION_PRESETS else 0)
    pace=c2.slider("Ritmo (palavras/min)",75,220,int(scene.get("pace_wpm",140)))
    pause_after=c3.slider("Pausa após a cena (ms)",0,5000,int(scene.get("pause_after_ms",650)),50)
    emphasis=st.text_input("Palavras para ênfase",value=", ".join(scene.get("emphasis") or []),placeholder="fé, esperar, alegria")
    segments=scene.get("segments") or []
    if project.get("cast_mode")=="narrator_characters":
        st.markdown("##### Falas / speakers")
        seg_json=st.text_area("Segmentos (modo avançado)",value=json.dumps(segments,ensure_ascii=False,indent=2),height=220,help="O FaithBloom recusa aprovação se as palavras do texto-fonte forem alteradas ou omitidas.")
    else:
        seg_json=json.dumps([{"speaker":"narrator","text":scene.get("source_text",""),"emotion":emotion,"pace_wpm":pace,"pause_after_ms":0}],ensure_ascii=False)

    b1,b2,b3=st.columns(3)
    if b1.button("💾 Salvar direção / nova versão"):
        try:
            parsed=json.loads(seg_json)
            patch={"emotion":emotion,"pace_wpm":pace,"pause_after_ms":pause_after,"emphasis":[x.strip() for x in emphasis.split(",") if x.strip()],"segments":parsed}
            new=revise_script_scene(scene,change_request="Direção de voz editada pela pessoa responsável",patch=patch,preserve_text=True)
            project["script_scenes"][idx]=new; project=save_audiobook_project(project); st.success(f"Versão {new['version_label']} salva."); st.rerun()
        except Exception as exc: st.error(str(exc))
    if b2.button("✨ Sugerir direção com AI Voice Director",disabled=not bool(os.environ.get("OPENROUTER_API_KEY"))):
        try:
            from openrouter_client import chamar_llm
            system,user=voice_director_prompt(scene,project); result=chamar_llm(system,user); directed=normalize_voice_director_result(scene,result)
            project["script_scenes"][idx]=directed; project=save_audiobook_project(project)
            if directed.get("voice_director_alert"): st.warning(directed["voice_director_alert"])
            else: st.success("Direção sugerida. Revise antes de aprovar.")
            st.rerun()
        except Exception as exc: st.error(f"Voice Director: {exc}")
    if b3.button("✅ Aprovar roteiro desta cena"):
        try:
            project["script_scenes"][idx]=approve_script_scene(scene); project=save_audiobook_project(project); st.success("Roteiro de performance aprovado."); st.rerun()
        except Exception as exc: st.error(str(exc))
    if not os.environ.get("OPENROUTER_API_KEY"):
        st.caption("AI Voice Director indisponível sem OPENROUTER_API_KEY. A edição manual continua funcionando.")

# ---------------- Generate queue
section_title("5 · Preview, custo & fila de TTS", "Gere uma cena primeiro. Só depois libere o lote completo. A fila pode pausar, continuar e recuperar checkpoints.", "Production Queue")
voices_ok=bool(project.get("voice_profiles")) and bool(project.get("casting"))
units=build_generation_units(project,only_approved_scripts=True)
st.dataframe([{k:u.get(k) for k in ("scene_number","segment_index","speaker","emotion","pace_wpm","estimated_seconds")} for u in units],use_container_width=True,hide_index=True) if units else st.caption("Aprove ao menos uma cena do roteiro para habilitar a geração.")
if units:
    c1,c2=st.columns(2)
    preview_scene=c1.selectbox("Cena para preview",sorted(set(u["scene_number"] for u in units)),key="r09_preview_scene")
    if c1.button("🎧 Criar fila somente desta cena",disabled=not voices_ok):
        try:
            job=create_audiobook_job(project,[preview_scene]); st.session_state.r09_job_id=job["id"]; st.success("Fila de preview criada.")
        except Exception as exc: st.error(str(exc))
    if c2.button("🏭 Criar fila de todas as cenas aprovadas",disabled=not voices_ok):
        try:
            job=create_audiobook_job(project); st.session_state.r09_job_id=job["id"]; st.success("Fila completa criada.")
        except Exception as exc: st.error(str(exc))

jobs=[j for j in listar_jobs(200) if j.get("tipo")=="audiobook_tts" and (j.get("metadata") or {}).get("project_id")==project.get("id")]
if jobs:
    jid=st.selectbox("Fila de audiobook",[j["id"] for j in jobs],index=0,format_func=lambda x:next((f"{j.get('nome')} · {j.get('status')}" for j in jobs if j["id"]==x),x))
    job=next(j for j in jobs if j["id"]==jid); summary=resumo_job(job)
    st.progress(summary["percentual"]/100.0,text=f"{summary['concluidos']}/{summary['total']} segmentos · {job.get('status')}")
    q1,q2,q3,q4,q5=st.columns(5)
    if q1.button("▶️ Processar próximo",disabled=not bool(os.environ.get("OPENROUTER_API_KEY"))):
        try:
            from openrouter_client import gerar_audio
            job=processar_proximo(jid,executor_audiobook(gerar_audio)); project=job.get("state") or project; project=save_audiobook_project(project); st.rerun()
        except Exception as exc: st.error(str(exc))
    if q2.button("⏩ Processar lote",disabled=not bool(os.environ.get("OPENROUTER_API_KEY"))):
        try:
            from openrouter_client import gerar_audio
            job=processar_lote(jid,executor_audiobook(gerar_audio),quantidade=min(5,max(1,summary["pendentes"]))); project=job.get("state") or project; project=save_audiobook_project(project); st.rerun()
        except Exception as exc: st.error(str(exc))
    if q3.button("⏸️ Pausar"): pausar_job(jid); st.rerun()
    if q4.button("↩️ Continuar"): continuar_job(jid); st.rerun()
    if q5.button("🛑 Cancelar"): cancelar_job(jid); st.rerun()
    if not os.environ.get("OPENROUTER_API_KEY"):
        st.caption("A fila pode ser preparada offline; chamadas TTS ficam desabilitadas até configurar OPENROUTER_API_KEY.")

# ---------------- Review audio versions
section_title("6 · Escuta & aprovação por segmento", "Compare A/B/C, favorite a melhor e aprove explicitamente. Regenerar nunca apaga a anterior.", "Audio Review")
all_units=build_generation_units(project,only_approved_scripts=True)
with_versions=[u for u in all_units if (project.get("audio_versions") or {}).get(u["id"])]
if not with_versions:
    st.caption("Ainda não há áudio gerado neste projeto.")
else:
    unit_id=st.selectbox("Segmento",[u["id"] for u in with_versions])
    versions=(project.get("audio_versions") or {}).get(unit_id,[])
    vid=st.selectbox("Versão",[v["id"] for v in versions],format_func=lambda x:next((f"Versão {v.get('version_label')} · {v.get('speaker')} {'⭐' if v.get('favorite') else ''} {'✅' if v.get('approved') else ''}" for v in versions if v["id"]==x),x))
    v=next(v for v in versions if v["id"]==vid); path=v.get("path","")
    if path and Path(path).exists(): st.audio(path)
    qa=(v.get("metadata") or {}).get("qa") or {}
    if qa.get("alerts"):
        for a in qa["alerts"]: st.warning(f"{a.get('code')}: {a.get('message')}")
    else: st.success("Sem bloqueio técnico conhecido. Ainda é necessária escuta humana.")
    a,b=st.columns(2)
    if a.button("✅ Aprovar esta versão"):
        project=approve_audio_version(project,unit_id,vid); project=save_audiobook_project(project); st.rerun()
    if b.button("⭐ Favoritar / desfavoritar"):
        project=favorite_audio_version(project,unit_id,vid,not bool(v.get("favorite"))); project=save_audiobook_project(project); st.rerun()

# ---------------- Final mix/export
section_title("7 · Mix final, QA & pacote", "Depois que todos os segmentos estiverem aprovados, monte o audiobook completo, escute e só então marque a aprovação final.", "Master Audio")
ready=audio_readiness(project)
if ready["ready"]: st.success(f"Todos os {ready['total_segments']} segmentos têm áudio aprovado e sem bloqueio técnico conhecido.")
else:
    for a in ready.get("alerts",[]): st.error(a["message"]) if a.get("severity")=="blocking" else st.warning(a["message"])

if st.button("🎚️ Montar mix final normalizado",disabled=not ready["ready"]):
    try:
        out_dir=Path("saida_audio"); out_dir.mkdir(exist_ok=True)
        out=str(out_dir/f"faithbloom_{project['id'][:10]}_master.mp3")
        result=merge_approved_audio(project,out,normalize=True); project["final_mix"]=result["path"]; project["final_mix_qa"]=result["qa"]; project=save_audiobook_project(project); st.success("Mix final criado."); st.rerun()
    except Exception as exc: st.error(str(exc))

final=project.get("final_mix","")
if final and Path(final).exists():
    st.audio(final)
    st.caption("Escute o arquivo completo. O QA técnico não consegue decidir sozinho se emoção, interpretação e pronúncia ficaram do jeito que você deseja.")
    checked=st.checkbox("Eu ouvi o mix final e aprovo esta performance para seguir ao Publishing & Distribution Center.")
    if st.button("✅ Registrar aprovação final",disabled=not checked):
        try:
            project=approve_final_mix(project); project=save_audiobook_project(project); st.success("Aprovação final registrada."); st.rerun()
        except Exception as exc: st.error(str(exc))

dist=distribution_readiness(project)
if dist["ready"]: st.success("🟢 Audiobook Studio: pronto para seguir ao módulo de distribuição/publicação.")
else: st.caption("Ainda não está liberado para distribuição pelo FaithBloom.")

if st.button("📦 Gerar pacote de estúdio"):
    try:
        out=str(Path(tempfile.gettempdir())/f"FaithBloom-Audiobook-{project['id'][:8]}.zip")
        result=export_audiobook_package(project,out)
        st.session_state.r09_export=result["path"]
    except Exception as exc: st.error(str(exc))
if st.session_state.get("r09_export") and Path(st.session_state.r09_export).exists():
    data=Path(st.session_state.r09_export).read_bytes()
    st.download_button("⬇️ Baixar pacote do audiobook",data=data,file_name=Path(st.session_state.r09_export).name,mime="application/zip")
    st.caption("Este pacote é o Master de estúdio. Cada plataforma de audiobook ainda deve passar por suas especificações no futuro Publishing & Distribution Center.")
