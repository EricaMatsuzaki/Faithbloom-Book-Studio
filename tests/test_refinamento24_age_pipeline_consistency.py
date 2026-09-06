from pathlib import Path

from age_profiles import perfil_etario
from agents.curador_tema import curador_tema_node
from agents.revisor import revisor_node
from agents.editor_historia import editar_cena, sugerir_licoes
from agents.audiobook import audiobook_node
from agents.sinopse import sinopse_node
from agents.marketing import marketing_lancamento_node
import agents.tradutor as tradutor
from prompt_master_compliance import avaliar_prompt_mestre
from quality_guardian import _age_profile
from state import LivroState


def test_curador_respeita_faixa_e_nao_contamina_versiculo_manual():
    capturado = {}

    def fake_llm(*, sistema, instrucao):
        capturado["sistema"] = sistema
        return {
            "emocao_central": "esperanca",
            "versiculo_referencia": "Provérbios 3:5",
            "aprendizado_cristao": "confiar em Deus",
            "titulo_sugerido": "Uma Nova Coragem",
            "justificativa": "Combina com confiança.",
        }

    state = {
        "_entrada_tema_livre": "uma criança precisa aprender a confiar",
        "faixa_etaria": "9-12",
        "versiculo_referencia": "Salmo 23:1",
    }
    out = curador_tema_node(state, fake_llm)
    assert "9–12 anos" in capturado["sistema"]
    assert out["versiculo_referencia"] == "Salmo 23:1"
    assert "bible_reference_candidate" not in out


def test_curador_registra_candidata_quando_referencia_foi_adotada():
    def fake_llm(*, sistema, instrucao):
        return {
            "emocao_central": "esperanca",
            "versiculo_referencia": "Provérbios 3:5",
            "aprendizado_cristao": "confiar em Deus",
            "titulo_sugerido": "Uma Nova Coragem",
            "justificativa": "Combina com confiança.",
        }

    out = curador_tema_node(
        {"_entrada_tema_livre": "confiar", "faixa_etaria": "6-8"},
        fake_llm,
    )
    assert out["versiculo_referencia"] == "Provérbios 3:5"
    assert out["bible_reference_candidate"]["reference"] == "Provérbios 3:5"
    assert out["bible_reference_candidate"]["status"] == "candidate_unverified"


def test_revisor_usa_mesmo_age_profile_do_roteirista():
    capturado = {}

    def fake_llm(*, sistema, instrucao):
        capturado["sistema"] = sistema
        return {"status": "APROVADO", "notas": []}

    out = revisor_node(
        {
            "faixa_etaria": "9-12",
            "titulo": "Teste",
            "cenas_texto": [{"numero": 1, "texto": "Uma cena."}],
            "licao_final": "Escolher o bem.",
            "versiculo_referencia": "Miquéias 6:8",
        },
        fake_llm,
    )
    assert out["revisao_aprovada"] is True
    assert "9–12 anos" in capturado["sistema"]
    assert "30 palavras por frase" in capturado["sistema"]
    assert "220 palavras por cena" in capturado["sistema"]


def test_editor_nao_infantiliza_atalho_legado_em_9_12():
    capturado = {}

    def fake_llm(*, sistema, instrucao):
        capturado["sistema"] = sistema
        return {"texto": "Texto revisado."}

    editar_cena(
        {"numero": 1, "texto": "Texto original.", "personagem_principal": "Lia"},
        "Simplifique a linguagem desta cena para uma criança pequena, mantendo a mesma ação.",
        {"faixa_etaria": "9-12", "titulo": "Teste"},
        fake_llm,
    )
    assert "para a faixa etária 9–12 anos" in capturado["sistema"]
    assert "para uma criança pequena" not in capturado["sistema"]


def test_sugestao_de_moral_muda_com_faixa_etaria():
    capturado = {}

    def fake_llm(*, sistema, instrucao):
        capturado["sistema"] = sistema
        return {"opcoes": []}

    sugerir_licoes({"faixa_etaria": "3-5", "titulo": "Teste"}, fake_llm)
    assert "3–5 anos" in capturado["sistema"]
    assert "mais curta e concreta" in capturado["sistema"]


def test_audiobook_adapta_performance_sem_pedir_reescrita():
    capturado = {}

    def fake_llm(*, sistema, instrucao):
        capturado["sistema"] = sistema
        capturado["instrucao"] = instrucao
        return {"roteiro": []}

    audiobook_node(
        {
            "faixa_etaria": "9-12",
            "cenas_texto": [{"numero": 1, "texto": "Texto aprovado."}],
            "licao_final": "Lição",
            "versiculo_referencia": "Salmo 1:1",
        },
        fake_llm,
    )
    assert "9–12 anos" in capturado["sistema"]
    assert "ritmo mais contínuo" in capturado["sistema"]
    assert "NÃO reescreva" in capturado["sistema"]


