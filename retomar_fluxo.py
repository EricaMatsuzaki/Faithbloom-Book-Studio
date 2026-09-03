"""FaithBloom 2.0 - Fase 4: Retomar livro + controle de ilustração cena por cena."""
import importlib
import os
import uuid
import streamlit as st
from family_profiles import assign_saved_project_to_profile

from estilo import aplicar_estilo, hero, badge_status
from openrouter_client import chamar_llm, gerar_imagem, gerar_audio
from agents.personagens_variacoes import (
    garantir_variacao_inicial, gerar_primeira_referencia, gerar_multiplas_variacoes,
    gerar_variacao, selecionar_variacao, aprovar_variacao, favoritar_variacao,
    registrar_variacao_externa,
)
from agents.ilustrador import (
    obter_imagem_cena, definir_imagem_cena, gerar_cena_unica, criar_variacao_cena,
    aprovar_imagem_cena, restaurar_ultima_imagem_cena,
)
from agents.atividades_colorir import atividades_colorir_node
from agents.audiobook import audiobook_node, narracao_node
from agents.dedicatoria import dedicatoria_node
from agents.tradutor import tradutor_node
from agents.sinopse import sinopse_node
from agents.pesquisa_mercado import pesquisa_palavras_chave_node, pesquisa_categorias_node
from agents.diagramador import diagramador_node
from agents.capa import capa_node
from agents.marketing import marketing_lancamento_node
from armazenamento import salvar_livro, listar_livros, salvar_na_galeria


def _salvar_upload(arquivo, prefixo: str) -> str:
    os.makedirs("saida_imagens", exist_ok=True)
    ext = os.path.splitext(getattr(arquivo, "name", ""))[1].lower() or ".png"
    caminho = os.path.join("saida_imagens", f"{prefixo}_{uuid.uuid4().hex[:10]}{ext}")
    with open(caminho, "wb") as f:
        f.write(arquivo.getbuffer())
    return caminho


def _todos_personagens_aprovados(s: dict) -> bool:
    ps = list(s.get("personagens", {}).values())
    return bool(ps) and all(p.get("aparencia_aprovada") and p.get("imagem_referencia") for p in ps)


def _todas_cenas_prontas(s: dict) -> tuple[bool, int, int]:
    cenas = s.get("cenas_texto", [])
    total = len(cenas)
    prontas = 0
    for cena in cenas:
        item = obter_imagem_cena(s, cena["numero"])
        if item and item.get("caminho_arquivo") and item.get("aprovado"):
            prontas += 1
    return prontas == total and total > 0, prontas, total


