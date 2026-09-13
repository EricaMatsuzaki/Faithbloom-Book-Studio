import streamlit as st

from estilo import aplicar_estilo, hero
from book_doctor import listar_projetos, carregar_relatorio
from editorial_remaster import (
    criar_rascunho_remaster_editorial,
    confirmar_mapeamento_cenas,
    gate_revisao_editorial,
)

st.set_page_config(page_title="Editorial Remaster", page_icon="✨", layout="wide")
aplicar_estilo()
hero(
    "✨ Full Editorial Remaster",
    "Revise uma obra publicada sem apagar sua alma: preserve o original, confirme o texto importado e prepare a passagem pela equipe editorial FaithBloom antes da remasterização visual.",
)

st.info(
    "🔒 O original do Book Doctor permanece imutável. Nesta etapa nenhuma IA reescreve o livro: primeiro o texto extraído é conferido e as páginas da história são confirmadas pela autora."
)

projetos = [
    p for p in listar_projetos()
    if p.get("tipo_projeto") == "story"
]

if not projetos:
    st.warning("Ainda não há Story Book importado no Book Doctor. Importe primeiro o PDF da obra publicada.")
    st.page_link("pages/16_🩺_Book_Doctor.py", label="🩺 Abrir Book Doctor →", use_container_width=True)
    st.stop()

labels = {
    p["id"]: f"{p.get('titulo') or 'Sem título'} · {p.get('status_publicacao') or 'status não informado'} · {p.get('idioma') or 'pt-BR'}"
    for p in projetos
}
projeto_id = st.selectbox(
    "Obra para revisar",
    [p["id"] for p in projetos],
    format_func=lambda x: labels.get(x, x),
)
projeto = next(p for p in projetos if p["id"] == projeto_id)
relatorio = carregar_relatorio(projeto)

st.markdown("### 1 · Parâmetros editoriais da nova edição")
c1, c2 = st.columns(2)
faixa = c1.selectbox("Faixa etária oficial", ["3-8", "3-5", "6-8", "9-12"], index=0)
versiculo = c2.text_input("Referência bíblica atual — preservar por padrão", value="")
licao = st.text_area("Lição de Moral atual — preservar por padrão", value="", height=90)
aprendizado = st.text_input("Aprendizado cristão central", value="")
emocao = st.text_input("Emoção central da obra", value="")

if st.button("✨ Preparar revisão editorial completa", type="primary"):
    try:
        draft = criar_rascunho_remaster_editorial(
            projeto,
            relatorio,
            faixa_etaria=faixa,
            versiculo_referencia=versiculo,
            licao_final=licao,
            aprendizado_cristao=aprendizado,
            emocao_central=emocao,
        )
        st.session_state["editorial_remaster_draft"] = draft
        st.session_state.pop("editorial_remaster_confirmed", None)
    except Exception as exc:
        st.error(f"Não foi possível preparar o remaster editorial: {exc}")

state = st.session_state.get("editorial_remaster_confirmed") or st.session_state.get("editorial_remaster_draft")

if state and state.get("projeto_book_doctor_id") == projeto_id:
    st.success("Rascunho derivado criado sem alterar o original.")
    a, b, c = st.columns(3)
    a.metric("Remaster", state.get("remaster_id", "—"))
    b.metric("Original protegido", "Sim" if state.get("original", {}).get("imutavel") else "Não")
    c.metric("Faixa", state.get("faixa_etaria", "—"))

    st.markdown("### 2 · Confira o texto extraído do PDF")
    st.caption(
        "PDFs podem conter capa, créditos, dedicatória e outras páginas editoriais. Por isso o FaithBloom não transforma automaticamente toda página com texto em cena da história."
    )
    paginas = state.get("paginas_texto_extraido") or []
    rows = [
        {
            "Página": x.get("pagina"),
            "Tem texto": "Sim" if x.get("tem_texto") else "Não",
            "Texto extraído": (x.get("texto_extraido") or "")[:600],
            "Erro": x.get("erro_extracao") or "",
        }
        for x in paginas
    ]
    st.dataframe(rows, use_container_width=True, hide_index=True)

    paginas_com_texto = [int(x["pagina"]) for x in paginas if x.get("tem_texto")]
    default_pages = paginas_com_texto
    selecionadas = st.multiselect(
        "Quais páginas pertencem à história que será revisada?",
        paginas_com_texto,
        default=default_pages,
        help="Desmarque capa, créditos, dedicatória, boas-vindas, ficha pedagógica ou outras páginas que não sejam cenas narrativas.",
    )

    if st.button("✅ Confirmar páginas da história"):
        try:
            confirmed = confirmar_mapeamento_cenas(state, selecionadas)
            st.session_state["editorial_remaster_confirmed"] = confirmed
            state = confirmed
            st.success("Mapeamento confirmado. A obra está pronta para entrar na revisão editorial.")
        except Exception as exc:
            st.error(str(exc))

    gate = gate_revisao_editorial(state)
    st.markdown("### 3 · Gate antes dos agentes")
    if gate["ok"]:
        st.success("Gate aprovado: o próximo especialista é o Revisor Editorial.")
    else:
        st.warning("A revisão automática continua bloqueada até a confirmação do mapeamento.")
        for item in gate.get("bloqueios", []):
            st.write("• " + item)

    with st.expander("🧭 Equipe/rota que será reutilizada", expanded=True):
        for idx, item in enumerate(state.get("rota_editorial") or [], 1):
            st.write(f"{idx}. {item}")

    st.caption(
        "Política: Revisor primeiro → Editor de História para ajustes pontuais → Roteirista somente quando necessário → motores compartilhados → Character Universe/Restoration Studio → Quality Guardian → publicação."
    )

    if gate["ok"]:
        st.info(
            "Próximo refinamento: conectar este estado confirmado ao Revisor Editorial e gerar um Dossiê de Revisão antes de qualquer reescrita ou nova ilustração."
        )
