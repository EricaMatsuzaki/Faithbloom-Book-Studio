"""On-demand personal services with explicit, contextual send confirmation."""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import streamlit as st

from assistant_services import (
    AssistantRoutineStore, AssistantServiceError, AutonomyPolicy, AUTONOMY_MODES,
    GmailClient, WhatsAppBusinessClient, connector_readiness,
)
from estilo import aplicar_estilo, hero
from family_profiles import list_workspace_profiles
from jarvis_daily_intelligence import build_daily_intelligence

st.set_page_config(page_title="Serviços do Assistente · FaithBloom", page_icon="📩", layout="wide")
aplicar_estilo()
hero("Serviços do Assistente", "Organize seu dia, consulte suas mensagens e revise cada envio antes de confirmar.")
st.page_link("pages/00_🤖_Jarvis.py", label="← Voltar ao Jarvis")

profiles = list_workspace_profiles()
if not profiles:
    st.info("Crie um perfil de workspace para organizar suas prioridades, lembretes e mensagens.")
    st.page_link("pages/34_🏠_Perfis_e_Dashboard.py", label="Criar ou selecionar perfil →")
    st.stop()

ids = [item["id"] for item in profiles]
names = {item["id"]: item["display_name"] for item in profiles}
active_id = str(st.session_state.get("faithbloom_workspace_profile_id") or "")
profile_id = st.selectbox("Perfil do workspace", ids, index=ids.index(active_id) if active_id in ids else 0, format_func=lambda value: names[value])
st.session_state["faithbloom_workspace_profile_id"] = profile_id
store = AssistantRoutineStore(profile_id)
preferences = store.preferences()
store.timezone_name = preferences["timezone"]
policy = AutonomyPolicy(preferences["autonomy_mode"])
suffix = f"fb56_{profile_id}"
readiness = connector_readiness()


def attempt(callback):
    try:
        return callback()
    except (AssistantServiceError, ValueError, KeyError) as exc:
        st.error(str(exc))
    except Exception:
        st.error("Não foi possível concluir esta operação agora. Nenhum novo envio será repetido automaticamente.")
    return None


def show_draft(channel: str, client) -> None:
    key = f"{suffix}_{channel}_draft"
    draft = st.session_state.get(key)
    if not isinstance(draft, dict):
        return
    payload = draft["payload"]
    with st.container(border=True):
        st.markdown("**Revise o envio**")
        st.write("Destinatário:", payload["to"])
        if channel == "gmail":
            st.write("Assunto:", payload["subject"])
            st.text(payload["body"])
        elif payload["type"] == "text":
            st.text(payload["text"]["body"])
        else:
            st.write("Modelo aprovado:", payload["template"]["name"])
            st.write("Idioma:", payload["template"]["language"]["code"])
        checked = st.checkbox("Confirmo o destinatário e o conteúdo acima", key=f"{suffix}_{channel}_confirm_{draft['id']}")
        opt_in = window = False
        if channel == "whatsapp":
            opt_in = st.checkbox("O destinatário autorizou mensagens desta conta", key=f"{suffix}_wa_opt_{draft['id']}")
            if payload["type"] == "text":
                window = st.checkbox("O cliente iniciou uma conversa nas últimas 24 horas", key=f"{suffix}_wa_window_{draft['id']}")
        if st.button("Confirmar e enviar esta mensagem", key=f"{suffix}_{channel}_send_{draft['id']}", disabled=not checked or not readiness[channel]["write_enabled"]):
            kwargs = {"profile_id": profile_id, "confirmation_fingerprint": draft["fingerprint"], "receipts": store.receipts()}
            if channel == "whatsapp":
                kwargs.update(recipient_opt_in=opt_in, customer_window_open=window)
            result = attempt(lambda: policy.execute(f"{channel}.send", lambda: client.send_confirmed(draft, **kwargs), confirmed=checked))
            if result:
                st.success("Mensagem enviada." if channel == "gmail" else "Mensagem aceita pelo WhatsApp. A entrega depende do provedor.")
                st.session_state.pop(key, None)
        if st.button("Descartar este rascunho", key=f"{suffix}_{channel}_discard_{draft['id']}"):
            st.session_state.pop(key, None)
            st.rerun()


daily_tab, gmail_tab, whatsapp_tab, settings_tab = st.tabs(["Meu dia", "Gmail", "WhatsApp Business", "Preferências e conexões"])

