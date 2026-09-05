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
        "output_format": "png",
    }


def test_image_generation_sends_one_base_image_as_input_image(image_call):
    calls, _, _, tmp_path = image_call
    reference = tmp_path / "mel.png"
    reference.write_bytes(b"one-reference")

    client.gerar_imagem("Editar Mel", imagem_base=str(reference))

    inputs = [ref["image_url"]["url"] for ref in calls[0]["payload"]["input_references"]]
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

    inputs = [ref["image_url"]["url"] for ref in calls[0]["payload"]["input_references"]]
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


def test_resolution_and_reference_contract(image_call):
    calls, _, _, tmp = image_call
    ref = tmp / "mel.png"
    ref.write_bytes(b"reference")
    client.gerar_imagem("Mel sem cachecol, fundo neutro", str(ref), resolution="4K")
    payload = calls[0]["payload"]
    assert payload["resolution"] == "4K"
    assert payload["input_references"][0]["type"] == "image_url"
    assert "image" not in payload and "response_format" not in payload


def test_missing_reference_blocks_generation(image_call):
    calls, completed, _, tmp = image_call
    with pytest.raises(client.OpenRouterFaithBloomError, match="referência"):
        client.gerar_imagem("Editar", str(tmp / "missing.png"))
    assert not calls and not completed


@pytest.mark.parametrize("status", [400, 401, 402, 403, 404, 422])
def test_client_errors_not_retried_and_do_not_expose_response(monkeypatch, status):
    from unittest.mock import Mock
    import requests
    response = requests.Response()
    response.status_code = status
    response._content = b"private-provider-response"
    post = Mock(return_value=response)
    monkeypatch.setattr(client.requests, "post", post)
    monkeypatch.setattr(client, "_headers", lambda: {})
    with pytest.raises(client.OpenRouterFaithBloomError) as error:
        client._post_com_retry("https://example.com", {}, 10)
    assert post.call_count == 1
    assert f"HTTP {status}" in str(error.value)
    assert "private-provider-response" not in str(error.value)


def test_neutral_master_prompt_preserves_identity_and_removes_seasonal_clothes():
    from scene_color_controls import build_restoration_prompt
    prompt = build_restoration_prompt("neutral_master", dna={"campos_bloqueados": {"olhos": "verdes"}})
    assert "cachecol" in prompt and "fundo neutro" in prompt
    assert "laço permanente" in prompt and "verdes" in prompt
    assert "NO_GENERATED_TEXT" in prompt
