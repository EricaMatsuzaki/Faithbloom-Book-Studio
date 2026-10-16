"""Refinamento 25 — Formato narrativo visual Quadrinhos / HQ infantil.

Quadrinhos não é tratado como um quinto estilo literário. É um FORMATO narrativo
visual que pode ser combinado com qualquer versão de história já escolhida.
O adaptador herda a skill `storyteller` e transforma a narrativa em roteiro
sequencial de páginas e painéis, sem gerar ilustrações nesta etapa.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from agent_skills import skill_contract
from age_profiles import normalizar_faixa_etaria, perfil_etario, instrucao_faixa_etaria
from generation_autosave import persist_generation_snapshot

FORMATO_QUADRINHOS_ID = "quadrinhos_hq_infantil"
FORMATO_QUADRINHOS_LABEL = "🗯️ Quadrinhos / HQ infantil"


def _limites_paineis(faixa: str) -> tuple[int, int]:
    faixa = normalizar_faixa_etaria(faixa)
    if faixa == "3-5":
        return 1, 3
    if faixa == "9-12":
        return 3, 6
    return 2, 4


def _resumo_personagens(state: dict) -> str:
    partes: list[str] = []
    for nome, dados in (state.get("personagens") or {}).items():
        if isinstance(dados, dict):
            papel = str(dados.get("papel") or "").strip()
            descricao = str(dados.get("descricao_fixa") or "").strip()
            cab = f"{nome} ({papel})" if papel else str(nome)
            partes.append(f"{cab}: {descricao}".strip())
        else:
            partes.append(str(nome))
    brief = str(state.get("personagens_historia_brief") or "").strip()
    if brief:
        partes.append("Briefing narrativo da autora: " + brief)
    return "\n".join(partes) or "Preserve os personagens já definidos na história, sem substituí-los."


def _historia_fonte(state: dict) -> str:
    cenas = state.get("cenas_texto") or []
    if isinstance(cenas, list) and cenas:
        blocos: list[str] = []
        for idx, cena in enumerate(cenas, start=1):
            if isinstance(cena, dict):
                texto = str(cena.get("texto") or "").strip()
                numero = cena.get("numero") or idx
                if texto:
                    blocos.append(f"Cena {numero}: {texto}")
            elif str(cena).strip():
                blocos.append(f"Cena {idx}: {str(cena).strip()}")
        if blocos:
            return "\n".join(blocos)
    return str(state.get("_entrada_tema_livre") or state.get("titulo") or "").strip()


def _normalizar_dialogos(valor: Any) -> list[dict]:
    if not isinstance(valor, list):
        return []
    saida: list[dict] = []
    for item in valor:
        if isinstance(item, dict):
            personagem = str(item.get("personagem") or item.get("quem") or "").strip()
            fala = str(item.get("fala") or item.get("texto") or "").strip()
            if fala:
                saida.append({"personagem": personagem, "fala": fala})
        elif str(item).strip():
            saida.append({"personagem": "", "fala": str(item).strip()})
    return saida


def _normalizar_resultado(resposta: Any, state: dict) -> dict:
    if not isinstance(resposta, dict):
        resposta = {"observacoes_diagramacao": str(resposta or "")}

    paginas_brutas = resposta.get("paginas") or resposta.get("pages") or []
    if not isinstance(paginas_brutas, list):
        paginas_brutas = []

    paginas: list[dict] = []
    for pidx, pagina in enumerate(paginas_brutas, start=1):
        if not isinstance(pagina, dict):
            continue
        paineis_brutos = pagina.get("paineis") or pagina.get("panels") or []
        if not isinstance(paineis_brutos, list):
            paineis_brutos = []
        paineis: list[dict] = []
        for qidx, painel in enumerate(paineis_brutos, start=1):
            if not isinstance(painel, dict):
                painel = {"acao_visual": str(painel or "")}
            paineis.append(
                {
                    "numero": int(painel.get("numero") or qidx),
                    "acao_visual": str(painel.get("acao_visual") or painel.get("acao") or painel.get("visual") or "").strip(),
                    "dialogos": _normalizar_dialogos(painel.get("dialogos") or painel.get("falas") or []),
                    "narracao": str(painel.get("narracao") or painel.get("legenda") or "").strip(),
                    "sfx": str(painel.get("sfx") or painel.get("onomatopeia") or "").strip(),
                    "emocao": str(painel.get("emocao") or "").strip(),
                    "personagem_foco": str(painel.get("personagem_foco") or painel.get("personagem") or "").strip(),
                }
            )
        paginas.append(
            {
                "numero": int(pagina.get("numero") or pidx),
                "layout_sugerido": str(pagina.get("layout_sugerido") or pagina.get("layout") or "").strip(),
                "gancho_virada": str(pagina.get("gancho_virada") or pagina.get("page_turn_hook") or "").strip(),
                "paineis": paineis,
            }
        )

    return {
        "formato": FORMATO_QUADRINHOS_ID,
        "label": FORMATO_QUADRINHOS_LABEL,
        "titulo": str(resposta.get("titulo") or state.get("titulo") or "").strip(),
        "faixa_etaria": normalizar_faixa_etaria(state.get("faixa_etaria")),
        "estilo_narrativo_origem": str(state.get("versao_narrativa_ativa") or state.get("estilo_narrativo") or "").strip(),
        "paginas": paginas,
        "licao_final": str(resposta.get("licao_final") or state.get("licao_final") or state.get("aprendizado_cristao") or "").strip(),
        "observacoes_diagramacao": str(resposta.get("observacoes_diagramacao") or "").strip(),
    }


def gerar_roteiro_quadrinhos(state: dict, chamar_llm) -> dict:
    """Adapta a história ativa para HQ infantil sem alterar a versão literária original."""
    faixa = normalizar_faixa_etaria(state.get("faixa_etaria"))
    perfil = perfil_etario(faixa)
    min_paineis, max_paineis = _limites_paineis(faixa)
    historia = _historia_fonte(state)
    if not historia:
        raise ValueError("É necessário ter uma ideia ou história antes de criar o roteiro de quadrinhos.")

    sistema = f"""
