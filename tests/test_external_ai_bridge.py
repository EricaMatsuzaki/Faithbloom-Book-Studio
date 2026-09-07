import json

import pytest

import external_ai_bridge as bridge


def _state():
    return {
        "colecao": "Coleção Teste",
        "titulo": "A Luz no Jardim",
        "faixa_etaria": "6-8",
        "_entrada_tema_livre": "Uma criança teme a noite no jardim e descobre coragem.",
        "emocao_central": "medo",
        "aprendizado_cristao": "Deus está presente quando sentimos medo.",
        "versiculo_referencia": "Salmos 56:3",
        "personagens_historia_brief": "Clara — protagonista curiosa.\nSofia — irmã mais nova.",
        "personagens": {},
        "versoes_narrativas_salvas": {},
    }


def _response():
    return {
        "titulo": "A Luz no Jardim",
        "sinopse_poetica": "Clara atravessa uma noite diferente.",
        "estilo_recomendado": "misto",
        "justificativa_criativa": "Equilibra ação, emoção e descoberta.",
        "cenas_texto": [
            {
                "numero": 1,
                "texto": "Clara ouviu as folhas farfalharem e apertou a lanterna.",
                "emocao": "medo",
                "emocao_secundaria": "curiosidade",
                "intensidade_emocional": 3,
                "transicao_emocional": "medo → curiosidade",
                "figurino": "pijama e casaco",
                "contexto_visual": "jardim à noite",
                "personagem_principal": "Clara",
                "expressao": "olhos atentos",
            },
            {
                "numero": 2,
                "texto": "Ela percebeu que o barulho vinha de um galho balançando.",
                "emocao": "alívio",
                "emocao_secundaria": "esperança",
                "intensidade_emocional": 2,
                "transicao_emocional": "curiosidade → alívio",
                "figurino": "pijama e casaco",
                "contexto_visual": "perto da árvore",
                "personagem_principal": "Clara",
                "expressao": "sorriso pequeno",
            },
        ],
        "licao_final": "Quando o medo chegar, podemos confiar em Deus.",
    }


def test_prompt_from_idea_inherits_storyteller_and_originality_contract():
    prompt = bridge.build_external_authoring_prompt(_state(), source_mode=bridge.SOURCE_IDEA)
    assert "FaithBloom Heart Arc" in prompt
    assert "ORIGINALITY & INEDITISM CONTRACT" in prompt
    assert "storyteller" in prompt.lower() or "Roteirista" in prompt
    assert "Salmos 56:3" in prompt
    assert "RETORNE SOMENTE JSON VÁLIDO" in prompt


def test_prompt_mode_requires_author_prompt():
    with pytest.raises(ValueError):
        bridge.build_external_authoring_prompt(_state(), source_mode=bridge.SOURCE_PROMPT, author_prompt="")


def test_owned_reference_is_marked_as_author_owned_not_third_party():
    prompt = bridge.build_external_authoring_prompt(
        _state(),
        source_mode=bridge.SOURCE_IDEA,
        author_owned_reference="Trecho do meu livro anterior.",
    )
    assert "TEXTO-BASE DA PRÓPRIA AUTORA" in prompt
    assert "Trecho do meu livro anterior." in prompt
    assert "não importe elementos externos" in prompt


def test_parser_accepts_plain_json_and_fenced_json():
    raw = json.dumps(_response(), ensure_ascii=False)
    version = bridge.parse_external_story_response(raw, _state())
    assert version["origem"] == bridge.EXTERNAL_AI_ORIGIN
    assert version["modo"] == "completa"
    assert len(version["cenas_texto"]) == 2
    assert version["estilo_recomendado"] == "misto"

    fenced = "```json\n" + raw + "\n```"
    version2 = bridge.parse_external_story_response(fenced, _state())
    assert version2["titulo"] == "A Luz no Jardim"


def test_parser_rejects_missing_scenes():
    with pytest.raises(ValueError):
        bridge.parse_external_story_response('{"titulo":"Sem cenas"}', _state())


def test_direct_imitation_prompt_is_blocked_before_export():
    result = bridge.prompt_originality_preflight(_state(), "Faça no estilo de uma obra famosa")
    assert result["status"] == "BLOCKED"
    assert any(x["code"] == "IMITATION_REQUEST" for x in result["blockers"])


def test_register_external_version_autosaves_without_llm(monkeypatch):
    state = _state()
    version = bridge.parse_external_story_response(json.dumps(_response(), ensure_ascii=False), state)
    calls = []

    def fake_persist(s, *, reason, updates=None):
        calls.append((reason, updates))
        return "fb://livros/teste.json"

    monkeypatch.setattr(bridge, "persist_generation_snapshot", fake_persist)
    key, path = bridge.register_external_version(state, version, source_mode=bridge.SOURCE_IDEA)
    assert key.startswith("ia_externa_")
    assert path == "fb://livros/teste.json"
    assert state["versoes_narrativas_salvas"][key]["origem"] == "external_ai_manual"
    assert calls and calls[0][0] == "ia_externa_ideia"


def test_external_page_has_no_openrouter_call():
    from pathlib import Path

    text = Path("pages/41_🤖_IA_Externa_sem_OpenRouter.py").read_text(encoding="utf-8")
    assert "openrouter_client" not in text
    assert "chamar_llm" not in text
