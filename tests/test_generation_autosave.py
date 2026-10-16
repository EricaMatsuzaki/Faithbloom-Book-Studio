from __future__ import annotations

import generation_autosave as ga
import agents.estilos_narrativos as estilos
import agents.roteirista_autoral as autoral
import agents.curador_tema as curador


def _state():
    return {
        "colecao": "PILOTO QA — FaithBloom 2.0",
        "titulo": "Clara e o Corredor",
        "_entrada_tema_livre": "Clara sente medo do corredor escuro.",
        "emocao_central": "medo",
        "aprendizado_cristao": "Confiar em Deus quando sentimos medo.",
        "versiculo_referencia": "Salmos 56:3",
        "faixa_etaria": "6-8",
        "paginas_minimas": 24,
        "personagens_historia_brief": "Clara; Sofia; Ben; Floc.",
    }


def test_autosave_reusa_projeto_existente(monkeypatch):
    saved = {}
    monkeypatch.setattr(ga, "listar_livros", lambda colecao: [
        {"titulo": "Clara e o Corredor", "storage_path": "livros/piloto/clara.json"}
    ])
    monkeypatch.setattr(ga, "salvar_livro", lambda state: (_ for _ in ()).throw(AssertionError("não deve criar duplicata")))

    def fake_update(path, state):
        saved["path"] = path
        saved["state"] = state
        return "fb://livros/piloto/clara.json"

    monkeypatch.setattr(ga, "atualizar_livro_salvo", fake_update)
    state = _state()
    out = ga.persist_generation_snapshot(state, reason="teste", updates={"comparativo_estilos": {"x": {}}})
    assert out == "fb://livros/piloto/clara.json"
    assert saved["path"] == "livros/piloto/clara.json"
    assert "comparativo_estilos" in saved["state"]
    assert state["autosave_status"] == "saved"


def test_comparativo_autosalva_biblioteca(monkeypatch):
    calls = []
    monkeypatch.setattr(estilos, "persist_generation_snapshot", lambda state, **kwargs: calls.append(kwargs) or "fb://x")

    def fake_llm(*, sistema, instrucao):
        return {"titulo": "Clara", "amostra": "Um passo.", "licao_final": "Confiar."}

    out = estilos.gerar_comparativo_estilos(_state(), fake_llm, modo="amostra")
    assert len(out) == 4
    assert calls
    assert "comparativo_estilos" in calls[-1]["updates"]
    assert len(calls[-1]["updates"]["versoes_narrativas_salvas"]) == 4


def test_estilo_adicional_autosalva(monkeypatch):
    calls = []
    monkeypatch.setattr(estilos, "persist_generation_snapshot", lambda state, **kwargs: calls.append(kwargs) or "fb://x")
    out = estilos.gerar_estilo_adicional(
        _state(),
        lambda **kwargs: {"titulo": "Clara", "amostra": "Refrão.", "licao_final": "Confiar."},
        "cumulativo_lengalenga",
        modo="amostra",
    )
    assert out["estilo"] == "cumulativo_lengalenga"
    assert calls and "cumulativo_lengalenga" in calls[-1]["updates"]["versoes_narrativas_salvas"]


def test_versao_autoral_autosalva(monkeypatch):
    calls = []
    monkeypatch.setattr(autoral, "persist_generation_snapshot", lambda state, **kwargs: calls.append(kwargs) or "fb://x")
    out = autoral.gerar_versao_autoral_roteirista(
        _state(),
        lambda **kwargs: {
            "titulo": "Clara",
            "cenas_texto": [{"numero": 1, "texto": "Clara respirou."}],
            "licao_final": "Confiar.",
            "estilo_recomendado": "misto",
        },
    )
    assert out["modo"] == "completa"
    assert calls and "roteirista_autoral" in calls[-1]["updates"]["versoes_narrativas_salvas"]


def test_curadoria_cria_destino_persistente(monkeypatch):
    calls = []
    monkeypatch.setattr(curador, "persist_generation_snapshot", lambda state, **kwargs: calls.append(kwargs) or "fb://x")
    state = _state()
    state.pop("titulo")
    state.pop("emocao_central")
    state.pop("aprendizado_cristao")
    state.pop("versiculo_referencia")
    out = curador.curador_tema_node(
        state,
        lambda **kwargs: {
            "titulo_sugerido": "Clara e o Corredor",
            "emocao_central": "medo",
            "aprendizado_cristao": "Confiar em Deus.",
            "versiculo_referencia": "Salmos 56:3",
            "justificativa": "Coerente com o tema.",
        },
    )
    assert out["titulo"] == "Clara e o Corredor"
    assert calls and calls[-1]["reason"] == "theme_curated"
