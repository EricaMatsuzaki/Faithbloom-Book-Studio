"""Biblioteca opcional de estilos narrativos do FaithBloom.

Os estilos desta página não substituem os quatro estilos do Prompt-Mestre e não
são gerados automaticamente. A autora escolhe quando quer explorar uma forma
narrativa adicional, preservando custo e controle editorial.
"""
from __future__ import annotations

from copy import deepcopy
import streamlit as st

from state import LivroState
from estilo import aplicar_estilo, hero
from openrouter_client import chamar_llm
from armazenamento import salvar_livro, atualizar_livro_salvo
from agents.estilos_narrativos import (
    ESTILOS_NARRATIVOS,
    ORDEM_ESTILOS_ADICIONAIS,
    aplicar_estilo_ao_state,
    gerar_estilo_adicional,
)
from age_profiles import normalizar_faixa_etaria, perfil_etario

st.set_page_config(page_title="Explorar outros estilos", page_icon="➕", layout="wide")
aplicar_estilo()
hero(
    "➕ Explorar outros estilos",
    "Biblioteca narrativa opcional: todos os estilos usam a skill-base profissional do Roteirista e só são gerados quando você pedir.",
)

if "state" not in st.session_state:
    st.session_state.state = LivroState(paginas_minimas=24, idiomas_alvo=[], personagens={})

s = st.session_state.state
s.setdefault("paginas_minimas", 24)
s.setdefault("personagens", {})
s.setdefault("versoes_narrativas_salvas", {})
s["faixa_etaria"] = normalizar_faixa_etaria(s.get("faixa_etaria"))
s["age_profile_id"] = s["faixa_etaria"]
perfil = perfil_etario(s["faixa_etaria"])

DERIVADOS_NARRATIVOS = (
    "revisao_aprovada",
    "notas_revisor",
    "mapa_emocional",
    "cenas_imagem",
    "imagens_cenas_enviadas",
    "cenas_imagem_aprovadas",
    "paginas_colorir",
    "traducoes",
    "roteiro_audiobook",
    "audio_gerado",
    "layout_paginas",
    "pacote_pronto",
    "checklist_kdp",
    "preflight_impressao",
    "pdf_miolo_print_ready",
    "sinopse_vendas_curta",
    "sinopse_contracapa",
    "material_lancamento",
)


def _persistir() -> str:
    caminho = str(s.get("storage_path") or "")
    if caminho:
        caminho = atualizar_livro_salvo(caminho, dict(s))
    else:
        caminho = salvar_livro(dict(s))
    s["storage_path"] = caminho
    return caminho


def _arquivar_derivados() -> None:
    ativa = str(s.get("versao_narrativa_ativa") or "").strip()
    if not ativa:
        return
    snapshot = {}
    for campo in DERIVADOS_NARRATIVOS:
        if campo in s and s.get(campo) not in (None, "", [], {}, False):
            snapshot[campo] = deepcopy(s.get(campo))
    if snapshot:
        historico = deepcopy(s.get("historico_derivados_por_versao") or {})
        historico.setdefault(ativa, []).append(snapshot)
        s["historico_derivados_por_versao"] = historico


def _ativar(chave: str, versao: dict) -> None:
    _arquivar_derivados()
    novo = aplicar_estilo_ao_state(dict(s), chave, versao)
    for campo in DERIVADOS_NARRATIVOS:
        novo.pop(campo, None)
    novo["revisao_aprovada"] = False
    novo["pacote_pronto"] = False
    novo["versao_narrativa_ativa"] = chave
    novo["versao_narrativa_origem"] = "comparative_story_director_additional"
    novo["estilo_escolhido_no_comparador"] = True
    novo["modo_comparacao_escolhido"] = versao.get("modo", "completa")
    novo["idade_historia_precisa_regenerar"] = False
    s.clear()
    s.update(novo)


st.info(
    "Esses estilos são opcionais. Os quatro estilos principais continuam intactos e esta página não gera nenhuma ilustração."
)
st.page_link("pages/39_✍️_Historia_4_Estilos.py", label="← Voltar para História em 4 Estilos", icon="✍️")

premissa = str(s.get("_entrada_tema_livre") or s.get("titulo") or "").strip()
colecao = str(s.get("colecao") or "").strip()

st.markdown("### Projeto atual")
st.write(f"**Título/ideia:** {s.get('titulo') or premissa or 'Ainda não definido'}")
st.write(f"**Faixa etária:** {perfil['short_label']}")
if s.get("aprendizado_cristao"):
    st.write(f"**Lição cristã:** {s['aprendizado_cristao']}")
if s.get("versiculo_referencia"):
    st.write(f"**Referência bíblica:** {s['versiculo_referencia']}")

