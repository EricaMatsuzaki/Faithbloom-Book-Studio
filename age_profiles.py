"""FaithBloom — perfis etários oficiais do Story Book Studio.

A faixa etária é uma decisão editorial por LIVRO. Ela orienta linguagem,
ritmo, densidade de texto, musicalidade, onomatopeias, tensão, perguntas
pedagógicas, profundidade da explicação cristã e tipografia do miolo.

O perfil 3–8 é mantido por compatibilidade com a coleção clássica atual.
Para novos projetos, perfis mais específicos (3–5, 6–8, 9–12) dão
resultados mais precisos.

Os limites de palavras e páginas são HEURÍSTICAS editoriais internas, não
promessas de mercado nem regras universais de desenvolvimento infantil.
"""
from __future__ import annotations

import unicodedata
from copy import deepcopy

DEFAULT_AGE_PROFILE = "3-8"

AGE_PROFILES: dict[str, dict] = {
    "3-5": {
        "label": "3–5 anos — Pré-leitor / leitura acompanhada",
        "short_label": "3–5 anos",
        "publico": "pré-leitor e criança em leitura acompanhada",
        "max_words_sentence": 14,
        "max_words_scene": 75,
        "ritmo": "muito simples, concreto, visual e repetitivo",
        "frases": "frases curtas, preferencialmente 5–12 palavras, uma ideia por frase",
        "texto_por_cena": "1–3 frases curtas na maior parte das cenas",
        "musicalidade": "alta, com repetição suave, pausas e refrões curtos",
        "onomatopeias": "equilibradas a expressivas, sempre ligadas à ação",
        "humor": "visual, simples e imediato",
        "tensao": "muito leve e rapidamente acolhida/resolvida",
        "espiritualidade": "concreta, amorosa e direta; sem conceitos teológicos abstratos",
        "moral": "curta, explícita e fácil de repetir",
        "perguntas_pedagogicas": 2,
        "densidade_visual": "muito alta; a imagem ajuda a carregar a compreensão",
        "paginas_recomendadas": "24–32 páginas para o formato ilustrado padrão",
        "pdf_font_size": 20.0,
        "pdf_leading": 30.0,
    },
    "3-8": {
        "label": "3–8 anos — Faixa ampla da coleção",
        "short_label": "3–8 anos",
        "publico": "faixa infantil ampla da coleção FaithBloom",
        "max_words_sentence": 18,
        "max_words_scene": 105,
        "ritmo": "simples, visual, musical e adequado à leitura em voz alta",
        "frases": "frases curtas e claras, idealmente 5–15 palavras",
        "texto_por_cena": "1–4 frases curtas, conforme o momento narrativo",
        "musicalidade": "moderada a alta, sem obrigar rima",
        "onomatopeias": "equilibradas",
        "humor": "leve, visual e compreensível sem explicação adulta",
        "tensao": "leve, segura e sem sofrimento pesado",
        "espiritualidade": "concreta, amorosa e compreensível para a infância",
        "moral": "clara, explícita e curta",
        "perguntas_pedagogicas": 3,
        "densidade_visual": "alta; texto e imagem trabalham juntos",
        "paginas_recomendadas": "24–40 páginas para o formato ilustrado amplo",
        "pdf_font_size": 18.0,
        "pdf_leading": 28.0,
    },
    "6-8": {
        "label": "6–8 anos — Leitor iniciante",
        "short_label": "6–8 anos",
        "publico": "leitor iniciante, com leitura acompanhada ou progressivamente independente",
        "max_words_sentence": 20,
        "max_words_scene": 120,
        "ritmo": "claro e ágil, com um pouco mais de diálogo e consequência narrativa",
        "frases": "frases curtas a médias, ainda fáceis de ler em voz alta",
        "texto_por_cena": "2–5 frases, preservando espaço visual",
        "musicalidade": "moderada, com repetições e sons em pontos estratégicos",
        "onomatopeias": "equilibradas, usadas sobretudo em ação, humor e surpresa",
        "humor": "leve, podendo incluir pequenas situações de expectativa e quebra de expectativa",
        "tensao": "leve a moderada, sempre adequada e segura",
        "espiritualidade": "clara, com causa/consequência e aplicação concreta da fé",
        "moral": "clara, podendo ter uma frase adicional de reflexão",
        "perguntas_pedagogicas": 3,
        "densidade_visual": "alta a moderada; ilustração continua essencial",
        "paginas_recomendadas": "28–40 páginas para o formato ilustrado",
        "pdf_font_size": 17.0,
        "pdf_leading": 25.0,
    },
    "9-12": {
        "label": "9–12 anos — Leitor independente / história ilustrada",
        "short_label": "9–12 anos",
        "publico": "leitor independente em história ilustrada",
        "max_words_sentence": 30,
        "max_words_scene": 220,
        "ritmo": "mais desenvolvido, com motivações, consequência, diálogo e transformação mais nuançados",
        "frases": "frases claras de comprimento variado, sem linguagem desnecessariamente adulta",
        "texto_por_cena": "parágrafos curtos ou blocos moderados, conforme a proposta ilustrada",
        "musicalidade": "leve a moderada; ritmo natural acima de repetição infantil intensa",
        "onomatopeias": "leves e pontuais, quando combinarem com a voz narrativa",
        "humor": "situacional e de personagem, sem infantilizar o leitor",
        "tensao": "moderada e segura; pode durar mais antes da resolução",
        "espiritualidade": "mais reflexiva, porém sem doutrina complexa, medo ou culpa como recurso",
        "moral": "clara, mas pode ser mais reflexiva e menos repetitiva",
        "perguntas_pedagogicas": 4,
        "densidade_visual": "moderada; a história ainda é ilustrada, mas o texto pode sustentar mais informação",
        "paginas_recomendadas": "32–64 páginas para a história ilustrada, conforme o projeto",
        "pdf_font_size": 15.5,
        "pdf_leading": 22.0,
    },
}


