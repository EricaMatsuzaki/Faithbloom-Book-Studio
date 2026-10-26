from contextlib import nullcontext

import estilo
import jarvis_heart_mic as heart
import painel_visual


def test_shared_style_hides_streamlit_page_dump_and_exposes_compact_menu(monkeypatch):
    assert 'stSidebarNav"] { display:none' in estilo.CSS

    class MenuUi:
        sidebar = nullcontext()

        def __init__(self):
            self.groups = []
            self.links = []
            self.markup = []

        def container(self, **_kwargs):
            return nullcontext()

        def expander(self, label, **_kwargs):
            self.groups.append(label.casefold())
            return nullcontext()

        def page_link(self, page, **kwargs):
            self.links.append((page, kwargs["label"]))

        def markdown(self, markup, **_kwargs):
            self.markup.append(markup)

    ui = MenuUi()
    monkeypatch.setattr(painel_visual, "st", ui)
    estilo.render_sidebar_navigation()

    assert ui.groups == [
        "criar & transformar", "universo & biblioteca",
        "qualidade & publicação", "ferramentas avançadas",
    ]
    routes = [page for page, _label in ui.links]
    assert len(routes) == len(set(routes))
    assert set(routes) == set(painel_visual._routes())
    assert ("pages/00_🤖_Jarvis.py", "Início") in ui.links
    assert ("pages/53_📁_Meus_Projetos.py", "Meus projetos") in ui.links
    assert "pages/0_🤖_Orquestrador_FaithBloom.py" in routes
    assert "pages/01_🎙️_Jarvis_Voz.py" in routes
    assert "pages/1_📖_Criar_do_Zero.py" in routes
    assert any('aria-label="FaithBloom Book Studio"' in markup for markup in ui.markup)


def test_heart_component_rebinds_click_handler_without_stale_dataset_guard():
    assert "root._fbHeartState" in heart.JS
    assert "heart.onclick" in heart.JS
    assert "dataset.bound" not in heart.JS
    assert "speechSynthesis" not in heart.JS
    assert "new Audio(" not in heart.JS


def test_heart_component_keeps_stream_state_across_component_rerenders():
    assert "root._fbHeartState||(root._fbHeartState=" in heart.JS
    assert "if(state.rec&&state.rec.state==='recording')stop();else start()" in heart.JS
