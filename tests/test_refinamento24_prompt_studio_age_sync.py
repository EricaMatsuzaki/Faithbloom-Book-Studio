from pathlib import Path


def test_prompt_mestre_studio_deriva_idade_do_projeto():
    source = Path("pages/38_🪄_Prompt_Mestre_Studio.py").read_text(encoding="utf-8")
    assert "normalizar_faixa_etaria" in source
    assert 'ficha["faixa_etaria"] = perfil["short_label"]' in source
    assert '"Faixa etária"' in source
    assert "disabled=True" in source
    assert "não deve divergir da ficha pedagógica" in source
