"""Runtime regressions for story selection and saved-project ownership."""
from __future__ import annotations

import ast
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from agents.estilos_narrativos import TODOS_ESTILOS, aplicar_estilo_ao_state
from agents.roteirista import roteirista_node
import agents.estilos_narrativos as estilos
import agents.roteirista_autoral as autoral


ROOT = Path(__file__).resolve().parents[1]
STORY_PAGE = ROOT / "pages/39_✍️_Historia_4_Estilos.py"


def _project():
    return {
        "titulo": "Lia e a Coragem",
        "colecao": "Coleção de Teste",
        "faixa_etaria": "6-8",
        "paginas_minimas": 24,
        "emocao_central": "coragem",
        "aprendizado_cristao": "Confiar em Deus.",
        "versiculo_referencia": "Salmos 56:3",
        "personagens": {
            "Lia": {
                "nome": "Lia",
                "papel": "protagonista",
                "descricao_fixa": "olhos verdes",
                "imagem_referencia": "official-master.png",
                "aparencia_aprovada": True,
            }
        },
    }


@pytest.mark.parametrize("style", list(TODOS_ESTILOS))
def test_selected_sample_reaches_full_story_generation_for_each_registered_style(style):
    original = _project()
    selected = aplicar_estilo_ao_state(original, style, {"modo": "amostra"})
    scenes = [{"numero": i + 1, "texto": f"Cena {i + 1}."} for i in range(12)]
    provider = Mock(return_value={"sinopse_poetica": "Uma jornada.", "cenas_texto": scenes, "licao_final": "Confiar."})

    result = roteirista_node(selected, provider)

    provider.assert_called_once()
    assert result["estilo_narrativo"] == style
    assert result["estilo_narrativo_label"] == TODOS_ESTILOS[style]["label"]
    assert TODOS_ESTILOS[style]["label"] in provider.call_args.kwargs["sistema"]
    assert result["cenas_texto"] == scenes
    assert result["personagens"] == original["personagens"]


@pytest.mark.parametrize("style", list(TODOS_ESTILOS))
def test_selected_complete_story_is_preserved_for_each_registered_style(style):
    original = _project()
    scenes = [{"numero": i + 1, "texto": f"Cena aprovada {i + 1}."} for i in range(12)]
    selected = aplicar_estilo_ao_state(
        original, style, {"modo": "completa", "cenas_texto": scenes, "licao_final": "Confiar."}
    )
    provider = Mock(side_effect=AssertionError("A história selecionada não deve consumir outra geração."))

    result = roteirista_node(selected, provider)

    provider.assert_not_called()
    assert result["cenas_texto"] == scenes
    assert result["estilo_narrativo_label"] == TODOS_ESTILOS[style]["label"]
    assert result["historia_escolhida_preservar"] is False
    assert result["revisao_aprovada"] is False
    assert result["personagens"] == original["personagens"]


def _page_persistence(state, session, save, update):
    """Load the shipped callback without executing unrelated UI or storage reads."""
    tree = ast.parse(STORY_PAGE.read_text(encoding="utf-8"))
    callback = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_persistir_estado")
    namespace = {
        "s": state,
        "st": SimpleNamespace(session_state=session),
        "salvar_livro": save,
        "atualizar_livro_salvo": update,
    }
    exec(compile(ast.Module(body=[callback], type_ignores=[]), str(STORY_PAGE), "exec"), namespace)
    return namespace["_persistir_estado"]()


def test_new_story_does_not_overwrite_previous_story_from_same_browser_session():
    old_path = "fb://livros/colecao/old-book-a.json"
    new_path = "fb://livros/colecao/new-book-b.json"
    old_book = {"titulo": "Old Book A", "cenas_texto": [{"numero": 1, "texto": "Preservada."}]}
    persisted = {old_path: deepcopy(old_book)}

    def save(state):
        persisted[new_path] = deepcopy(state)
        return new_path

    def update(path, state):
        persisted[path] = deepcopy(state)
        return path

    save_mock, update_mock = Mock(side_effect=save), Mock(side_effect=update)
    new_book = {"titulo": "New Book B", "colecao": "Coleção"}
    result = _page_persistence(new_book, {"historia4_storage_path": old_path}, save_mock, update_mock)

    assert result == new_path
    save_mock.assert_called_once()
    update_mock.assert_not_called()
    assert persisted[old_path] == old_book
    assert persisted[new_path]["titulo"] == "New Book B"
    assert new_book["storage_path"] == new_path


