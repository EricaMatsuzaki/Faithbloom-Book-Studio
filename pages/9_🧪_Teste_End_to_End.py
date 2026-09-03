import streamlit as st
from estilo import aplicar_estilo, hero, section_title, callout
from integracao_e2e import rodar_diagnostico_completo, testar_openrouter_texto

st.set_page_config(page_title="Teste End-to-End", page_icon="🧪", layout="wide")
aplicar_estilo()
hero(
    "🧪 Central de Testes End-to-End",
    "Valide o FaithBloom antes de gastar créditos: ambiente, integrações, contratos entre fases e readiness do livro de Natal.",
    "Fase 11 · Quality Gate",
)

callout(
    "Seguro por padrão",
    "O diagnóstico completo é offline e não chama modelos de texto, imagem ou voz. O teste real da OpenRouter só roda quando você clicar explicitamente.",
    "🛡️",
)

if "e2e_diag" not in st.session_state:
    st.session_state.e2e_diag = None

c1,c2=st.columns([2,1])
with c1:
    if st.button("▶️ Rodar diagnóstico completo (sem gastar créditos)", type="primary", use_container_width=True):
        with st.spinner("Verificando módulos, contratos e o livro de Natal..."):
            st.session_state.e2e_diag=rodar_diagnostico_completo()
with c2:
    if st.button("🧹 Limpar resultado", use_container_width=True):
        st.session_state.e2e_diag=None
        st.rerun()

diag=st.session_state.e2e_diag
if diag:
    a,b,c=st.columns(3)
    total=sum(len(v) for v in diag["grupos"].values())
    aprovados=sum(1 for v in diag["grupos"].values() for x in v if x["ok"])
    a.metric("Checks", total)
    b.metric("Aprovados", aprovados)
    c.metric("Bloqueios", len(diag["erros"]))
    if diag["ok"]:
        st.success("✅ Quality Gate técnico aprovado. Avisos ainda podem exigir decisão humana.")
    else:
        st.error("❌ Existem bloqueios técnicos. Corrija os itens vermelhos antes do teste de produção.")

    for grupo, checks in diag["grupos"].items():
        with st.expander(grupo, expanded=(grupo=="Livro de Natal" or any(not x["ok"] for x in checks))):
            for x in checks:
                if x["ok"]:
                    st.success(f"✅ {x['nome']} — {x['detalhe']}")
                elif x["nivel"]=="aviso":
                    st.warning(f"⚠️ {x['nome']} — {x['detalhe']}")
                else:
                    st.error(f"❌ {x['nome']} — {x['detalhe']}")

    natal=diag.get("natal_state") or {}
    if natal:
        section_title("🎄 Livro de Natal", "Resumo do estado que será enviado ao fluxo Retomar, sem gerar imagens.", "Projeto piloto")
        x1,x2,x3,x4=st.columns(4)
        x1.metric("Cenas", len(natal.get("cenas_texto",[])))
        x2.metric("Personagens", len(natal.get("personagens",{})))
        x3.metric("Idiomas alvo", len(natal.get("idiomas_alvo",[])))
        x4.metric("Revisão", "Aprovada" if natal.get("revisao_aprovada") else "Pendente")
        st.caption(f"Versículo: {natal.get('versiculo_referencia','')} · Trim: {natal.get('trim_largura_in',8.5)} × {natal.get('trim_altura_in',8.5)} in")
        st.page_link("pages/2_#L01f4da_Retomar_Livro.py", label="🎄 Abrir Retomar Livro agora", use_container_width=True)

section_title("Teste real da OpenRouter", "Opcional. Faz uma única chamada curta de texto; não gera imagem nem áudio.", "API")
st.warning("Este botão pode consumir uma quantidade pequena de créditos da sua conta OpenRouter.")
if st.button("🔌 Testar OpenRouter (1 chamada curta)"):
    with st.spinner("Testando conexão..."):
        r=testar_openrouter_texto()
    if r.get("ok"):
        st.success(f"✅ OpenRouter respondeu corretamente: {r.get('resposta')}")
    else:
        st.error(f"❌ Falha: {r.get('erro') or r.get('resposta')}")

section_title("Roteiro do teste profissional", "Ordem recomendada para validar o FaithBloom com o livro de Natal.", "E2E")
st.markdown("""
1. **Diagnóstico offline** — todos os imports e contratos críticos precisam passar.
2. **Personagens** — aprovar Mel, Manu e o personagem amigo antes de qualquer geração em massa.
3. **Cena piloto** — gerar apenas 1 cena com todos os personagens necessários e avaliar consistência.
4. **Variação** — testar `Gerar nova`, `Criar variação`, `Restaurar anterior` e `Salvar na Galeria`.
5. **Lote pequeno** — produzir 3 cenas (início, meio e final) antes do restante do livro.
6. **Livro completo** — somente depois da aprovação visual do lote piloto.
7. **Line arts** — gerar as atividades a partir de cenas aprovadas.
8. **Preflight** — conferir PPI real, bleed, margens e PDF Print Ready.
9. **Capa física** — montar matematicamente e revisar com o template da KDP.
10. **KDP Previewer + prova física** — etapa humana final antes de publicar.
""")
