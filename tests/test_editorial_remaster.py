from pathlib import Path
import json

from pypdf import PdfWriter

import book_doctor
import editorial_remaster


def _pdf(path: Path, pages: int = 2) -> None:
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=612, height=792)
    with path.open("wb") as f:
        writer.write(f)


def _project(tmp_path: Path) -> dict:
    project = {
        "id": "mel123",
        "titulo": "Quando Mel Aprendeu a Esperar",
        "idioma": "pt-BR",
        "pasta": str(tmp_path / "book"),
        "tipo_projeto": "story",
        "status_publicacao": "publicado",
        "colecao": "Pequenas Histórias, Grandes Lições",
    }
    (Path(project["pasta"]) / "originais").mkdir(parents=True)
    (Path(project["pasta"]) / "remastered").mkdir(parents=True)
    source = tmp_path / "miolo.pdf"
    _pdf(source)
    original = book_doctor.preservar_original(project, str(source), "miolo")
    return project


def test_remaster_preserves_original_and_fails_closed_before_scene_confirmation(tmp_path):
    project = _project(tmp_path)
    manifest = json.loads((Path(project["pasta"]) / "originais" / "manifest.json").read_text(encoding="utf-8"))
    original = manifest[-1]["arquivo"]
    before = book_doctor.sha256(original)

    draft = editorial_remaster.criar_rascunho_remaster_editorial(project, {"titulo": project["titulo"]})

    assert book_doctor.sha256(original) == before
    assert draft["original"]["sha256"] == before
    assert draft["original"]["imutavel"] is True
    assert draft["cenas_texto"] == []
    assert draft["mapeamento_cenas_confirmado"] is False
    gate = editorial_remaster.gate_revisao_editorial(draft)
    assert gate["ok"] is False
    assert "mapeamento_cenas_nao_confirmado" in gate["bloqueios"]
    assert gate["next_step"] == "aguardar_confirmacao"


def test_remaster_route_reuses_existing_specialists_in_safe_order(tmp_path):
    project = _project(tmp_path)
    draft = editorial_remaster.criar_rascunho_remaster_editorial(project)
    route = draft["rota_editorial"]

    assert route[0] == "book_doctor"
    assert route.index("story_reviewer") < route.index("story_editor")
    assert route.index("story_editor") < route.index("storyteller")
    assert route.index("storyteller") < route.index("character_universe")
    assert route.index("character_universe") < route.index("restoration_studio")
    assert route.index("restoration_studio") < route.index("quality_guardian")
    assert route[-1] == "publishing_distribution_center"
    assert len(route) == len(set(route))
    assert draft["politica_revisao"]["preservar_original"] is True
    assert draft["politica_revisao"]["revisao_textual_antes_visual"] is True
    assert draft["politica_revisao"]["aprovacao_humana_obrigatoria"] is True


def test_sha_mismatch_blocks_remaster(tmp_path):
    project = _project(tmp_path)
    manifest_path = Path(project["pasta"]) / "originais" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    original = Path(manifest[-1]["arquivo"])
    original.write_bytes(original.read_bytes() + b"changed")

    try:
        editorial_remaster.criar_rascunho_remaster_editorial(project)
    except ValueError as exc:
        assert "SHA-256" in str(exc)
    else:
        raise AssertionError("Remaster deveria bloquear original com hash divergente")


def test_non_story_project_is_rejected(tmp_path):
    project = _project(tmp_path)
    project["tipo_projeto"] = "coloring"

    try:
        editorial_remaster.criar_rascunho_remaster_editorial(project)
    except ValueError as exc:
        assert "Story Book" in str(exc)
    else:
        raise AssertionError("Remaster textual não deve aceitar coloring nesta etapa")


def test_confirmed_mapping_builds_only_explicitly_selected_pages():
    draft = {
        "paginas_texto_extraido": [
            {"pagina": 1, "texto_extraido": "Capa", "tem_texto": True},
            {"pagina": 2, "texto_extraido": "Mel olhou para a semente.", "tem_texto": True},
            {"pagina": 3, "texto_extraido": "Ela esperou mais um pouco.", "tem_texto": True},
        ],
        "original": {},
    }
    confirmed = editorial_remaster.confirmar_mapeamento_cenas(draft, [2, 3])

    assert confirmed["mapeamento_cenas_confirmado"] is True
    assert [x["pagina_origem"] for x in confirmed["cenas_texto"]] == [2, 3]
    assert confirmed["cenas_texto"][0]["texto"] == "Mel olhou para a semente."
    assert all(x["origem"] == "book_doctor_pdf" for x in confirmed["cenas_texto"])


def _confirmed_state(tmp_path: Path) -> dict:
    project = _project(tmp_path)
    draft = editorial_remaster.criar_rascunho_remaster_editorial(
        project,
        faixa_etaria="3-8",
        versiculo_referencia="Eclesiastes 3:1",
        licao_final="Há um tempo certo para cada coisa.",
        aprendizado_cristao="aprender a esperar com confiança em Deus",
        emocao_central="impaciência",
    )
    draft["paginas_texto_extraido"] = [
        {"pagina": 4, "texto_extraido": "Mel olhou para o vaso e quis ver a semente crescer logo.", "tem_texto": True},
        {"pagina": 5, "texto_extraido": "Ela esperou, observou e percebeu que algumas coisas precisam de tempo.", "tem_texto": True},
    ]
    return editorial_remaster.confirmar_mapeamento_cenas(draft, [4, 5])


def test_dossier_runs_reviewer_first_without_rewriting_story(tmp_path):
    state = _confirmed_state(tmp_path)
    original_hash = state["original"]["sha256"]
    scenes_before = json.loads(json.dumps(state["cenas_texto"], ensure_ascii=False))
    calls = []

    def fake_llm(*, sistema, instrucao):
        calls.append((sistema, instrucao))
        return {
            "status": "REVISAR",
            "notas": [
                {"cena": 1, "problema": "Mostrar a impaciência mais pela ação e menos pela explicação."}
            ],
        }

    dossier = editorial_remaster.gerar_dossie_revisao(state, fake_llm)

    assert len(calls) == 1
    assert "Revisor/Editor independente" in calls[0][0]
    assert dossier["revisor"]["status"] == "REVISAR"
    assert dossier["precisa_revisao_textual"] is True
    assert dossier["alteracoes_aplicadas"] is False
    assert dossier["aprovacao_humana_pendente"] is True
    assert "story_editor" in dossier["proximos_especialistas"]
    assert "storyteller" in dossier["proximos_especialistas"]
    assert state["cenas_texto"] == scenes_before
    assert book_doctor.sha256(state["original"]["arquivo"]) == original_hash
    assert dossier["prompt_mestre"]["faixa_etaria"] == "3-8"
    assert "Lição de Moral" in dossier["prompt_mestre"]["aprovados"]


def test_dossier_does_not_call_editor_or_storyteller_when_reviewer_approves(tmp_path):
    state = _confirmed_state(tmp_path)
    calls = []

    def fake_llm(*, sistema, instrucao):
        calls.append((sistema, instrucao))
        return {"status": "APROVADO", "notas": []}

    dossier = editorial_remaster.gerar_dossie_revisao(state, fake_llm)

    assert len(calls) == 1
    assert dossier["revisor"]["status"] == "APROVADO"
    assert dossier["precisa_revisao_textual"] is False
    assert "story_editor" not in dossier["proximos_especialistas"]
    assert "storyteller" not in dossier["proximos_especialistas"]
    assert dossier["alteracoes_aplicadas"] is False
