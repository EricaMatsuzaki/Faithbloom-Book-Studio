import pytest

from jarvis_multimodal import (
    MAX_FILE_BYTES,
    MAX_PACKAGE_BYTES,
    build_handoff_package,
    choose_route,
    classify_attachment,
    normalize_attachment,
)


def test_classifies_supported_attachment_types():
    assert classify_attachment("historia.pdf", "application/pdf") == "pdf"
    assert classify_attachment("capa.png", "image/png") == "image"
    assert classify_attachment("roteiro.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document") == "document"
    assert classify_attachment("narracao.m4a", "audio/mp4") == "audio"


def test_default_limits_accept_large_published_book_pdf():
    # Regressão real: o PDF publicado da Mel tem 108,443,373 bytes.
    published_book_bytes = 108_443_373
    assert MAX_FILE_BYTES >= published_book_bytes
    assert MAX_PACKAGE_BYTES >= published_book_bytes


def test_pdf_review_reuses_book_doctor_route():
    attachment = normalize_attachment("historia.pdf", "application/pdf", b"%PDF-fake")
    route = choose_route("Jarvis, revise esta história", [attachment])
    assert route["id"] == "story_review"
    assert "Book_Doctor" in route["page"]
    assert "Revisor" in route["agents"]


def test_full_remaster_still_starts_in_book_doctor_but_carries_autopilot_intent():
    attachment = normalize_attachment("historia.pdf", "application/pdf", b"%PDF-fake")
    package = build_handoff_package(
        "Jarvis, faça uma revisão completa e remasterize este livro pelo fluxo completo",
        [attachment],
    )
    assert package["route"]["id"] == "story_review"
    assert package["workflow_intent"] == "editorial_remaster_full"
    assert "Full Editorial Remaster" in package["spoken"]
    assert package["master_promotion_allowed"] is False
    assert package["requires_confirmation"] is True


def test_standard_pdf_review_does_not_force_full_remaster():
    attachment = normalize_attachment("historia.pdf", "application/pdf", b"%PDF-fake")
    package = build_handoff_package("Jarvis, apenas analise este manuscrito", [attachment])
    assert package["route"]["id"] == "story_review"
    assert package["workflow_intent"] == "standard"


def test_image_improvement_reuses_restoration_studio():
    attachment = normalize_attachment("capa.png", "image/png", b"fake-image")
    route = choose_route("melhore esta capa", [attachment])
    assert route["id"] == "image_restore"
    assert "Restoration_Studio" in route["page"]


def test_character_reference_does_not_promote_master():
    attachment = normalize_attachment("mel.png", "image/png", b"fake-image")
    package = build_handoff_package("use esta imagem como referência da Mel", [attachment])
    assert package["route"]["id"] == "character_reference"
    assert package["master_promotion_allowed"] is False
    assert package["requires_confirmation"] is True
    assert package["requires_target_collection"] is True
    assert package["target_collection"] == ""
    assert "confirme a coleção correta" in package["spoken"]


def test_non_character_handoff_does_not_require_collection():
    attachment = normalize_attachment("capa.png", "image/png", b"fake-image")
    package = build_handoff_package("melhore esta capa", [attachment])
    assert package["route"]["id"] == "image_restore"
    assert package["requires_target_collection"] is False


def test_audio_routes_to_existing_audiobook_studio():
    attachment = normalize_attachment("voz.wav", "audio/wav", b"RIFFfake")
    route = choose_route("use este áudio na narração", [attachment])
    assert route["id"] == "audiobook"
    assert "Audiobook_Studio" in route["page"]


def test_story_creation_without_attachment_routes_to_existing_creation_flow():
    route = choose_route("Crie uma história infantil sobre coragem e fé", [])
    assert route["id"] == "story_create"
    assert "Criar_do_Zero" in route["page"]


def test_empty_attachment_is_rejected():
    with pytest.raises(ValueError, match="está vazio"):
        normalize_attachment("vazio.pdf", "application/pdf", b"")