with daily_tab:
    st.caption(f"Horários de {store.timezone_name}. Lembretes aparecem ao abrir esta tela; avisos automáticos em segundo plano precisam de um serviço de agendamento.")
    with st.form(f"{suffix}_item_form", clear_on_submit=True):
        kind = st.radio("Organizar", ["priority", "reminder"], format_func=lambda value: "Prioridade" if value == "priority" else "Lembrete", horizontal=True)
        title = st.text_input("O que você precisa fazer?")
        rank = st.selectbox("Prioridade", [1, 2, 3], index=1, format_func=lambda value: {1: "Alta", 2: "Média", 3: "Baixa"}[value])
        date = st.date_input("Data do lembrete", value=datetime.now(ZoneInfo(store.timezone_name)).date())
        at = st.time_input("Horário do lembrete")
        notes = st.text_area("Notas", height=80)
        if st.form_submit_button("Salvar no meu dia"):
            due = datetime.combine(date, at, ZoneInfo(store.timezone_name)) if kind == "reminder" else None
            result = attempt(lambda: policy.execute(f"routines.{kind}.save", lambda: store.add_item(title, kind=kind, due_at=due, priority=rank, notes=notes), confirmed=True))
            if result:
                st.success("Salvo neste perfil.")
    reminders = attempt(store.due_reminders) or []
    if reminders:
        st.warning("Lembretes pendentes: " + "; ".join(item["title"] for item in reminders))
    for item in attempt(store.list_items) or []:
        row = st.columns([6, 1])
        row[0].write(item["title"])
        row[0].caption(" · ".join(value for value in ["Prioridade" if item["kind"] == "priority" else "Lembrete", item.get("due_at", ""), item.get("notes", "")] if value))
        if row[1].button("Concluir", key=f"{suffix}_done_{item['id']}"):
            result = attempt(lambda: policy.execute("routines.complete", lambda: store.complete_item(item["id"]), confirmed=True))
            if result:
                st.rerun()
    st.divider()
    include_external = st.checkbox("Incluir clima e Google Calendar no resumo", key=f"{suffix}_external")
    location = st.text_input("Cidade para o clima", value="Toyohashi, Japan", key=f"{suffix}_city")
    if st.button("Preparar meu resumo do dia", key=f"{suffix}_briefing"):
        intelligence = attempt(lambda: build_daily_intelligence(location=location, timezone_name=store.timezone_name)) if include_external else {}
        result = attempt(lambda: policy.execute("routines.briefing.save", lambda: store.daily_briefing(daily_intelligence=intelligence or {}), confirmed=True))
        if result:
            st.success("Resumo salvo.")
            st.write((result.get("daily_intelligence") or {}).get("text") or (result.get("daily_intelligence") or {}).get("spoken") or "Seu resumo pessoal está pronto.")
            st.write("Prioridades:", [item["title"] for item in result["priorities"]])
    reflection = st.text_area("Como foi o seu dia?", key=f"{suffix}_reflection", height=90)
    if st.button("Registrar fechamento do dia", key=f"{suffix}_close"):
        result = attempt(lambda: policy.execute("routines.day_close.save", lambda: store.close_day(reflection=reflection), confirmed=True))
        if result:
            st.success(f"Fechamento salvo: {len(result['completed'])} concluído(s), {len(result['pending'])} pendente(s).")
    with st.expander("Histórico do meu dia"):
        for row in (attempt(lambda: store.history("day_closings")) or [])[:20]:
            st.write(f"{row['date']}: {len(row['completed'])} concluído(s), {len(row['pending'])} pendente(s)")
            if row.get("reflection"):
                st.text(row["reflection"])
        for row in (attempt(lambda: store.history("briefings")) or [])[:10]:
            st.caption(f"Resumo de {row['date']} · {len(row['priorities'])} prioridades")

with gmail_tab:
    gmail = GmailClient()
    if not readiness["gmail"]["configured"]:
        st.info("O Gmail precisa ser conectado com OAuth e autorização para leitura e envio.")
    if st.button("Verificar conexão Gmail", disabled=not readiness["gmail"]["configured"], key=f"{suffix}_gmail_check"):
        result = attempt(gmail.check_connection)
        if result:
            st.session_state[f"{suffix}_gmail_checked"] = result
    checked = st.session_state.get(f"{suffix}_gmail_checked")
    if checked:
        st.success(f"Leitura verificada nesta sessão: {checked['email']}. O envio não foi testado.")
    query = st.text_input("Buscar mensagens", value="in:inbox", key=f"{suffix}_gmail_query")
    if st.button("Consultar Gmail", disabled=not readiness["gmail"]["configured"], key=f"{suffix}_gmail_list"):
        listing = attempt(lambda: gmail.list_messages(query=query))
        if listing:
            messages = []
            for item in listing["messages"]:
                message = attempt(lambda: gmail.get_message(item["id"]))
                if message:
                    messages.append(message)
            st.session_state[f"{suffix}_gmail_messages"] = messages
    for message in st.session_state.get(f"{suffix}_gmail_messages") or []:
        with st.expander(message["subject"] or "Sem assunto"):
            st.write(message["from"])
            st.text(message["body"] or message["snippet"])
    with st.form(f"{suffix}_gmail_draft_form"):
        recipient = st.text_input("E-mail do destinatário")
        subject = st.text_input("Assunto")
        body = st.text_area("Mensagem", height=150)
        if st.form_submit_button("Preparar mensagem para revisão"):
            draft = attempt(lambda: gmail.prepare_send(profile_id, recipient, subject, body))
            if draft:
                st.session_state[f"{suffix}_gmail_draft"] = draft
    if not readiness["gmail"]["write_enabled"]:
        st.caption("O envio está desabilitado. Você pode preparar e revisar um rascunho.")
    show_draft("gmail", gmail)