if not colecao or not premissa:
    st.warning("Primeiro defina a coleção e a ideia na página ✍️ História em 4 Estilos.")

pode_gerar = bool(colecao and premissa)
biblioteca = s.get("versoes_narrativas_salvas") or {}

for chave in ORDEM_ESTILOS_ADICIONAIS:
    spec = ESTILOS_NARRATIVOS[chave]
    with st.container(border=True):
        st.markdown(f"## {spec['label']}")
        st.write(spec["descricao"])
        st.markdown(
            "**DNA deste estilo:** acumulação progressiva + refrão original + musicalidade + antecipação + "
            "participação da criança + humor crescente + clímax e resolução satisfatória."
        )
        st.caption(
            "Especialmente forte para 3–5; funciona muito bem em 6–8 com variações mais criativas. "
            "Em 9–12, só deve ser usado quando a estrutura puder ganhar sofisticação suficiente."
        )
        st.caption(
            "O FaithBloom usa os princípios de narrativa cumulativa/lengalenga, mas exige texto, refrão, personagens e progressão originais — sem copiar obras existentes."
        )

        c1, c2 = st.columns(2)
        if c1.button(
            "✨ Gerar amostra Cumulativo/Lengalenga",
            key=f"amostra_extra_{chave}",
            use_container_width=True,
            disabled=not pode_gerar,
        ):
            with st.spinner("Criando uma amostra cumulativa original com a skill do Roteirista..."):
                versao = gerar_estilo_adicional(dict(s), chamar_llm, chave, modo="amostra")
                item = deepcopy(versao)
                item["origem"] = "comparative_story_director_additional"
                item["faixa_etaria"] = s.get("faixa_etaria")
                item["colecao"] = s.get("colecao")
                item["status"] = "atual"
                biblioteca = deepcopy(s.get("versoes_narrativas_salvas") or {})
                biblioteca[chave] = item
                s["versoes_narrativas_salvas"] = biblioteca
            st.rerun()

        if c2.button(
            "📚 Gerar história COMPLETA Cumulativo/Lengalenga",
            key=f"completa_extra_{chave}",
            use_container_width=True,
            disabled=not pode_gerar,
        ):
            with st.spinner("Escrevendo a história cumulativa completa com a skill do Roteirista..."):
                versao = gerar_estilo_adicional(dict(s), chamar_llm, chave, modo="completa")
                item = deepcopy(versao)
                item["origem"] = "comparative_story_director_additional"
                item["faixa_etaria"] = s.get("faixa_etaria")
                item["colecao"] = s.get("colecao")
                item["status"] = "atual"
                biblioteca = deepcopy(s.get("versoes_narrativas_salvas") or {})
                biblioteca[chave] = item
                s["versoes_narrativas_salvas"] = biblioteca
            st.rerun()

        versao = (s.get("versoes_narrativas_salvas") or {}).get(chave) or {}
        if versao:
            st.divider()
            st.caption(f"Versão salva · modo: {versao.get('modo', 'amostra')}")
            if versao.get("titulo"):
                st.markdown(f"### {versao['titulo']}")
            if versao.get("sinopse_poetica"):
                st.write(versao["sinopse_poetica"])
            if versao.get("modo") == "completa" and versao.get("cenas_texto"):
                for cena in versao["cenas_texto"]:
                    if isinstance(cena, dict):
                        st.markdown(f"**Cena {cena.get('numero', '')}**")
                        st.write(cena.get("texto", ""))
                    else:
                        st.write(cena)
            else:
                st.write(versao.get("amostra") or "Amostra não disponível.")
            if versao.get("licao_final"):
                st.markdown(f"**⭐ Lição de Moral:** {versao['licao_final']}")

            ativa = s.get("versao_narrativa_ativa")
            if st.button(
                "✅ Tornar Cumulativo/Lengalenga a versão ativa",
                key=f"ativar_extra_{chave}",
                type="primary",
                disabled=ativa == chave,
                use_container_width=True,
            ):
                _ativar(chave, versao)
                st.rerun()

if s.get("versoes_narrativas_salvas"):
    if st.button("💾 Salvar Biblioteca de Versões", use_container_width=True, disabled=not pode_gerar):
        try:
            _persistir()
            st.success("Biblioteca salva. Esta versão poderá ser retomada depois sem regenerar.")
        except Exception as exc:
            st.error(f"Não foi possível salvar a biblioteca: {exc}")

st.caption(
    "Meta editorial do Cumulativo/Lengalenga FaithBloom: criar prazer de antecipação e releitura — a criança reconhece o padrão, participa, ri e quer ouvir de novo."
)