def test_existing_story_updates_its_own_path_instead_of_browser_session_path():
    own_path = "fb://livros/colecao/current-book.json"
    state = {"titulo": "Current Book", "colecao": "Coleção", "storage_path": own_path}
    save = Mock(side_effect=AssertionError("O projeto existente deve ser atualizado."))
    update = Mock(return_value=own_path)

    assert _page_persistence(state, {"historia4_storage_path": "fb://another-book.json"}, save, update) == own_path

    save.assert_not_called()
    update.assert_called_once_with(own_path, state)


def test_failed_save_keeps_previous_project_and_new_unsaved_state_unchanged():
    state = {"titulo": "New Book", "colecao": "Coleção"}
    original = deepcopy(state)
    save = Mock(side_effect=RuntimeError("Storage indisponível"))
    update = Mock()

    with pytest.raises(RuntimeError, match="Storage indisponível"):
        _page_persistence(state, {"historia4_storage_path": "fb://previous-book.json"}, save, update)

    assert state == original
    update.assert_not_called()


@pytest.mark.parametrize("mode", ["amostra", "completa"])
def test_comparison_checkpoints_successful_versions_before_later_provider_failure(monkeypatch, mode):
    snapshots = []
    monkeypatch.setattr(estilos, "persist_generation_snapshot", lambda state, **kwargs: snapshots.append(deepcopy(kwargs["updates"])) or "fb://book.json")
    state = _project()
    previous = {"estilo_3": {"amostra": "Versão anterior preservada.", "status": "atual"}}
    state["versoes_narrativas_salvas"] = deepcopy(previous)
    provider = Mock(side_effect=[
        {"titulo": "T", "amostra": "Nova aventura", "cenas_texto": [{"numero": 1, "texto": "Nova aventura"}], "licao_final": "L"},
        {"titulo": "T", "amostra": "Nova poesia", "cenas_texto": [{"numero": 1, "texto": "Nova poesia"}], "licao_final": "L"},
        RuntimeError("Falha na terceira chamada"),
    ])

    with pytest.raises(RuntimeError, match="terceira chamada"):
        estilos.gerar_comparativo_estilos(state, provider, modo=mode)

    assert provider.call_count == 3
    assert len(snapshots) == 2
    assert list(snapshots[0]["comparativo_estilos"]) == ["estilo_1"]
    assert list(snapshots[1]["comparativo_estilos"]) == ["estilo_1", "estilo_2"]
    assert state["comparativo_estilos"]["estilo_2"]["amostra"] == "Nova poesia"
    assert snapshots[-1]["versoes_narrativas_salvas"]["estilo_3"] == previous["estilo_3"]


def test_explicit_page_checkpoint_replaces_default_autosave_and_stops_on_save_failure(monkeypatch):
    autosave = Mock(side_effect=AssertionError("A tela já fornece seu próprio checkpoint persistente."))
    monkeypatch.setattr(estilos, "persist_generation_snapshot", autosave)
    provider = Mock(return_value={"titulo": "T", "amostra": "Aventura", "licao_final": "L"})
    checkpoint = Mock(side_effect=RuntimeError("Não foi possível salvar o projeto"))
    state = _project()

    with pytest.raises(RuntimeError, match="salvar o projeto"):
        estilos.gerar_comparativo_estilos(state, provider, on_progress=checkpoint)

    provider.assert_called_once()
    autosave.assert_not_called()
    assert list(state["comparativo_estilos"]) == ["estilo_1"]


