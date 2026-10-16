"""Biblioteca opcional de estilos e formatos narrativos do FaithBloom.

Os estilos desta página não substituem os quatro estilos do Prompt-Mestre e não
são gerados automaticamente. Formatos visuais, como Quadrinhos/HQ, são uma camada
separada e podem ser combinados com a versão literária escolhida.
"""
from __future__ import annotations

from copy import deepcopy
import streamlit as st

from state import LivroState
from estilo import aplicar_estilo, hero
from openrouter_client import chamar_llm
from armazenamento import salvar_livro, atualizar_livro_salvo
from agents.estilos_narrativos import (
    ESTILOS_ADICIONAIS,
    ORDEM_ESTILOS_ADICIONAIS,
    aplicar_estilo_ao_state,
    gerar_estilo_adicional,
)
from agents.formato_quadrinhos import (
    FORMATO_QUADRINHOS_ID,
    FORMATO_QUADRINHOS_LABEL,
    gerar_roteiro_quadrinhos,
)
from age_profiles import normalizar_faixa_etaria, perfil_etario

st.set_page_config(page_title="Explorar outros estilos", page_icon="➕", layout="wide")
aplicar_estilo()
hero(
    "➕ Explorar outros estilos",
    "Biblioteca opcional: estilos adicionais usam a skill-base do Roteirista; formatos visuais podem ser combinados com a história escolhida.",
)

if "state" not in st.session_state:
    st.session_state.state = LivroState(paginas_minimas=24, idiomas_alvo=[], personagens={})

s = st.session_state.state
s.setdefault("paginas_minimas", 24)
s.setdefault("personagens", {})
s.setdefault("versoes_narrativas_salvas", {})
s.setdefault("formatos_narrativos_salvos", {})
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


def _salvar_estilo_gerado(chave: str, versao: dict) -> None:
    item = deepcopy(versao)
    item["origem"] = "comparative_story_director_additional"
    item["faixa_etaria"] = s.get("faixa_etaria")
    item["colecao"] = s.get("colecao")
    item["status"] = "atual"
    biblioteca = deepcopy(s.get("versoes_narrativas_salvas") or {})
    biblioteca[chave] = item
    s["versoes_narrativas_salvas"] = biblioteca


