"""Painel Fase 13 — proteção de custos, logs e geração segura."""
import streamlit as st

from controle_geracao import POLITICA, estimar_custo, ler_registros, resumo_financeiro, validar_lote_imagens
from estilo import aplicar_estilo, hero, section_title, callout

st.set_page_config(page_title="Custos & Segurança | FaithBloom",page_icon="🛡️",layout="wide")
aplicar_estilo()
hero("Custos & Segurança","Proteções para evitar cliques duplicados, lotes grandes por engano e gastos acima do orçamento definido.","Fase 13 · Production Guardrails")

res=resumo_financeiro()
a,b,c,d=st.columns(4)
a.metric("Uso estimado hoje",f"US${res['gasto_estimado_hoje_usd']:.2f}")
b.metric("Limite diário",f"US${res['limite_diario_usd']:.2f}")
c.metric("Saldo protegido",f"US${res['saldo_protegido_usd']:.2f}")
d.metric("Máx. imagens/lote",res['max_imagens_lote'])
st.progress(res['percentual_usado']/100 if res['percentual_usado'] else 0,text=f"{res['percentual_usado']:.1f}% do orçamento protegido usado")

callout("Estimativas, não tabela oficial de preços","Os valores usados pelo FaithBloom são configuráveis e servem como guardrail. Quando o provedor devolve custo real na resposta, esse valor tem prioridade no histórico. Ajuste os Secrets conforme os modelos usados.","💰")

section_title("Simulador antes de gerar","Estime o impacto de um lote antes de clicar em qualquer geração paga.","Planejamento")
modalidade=st.selectbox("Tipo",["imagem","texto","audio"])
if modalidade=="audio":
    minutos=st.number_input("Minutos estimados de áudio",0.1,500.0,5.0,0.5)
    quantidade=st.number_input("Quantidade",1,100,1)
    estimativa=estimar_custo("audio",int(quantidade),float(minutos))
else:
    quantidade=st.number_input("Quantidade de chamadas",1,100,1)
    estimativa=estimar_custo(modalidade,int(quantidade))
    if modalidade=="imagem":
        try:
            validar_lote_imagens(int(quantidade)); st.success("Lote dentro do limite de segurança atual.")
        except Exception as exc:
            st.error(str(exc))
st.metric("Estimativa configurada",f"~US${estimativa:.2f}")

section_title("Proteções ativas","Aplicadas dentro do cliente OpenRouter; não dependem de lembrar de clicar corretamente.","Guardrails")
st.markdown(f"""
- **Clique duplicado:** mesma geração é bloqueada enquanto estiver em andamento e por {POLITICA.cooldown_duplicado_seg:g}s após o disparo.
- **Retry controlado:** até {POLITICA.tentativas_http} tentativas em erros transitórios/429/5xx, com backoff.
- **Orçamento diário:** novas chamadas são bloqueadas antes de ultrapassar aproximadamente US${POLITICA.orcamento_diario_usd:.2f}.
- **Lote de imagens:** limite recomendado de {POLITICA.max_imagens_lote} por ação de produção.
- **Logs sanitizados:** não salvam prompts completos, headers ou API keys.
- **Erro seguro:** respostas brutas do provedor não são despejadas na interface.
""")

section_title("Histórico de chamadas","Auditoria técnica sem expor o conteúdo completo dos prompts.","Logs")
reg=ler_registros(100)
if not reg:
    st.info("Nenhuma chamada registrada nesta instalação ainda.")
else:
    # Somente campos seguros.
    tabela=[]
    for r in reversed(reg):
        tabela.append({
            "data":r.get("criado_em",""),"tipo":r.get("modalidade",""),"modelo":r.get("modelo",""),
            "status":r.get("status",""),"estimativa_usd":r.get("estimativa_usd"),
            "custo_reportado_usd":r.get("custo_reportado_usd"),"duracao_ms":r.get("duracao_ms"),
            "request_id":r.get("request_id","")[:10],
        })
    st.dataframe(tabela,use_container_width=True,hide_index=True)

section_title("Configuração recomendada no Streamlit Secrets","Você pode ajustar os limites sem alterar código.","Secrets")
st.code('''FAITHBLOOM_BUDGET_DIARIO_USD = "25.00"\nFAITHBLOOM_MAX_IMAGENS_LOTE = "5"\nFAITHBLOOM_COOLDOWN_DUPLICADO_SEG = "3"\nFAITHBLOOM_HTTP_RETRIES = "3"\nFAITHBLOOM_EST_TEXTO_USD = "0.03"\nFAITHBLOOM_EST_IMAGEM_USD = "0.08"\nFAITHBLOOM_EST_AUDIO_MIN_USD = "0.03"''',language="toml")
st.caption("Nunca coloque a OPENROUTER_API_KEY em logs, screenshots ou no repositório GitHub.")
