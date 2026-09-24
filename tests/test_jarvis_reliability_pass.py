from pathlib import Path

from editorial_remaster import extrair_texto_manuscrito
from jarvis_handoff_inbox import enqueue_handoff
from jarvis_multimodal import build_handoff_package, choose_route, should_prepare_handoff


def test_text_only_full_review_routes_to_book_doctor():
    text = "Quero fazer a Revisão Completa deste texto-base. PÁGINA 5 — TEXTO\nEra uma vez."
    route = choose_route(text, [])
    assert route["id"] == "story_review"
    assert "Book_Doctor" in route["page"]
    assert should_prepare_handoff(text) is True


def test_text_only_full_review_carries_autopilot_intent_and_text_payload():
    text = "Faça a revisão completa. PÁGINA 5 — TEXTO\nMel esperou."
    package = build_handoff_package(text, [])
    assert package["route"]["id"] == "story_review"
    assert package["workflow_intent"] == "editorial_remaster_full"
    assert package["input_mode"] == "text"
    assert package["text_payload"] == text
    assert package["fingerprint"]


def test_normal_conversation_does_not_force_editorial_handoff():
    text = "Oi Jarvis, como você está?"
    assert should_prepare_handoff(text) is False
    assert choose_route(text, [])["id"] == "orchestrator"


def test_creation_text_is_actionable_without_attachment():
    text = "Crie uma história infantil sobre coragem e fé"
    assert should_prepare_handoff(text) is True
    assert choose_route(text, [])["id"] == "story_create"


def test_handoff_fingerprint_prevents_duplicate_active_entries():
    state = {}
    p1 = build_handoff_package("Faça a revisão completa deste texto-base.", [])
    p2 = build_handoff_package("Faça a revisão completa deste texto-base.", [])
    assert p1["id"] != p2["id"]
    assert p1["fingerprint"] == p2["fingerprint"]
    first = enqueue_handoff(state, p1)
    second = enqueue_handoff(state, p2)
    assert second["id"] == first["id"]
    assert len(state["jarvis_handoff_inbox"]) == 1


def test_text_manuscript_keeps_text_pages_and_excludes_illustration_blocks(tmp_path: Path):
    source = tmp_path / "story.txt"
    source.write_text(
        "INSTRUÇÕES AO JARVIS\nPreserve a história.\n\n"
        "PÁGINA 5 — TEXTO\nMel olhou para a semente.\n\n"
        "PÁGINA 6 — ILUSTRAÇÃO\nMel no jardim.\n\n"
        "PÁGINA 7 — TEXTO\nMel decidiu esperar.",
        encoding="utf-8",
    )
    pages = extrair_texto_manuscrito(str(source))
    by_page = {p["pagina"]: p for p in pages}
    assert by_page[5]["texto_extraido"] == "Mel olhou para a semente."
    assert by_page[6]["texto_extraido"] == ""
    assert by_page[7]["texto_extraido"] == "Mel decidiu esperar."
    assert all("INSTRUÇÕES AO JARVIS" not in p["texto_extraido"] for p in pages)