def test_default_checkpoint_failure_keeps_completed_version_and_stops_further_paid_calls(monkeypatch):
    state = _project()
    provider = Mock(return_value={"titulo": "T", "amostra": "Aventura concluída", "licao_final": "L"})
    autosave = Mock(side_effect=RuntimeError("Storage indisponível no primeiro checkpoint"))
    monkeypatch.setattr(estilos, "persist_generation_snapshot", autosave)

    with pytest.raises(RuntimeError, match="primeiro checkpoint"):
        estilos.gerar_comparativo_estilos(state, provider)

    provider.assert_called_once()
    autosave.assert_called_once()
    assert state["comparativo_estilos"]["estilo_1"]["amostra"] == "Aventura concluída"
    assert state["versoes_narrativas_salvas"]["estilo_1"]["amostra"] == "Aventura concluída"
    assert state["autosave_status"] == "error"
    assert "primeiro checkpoint" in state["autosave_error"]


@pytest.mark.parametrize("mode,response", [
    ("amostra", {}), ("amostra", {"amostra": "  \n"}),
    ("completa", {}), ("completa", {"cenas_texto": []}),
    ("completa", {"cenas_texto": [{"numero": 1, "texto": "  "}]}),
    ("completa", {"cenas_texto": [{"numero": 1, "texto": None}]}),
])
def test_empty_comparison_reply_does_not_replace_or_persist_previous_draft(monkeypatch, mode, response):
    old = {"modo": mode, "amostra": "Amostra revisada", "cenas_texto": [{"numero": 1, "texto": "História revisada"}]}
    state = {**_project(), "comparativo_estilos": {"estilo_1": deepcopy(old)}, "versoes_narrativas_salvas": {"estilo_1": deepcopy(old)}}
    before = deepcopy(state)
    autosave = Mock()
    monkeypatch.setattr(estilos, "persist_generation_snapshot", autosave)
    provider = Mock(return_value=response)

    with pytest.raises(ValueError, match="Sua versão anterior foi preservada"):
        estilos.gerar_comparativo_estilos(state, provider, modo=mode)

    assert state == before
    autosave.assert_not_called()
    provider.assert_called_once()


@pytest.mark.parametrize("response", [{}, {"cenas_texto": []}, {"cenas_texto": [{"texto": "  "}]}, "Sinopse sem história"])
def test_empty_authorial_reply_keeps_previous_complete_version(monkeypatch, response):
    old = {"modo": "completa", "cenas_texto": [{"numero": 1, "texto": "História da autora"}]}
    state = {**_project(), "versao_roteirista_autoral": deepcopy(old), "versoes_narrativas_salvas": {"roteirista_autoral": deepcopy(old)}}
    before = deepcopy(state)
    autosave = Mock()
    monkeypatch.setattr(autoral, "persist_generation_snapshot", autosave)

    with pytest.raises(ValueError, match="Sua versão anterior foi preservada"):
        autoral.gerar_versao_autoral_roteirista(state, Mock(return_value=response))

    assert state == before
    autosave.assert_not_called()


def test_real_authorial_page_reports_empty_reply_without_replacing_previous_story(monkeypatch):
    from streamlit.testing.v1 import AppTest
    import armazenamento
    import author_profiles
    import openrouter_client

    old = {"modo": "completa", "titulo": "Versão revisada", "cenas_texto": [{"numero": 1, "texto": "História preservada."}], "licao_final": "Confiar."}
    state = {**_project(), "versao_roteirista_autoral": deepcopy(old), "versoes_narrativas_salvas": {"roteirista_autoral": deepcopy(old)}}
    provider = Mock(return_value={})
    autosave = Mock()
    monkeypatch.setattr(armazenamento, "listar_livros", lambda *args: [])
    monkeypatch.setattr(armazenamento, "listar_colecoes", lambda: [state["colecao"]])
    monkeypatch.setattr(armazenamento, "carregar_biblioteca_personagens", lambda *_: {})
    monkeypatch.setattr(author_profiles, "list_author_profiles", lambda: [])
    monkeypatch.setattr(openrouter_client, "chamar_llm", provider)
    monkeypatch.setattr(autoral, "persist_generation_snapshot", autosave)
    app = AppTest.from_file(ROOT / "app.py").switch_page(STORY_PAGE.relative_to(ROOT).as_posix())
    app.session_state["state"] = state
    app.run(timeout=15)
    assert not app.exception
    next(item for item in app.button if item.label == "⭐ Gerar versão do Roteirista").click().run(timeout=15)

    assert not app.exception
    provider.assert_called_once()
    autosave.assert_not_called()
    assert any("Sua versão anterior foi preservada" in item.value for item in app.error)
    assert app.session_state["state"]["versao_roteirista_autoral"] == old
    assert app.session_state["state"]["versoes_narrativas_salvas"]["roteirista_autoral"] == old