Você é o Comic Story Adapter do FaithBloom Book Studio.
Você HERDA integralmente a skill formal `storyteller` do Roteirista e acrescenta
especialização em narrativa sequencial infantil, páginas, painéis, diálogo, timing
cômico, leitura visual e ganchos de virada de página.

Quadrinhos/HQ é FORMATO narrativo visual, não substitui o estilo literário escolhido.
Preserve a história, personagens, relações, faixa etária, transformação emocional,
lição cristã e referência bíblica. Não reescreva a obra como imitação de nenhuma
série, autora, roteirista, personagem ou universo existente.

FAIXA ETÁRIA OBRIGATÓRIA:
{instrucao_faixa_etaria(faixa)}

REGRAS DO FORMATO:
- transforme a narrativa em sequência clara de páginas e painéis;
- cada painel deve ter um beat visual principal fácil de ilustrar;
- use normalmente {min_paineis} a {max_paineis} painéis por página para {perfil['short_label']}, variando quando a clareza pedir;
- diálogos devem ser curtos, naturais e adequados à idade;
- use caixas de narração somente quando a imagem e o diálogo não bastarem;
- onomatopeias/SFX podem reforçar humor, ação e ritmo, sem excesso;
- crie ganchos de virada de página quando houver oportunidade real;
- humor deve nascer de situação, expressão, timing e personalidade, nunca de humilhação;
- preserve Character DNA e continuidade de figurino/contexto;
- a fé aparece naturalmente nas escolhas, relações, oração, gratidão, reconciliação ou descoberta, sem sermão longo;
- preserve somente a referência bíblica fornecida; não invente nem traduza livremente o texto do versículo;
- BALÕES, LEGENDAS e SFX devem existir como CAMPOS DE TEXTO para diagramação posterior; nunca peça ao gerador de imagens para desenhar texto legível dentro da ilustração;
- não copie bordões, piadas recorrentes, enquadramentos distintivos, design de página, personagens, traço ou identidade visual de quadrinhos existentes;
- mantenha originalidade editorial e visual do FaithBloom.

RETORNO JSON OBRIGATÓRIO:
{{
  "titulo": "...",
  "paginas": [
    {{
      "numero": 1,
      "layout_sugerido": "descrição simples da composição da página",
      "gancho_virada": "gancho opcional",
      "paineis": [
        {{
          "numero": 1,
          "acao_visual": "ação concreta e composição do painel",
          "dialogos": [{{"personagem": "Nome", "fala": "fala curta"}}],
          "narracao": "legenda opcional",
          "sfx": "onomatopeia opcional",
          "emocao": "emoção principal",
          "personagem_foco": "Nome"
        }}
      ]
    }}
  ],
  "licao_final": "moral curta e natural",
  "observacoes_diagramacao": "orientações de ritmo, balões e leitura"
}}
""".strip() + "\n\n" + skill_contract("storyteller")

    instrucao = f"""
HISTÓRIA FONTE — preserve os acontecimentos essenciais:
{historia}

Título atual: {state.get('titulo','')}
Estilo narrativo ativo: {state.get('estilo_narrativo_label') or state.get('estilo_narrativo') or ''}
Emoção central: {state.get('emocao_central','')}
Lição cristã: {state.get('aprendizado_cristao') or state.get('licao_final') or ''}
Referência bíblica: {state.get('versiculo_referencia','')}
Faixa etária: {perfil['short_label']}

PERSONAGENS:
{_resumo_personagens(state)}

Adapte para um roteiro completo de HQ infantil. Não gere imagens.
""".strip()

    resposta = chamar_llm(sistema=sistema, instrucao=instrucao)
    roteiro = _normalizar_resultado(resposta, state)
    try:
        formatos = deepcopy(state.get("formatos_narrativos_salvos") or {})
        formatos[FORMATO_QUADRINHOS_ID] = deepcopy(roteiro)
        persist_generation_snapshot(
            state,
            reason="formato_quadrinhos_hq",
            updates={"formatos_narrativos_salvos": formatos},
        )
    except Exception as exc:
        state["autosave_status"] = "error"
        state["autosave_error"] = str(exc)
    return roteiro


SKILL_PROFILE_IDS = ("storyteller",)