def test_tradutor_preserva_faixa_do_master(monkeypatch):
    capturado = {}

    monkeypatch.setattr(tradutor, "idioma_elegivel_paperback", lambda _: True)

    def fake_localizar(state, chamar_llm, locale, **kwargs):
        capturado.update(kwargs)
        return {"locale": locale, "cenas_texto": []}

    monkeypatch.setattr(tradutor, "localizar_livro", fake_localizar)
    monkeypatch.setattr(
        tradutor,
        "revisar_localizacao_estrutural",
        lambda *args, **kwargs: {"ok": True, "alertas": [], "bloqueantes": 0},
    )

    out = tradutor.tradutor_node(
        {
            "faixa_etaria": "9-12",
            "idiomas_alvo": ["en"],
            "versiculo_referencia": "Salmo 1:1",
            "cenas_texto": [],
        },
        lambda **kwargs: {},
    )
    assert capturado["faixa_etaria"] == "9–12 anos"
    assert "FAIXA ETÁRIA OFICIAL: 9–12 anos" in capturado["instrucoes"]
    assert out["traducoes"]["en-US"]["faixa_etaria"] == "9-12"


def test_sinopse_comercial_respeita_faixa_e_evitar_promessas():
    capturado = {}

    def fake_llm(*, sistema, instrucao):
        capturado["sistema"] = sistema
        return {"sinopse_vendas_curta": "Curta", "sinopse_contracapa": "Longa"}

    out = sinopse_node(
        {
            "faixa_etaria": "9-12",
            "titulo": "Teste",
            "sinopse_poetica": "Uma jornada.",
            "aprendizado_cristao": "gratidão",
            "versiculo_referencia": "Salmo 118:24",
        },
        fake_llm,
    )
    assert "9–12 anos" in capturado["sistema"]
    assert "não infantilize" in capturado["sistema"]
    assert "não invente prêmios" in capturado["sistema"]
    assert out["sinopse_vendas_curta"] == "Curta"


def test_marketing_respeita_faixa_e_claims_seguros():
    capturado = {}

    def fake_llm(*, sistema, instrucao):
        capturado["sistema"] = sistema
        return {"legenda_instagram": "Post"}

    out = marketing_lancamento_node(
        {
            "faixa_etaria": "9-12",
            "colecao": "Coleção",
            "titulo": "Teste",
            "sinopse_vendas_curta": "Sinopse",
            "aprendizado_cristao": "gratidão",
            "versiculo_referencia": "Salmo 118:24",
            "autora": "Autora",
        },
        fake_llm,
    )
    assert "9–12 anos" in capturado["sistema"]
    assert "evitando chamar leitores 9–12" in capturado["sistema"]
    assert "não afirmar nem insinuar que o livro é best-seller" in capturado["sistema"]
    assert out["material_lancamento"]["legenda_instagram"] == "Post"


def test_compliance_avisa_ficha_com_idade_divergente():
    result = avaliar_prompt_mestre(
        {
            "faixa_etaria": "6-8",
            "licao_final": "Uma lição.",
            "ficha_pedagogica": {"faixa_etaria": "3–5 anos"},
            "paginas_colorir": [{}, {}, {}],
        }
    )
    codes = {x["codigo"] for x in result["recomendacoes"]}
    assert "FICHA_FAIXA_ETARIA_DIVERGENTE" in codes
    assert result["faixa_etaria"] == "6-8"


def test_compliance_mantem_3_8_como_compatibilidade_quando_idade_nao_confirmada():
    result = avaliar_prompt_mestre({"licao_final": "Uma lição.", "paginas_colorir": [{}, {}, {}]})
    codes = {x["codigo"] for x in result["recomendacoes"]}
    assert "FAIXA_ETARIA_NAO_CONFIRMADA" in codes
    assert result["faixa_etaria"] == "3-8"


def test_quality_guardian_nao_deriva_dos_limites_oficiais():
    for faixa in ("3-5", "3-8", "6-8", "9-12"):
        key, guardian = _age_profile({"faixa_etaria": faixa})
        official = perfil_etario(faixa)
        assert key == faixa
        assert guardian["max_words_sentence"] == official["max_words_sentence"]
        assert guardian["max_words_scene"] == official["max_words_scene"]


def test_state_tem_faixa_etaria_como_campo_oficial_e_sem_duplicata_colorir():
    assert "faixa_etaria" in LivroState.__annotations__
    assert "age_profile_id" in LivroState.__annotations__
    assert "storage_path" in LivroState.__annotations__
    source = Path("state.py").read_text(encoding="utf-8")
    assert source.count("paginas_colorir:") == 1


def test_dashboard_envia_criacao_para_novo_fluxo():
    source = Path("app.py").read_text(encoding="utf-8")
    assert 'card("Criar um livro"' in source
    assert '"pages/39_✍️_Historia_4_Estilos.py"' in source
    assert 'Criar do Zero — fluxo clássico 3–8' in source


def test_novo_fluxo_pede_colecao_autoria_salva_rascunho_e_carrega_biblioteca():
    source = Path("pages/39_✍️_Historia_4_Estilos.py").read_text(encoding="utf-8")
    assert 'st.subheader("1. Coleção e autoria")' in source
    assert "list_author_profiles" in source
    assert "listar_colecoes" in source
    assert "carregar_biblioteca_personagens" in source
    assert "st.session_state.biblioteca_colecao" in source
    assert '"💾 Salvar rascunho"' in source
    assert "_invalidar_comparativo_por_mudanca_editorial" in source


def test_novo_fluxo_permita_limpar_autoria_selecao():
    source = Path("pages/39_✍️_Historia_4_Estilos.py").read_text(encoding="utf-8")
    assert "if autores != atuais:" in source
    assert "set_project_authors(dict(s), autores)" in source