def render_retomar_page():
    aplicar_estilo()
    hero("📚 Retomar Livro", "Continue de onde parou — sem refazer história nem imagens já aprovadas.")

    if "state_r" not in st.session_state:
        st.session_state.state_r = None
    if "etapa_r" not in st.session_state:
        st.session_state.etapa_r = "carregar"

    with st.sidebar:
        st.subheader("📚 Projetos salvos")
        for livro in listar_livros():
            st.markdown(f"{badge_status(livro['pacote_pronto'])} &nbsp; {livro['titulo']}", unsafe_allow_html=True)

    s = st.session_state.state_r

    if st.session_state.etapa_r == "carregar":
        st.info("🎄 O livro de Natal já está pronto para este fluxo: use `historia_natal` e `ESTADO_INICIAL_NATAL`.")
        nome_modulo = st.text_input("Arquivo do roteiro (sem .py)", value="historia_natal")
        nome_variavel = st.text_input("Variável de estado", value="ESTADO_INICIAL_NATAL")
        if st.button("📂 Carregar livro", type="primary", use_container_width=True):
            try:
                modulo = importlib.import_module(nome_modulo)
                estado = dict(getattr(modulo, nome_variavel))
                estado.setdefault("cenas_imagem", [])
                estado.setdefault("historico_imagens_cenas", {})
                estado.setdefault("cenas_imagem_aprovadas", [])
                estado.setdefault("imagens_cenas_enviadas", {})
                estado.setdefault("dedicatoria_texto", "")
                st.session_state.state_r = estado
                st.session_state.etapa_r = "personagens"
                st.rerun()
            except Exception as e:
                st.error(f"Não consegui carregar o livro: {e}")
        return

    if s is None:
        st.session_state.etapa_r = "carregar"
        st.rerun()

    st.caption(f"📖 **{s.get('titulo','')}** · {len(s.get('cenas_texto', []))} cenas · {s.get('versiculo_referencia','')}")

    if st.session_state.etapa_r == "personagens":
        st.subheader("👥 1. Aprove os personagens antes das cenas")
        st.caption("Nenhuma ilustração do livro inteiro será gerada nesta etapa. Você pode testar opções sem perder a primeira.")

        for nome in list(s.get("personagens", {}).keys()):
            p = garantir_variacao_inicial(s["personagens"][nome])
            with st.expander(f"{nome} · {p.get('papel','')}" , expanded=not p.get("aparencia_aprovada")):
                p["descricao_fixa"] = st.text_area("DNA visual", value=p.get("descricao_fixa", ""), key=f"r_dna_{nome}")

                upload = st.file_uploader("Enviar referência própria (opcional)", type=["png","jpg","jpeg","webp"], key=f"r_ref_{nome}")
                if upload is not None and st.button("➕ Adicionar imagem enviada às opções", key=f"r_add_ref_{nome}"):
                    caminho = _salvar_upload(upload, f"ref_{nome}")
                    p = registrar_variacao_externa(p, caminho)
                    s["personagens"][nome] = p
                    st.rerun()

                if not p.get("imagem_referencia") and st.button("✨ Gerar primeira opção", key=f"r_first_{nome}"):
                    with st.spinner(f"Criando a primeira referência de {nome}..."):
                        p = gerar_primeira_referencia(p, gerar_imagem)
                    s["personagens"][nome] = p
                    st.rerun()

                variacoes = p.get("variacoes_visuais", [])
                if variacoes:
                    cols = st.columns(min(3, len(variacoes)))
                    for i, v in enumerate(variacoes):
                        with cols[i % len(cols)]:
                            st.image(v.get("caminho_arquivo"), use_container_width=True)
                            st.caption(f"Opção {i+1}" + (" ⭐" if v.get("favorita") else ""))
                            vid=v.get("id")
                            if st.button("Selecionar", key=f"r_sel_{nome}_{vid}"):
                                s["personagens"][nome]=selecionar_variacao(p,vid); st.rerun()
                            if st.button("💖 Favoritar" if not v.get("favorita") else "♡ Desfavoritar", key=f"r_fav_{nome}_{vid}"):
                                s["personagens"][nome]=favoritar_variacao(p,vid,not bool(v.get("favorita"))); st.rerun()
                            if st.button("💾 Galeria", key=f"r_gal_{nome}_{vid}"):
                                salvar_na_galeria(v.get("caminho_arquivo"), nome, "personagem", [nome,p.get("papel","")], {"livro":s.get("titulo","")})
                                st.success("Salvo na Galeria.")

                c1,c2=st.columns(2)
                if c1.button("✨ Gerar +2 opções", key=f"r_more_{nome}", use_container_width=True):
                    with st.spinner("Gerando duas alternativas sem apagar as anteriores..."):
                        s["personagens"][nome]=gerar_multiplas_variacoes(p,gerar_imagem,2,p.get("variacao_selecionada_id")); st.rerun()
                pedido=st.text_input("Ajuste por prompt", placeholder="Ex.: mais fofuxa, menor, mais rosinha; preserve o rostinho", key=f"r_prompt_{nome}")
                if c2.button("🔀 Criar variação da selecionada", key=f"r_var_{nome}", use_container_width=True):
                    with st.spinner("Criando variação..."):
                        s["personagens"][nome]=gerar_variacao(p,gerar_imagem,pedido,p.get("variacao_selecionada_id")); st.rerun()

                selecionada=p.get("variacao_selecionada_id")
                if selecionada and st.button("✅ Aprovar e travar esta aparência", key=f"r_ok_{nome}", type="primary"):
                    s["personagens"][nome]=aprovar_variacao(p,selecionada); st.rerun()
                if p.get("aparencia_aprovada"):
                    st.success("🔒 Aparência aprovada. O FaithBloom usará esta referência nas cenas.")

        st.markdown("---")
        texto_dedicatoria = st.text_area("💐 Dedicatória (opcional) · uma pessoa por linha: Nome - relação", key="r_dedic")
        if texto_dedicatoria.strip():
            lista=[]
            for linha in texto_dedicatoria.splitlines():
                if "-" in linha:
                    a,b=linha.split("-",1); lista.append({"pessoa":a.strip(),"relacao":b.strip()})
            s["lista_dedicatoria"]=lista

        if _todos_personagens_aprovados(s):
            if st.button("🎨 Ir para ilustrações cena por cena", type="primary", use_container_width=True):
                st.session_state.etapa_r="cenas"; st.rerun()
        else:
            st.warning("Aprove todos os personagens antes de liberar as ilustrações. Isso evita gastar créditos com referências erradas.")
        return

    if st.session_state.etapa_r == "cenas":
        st.subheader("🎨 2. Ilustrações — controle cena por cena")
        st.caption("A imagem atual nunca é apagada quando você pede outra: ela vai para o histórico e pode ser restaurada.")
        ok, prontas, total = _todas_cenas_prontas(s)
        st.progress(prontas / total if total else 0, text=f"{prontas}/{total} cenas aprovadas")

        for cena in s.get("cenas_texto", []):
            n=int(cena["numero"]); item=obter_imagem_cena(s,n)
            with st.expander(f"Cena {n} · {'✅ aprovada' if item and item.get('aprovado') else '🟡 revisar'}", expanded=not bool(item and item.get("aprovado"))):
                st.write(cena.get("texto", ""))
                st.caption(f"Emoção: {cena.get('emocao','')} · Cenário: {cena.get('contexto_visual','')}")
                if item and item.get("caminho_arquivo"):
                    st.image(item["caminho_arquivo"], use_container_width=True)
                    st.caption(f"Origem: {item.get('origem','')}")
                else:
                    st.info("Esta cena ainda não tem imagem. Você pode gerar ou enviar uma pronta.")

                instrucao=st.text_area("✍️ Pedido específico para esta cena", placeholder="Ex.: manter tudo igual, mas deixar a Mel sorrindo mais; não alterar Manu nem o cenário.", key=f"r_scene_prompt_{n}")
                c1,c2,c3=st.columns(3)
                if c1.button("✨ Gerar" if not item else "🔄 Gerar nova", key=f"r_gen_scene_{n}", use_container_width=True):
                    with st.spinner(f"Gerando somente a cena {n}..."):
                        gerar_cena_unica(s,n,gerar_imagem,instrucao)
                    st.rerun()
                if c2.button("🔀 Criar variação", key=f"r_var_scene_{n}", disabled=not bool(item), use_container_width=True):
                    with st.spinner("Criando variação sem apagar a atual..."):
                        criar_variacao_cena(s,n,gerar_imagem,instrucao)
                    st.rerun()
                if c3.button("↩️ Voltar à anterior", key=f"r_restore_scene_{n}", disabled=not bool(s.get("historico_imagens_cenas",{}).get(str(n))), use_container_width=True):
                    restaurar_ultima_imagem_cena(s,n); st.rerun()

                upload=st.file_uploader("📤 Substituir/usar minha imagem", type=["png","jpg","jpeg","webp"], key=f"r_upload_scene_{n}")
                if upload is not None and st.button("Usar imagem enviada nesta cena", key=f"r_use_scene_{n}"):
                    caminho=_salvar_upload(upload,f"cena_{n}_autora")
                    definir_imagem_cena(s,n,caminho,"(imagem enviada pela autora)","enviada_pela_autora",False)
                    st.rerun()

                if item and item.get("caminho_arquivo"):
                    a,b=st.columns(2)
                    if a.button("✅ Aprovar / travar cena", key=f"r_approve_scene_{n}", type="primary", use_container_width=True):
                        aprovar_imagem_cena(s,n,True); st.rerun()
                    if b.button("💾 Salvar imagem na Galeria", key=f"r_gallery_scene_{n}", use_container_width=True):
                        salvar_na_galeria(item["caminho_arquivo"], f"{s.get('titulo','')} · Cena {n}", "cena", [s.get("titulo",""),f"cena-{n}"], {"cena_numero":n,"texto":cena.get("texto","")})
                        st.success("Imagem preservada na Galeria para futuro uso ou Line Art.")

                hist=s.get("historico_imagens_cenas",{}).get(str(n),[])
                if hist:
                    st.caption(f"🕘 {len(hist)} versão(ões) anterior(es) preservada(s).")

        ok, prontas, total = _todas_cenas_prontas(s)
        st.markdown("---")
        if ok:
            st.success("Todas as cenas estão aprovadas. Agora podemos finalizar sem regerar as imagens.")
            if st.button("🚀 Finalizar livro (line arts + áudio + tradução + sinopse + KDP)", type="primary", use_container_width=True):
                st.session_state.etapa_r="finalizar"; st.rerun()
        else:
            st.warning(f"Ainda faltam {total-prontas} cena(s) aprovadas.")
        return

    if st.session_state.etapa_r == "finalizar":
        progresso=st.progress(0,text="Gerando atividades de colorir...")
        s.update(atividades_colorir_node(dict(s),gerar_imagem)); progresso.progress(18,text="Preparando audiobook...")
        s.update(audiobook_node(dict(s),chamar_llm)); progresso.progress(28,text="Narrando...")
        s.update(narracao_node(dict(s),gerar_audio)); progresso.progress(40,text="Dedicatória...")
        if s.get("lista_dedicatoria"):
            s.update(dedicatoria_node(dict(s),chamar_llm))
        else:
            s.setdefault("dedicatoria_texto","")
        progresso.progress(53,text="Traduzindo..."); s.update(tradutor_node(dict(s),chamar_llm))
        progresso.progress(64,text="Criando sinopse..."); s.update(sinopse_node(dict(s),chamar_llm))
        progresso.progress(72,text="SEO KDP..."); s.update(pesquisa_palavras_chave_node(dict(s),chamar_llm)); s.update(pesquisa_categorias_node(dict(s),chamar_llm))
        progresso.progress(82,text="Diagramando..."); s.update(diagramador_node(dict(s)))
        progresso.progress(90,text="Capas..."); s.update(capa_node(dict(s),gerar_imagem))
        progresso.progress(96,text="Material de lançamento..."); s.update(marketing_lancamento_node(dict(s),chamar_llm))
        caminho=salvar_livro(dict(s)); assign_saved_project_to_profile(st.session_state.get("faithbloom_workspace_profile_id", ""), "story", caminho, dict(s)); st.session_state.caminho_salvo_r=caminho
        progresso.progress(100,text="Pronto!")
        st.session_state.etapa_r="resultado"; st.rerun()

    if st.session_state.etapa_r == "resultado":
        st.success("✅ Livro retomado e processado sem descartar as imagens aprovadas.")
        st.caption(f"Salvo em: {st.session_state.get('caminho_salvo_r','')}")
        if s.get("capa_ebook"): st.image(s["capa_ebook"], caption="Capa eBook", width=360)
        st.subheader("🎨 Cenas finais")
        for item in s.get("cenas_imagem",[]):
            st.image(item.get("caminho_arquivo"), caption=f"Cena {item.get('numero')} · {item.get('origem','')}", width=420)
        st.subheader("🖍️ Atividades de colorir")
        cols=st.columns(3)
        for i,p in enumerate(s.get("paginas_colorir",[])):
            cols[i%3].image(p.get("caminho_arquivo"),caption=f"Cena {p.get('numero','')}")
        st.subheader("📝 Sinopse"); st.write(s.get("sinopse_vendas_curta",""))
        with st.expander("Checklist KDP"):
            st.json(s.get("checklist_kdp",{}))
        if st.button("📚 Retomar outro livro"):
            st.session_state.state_r=None; st.session_state.etapa_r="carregar"; st.rerun()
