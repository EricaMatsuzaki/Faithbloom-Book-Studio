import estilo
import jarvis_heart_mic as heart


def test_shared_style_hides_streamlit_page_dump_and_exposes_compact_menu():
    assert 'stSidebarNav"] { display:none' in estilo.CSS
    source = estilo.render_sidebar_navigation.__code__.co_consts
    labels = " ".join(str(value) for value in source)
    assert "FaithBloom" in labels
    assert "Criar & transformar" in labels
    assert "Universo & biblioteca" in labels
    assert "Qualidade & publicação" in labels
    assert "Ferramentas avançadas" in labels


def test_heart_component_rebinds_click_handler_without_stale_dataset_guard():
    assert "root._fbHeartState" in heart.JS
    assert "heart.onclick" in heart.JS
    assert "dataset.bound" not in heart.JS
    assert "speechSynthesis" not in heart.JS
    assert "new Audio(" not in heart.JS


def test_heart_component_keeps_stream_state_across_component_rerenders():
    assert "root._fbHeartState||(root._fbHeartState=" in heart.JS
    assert "if(state.rec&&state.rec.state==='recording')stop();else start()" in heart.JS