st.info(
    "Nada nesta página é gerado automaticamente. Os quatro estilos principais continuam intactos e nenhuma ilustração é criada aqui."
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

st.divider()
st.markdown("# 📚 Estilos narrativos adicionais")
st.caption(
    "Eles mudam COMO a história é contada. Todos herdam a skill profissional `storyteller`, mas cada um acrescenta um mecanismo narrativo próprio."
)

for chave in ORDEM_ESTILOS_ADICIONAIS:
    spec = ESTILOS_ADICIONAIS[chave]
    nome_curto = spec.get("ui_nome_curto") or spec["label"]
    with st.container(border=True):
        st.markdown(f"## {spec['label']}")
        st.write(spec["descricao"])
        st.markdown(f"**DNA deste estilo:** {spec.get('dna', spec['instrucao'])}")
        if spec.get("faixas_recomendadas"):
            st.caption(spec["faixas_recomendadas"])
        st.caption(
            "Originalidade obrigatória: usar princípios literários gerais sem copiar voz, bordões, personagens, refrões, cenas, layouts ou identidade visual de obras existentes."
        )

        c1, c2 = st.columns(2)
        if c1.button(
            f"✨ Gerar amostra {nome_curto}",
            key=f"amostra_extra_{chave}",
            use_container_width=True,
            disabled=not pode_gerar,
        ):
            with st.spinner(f"Criando amostra {nome_curto} com a skill do Roteirista..."):
                versao = gerar_estilo_adicional(dict(s), chamar_llm, chave, modo="amostra")
                _salvar_estilo_gerado(chave, versao)
            st.rerun()

        if c2.button(
            f"📚 Gerar história COMPLETA {nome_curto}",
            key=f"completa_extra_{chave}",
            use_container_width=True,
            disabled=not pode_gerar,
        ):
            with st.spinner(f"Escrevendo a história completa {nome_curto} com a skill do Roteirista..."):
                versao = gerar_estilo_adicional(dict(s), chamar_llm, chave, modo="completa")
                _salvar_estilo_gerado(chave, versao)
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

            elementos = versao.get("elementos_graficos_sugeridos") or []
            if elementos:
                with st.expander("📝 Elementos gráficos sugeridos"):
                    for item in elementos:
                        st.write(f"• {item}")

            if versao.get("licao_final"):
                st.markdown(f"**⭐ Lição de Moral:** {versao['licao_final']}")

            ativa = s.get("versao_narrativa_ativa")
            if st.button(
                f"✅ Tornar {nome_curto} a versão ativa",
                key=f"ativar_extra_{chave}",
                type="primary",
                disabled=ativa == chave,
                use_container_width=True,
            ):
                _ativar(chave, versao)
                st.rerun()

        if spec.get("meta_editorial"):
            st.caption(f"Meta editorial: {spec['meta_editorial']}")

# ---------------------------------------------------------------- FORMATO HQ
st.divider()
st.markdown("# 🗯️ Formatos narrativos visuais")
st.caption(
    "Formato visual responde a COMO a história será apresentada. Ele não substitui o estilo literário: uma HQ pode nascer de Aventura, Misto, Cotidiano Cômico, Cumulativo ou outra versão."
)

with st.container(border=True):
    st.markdown(f"## {FORMATO_QUADRINHOS_LABEL}")
    st.write(
        "Transforma a história completa escolhida em roteiro sequencial de páginas e painéis, com ações visuais, diálogos, balões, legendas, SFX/onomatopeias e ganchos de virada de página."
    )
    st.markdown(
        "**DNA do formato:** leitura visual sequencial + painéis claros + diálogos curtos + timing cômico + expressões + onomatopeias + page-turn + balões diagramados profissionalmente."
    )
    st.caption(
        "Importante: balões, legendas e SFX ficam como texto estruturado para o Diagramador. O gerador de imagens não deve desenhar texto legível dentro da arte."
    )
    st.caption(
        "Originalidade obrigatória: o FaithBloom pode usar a linguagem geral dos quadrinhos, mas não copia personagens, bordões, traço, humor, composição distintiva ou identidade visual de nenhuma coleção existente."
    )

    tem_historia_completa = bool(s.get("cenas_texto"))
    if not tem_historia_completa:
        st.warning(
            "Para criar a HQ, escolha primeiro uma história COMPLETA como versão ativa. Assim o formato de quadrinhos adapta sua obra sem criar outra história por cima."
        )

    if st.button(
        "🗯️ Gerar roteiro de Quadrinhos/HQ infantil",
        key="gerar_formato_hq",
        type="primary",
        use_container_width=True,
        disabled=not bool(pode_gerar and tem_historia_completa),
    ):
        with st.spinner("Adaptando a história ativa para páginas e painéis de HQ infantil..."):
            roteiro = gerar_roteiro_quadrinhos(dict(s), chamar_llm)
            formatos = deepcopy(s.get("formatos_narrativos_salvos") or {})
            formatos[FORMATO_QUADRINHOS_ID] = roteiro
            s["formatos_narrativos_salvos"] = formatos
        st.rerun()

    roteiro_hq = (s.get("formatos_narrativos_salvos") or {}).get(FORMATO_QUADRINHOS_ID) or {}
    if roteiro_hq:
        st.divider()
        st.markdown(f"### {roteiro_hq.get('titulo') or s.get('titulo') or 'Roteiro de HQ'}")
        st.caption(
            f"Base narrativa: {roteiro_hq.get('estilo_narrativo_origem') or s.get('versao_narrativa_ativa') or 'história ativa'} · Faixa: {roteiro_hq.get('faixa_etaria') or s.get('faixa_etaria')}"
        )
        for pagina in roteiro_hq.get("paginas") or []:
            numero = pagina.get("numero", "")
            with st.expander(f"📄 Página {numero}"):
                if pagina.get("layout_sugerido"):
                    st.write(f"**Layout sugerido:** {pagina['layout_sugerido']}")
                for painel in pagina.get("paineis") or []:
                    st.markdown(f"**Painel {painel.get('numero', '')}**")
                    if painel.get("acao_visual"):
                        st.write(painel["acao_visual"])
                    for fala in painel.get("dialogos") or []:
                        quem = fala.get("personagem") or "Personagem"
                        st.write(f"💬 **{quem}:** {fala.get('fala', '')}")
                    if painel.get("narracao"):
                        st.write(f"📝 Narração: {painel['narracao']}")
                    if painel.get("sfx"):
                        st.write(f"💥 SFX: {painel['sfx']}")
                if pagina.get("gancho_virada"):
                    st.write(f"➡️ **Gancho de virada:** {pagina['gancho_virada']}")
        if roteiro_hq.get("licao_final"):
            st.markdown(f"**⭐ Lição de Moral:** {roteiro_hq['licao_final']}")
        if roteiro_hq.get("observacoes_diagramacao"):
            with st.expander("🎨 Orientações para diagramação da HQ"):
                st.write(roteiro_hq["observacoes_diagramacao"])

        formato_ativo = s.get("formato_narrativo_ativo")
        if st.button(
            "✅ Usar Quadrinhos/HQ como formato ativo",
            key="ativar_formato_hq",
            use_container_width=True,
            disabled=formato_ativo == FORMATO_QUADRINHOS_ID,
        ):
            s["formato_narrativo_ativo"] = FORMATO_QUADRINHOS_ID
            s["roteiro_quadrinhos"] = deepcopy(roteiro_hq)
            st.success("Formato Quadrinhos/HQ definido como ativo. A história literária original foi preservada.")

if s.get("versoes_narrativas_salvas") or s.get("formatos_narrativos_salvos"):
    if st.button("💾 Salvar Biblioteca de Versões", use_container_width=True, disabled=not pode_gerar):
        try:
            _persistir()
            st.success("Biblioteca salva. Versões narrativas e formatos poderão ser retomados depois sem regenerar.")
        except Exception as exc:
            st.error(f"Não foi possível salvar a biblioteca: {exc}")

st.caption(
    "FaithBloom separa Estilo Narrativo de Formato Visual: isso permite combinar uma mesma história com diferentes mecanismos de escrita e diferentes experiências de leitura."
)
