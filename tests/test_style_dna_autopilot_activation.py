import style_dna


def test_unico_style_oficial_da_colecao_e_ativado_para_story(monkeypatch):
    saved = {}
    index = [{"id": "style-1", "nome": "Colecao Visual", "colecao": "Mel", "modo": "geral", "status": "oficial"}]
    style = {
        "id": "style-1", "nome": "Colecao Visual", "colecao": "Mel", "modo": "geral",
        "status": "oficial", "regras": {"luz": "suave"},
        "usos_permitidos": ["coloring", "cover"], "metadata": {}, "versoes": [],
    }

    monkeypatch.setattr(style_dna, "_index", lambda: index)
    monkeypatch.setattr(style_dna, "carregar_style", lambda sid: style)

    def fake_update(sid, novos):
        saved.update(novos)
        style.update(novos)
        return style

    monkeypatch.setattr(style_dna, "atualizar_style", fake_update)
    cards = style_dna.listar_styles("Mel")

    assert len(cards) == 1
    assert "story" in saved["usos_permitidos"]
    assert saved["metadata"]["story_auto_activation"]["rules_changed"] is False
    assert style["regras"] == {"luz": "suave"}


def test_multiplos_styles_nao_sao_ativados_silenciosamente(monkeypatch):
    index = [
        {"id": "a", "nome": "A", "colecao": "Mel", "status": "oficial"},
        {"id": "b", "nome": "B", "colecao": "Mel", "status": "oficial"},
    ]
    monkeypatch.setattr(style_dna, "_index", lambda: index)
    called = []
    monkeypatch.setattr(style_dna, "atualizar_style", lambda *args, **kwargs: called.append((args, kwargs)))

    cards = style_dna.listar_styles("Mel")

    assert len(cards) == 2
    assert called == []
