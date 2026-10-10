"""Shared valid provider output for editorial contract regression tests."""
import pytest


@pytest.fixture
def complete_editorial_extras():
    def make(count=3, reference="Efésios 4:32"):
        return {
            "boas_vindas": "Olá, amiguinho!",
            "pais_educadores": {
                "mensagem": "Conversem sobre a história.", "tema": "Bondade",
                "emocao_trabalhada": "alegria", "principio_biblico": "bondade",
                "habilidade_socioemocional": "empatia",
                "perguntas": [f"Pergunta {i + 1}?" for i in range(count)],
                "aplicacoes": ["Praticar a bondade em casa."],
            },
            "ficha_pedagogica": {
                "faixa_etaria": "3–8 anos", "tema_central": "Bondade",
                "emocao_principal": "alegria", "habilidade_socioemocional": "empatia",
                "valor_cristao": "bondade", "versiculo_referencia": reference,
                "objetivo_pedagogico": "Conversar sobre a escolha da personagem.",
                "psicologia_das_cores": "A luz quente acompanha o acolhimento da cena.",
                "perguntas_reflexao": [f"Pergunta {i + 1}?" for i in range(count)],
            },
        }
    return make
