from pathlib import Path

from PIL import Image, ImageDraw

from coloring_book_doctor import (
    perfil_faixa_etaria, analisar_line_art_avancada, auditar_lote_colorir,
    gerar_plano_recuperacao, plano_acabamento_colorir,
)
import cover_master


def _line_art(path: Path, gray=False, border=False):
    img = Image.new("L", (600, 600), 255)
    d = ImageDraw.Draw(img)
    color = 130 if gray else 0
    d.ellipse((150, 120, 450, 420), outline=color, width=12)
    d.ellipse((225, 210, 250, 235), fill=color)
    d.ellipse((350, 210, 375, 235), fill=color)
    d.arc((250, 250, 350, 330), 10, 170, fill=color, width=8)
    if border:
        d.rectangle((2, 2, 597, 597), outline=0, width=8)
    img.save(path)


def test_age_profiles_are_explicit():
    assert perfil_faixa_etaria("3-4")["complexidade_max"] < perfil_faixa_etaria("9-12")["complexidade_max"]
    assert "contornos" in perfil_faixa_etaria("3-4")["orientacao"].lower()


def test_advanced_line_art_qa_reports_measurable_metrics(tmp_path):
    p = tmp_path / "line.png"; _line_art(p)
    r = analisar_line_art_avancada(str(p), "5-6", 2.0, 2.0)
    assert r["largura_px"] == 600 and r["altura_px"] == 600
    assert r["complexidade_heuristica"] >= 0
    assert r["espessura_classe"] in {"muito fino", "fino", "médio", "grosso", "muito grosso"}
    assert r["print_qa"]["ppi_efetivo"] == 300.0
    assert "heurísticas" in r["nota_metodologica"]


def test_gray_and_border_create_alerts(tmp_path):
    p = tmp_path / "problem.png"; _line_art(p, gray=True, border=True)
    r = analisar_line_art_avancada(str(p), "3-4")
    codigos = {a["codigo"] for a in r["alertas"]}
    assert "cinzas" in codigos
    assert "borda" in codigos
    assert r["status"] in {"ajustes", "atencao", "bloqueante"}


def test_batch_audit_and_recovery_plan(tmp_path):
    a = tmp_path / "a.png"; b = tmp_path / "b.png"
    _line_art(a); _line_art(b, gray=True)
    assets = [
        {"id": "p010-i01", "pagina": 10, "arquivo": str(a)},
        {"id": "p012-i01", "pagina": 12, "arquivo": str(b)},
    ]
    rel = auditar_lote_colorir(assets, "5-6")
    assert rel["total_assets"] == 2
    assert sum(rel["resumo"].values()) == 2
    plan = gerar_plano_recuperacao(rel)
    assert len(plan["itens"]) == 2
    assert all("acao_sugerida" in x for x in plan["itens"])


def test_finish_plan_keeps_essentials_and_optionals():
    p = plano_acabamento_colorir(["Copyright", "Teste de cores"], incluir_lombada=True)
    assert "Capa frontal" in p["essenciais"]
    assert "Lombada (quando aplicável)" in p["essenciais"]
    assert p["opcionais_selecionados"] == ["Copyright", "Teste de cores"]


def test_cover_prompt_forbids_ai_typography(monkeypatch):
    monkeypatch.setattr(cover_master, "carregar_personagem_oficial", lambda cid: {})
    monkeypatch.setattr(cover_master, "carregar_style", lambda sid: {})
    prompt = cover_master.montar_prompt_cover_master("Cute Friends", [], "", "jardim", "mais fofo")
    assert "SEM título" in prompt
    assert "SEM texto" in prompt
    assert "jardim" in prompt


def test_cover_variations_are_versioned_and_selected(tmp_path):
    projeto = {"id": "abc", "pasta": str(tmp_path), "titulo": "Cute Friends"}
    a = tmp_path / "a.png"; b = tmp_path / "b.png"
    Image.new("RGB", (200, 200), "white").save(a)
    Image.new("RGB", (200, 200), "white").save(b)
    cover_master.criar_cover_master(projeto)
    va = cover_master.registrar_variacao_cover(projeto, "frente", str(a), "teste")
    vb = cover_master.registrar_variacao_cover(projeto, "frente", str(b), "teste")
    cover_master.aprovar_variacao_cover(projeto, vb["id"])
    plan = cover_master.carregar_cover_master(projeto)
    assert len(plan["variacoes"]) == 2
    selected = cover_master.variacao_selecionada(plan, "frente")
    assert selected["id"] == vb["id"]
    assert va["id"] != vb["id"]


def test_localized_cover_uses_same_master_plan(tmp_path):
    projeto = {"id": "abc", "pasta": str(tmp_path), "titulo": "Cute Friends"}
    cover_master.criar_cover_master(projeto)
    cover_master.registrar_edicao_localizada(projeto, "pt-BR", "Amigos Fofos", "", "Sinopse PT")
    cover_master.registrar_edicao_localizada(projeto, "en-US", "Cute Friends", "", "English blurb")
    plan = cover_master.carregar_cover_master(projeto)
    assert set(plan["edicoes_localizadas"]) == {"pt-BR", "en-US"}
    assert plan["arte_master_sem_texto"] is True