def test_real_comparison_page_keeps_first_two_versions_when_third_provider_call_fails(monkeypatch):
    from streamlit.testing.v1 import AppTest
    import armazenamento
    import author_profiles
    import openrouter_client

    saved = {}
    path = "fb://livros/colecao/current.json"

    def save(state):
        saved[path] = deepcopy(state)
        return path

    def update(actual_path, state):
        assert actual_path == path
        saved[path] = deepcopy(state)
        return path

    monkeypatch.setattr(armazenamento, "listar_livros", lambda *args: [])
    monkeypatch.setattr(armazenamento, "listar_colecoes", lambda: ["Coleção de Teste"])
    monkeypatch.setattr(armazenamento, "carregar_biblioteca_personagens", lambda *_: {})
    monkeypatch.setattr(armazenamento, "salvar_livro", save)
    monkeypatch.setattr(armazenamento, "atualizar_livro_salvo", update)
    monkeypatch.setattr(author_profiles, "list_author_profiles", lambda: [])
    provider = Mock(side_effect=[
        {"titulo": "T", "amostra": "Aventura concluída", "licao_final": "L"},
        {"titulo": "T", "amostra": "Poesia concluída", "licao_final": "L"},
        RuntimeError("Provedor temporariamente indisponível"),
    ])
    monkeypatch.setattr(openrouter_client, "chamar_llm", provider)

    app = AppTest.from_file(ROOT / "app.py").switch_page(STORY_PAGE.relative_to(ROOT).as_posix())
    app.session_state["state"] = _project()
    app.session_state["historia4_storage_path"] = "fb://previous-project.json"
    app.run(timeout=15)
    assert not app.exception
    button = next(item for item in app.button if item.label == "✨ Ver amostras dos 4 estilos")
    button.click().run(timeout=15)

    assert not app.exception
    assert provider.call_count == 3
    assert any("Provedor temporariamente indisponível" in item.value for item in app.error)
    assert any("versões concluídas" in item.value for item in app.info)
    assert list(saved[path]["comparativo_estilos"]) == ["estilo_1", "estilo_2"]
    assert list(app.session_state["state"]["comparativo_estilos"]) == ["estilo_1", "estilo_2"]
    assert app.session_state["state"]["storage_path"] == path
    assert any("Aventura concluída" == item.value for item in app.markdown)
    assert any("Poesia concluída" == item.value for item in app.markdown)


def _editor_app(monkeypatch, provider, state, *, save_error=False):
    from streamlit.testing.v1 import AppTest
    import armazenamento
    import openrouter_client
    import generation_autosave

    saved = []
    image_provider = Mock(side_effect=AssertionError("A revisão editorial não deve gerar imagens."))
    monkeypatch.setattr(armazenamento, "listar_livros", lambda *args: [])
    monkeypatch.setattr(openrouter_client, "chamar_llm", provider)
    monkeypatch.setattr(openrouter_client, "gerar_imagem", image_provider)

    def save(path, snapshot):
        if save_error:
            raise RuntimeError("Storage temporariamente indisponível")
        saved.append(deepcopy(snapshot))
        return path

    monkeypatch.setattr(generation_autosave, "atualizar_livro_salvo", save)
    app = AppTest.from_file(ROOT / "app.py").switch_page("pages/1_📖_Criar_do_Zero.py")
    app.session_state["state"] = deepcopy(state)
    app.session_state["etapa"] = "revisar_texto"
    app.run(timeout=15)
    assert not app.exception
    provider.assert_not_called()
    image_provider.assert_not_called()
    return app, saved, image_provider


def _editor_project():
    return {
        **_project(),
        "storage_path": "fb://livros/colecao/current.json",
        "cenas_texto": [{
            "numero": 1, "texto": "Lia respirou e deu um passo corajoso.",
            "emocao": "esperanca", "figurino": "vestido amarelo", "contexto_visual": "jardim",
        }],
        "licao_final": "Confiar em Deus.",
    }


