from pathlib import Path

from age_profiles import opcoes_faixa_etaria


def test_translation_studio_usa_perfis_etarios_canonicos():
    source = Path("pages/21_Translation_Localization_Studio.py").read_text(encoding="utf-8")
    assert "from age_profiles import normalizar_faixa_etaria, opcoes_faixa_etaria" in source
    assert "age_options=opcoes_faixa_etaria()" in source
    assert 'master_age=normalizar_faixa_etaria(master.get("faixa_etaria"))' in source
    assert 'opt.profile_id==master_age' in source
    assert 'idade=idade_opt.profile_id' in source
    assert "9–10" not in source
    assert "Personalizado" not in source


def test_perfis_oficiais_incluem_9_12_e_nao_9_10():
    ids = [opt.profile_id for opt in opcoes_faixa_etaria()]
    assert set(ids) == {"3-5", "3-8", "6-8", "9-12"}
    assert "9-10" not in ids
