import os
from copy import deepcopy
from pathlib import Path
import streamlit as st
from estilo import aplicar_estilo, hero, section_title, callout
from historia_natal import ESTADO_INICIAL_NATAL
from integracao_e2e import preparar_state_retomada
from openrouter_client import gerar_imagem
from agents.ilustrador import definir_imagem_cena, obter_imagem_cena, aprovar_imagem_cena
from piloto_visual import (personagens_aprovados,cenas_recomendadas_piloto,prompt_piloto,
    montar_folha_referencias,checklist_avaliacao,piloto_aprovado,readiness_producao)

st.set_page_config(page_title="Piloto Visual",page_icon="🎄",layout="wide")
aplicar_estilo()
hero("🎄 Laboratório Visual — Livro de Natal","Valide Mel, Manu e Max em um lote pequeno antes de liberar as 22 cenas.","Fase 12 · Visual Quality Gate")
callout("Economia de créditos","O FaithBloom não gera o livro inteiro aqui. Primeiro 1 cena crítica; depois 3 cenas representativas. A produção completa só é liberada após sua aprovação.","🛡️")

if "piloto_natal_state" not in st.session_state:
    st.session_state.piloto_natal_state=preparar_state_retomada(ESTADO_INICIAL_NATAL)
s=st.session_state.piloto_natal_state
s.setdefault("piloto_visual",{"lote_validacao":{}})

section_title("1. Personagens aprovados","O piloto usa somente referências visuais já aprovadas.","Gate 1")
ok,pend=personagens_aprovados(s)
if not ok:
    st.warning("Ainda faltam referências aprovadas: "+", ".join(pend)+". Aprove-as primeiro em Retomar Livro.")
    st.page_link("pages/2_#L01f4da_Retomar_Livro.py",label="👥 Ir para aprovação dos personagens",use_container_width=True)
else:
    cols=st.columns(len(s.get("personagens",{})))
    for col,(nome,p) in zip(cols,s["personagens"].items()):
        with col:
            st.image(p["imagem_referencia"],use_container_width=True); st.success(f"🔒 {nome}")

section_title("2. Cena piloto crítica","Para o Natal, recomendamos uma cena com Mel + Manu + Max juntos.","Gate 2")
recs=cenas_recomendadas_piloto(s)
nums=[int(c["numero"]) for c in s.get("cenas_texto",[])]
default=recs[0] if recs else nums[0]
numero=st.selectbox("Cena piloto",nums,index=nums.index(default))
cena=next(c for c in s["cenas_texto"] if int(c["numero"])==numero)
st.write(cena.get("texto","")); st.caption(cena.get("contexto_visual",""))
instr=st.text_area("Pedido adicional (opcional)",placeholder="Ex.: preserve exatamente o rostinho da Mel; Max deve manter o cachecol verde.")

if st.button("✨ Gerar SOMENTE esta cena piloto",type="primary",disabled=not ok,use_container_width=True):
    prompt,nomes=prompt_piloto(s,numero,instr)
    folha=montar_folha_referencias(s,nomes,os.path.join("saida_imagens",f"refs_piloto_cena_{numero}.jpg"))
    with st.spinner("Gerando uma única cena para validar consistência..."):
        caminho=gerar_imagem(prompt=prompt,imagem_base=folha)
    definir_imagem_cena(s,numero,caminho,prompt,"piloto_visual",False)
    s["piloto_visual"]["cena_piloto_numero"]=numero
    st.rerun()

item=obter_imagem_cena(s,numero)
if item and item.get("caminho_arquivo"):
    st.image(item["caminho_arquivo"],use_container_width=True)
    st.markdown("#### Checklist visual humano")
    labels={"identidade_personagens":"Rostos/identidade consistentes","cores_marcas_acessorios":"Cores, marcas e acessórios corretos","proporcoes":"Proporções consistentes","figurino":"Figurino correto","emocao":"Emoção correta","cenario":"Cenário coerente","sem_texto_embutido":"Sem texto indesejado na arte","qualidade_visual":"Qualidade visual aprovada"}
    av=s["piloto_visual"].setdefault("avaliacao_cena",checklist_avaliacao())
    for k,label in labels.items(): av[k]=st.checkbox(label,value=bool(av.get(k)),key=f"av_{numero}_{k}")
    if st.button("✅ Aprovar cena piloto",disabled=not piloto_aprovado(av),use_container_width=True):
        aprovar_imagem_cena(s,numero,True); s["piloto_visual"]["cena_piloto_aprovada"]=True; st.rerun()

section_title("3. Lote pequeno: início + meio + final","Somente depois da cena piloto aprovada.","Gate 3")
for n in recs:
    c=next(c for c in s["cenas_texto"] if int(c["numero"])==n)
    registro=s["piloto_visual"]["lote_validacao"].setdefault(str(n),{"aprovado":False})
    with st.expander(f"Cena {n} · {'✅ aprovada' if registro['aprovado'] else '🟡 pendente'}",expanded=False):
        st.write(c.get("texto",""))
        atual=obter_imagem_cena(s,n)
        if atual and atual.get("caminho_arquivo"): st.image(atual["caminho_arquivo"],use_container_width=True)
        if st.button(f"✨ Gerar apenas cena {n}",key=f"pilot_gen_{n}",disabled=not s["piloto_visual"].get("cena_piloto_aprovada")):
            prompt,nomes=prompt_piloto(s,n,"")
            folha=montar_folha_referencias(s,nomes,os.path.join("saida_imagens",f"refs_piloto_cena_{n}.jpg"))
            with st.spinner(f"Gerando cena {n}..."): caminho=gerar_imagem(prompt=prompt,imagem_base=folha)
            definir_imagem_cena(s,n,caminho,prompt,"lote_piloto",False); st.rerun()
        if atual and st.checkbox("Aprovo visualmente esta cena",value=registro["aprovado"],key=f"lot_ok_{n}"):
            registro["aprovado"]=True; aprovar_imagem_cena(s,n,True)

r=readiness_producao(s)
st.markdown("---")
if r["liberado_producao_completa"]:
    st.success("🟢 PRODUÇÃO COMPLETA LIBERADA — personagens + cena crítica + lote de 3 cenas foram aprovados.")
    st.page_link("pages/2_#L01f4da_Retomar_Livro.py",label="🎨 Continuar produção cena por cena",use_container_width=True)
else:
    st.info(f"Produção completa ainda protegida. Personagens: {'OK' if r['personagens_ok'] else 'pendente'} · Cena piloto: {'OK' if r['cena_piloto_ok'] else 'pendente'} · Lote: {'OK' if r['lote_piloto_ok'] else 'pendente'}")
