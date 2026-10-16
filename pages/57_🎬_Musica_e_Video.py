"""Human-reviewed media production from original approved assets."""
from __future__ import annotations

import json

import streamlit as st

from estilo import aplicar_estilo, hero
from media_studio import MediaStudioStore, MediaStudioError, ReplicateMediaClient, media_readiness, render_animatic
from storage_backend import materializar

st.set_page_config(page_title="Música e Vídeo · FaithBloom", page_icon="🎬", layout="wide")
aplicar_estilo()
hero("Música, Vídeo e Ideias", "Transforme suas artes aprovadas em um animatic e revise cada nova criação.")
st.page_link("pages/00_🤖_Jarvis.py", label="← Voltar ao Jarvis")

store = MediaStudioStore()
readiness = media_readiness()
client = ReplicateMediaClient(store)


def attempt(callback):
    try:
        return callback()
    except MediaStudioError as exc:
        st.error(str(exc))
    except Exception:
        st.error("Não foi possível concluir agora. Nenhuma geração paga será repetida automaticamente.")
    return None


media_tab, ideas_tab = st.tabs(["Projetos de mídia", "Cofre de ideias"])

with media_tab:
    st.caption("O animatic local usa movimento suave de câmera sobre a arte original. Ele não anima braços, olhos ou expressões dos personagens.")
    with st.expander("Criar um projeto", expanded=True):
        with st.form("fb57_new_project"):
            title = st.text_input("Título")
            kind = st.radio("Produzir", ["animation_video", "music"], format_func=lambda value: "Vídeo / animatic" if value == "animation_video" else "Música", horizontal=True)
            source_ref = st.text_input("Referência do livro ou Master de origem (opcional)")
            if st.form_submit_button("Criar projeto"):
                created = attempt(lambda: store.create(title, kind, source_ref=source_ref))
                if created:
                    st.session_state["fb57_project_id"] = created["id"]
                    st.rerun()

    projects = attempt(store.list_projects) or []
    projects = [p for p in projects if isinstance(p, dict) and p.get("id")]
    if not projects:
        st.info("Crie um projeto para guardar suas fontes e os resultados de mídia.")
    else:
        ids = [p["id"] for p in projects]
        names = {p["id"]: p["title"] for p in projects}
        active = st.session_state.get("fb57_project_id")
        project_id = st.selectbox("Projeto", ids, index=ids.index(active) if active in ids else 0, format_func=lambda value: f"{names[value]} · {value[:8]}")
        st.session_state["fb57_project_id"] = project_id
        state = attempt(lambda: store.load(project_id))
        if state:
            prefix = f"fb57_{project_id}"
            st.caption(f"Estado: {state['status']} · Fontes e resultados ficam no mesmo projeto. A aprovação não promove nenhum Master.")
            if state["kind"] == "animation_video":
                with st.form(f"{prefix}_sources", clear_on_submit=True):
                    images = st.file_uploader("Artes originais aprovadas, na ordem do vídeo", type=["png", "jpg", "jpeg", "webp"], accept_multiple_files=True)
                    provenance = st.text_input("Origem destas artes", value=state.get("source_ref") or "upload da autora")
                    approved = st.checkbox("Revisei as imagens e aprovo seu uso neste vídeo")
                    if st.form_submit_button("Adicionar fontes aprovadas"):
                        added = False
                        for image in images or []:
                            result = attempt(lambda data=image.getvalue(): store.add_image(project_id, data, approved=approved, provenance=provenance))
                            added = bool(result) or added
                        if added:
                            st.rerun()
                for index, source in enumerate(state["sources"]):
                    st.image(materializar(source["asset"]), caption=f"Fonte {index + 1} · original aprovado", width=160)
                with st.form(f"{prefix}_audio", clear_on_submit=True):
                    audio = st.file_uploader("Áudio opcional aprovado", type=["wav", "mp3"])
                    approved_audio = st.checkbox("Revisei o áudio e aprovo seu uso")
                    if st.form_submit_button("Adicionar áudio") and audio:
                        if attempt(lambda: store.add_audio(project_id, audio.getvalue(), approved=approved_audio)):
                            st.rerun()
                if state.get("audio"):
                    st.audio(materializar(state["audio"]["asset"]))
                seconds = st.slider("Segundos por imagem", 1, 10, 3, key=f"{prefix}_seconds")
                if not readiness["local_animatic"]["available"]:
                    st.info("O servidor precisa instalar ffmpeg para habilitar o render local.")
                if st.button("Renderizar animatic MP4 local", disabled=not state["sources"] or not readiness["local_animatic"]["available"], key=f"{prefix}_render"):
                    with st.spinner("Preparando seu animatic..."):
                        result = attempt(lambda: render_animatic(store, project_id, seconds_per_image=seconds))
                    if result:
                        st.rerun()

            provider = readiness[state["kind"]]
            with st.expander("Gerar com modelo de IA configurado"):
                if not provider["available"]:
                    st.info("Esta geração precisa de modelo, campos de entrada, estimativa de custo e orçamento configurados pelo administrador. O envio pago deve operar em um único worker declarado.")
                else:
                    st.write("Modelo:", provider["model"])
                    st.caption(f"Estimativa por pedido: US$ {provider['estimated_cost_usd']:.2f}. Teto estimado deste projeto: US$ {provider['max_cost_usd']:.2f}. O preço final depende do provedor.")
                    st.caption("Campos aceitos: " + ", ".join(provider["input_fields"]))
                    source_id = ""
                    if state["kind"] == "animation_video":
                        source_ids = [s["id"] for s in state["sources"]]
                        if source_ids:
                            source_id = st.selectbox("Imagem aprovada para o modelo", source_ids, format_func=lambda value: f"Fonte {source_ids.index(value) + 1}", key=f"{prefix}_provider_source")
                        st.caption(f"A imagem original será enviada no campo {provider['image_input_field']}; não preencha esse campo no JSON.")
                    input_text = st.text_area("Entrada JSON conforme a documentação do modelo", value="{}", key=f"{prefix}_input")
                    if st.button("Preparar pedido para revisão", key=f"{prefix}_draft"):
                        def prepare():
                            try:
                                payload = json.loads(input_text)
                            except ValueError:
                                raise MediaStudioError("Informe um objeto JSON válido.") from None
                            return client.draft(project_id, payload, source_id=source_id)
                        draft = attempt(prepare)
                        if draft:
                            st.session_state[f"{prefix}_draft_value"] = draft
                    draft = st.session_state.get(f"{prefix}_draft_value")
                    if draft:
                        # Do not print base64 images or credentials in review.
                        review = {k: v for k, v in draft["input"].items() if k != provider.get("image_input_field")}
                        st.json({"model": draft["model"], "input": review, "source_id": draft["source_id"], "estimated_cost_usd": draft["estimated_cost_usd"]})
                        confirmed = st.checkbox("Confirmo esta entrada, a fonte aprovada e o custo estimado", key=f"{prefix}_confirm_{draft['fingerprint']}")
                        if st.button("Confirmar e enviar esta geração", disabled=not confirmed, key=f"{prefix}_submit_{draft['fingerprint']}"):
                            if attempt(lambda: client.submit(draft, confirmed_fingerprint=draft["fingerprint"])):
                                st.session_state.pop(f"{prefix}_draft_value", None)
                                st.rerun()

            for job in state["jobs"]:
                st.write(f"Processamento {job['id'][:8]}: {job['status']}")
                if job.get("prediction_id") and not job.get("output_id") and job["status"] not in {"failed", "canceled"}:
                    if st.button("Atualizar processamento", key=f"{prefix}_poll_{job['id']}"):
                        if attempt(lambda: client.poll(project_id, job["id"])):
                            st.rerun()
                elif job["status"] in {"submission_pending", "submission_uncertain"}:
                    st.warning("Envio sem confirmação. Confira o painel do provedor; este projeto bloqueará novos pedidos pagos até a reconciliação.")

            for output in reversed(state["outputs"]):
                with st.container(border=True):
                    st.write("Resultado:", output["status"])
                    local = materializar(output["asset"])
                    if state["kind"] == "music":
                        st.audio(local)
                    else:
                        st.video(local)
                    with open(local, "rb") as media_file:
                        st.download_button("Baixar mídia", media_file.read(), file_name=f"faithbloom-{output['id']}{'.mp4' if state['kind'] == 'animation_video' else ('.wav' if 'wav' in output['inspection']['format'] else '.mp3')}", key=f"{prefix}_download_{output['id']}")
                    if not output["approved"]:
                        confirmed = st.checkbox("Revisei esta mídia e aprovo o resultado", key=f"{prefix}_approve_{output['id']}")
                        if st.button("Aprovar este resultado", disabled=not confirmed, key=f"{prefix}_approve_button_{output['id']}"):
                            if attempt(lambda: store.approve_output(project_id, output["id"], confirmed=confirmed)):
                                st.rerun()

with ideas_tab:
    with st.form("fb57_idea", clear_on_submit=True):
        title = st.text_input("Nome da ideia")
        text = st.text_area("Guarde sua inspiração")
        if st.form_submit_button("Guardar ideia"):
            if attempt(lambda: store.capture_idea(text, title=title)):
                st.rerun()
    for idea in attempt(store.list_ideas) or []:
        with st.container(border=True):
            st.markdown(f"**{idea['title']}**")
            st.text(idea["text"])
            st.caption(idea["status"])
            if idea["status"] == "captured" and st.button("Escolher esta ideia para desenvolver", key=f"fb57_idea_{idea['id']}"):
                if attempt(lambda: store.approve_idea(idea["id"], confirmed=True)):
                    st.rerun()
