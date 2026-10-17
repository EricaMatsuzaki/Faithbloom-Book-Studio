"""
Ir Direto para Etapa - escolha um livro salvo e rode só UM agente
específico, sem passar pelo pipeline inteiro de novo.

Casos de uso: já tem a história pronta e só quer ilustrar; já ilustrou
e só quer regerar a capa depois de trocar o selo; já publicou e só
quer rodar o Tradutor pra um idioma novo; etc.
"""

import streamlit as st
from estilo import aplicar_estilo, hero

from openrouter_client import chamar_llm, gerar_imagem, gerar_audio
from armazenamento import listar_livros, carregar_livro, salvar_livro
from emotional_review_ui import render_emotional_gate, consume_emotional_consent

from agents.roteirista import roteirista_node
from agents.revisor import revisor_node
from agents.ilustrador import ilustrador_node
from agents.atividades_colorir import atividades_colorir_node
from agents.audiobook import audiobook_node, narracao_node
from agents.dedicatoria import dedicatoria_node
from agents.tradutor import tradutor_node
from agents.sinopse import sinopse_node
from agents.pesquisa_mercado import pesquisa_palavras_chave_node, pesquisa_categorias_node
from agents.diagramador import diagramador_node
from agents.capa import capa_node
from agents.marketing import marketing_lancamento_node

st.set_page_config(page_title="Ir Direto para Etapa", page_icon="🎯", layout="wide")
aplicar_estilo()
hero("🎯 Ir Direto para Etapa", "Rode só o agente que você precisa, sem repetir o resto.")
st.caption("Carregue um livro salvo e rode só o agente que você precisa - sem repetir o resto do pipeline.")

livros = listar_livros()
if not livros:
    st.info("Nenhum livro salvo ainda. Crie um primeiro em 'Criar do Zero' ou 'Retomar Livro'.")
    st.stop()

# Titles/collections may repeat. The durable reference selects the exact work.
opcoes = {l['storage_path']: l for l in livros}
escolha = st.selectbox("Livro", list(opcoes), format_func=lambda ref: (
    f"{opcoes[ref]['titulo']} ({opcoes[ref]['colecao']}) · {ref.rsplit('/', 1)[-1]}"))
livro_info = opcoes[escolha]

if "state_etapa" not in st.session_state or st.session_state.get("livro_carregado") != escolha:
    st.session_state.state_etapa = carregar_livro(livro_info["colecao"], escolha)
    st.session_state.state_etapa['storage_path'] = escolha if escolha.startswith('fb://') else 'fb://' + escolha
    st.session_state.livro_carregado = escolha

s = st.session_state.state_etapa

ETAPAS = {
    "Roteirista (reescreve a história)": lambda st_: roteirista_node(st_, chamar_llm),
    "Revisor (audita o texto)": lambda st_: revisor_node(st_, chamar_llm),
    "Ilustrador (personagens + cenas)": lambda st_: ilustrador_node(st_, gerar_imagem),
    "Atividades para Colorir (3 páginas)": lambda st_: atividades_colorir_node(st_, gerar_imagem),
    "Audiobook - roteiro narrado": lambda st_: audiobook_node(st_, chamar_llm),
    "Audiobook - narração (TTS)": lambda st_: narracao_node(st_, gerar_audio),
    "Dedicatória Dinâmica": lambda st_: dedicatoria_node(st_, chamar_llm),
    "Tradutor/Localizador": lambda st_: tradutor_node(st_, chamar_llm),
    "Sinopse de Vendas": lambda st_: sinopse_node(st_, chamar_llm),
    "Pesquisa de Palavras-chave": lambda st_: pesquisa_palavras_chave_node(st_, chamar_llm),
    "Pesquisa de Categorias": lambda st_: pesquisa_categorias_node(st_, chamar_llm),
    "Diagramador (layout + validação KDP)": lambda st_: diagramador_node(st_),
    "Capa e Contracapa": lambda st_: capa_node(st_, gerar_imagem),
    "Marketing de Lançamento": lambda st_: marketing_lancamento_node(st_, chamar_llm),
}

etapa_escolhida = st.selectbox("Qual agente rodar?", list(ETAPAS.keys()))
is_illustration = etapa_escolhida == 'Ilustrador (personagens + cenas)'
image_ready, image_consent, image_token = True, False, ''
if is_illustration:
    image_ready, image_consent, image_token = render_emotional_gate(
        st, 'state_etapa', 'pages/4_🎯_Ir_Direto_para_Etapa.py', action='direct_book_illustration')
    masters = list((s.get('personagens') or {}).values())
    masters_ready = bool(masters) and all(p.get('aparencia_aprovada') is True and p.get('imagem_referencia') for p in masters)
    if not masters_ready:
        st.info('Aprove as referências dos personagens antes de gerar novas ilustrações.')
    image_ready = image_ready and masters_ready

with st.expander("Ver estado atual do livro (o que já foi gerado)"):
    st.json({k: v for k, v in s.items() if not isinstance(v, list) or len(v) < 5})

if st.button(f"▶️ Rodar: {etapa_escolhida}", disabled=not image_ready):
    with st.spinner("Rodando..."):
        if is_illustration:
            consume_emotional_consent(st.session_state, image_token)
            novo_estado = ilustrador_node(dict(s), gerar_imagem, consent_confirmed=image_consent)
        else:
            novo_estado = ETAPAS[etapa_escolhida](dict(s))
    st.session_state.state_etapa = novo_estado
    s = novo_estado
    st.success("Etapa concluída — resultado atualizado no estado do livro.")

    # Mostra o resultado mais relevante pra etapa rodada
    if "cenas_texto" in etapa_escolhida.lower() or "roteirista" in etapa_escolhida.lower():
        st.write(s.get("cenas_texto", []))
    if "ilustrador" in etapa_escolhida.lower():
        for cena in s.get("cenas_imagem", []):
            st.image(cena["caminho_arquivo"], caption=f"Cena {cena['numero']}")
    if "capa" in etapa_escolhida.lower():
        col1, col2 = st.columns(2)
        if s.get("capa_ebook"):
            col1.image(s["capa_ebook"], caption="Capa eBook")
        if s.get("capa_fisica_wrap"):
            col2.image(s["capa_fisica_wrap"], caption="Capa física")
    if "dedicatória" in etapa_escolhida.lower() or "dedicatoria" in etapa_escolhida.lower():
        st.write(s.get("dedicatoria_texto", ""))
    if "diagramador" in etapa_escolhida.lower():
        st.json(s.get("checklist_kdp", {}))

if st.button("💾 Salvar como novo arquivo"):
    caminho = salvar_livro(dict(s))
    st.success(f"Salvo em: {caminho}")
