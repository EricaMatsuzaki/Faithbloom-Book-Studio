"""Galeria profissional + status de persistência do FaithBloom 2.0."""
import streamlit as st
from estilo import aplicar_estilo, hero
from armazenamento import (
    estatisticas_armazenamento, listar_galeria, favoritar_item_galeria,
    excluir_item_galeria, listar_colecoes, carregar_biblioteca_personagens,
    listar_livros, listar_livros_colorir, migrar_dados_locais_legados,
)
from coloring_presets import listar_presets

st.set_page_config(page_title="Galeria & Armazenamento", page_icon="🗃️", layout="wide")
aplicar_estilo()
hero("🗃️ Galeria & Armazenamento", "Seus assets, personagens, projetos e estilos em um só lugar — com persistência preparada para a nuvem.")

st.info("✨ Nova biblioteca visual disponível: o Refinamento 16 adiciona busca avançada, miniaturas, Masters, versões, vínculos de uso e Storage Manager.")
st.page_link("pages/31_🖼️_Asset_Library_Media_Manager.py", label="🖼️ Abrir Asset Library & Media Manager →", use_container_width=True)

stats = estatisticas_armazenamento()
c1,c2,c3,c4,c5 = st.columns(5)
c1.metric("Galeria", stats["galeria"]); c2.metric("Coleções", stats["colecoes"]); c3.metric("Story Books", stats["livros"]); c4.metric("Coloring Books", stats["livros_colorir"]); c5.metric("Storage", stats["modo"].upper())
if stats["persistente_cloud"]:
    st.success("☁️ Persistência em nuvem ativa. Seus arquivos sobrevivem a reinicializações do Streamlit.")
else:
    st.warning("💻 Modo LOCAL ativo. Ótimo para desenvolvimento, mas no Streamlit Cloud os arquivos podem ser perdidos em reinicializações. Configure Supabase antes de produção.")

tab_gal, tab_chars, tab_proj, tab_presets, tab_storage = st.tabs(["🖼️ Galeria", "👥 Personagens", "📚 Projetos", "🎨 Estilos", "☁️ Persistência"])

with tab_gal:
    a,b,c = st.columns([2,1,1])
    busca = a.text_input("Buscar", placeholder="coelhinha, Natal, line art...")
    filtro = b.selectbox("Tipo", ["Todos","personagem","cena","line_art","referencia","capa"])
    favoritas = c.checkbox("Só favoritas")
    itens = listar_galeria(None if filtro=="Todos" else filtro, favoritas, busca)
    if not itens: st.info("Nenhuma imagem encontrada.")
    cols=st.columns(4)
    for i,item in enumerate(itens):
        with cols[i%4]:
            with st.container(border=True):
                if item.get("caminho_arquivo"): st.image(item["caminho_arquivo"], use_container_width=True)
                st.markdown(f"**{item.get('nome','Imagem')}**")
                st.caption(" · ".join(item.get("tags",[])) or item.get("tipo",""))
                b1,b2=st.columns(2)
                if b1.button("💖" if item.get("favorita") else "♡", key=f"fav9_{item['id']}", use_container_width=True):
                    favoritar_item_galeria(item["id"], not bool(item.get("favorita"))); st.rerun()
                if b2.button("🗑️", key=f"del9_{item['id']}", use_container_width=True):
                    excluir_item_galeria(item["id"]); st.rerun()

with tab_chars:
    colecoes = listar_colecoes()
    if not colecoes: st.info("Ainda não há coleções com personagens oficiais.")
    else:
        col = st.selectbox("Coleção", colecoes, key="gal_col")
        bib = carregar_biblioteca_personagens(col)
        cards=st.columns(4)
        for i,(nome,p) in enumerate(bib.items()):
            with cards[i%4]:
                with st.container(border=True):
                    if p.get("imagem_referencia"): st.image(p["imagem_referencia"], use_container_width=True)
                    st.markdown(f"**{nome}**"); st.caption(p.get("papel","")); st.write(p.get("descricao_fixa",""))
                    if p.get("aparencia_aprovada"): st.success("🔒 Oficial")

with tab_proj:
    st.subheader("📖 Livros com história")
    for x in listar_livros()[:20]: st.write(f"• **{x['titulo']}** — {x.get('colecao','')}")
    st.subheader("🖍️ Livros de colorir")
    for x in listar_livros_colorir()[:20]: st.write(f"• **{x['titulo']}** — {x.get('tema_geral','')}")

with tab_presets:
    presets = listar_presets()
    cols=st.columns(3)
    for i,p in enumerate(presets):
        with cols[i%3]:
            with st.container(border=True):
                st.markdown(f"**{p.get('nome','Estilo')}**")
                st.caption(f"{p.get('publico','')} · {p.get('faixa_etaria','')}")
                st.write(f"Traço: {p.get('espessura','')} · Complexidade: {p.get('complexidade','')}")
                if p.get("favorito"): st.success("⭐ Favorito")

with tab_storage:
    st.markdown("### ☁️ Ativar persistência no Streamlit Cloud")
    st.code('''FAITHBLOOM_STORAGE_MODE = "supabase"\nSUPABASE_URL = "https://SEU-PROJETO.supabase.co"\nSUPABASE_SERVICE_ROLE_KEY = "SUA-CHAVE-SERVICE-ROLE"\nFAITHBLOOM_SUPABASE_BUCKET = "faithbloom"''', language="toml")
    st.caption("Crie antes um bucket PRIVADO chamado `faithbloom` no Supabase Storage. A service-role key deve ficar somente em Secrets do Streamlit, nunca no GitHub.")
    st.markdown("### 🔁 Migrar dados locais antigos")
    st.write("Se você já possui livros, galeria ou personagens nas pastas locais antigas, este botão envia uma cópia para o backend ativo. Os originais não são apagados.")
    if st.button("Migrar dados locais para o backend ativo", type="primary"):
        with st.spinner("Migrando..."):
            resultado = migrar_dados_locais_legados()
        st.success(f"Migração concluída: {resultado['json']} JSONs e {resultado['assets']} assets.")
        if resultado["erros"]: st.warning("Alguns itens não migraram:\n" + "\n".join(resultado["erros"][:10]))
