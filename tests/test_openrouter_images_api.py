import base64

import pytest

import openrouter_client as client


class _Response:
    def __init__(self, body):
        self.body = body

    def json(self):
        return self.body


@pytest.fixture
def image_call(monkeypatch, tmp_path):
    calls = []
    completed = []
    png = b"\x89PNG\r\n\x1a\nfaithbloom"

    monkeypatch.setattr(client, "PASTA_IMAGENS", str(tmp_path / "saida_imagens"))
    (tmp_path / "saida_imagens").mkdir()
    monkeypatch.setattr(client, "iniciar_requisicao", lambda *args: ("request", "signature", 0.1, 1.0))
    monkeypatch.setattr(client, "finalizar_requisicao", lambda *args, **kwargs: completed.append((args, kwargs)))

    def post(url, payload, timeout):
        calls.append({"url": url, "payload": payload, "timeout": timeout})
        return _Response({"data": [{"b64_json": base64.b64encode(png).decode()}]})

    monkeypatch.setattr(client, "_post_com_retry", post)
    return calls, completed, png, tmp_path


def test_image_generation_prompt_only_uses_current_images_api(image_call):
    calls, _, _, _ = image_call

    client.gerar_imagem("Mel em um jardim")

    assert calls[0]["url"] == f"{client.OPENROUTER_BASE_URL}/images"
    assert calls[0]["payload"] == {
        "model": client.MODELO_IMAGEM,
        "prompt": "Mel em um jardim",
        "response_format": "b64_json",
    }


def test_image_generation_sends_one_base_image_as_input_image(image_call):
    calls, _, _, tmp_path = image_call
    reference = tmp_path / "mel.png"
    reference.write_bytes(b"one-reference")

    client.gerar_imagem("Editar Mel", imagem_base=str(reference))

    inputs = calls[0]["payload"]["image"]
    assert len(inputs) == 1
    assert inputs[0].startswith("data:image/png;base64,")


def test_image_generation_sends_multiple_unique_references(image_call):
    calls, _, _, tmp_path = image_call
    base = tmp_path / "base.png"
    second = tmp_path / "second.jpg"
    base.write_bytes(b"base")
    second.write_bytes(b"second")

    client.gerar_imagem(
        "Editar cena",
        imagem_base=str(base),
        imagens_referencia=[str(base), str(second)],
    )

    inputs = calls[0]["payload"]["image"]
    assert len(inputs) == 2
    assert inputs[0].startswith("data:image/png;base64,")
    assert inputs[1].startswith("data:image/jpeg;base64,")


def test_valid_b64_json_is_saved_in_image_output_directory(image_call):
    _, completed, png, _ = image_call

    result = client.gerar_imagem("Criar ilustração")

    with open(result, "rb") as generated:
        assert generated.read() == png
    assert completed[-1][0][6] == "sucesso"


def test_response_without_image_has_friendly_error_and_safe_log(monkeypatch, image_call):
    _, completed, _, _ = image_call
    monkeypatch.setattr(client, "_post_com_retry", lambda *_args, **_kwargs: _Response({"data": []}))

    with pytest.raises(client.OpenRouterFaithBloomError, match="não retornou uma imagem"):
        client.gerar_imagem("Criar ilustração")

    assert completed[-1][0][6] == "erro"
    assert "OPENROUTER_API_KEY" not in completed[-1][1]["detalhe"]
    assert "base64" not in completed[-1][1]["detalhe"]