class AgeOption(tuple):
    """Opção compatível com UIs antigas e novas.

    Funciona como `(id, label)` para telas que precisam separar valor e rótulo,
    mas também se comporta como o id textual em fluxos legados que fazem
    `"6-8" in opcoes`, `opcoes.index("6-8")` ou passam a opção diretamente
    para `perfil_etario()`.
    """

    def __new__(cls, profile_id: str, label: str):
        return super().__new__(cls, (profile_id, label))

    @property
    def profile_id(self) -> str:
        return tuple.__getitem__(self, 0)

    @property
    def label(self) -> str:
        return tuple.__getitem__(self, 1)

    def __str__(self) -> str:
        return self.profile_id

    def __eq__(self, other) -> bool:
        if isinstance(other, str):
            return self.profile_id == other
        return tuple.__eq__(self, other)

    def __hash__(self) -> int:
        return hash(self.profile_id)


def _slug(value: str | None) -> str:
    # Troca travessões ANTES de remover caracteres não ASCII, senão "3–5"
    # poderia virar "35". Depois retiramos rótulos humanos comuns.
    texto = str(value or "").replace("–", "-").replace("—", "-")
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    texto = texto.strip().lower().replace(" ", "")
    for sufixo in ("anos", "ano"):
        if texto.endswith(sufixo):
            texto = texto[: -len(sufixo)]
    return texto


def normalizar_faixa_etaria(value: str | None) -> str:
    raw = _slug(value)
    aliases = {
        "3-5": "3-5",
        "3a5": "3-5",
        "3-8": "3-8",
        "3a8": "3-8",
        "6-8": "6-8",
        "6a8": "6-8",
        "9-12": "9-12",
        "9a12": "9-12",
    }
    return aliases.get(raw, DEFAULT_AGE_PROFILE)


def perfil_etario(value: str | None) -> dict:
    key = normalizar_faixa_etaria(value)
    return deepcopy({"id": key, **AGE_PROFILES[key]})


def opcoes_faixa_etaria() -> list[AgeOption]:
    """Retorna opções com id + rótulo sem quebrar consumidores legados."""
    ids = ("3-5", "6-8", "9-12", "3-8")
    return [AgeOption(profile_id, AGE_PROFILES[profile_id]["label"]) for profile_id in ids]


def instrucao_faixa_etaria(value: str | None) -> str:
    p = perfil_etario(value)
    return (
        f"FAIXA ETÁRIA OFICIAL: {p['short_label']} ({p['publico']}). "
        f"Ritmo: {p['ritmo']}. Frases: {p['frases']}. "
        f"Texto por cena: {p['texto_por_cena']}. Musicalidade: {p['musicalidade']}. "
        f"Onomatopeias: {p['onomatopeias']}. Humor: {p['humor']}. "
        f"Tensão: {p['tensao']}. Espiritualidade: {p['espiritualidade']}. "
        f"Moral: {p['moral']}. Densidade visual: {p['densidade_visual']}."
    )