def test_story_editor_generates_and_saves_extras_only_after_explicit_request(monkeypatch, complete_editorial_extras):
    from age_profiles import perfil_etario

    state = _editor_project()
    count = perfil_etario(state["faixa_etaria"])["perguntas_pedagogicas"]
    provider = Mock(return_value=complete_editorial_extras(count, state["versiculo_referencia"]))
    app, saved, image_provider = _editor_app(monkeypatch, provider, state)
    app.button(key="zero_editorial_extras").click().run(timeout=15)

    assert not app.exception
    provider.assert_called_once()
    image_provider.assert_not_called()
    assert len(saved) == 1
    result = app.session_state["state"]
    assert result["cenas_texto"] == state["cenas_texto"]
    assert result["personagens"] == state["personagens"]
    assert result["boas_vindas"] == saved[0]["boas_vindas"] == "Olá, amiguinho!"
    assert result["pais_educadores"] == saved[0]["pais_educadores"]
    assert result["ficha_pedagogica"]["faixa_etaria"] == "6–8 anos"
    assert saved[0]["storage_path"] == state["storage_path"]
    assert any("consome créditos" in item.value for item in app.caption)
    assert any(item.value == "Olá, amiguinho!" for item in app.markdown)


@pytest.mark.parametrize("invalid_response", [False, True])
def test_failed_extras_preserve_existing_editorial_work(monkeypatch, complete_editorial_extras, invalid_response):
    from age_profiles import perfil_etario

    state = _editor_project()
    count = perfil_etario(state["faixa_etaria"])["perguntas_pedagogicas"]
    state.update(complete_editorial_extras(count, state["versiculo_referencia"]))
    state["boas_vindas"] = "Texto anterior revisado pela autora."
    provider = Mock(return_value={} if invalid_response else None,
                    side_effect=None if invalid_response else RuntimeError("Provedor indisponível"))
    app, saved, _ = _editor_app(monkeypatch, provider, state)
    app.button(key="zero_editorial_extras").click().run(timeout=15)

    assert not app.exception
    assert app.error
    assert not saved
    result = app.session_state["state"]
    for key in ("boas_vindas", "pais_educadores", "ficha_pedagogica", "cenas_texto", "personagens"):
        assert result[key] == state[key]


def test_extras_storage_failure_is_visible_without_discarding_generated_result(monkeypatch, complete_editorial_extras):
    from age_profiles import perfil_etario

    state = _editor_project()
    count = perfil_etario(state["faixa_etaria"])["perguntas_pedagogicas"]
    provider = Mock(return_value=complete_editorial_extras(count, state["versiculo_referencia"]))
    app, saved, _ = _editor_app(monkeypatch, provider, state, save_error=True)
    app.button(key="zero_editorial_extras").click().run(timeout=15)

    assert not app.exception
    assert not saved
    assert any("não foi possível salvá-los" in item.value for item in app.warning)
    assert app.session_state["state"]["boas_vindas"] == "Olá, amiguinho!"


def test_finalization_passes_live_session_state_to_illustrator_for_interruption_recovery(monkeypatch):
    from streamlit.testing.v1 import AppTest
    import armazenamento
    import agents.ilustrador

    state = _editor_project()
    generated = {"numero": 1, "caminho_arquivo": "completed-first-scene.png", "aprovado": False}

    def partial_generation(live_state, _provider):
        live_state["cenas_imagem"] = [generated]
        raise RuntimeError("Interrupção na próxima cena")

    monkeypatch.setattr(armazenamento, "listar_livros", lambda *args: [])
    monkeypatch.setattr(agents.ilustrador, "ilustrador_node", partial_generation)
    app = AppTest.from_file(ROOT / "app.py").switch_page("pages/1_📖_Criar_do_Zero.py")
    app.session_state["state"] = state
    app.session_state["etapa"] = "finalizando"
    app.run(timeout=15)

    assert len(app.exception) == 1
    assert "Interrupção na próxima cena" in app.exception[0].message
    assert app.session_state["state"]["cenas_imagem"] == [generated]
