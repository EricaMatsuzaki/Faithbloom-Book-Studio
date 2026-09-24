from age_profiles import opcoes_faixa_etaria, perfil_etario


def test_age_options_expose_ids_and_human_labels():
    opcoes = opcoes_faixa_etaria()

    assert [x[0] for x in opcoes] == ["3-5", "6-8", "9-12", "3-8"]
    assert [x[1] for x in opcoes] == [
        "3–5 anos — Pré-leitor / leitura acompanhada",
        "6–8 anos — Leitor iniciante",
        "9–12 anos — Leitor independente / história ilustrada",
        "3–8 anos — Faixa ampla da coleção",
    ]
    assert all(label != "-" for _, label in opcoes)


def test_age_options_remain_compatible_with_legacy_string_flows():
    opcoes = opcoes_faixa_etaria()

    assert "6-8" in opcoes
    assert opcoes.index("6-8") == 1
    assert str(opcoes[1]) == "6-8"
    assert perfil_etario(opcoes[1])["id"] == "6-8"
    assert perfil_etario(opcoes[1])["short_label"] == "6–8 anos"
