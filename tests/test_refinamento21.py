from agent_skills import validate_registry, get_agent_profile, skill_contract
from biblical_reference_validator import create_reference_candidate, validate_reference_candidate, reference_gate
from bestseller_readiness import evaluate_bestseller_readiness
from market_intelligence import make_market_evidence, validate_market_evidence, classify_market_mode, evidence_prompt
from quality_guardian import check_agent_skills, check_bible, check_market_readiness
from agents.curador_tema import curador_tema_node
from agents.pesquisa_mercado import pesquisa_palavras_chave_node


def test_agent_registry_has_23_roles_and_21_modules():
    audit = validate_registry()
    assert audit["ok"] is True
    assert audit["role_count"] == 23
    assert audit["module_count"] == 21


def test_every_profile_has_formal_limits_and_quality_criteria():
    for rid in ("storyteller", "illustrator", "market_keywords", "translator_localizer", "cover_specialist", "audiobook_director"):
        p = get_agent_profile(rid)
        assert len(p["skills"]) >= 3
        assert len(p["quality_criteria"]) >= 2
        assert any("best-seller" in x or "bestseller" in x for x in p["forbidden"])
        assert "SKILL CONTRACT" in skill_contract(rid)


def test_market_without_evidence_is_explicitly_inference_only():
    mode = classify_market_mode([])
    assert mode["mode"] == "model_inference_only"
    assert mode["can_make_observed_market_claims"] is False
    prompt = evidence_prompt([])
    assert "NÃO pode afirmar volume" in prompt


def test_valid_market_evidence_enables_observed_claim_scope_only():
    ev = make_market_evidence(
        source_type="retailer_observation", source_name="Loja observada",
        source_url="https://example.com/book", market="US/en-US",
        observation="Amostra de títulos concorrentes revisada manualmente.",
        observed_at="2026-09-03", verified_by_human=True,
    )
    assert validate_market_evidence(ev)["ok"] is True
    mode = classify_market_mode([ev])
    assert mode["mode"] == "observed_evidence"
    assert mode["can_make_observed_market_claims"] is True


def test_bible_reference_is_candidate_until_source_context_and_human_approval():
    cand = create_reference_candidate("Lucas 2:11", reason="Natal")
    assert cand["status"] == "candidate_unverified"
    assert reference_gate({"versiculo_referencia": "Lucas 2:11", "bible_reference_candidate": cand})["ok"] is False
    validated = validate_reference_candidate(
        cand, source_name="Fonte aprovada", source_reference="ISBN/URL",
        context_note="Contexto conferido e coerente com a aplicação narrativa.",
        context_verified=True, human_approved=True, approved_by="Autora",
    )
    assert validated["status"] == "validated"
    gate = reference_gate({"versiculo_referencia": "Lucas 2:11", "bible_reference_validation": validated})
    assert gate["ok"] is True
    assert validated["scripture_text_stored_here"] is False


def test_curator_marks_ai_reference_as_candidate_not_validated():
    def llm(**kwargs):
        return {
            "emocao_central": "esperanca",
            "versiculo_referencia": "Lucas 2:11",
            "aprendizado_cristao": "lembrar o nascimento de Jesus",
            "titulo_sugerido": "Quando Mel Descobriu o Natal",
            "justificativa": "Conecta-se ao tema do Natal.",
        }
    state = {"_entrada_tema_livre": "Natal", "personagens": {}}
    out = curador_tema_node(state, llm)
    assert out["versiculo_referencia"] == "Lucas 2:11"
    assert out["bible_reference_candidate"]["status"] == "candidate_unverified"
    assert out["bible_reference_validation"]["status"] == "candidate_unverified"


def test_market_agent_records_provenance_inference_only_without_evidence():
    def llm(**kwargs):
        assert "MODEL_INFERENCE_ONLY" in kwargs["sistema"]
        return ["christian patience book kids"] * 7
    state = {"titulo": "Teste", "aprendizado_cristao": "paciência", "emocao_central": "esperanca", "sinopse_vendas_curta": "", "market_evidence": []}
    out = pesquisa_palavras_chave_node(state, llm)
    assert out["market_suggestions_provenance"]["mode"] == "model_inference_only"


def test_bestseller_readiness_never_outputs_probability_or_sales_guarantee():
    state = {
        "titulo": "Livro Teste", "faixa_etaria": "3–8", "revisao_aprovada": True,
        "aprendizado_cristao": "confiar em Deus", "versiculo_referencia": "Salmo 27:14",
        "cenas_texto": [{"numero": 1, "texto": "Mel queria descobrir algo.", "emocao": "esperanca", "contexto_visual": "jardim"}],
        "personagens": {}, "market_evidence": [],
    }
    r = evaluate_bestseller_readiness(state)
    assert "probability" not in r
    assert r["policy"]["bestseller_probability_generated"] is False
    assert r["policy"]["sales_guarantee"] is False
    assert r["status"] == "BLOCKED"


def test_quality_guardian_checks_skill_registry_and_unvalidated_bible_reference():
    skills = check_agent_skills({})
    assert any(x["code"] == "skill_registry_ok" for x in skills)
    bible = check_bible({"aprendizado_cristao": "fé", "versiculo_referencia": "João 3:16"})
    assert any(x["code"] == "biblical_reference_validation" and x["severity"] == "bloqueante" for x in bible)


def test_market_guardian_flags_missing_observed_evidence_without_fake_metrics():
    items = check_market_readiness({"palavras_chave_kdp": ["abc"], "market_evidence": []})
    assert any(x["code"] == "market_evidence_missing" for x in items)
    assert all("%" not in x["finding"] for x in items)