with whatsapp_tab:
    whatsapp = WhatsAppBusinessClient()
    st.caption("Conexão pela API oficial WhatsApp Business. Mensagens livres exigem conversa ativa; fora da janela de 24 horas, use um modelo aprovado.")
    if st.button("Verificar conexão WhatsApp", disabled=not readiness["whatsapp"]["configured"], key=f"{suffix}_wa_check"):
        result = attempt(whatsapp.check_connection)
        if result:
            st.session_state[f"{suffix}_wa_checked"] = result
    checked = st.session_state.get(f"{suffix}_wa_checked")
    if checked:
        st.success(f"Conexão de leitura verificada: {checked['phone']} · {checked['name']}. Envio e entrega não foram testados.")
    with st.form(f"{suffix}_wa_draft_form"):
        recipient = st.text_input("Número com DDI", placeholder="+81…")
        template = st.checkbox("Usar modelo aprovado pela Meta")
        template_name = st.text_input("Nome do modelo aprovado")
        template_language = st.text_input("Idioma do modelo", value="pt_BR")
        body = st.text_area("Mensagem livre", height=120)
        if st.form_submit_button("Preparar WhatsApp para revisão"):
            if template and not template_name.strip():
                st.error("Informe o nome do modelo aprovado antes de preparar o envio.")
                draft = None
            else:
                draft = attempt(lambda: whatsapp.prepare_send(profile_id, recipient, body, template_name=template_name if template else "", template_language=template_language))
            if draft:
                st.session_state[f"{suffix}_whatsapp_draft"] = draft
    if not readiness["whatsapp"]["write_enabled"]:
        st.caption("O envio WhatsApp está desabilitado. Você pode preparar um rascunho.")
    show_draft("whatsapp", whatsapp)
    st.info("A recepção automática de mensagens ainda depende de um endpoint público HTTPS para o webhook. Esta tela não recebe mensagens em segundo plano.")

with settings_tab:
    with st.form(f"{suffix}_preferences"):
        mode = st.selectbox("Autonomia do assistente", list(AUTONOMY_MODES), index=list(AUTONOMY_MODES).index(preferences["autonomy_mode"]), format_func=lambda value: AUTONOMY_MODES[value])
        zone = st.text_input("Fuso horário", value=preferences["timezone"])
        st.caption("Assistente e Copiloto pedem confirmação para alterações. Gerente pode organizar rotinas locais. Todos exigem confirmação para envios, gastos, mudanças na agenda e exclusões.")
        if st.form_submit_button("Salvar preferências"):
            result = attempt(lambda: store.save_preferences(autonomy_mode=mode, timezone_name=zone))
            if result:
                st.rerun()
    for channel in ("gmail", "whatsapp"):
        data = readiness[channel]
        st.write(f"**{channel.title()}**: " + ("configurado; validação real pendente" if data["configured"] else "configuração pendente"))
        if data["missing"]:
            st.code("\n".join(data["missing"]))
    with st.expander("Configuração dos serviços"):
        st.write("Gmail: use GOOGLE_GMAIL_CLIENT_ID, GOOGLE_GMAIL_CLIENT_SECRET e GOOGLE_GMAIL_REFRESH_TOKEN; as credenciais Google Calendar existentes também podem ser reutilizadas se o token incluir os escopos Gmail. Habilite JARVIS_GMAIL_WRITE_ENABLED somente após conectar a conta.")
        st.write("WhatsApp: configure WHATSAPP_ACCESS_TOKEN, WHATSAPP_PHONE_NUMBER_ID, WHATSAPP_GRAPH_API_VERSION e JARVIS_WHATSAPP_WRITE_ENABLED. Para um futuro endpoint HTTPS, WHATSAPP_APP_SECRET valida a assinatura e WHATSAPP_WEBHOOK_VERIFY_TOKEN valida o desafio de cadastro.")
        st.write("Guarde tokens em Secrets do Streamlit. A instalação de um endpoint de webhook e de um agendador persistente continua pendente.")
