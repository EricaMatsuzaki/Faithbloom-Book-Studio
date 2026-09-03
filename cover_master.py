"""FaithBloom Cover Master — capa de Coloring/Activity Book com versionamento.

A IA pode criar a ARTE, mas nunca calcula o wrap final. A geometria física,
bleed, safe areas, lombada e barcode continuam a cargo de capa_profissional.py.
"""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

from capa_profissional import gerar_capa_print_ready
from character_universe import carregar_personagem_oficial, personagem_para_prompt
from style_dna import carregar_style, style_para_prompt


def _agora() -> int: return int(time.time())

def _plan_path(projeto: dict) -> Path:
    p = Path(projeto["pasta"]) / "cover_master"
    p.mkdir(parents=True, exist_ok=True)
    return p / "cover_master_plan.json"

def _save(projeto: dict, plan: dict) -> dict:
    plan["atualizado_em"] = _agora()
    _plan_path(projeto).write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    return plan

def carregar_cover_master(projeto: dict) -> dict:
    p = _plan_path(projeto)
    if not p.exists(): return {}
    try:
        d = json.loads(p.read_text(encoding="utf-8")); return d if isinstance(d, dict) else {}
    except Exception: return {}


def criar_cover_master(projeto: dict, metadata: dict | None = None) -> dict:
    plan = carregar_cover_master(projeto)
    if not plan:
        plan = {
            "id": uuid.uuid4().hex[:12], "projeto_id": projeto.get("id", ""),
            "criado_em": _agora(), "variacoes": [], "edicoes_localizadas": {},
            "arte_master_sem_texto": True, "politica": "original_e_variacoes_preservados",
        }
    plan.setdefault("metadata", {}).update(metadata or {})
    return _save(projeto, plan)


def referencias_cover(character_ids: list[str], preferir_line_art: bool = True) -> list[str]:
    refs = []
    for cid in character_ids or []:
        ch = carregar_personagem_oficial(cid)
        if not ch: continue
        ordem = [ch.get("line_art_master"), ch.get("color_master")] if preferir_line_art else [ch.get("color_master"), ch.get("line_art_master")]
        asset = next((x for x in ordem if x and Path(x).exists()), "")
        if asset and asset not in refs: refs.append(asset)
    return refs


def montar_prompt_cover_master(
    titulo: str,
    character_ids: list[str] | None = None,
    style_id: str = "",
    tema: str = "",
    instrucao_autora: str = "",
    modo: str = "colorido_fiel_line_art",
) -> str:
    partes = [
        "ARTE MASTER DE CAPA para livro de colorir. Gerar SOMENTE a ilustração de fundo/frente, SEM título, SEM letras, SEM nome da autora e SEM texto gerado por IA.",
        "Composição original, adequada a impressão, com área visual de respiro para tipografia ser aplicada depois pelo motor editorial.",
    ]
    if modo == "colorido_fiel_line_art":
        partes.append("Criar versão colorida premium mantendo fielmente identidade, proporções e traços essenciais dos personagens/line arts oficiais usados como referência.")
    elif modo == "line_art":
        partes.append("Manter linguagem de line art preto/branco como identidade principal da capa, com composição editorial forte e limpa.")
    elif modo == "preview_lapis":
        partes.append("Usar aparência de preview colorido por lápis de cor, mas preservar o desenho-base e a identidade dos personagens.")
    if tema.strip(): partes.append("Tema/cenário: " + tema.strip())
    for cid in character_ids or []:
        ch = carregar_personagem_oficial(cid)
        if ch:
            partes.append(personagem_para_prompt(ch, modo="color", contexto="cover"))
    if style_id:
        st = carregar_style(style_id)
        if st: partes.append(style_para_prompt(st, contexto="cover"))
    if instrucao_autora.strip(): partes.append("Instrução específica da autora: " + instrucao_autora.strip())
    partes.append("Não inventar personagens adicionais. Não alterar Character DNA. Roupa, pose, expressão, cenário, estação e festividade podem variar somente conforme solicitado.")
    return "\n".join(p for p in partes if p)


def registrar_variacao_cover(projeto: dict, papel: str, asset: str, origem: str, metadata: dict | None = None, aprovada: bool = False) -> dict:
    if papel not in {"frente", "verso"}: raise ValueError("papel deve ser frente ou verso")
    plan = carregar_cover_master(projeto) or criar_cover_master(projeto)
    rec = {
        "id": uuid.uuid4().hex[:12], "papel": papel, "asset": asset, "origem": origem,
        "metadata": metadata or {}, "criada_em": _agora(), "aprovada": bool(aprovada),
    }
    plan.setdefault("variacoes", []).append(rec)
    _save(projeto, plan); return rec


def aprovar_variacao_cover(projeto: dict, variacao_id: str) -> dict:
    plan = carregar_cover_master(projeto)
    alvo = next((x for x in plan.get("variacoes", []) if x.get("id") == variacao_id), None)
    if not alvo: raise KeyError(variacao_id)
    # Uma capa aprovada por papel vira a seleção ativa, mas versões anteriores continuam no histórico.
    for x in plan.get("variacoes", []):
        if x.get("papel") == alvo.get("papel"):
            x["selecionada"] = x.get("id") == variacao_id
    alvo["aprovada"] = True; alvo["aprovada_em"] = _agora()
    return _save(projeto, plan)


def variacao_selecionada(plan: dict, papel: str) -> dict:
    itens = [x for x in plan.get("variacoes", []) if x.get("papel") == papel]
    return next((x for x in itens if x.get("selecionada") and x.get("aprovada")), {})


def registrar_edicao_localizada(projeto: dict, locale: str, titulo: str, subtitulo: str = "", sinopse: str = "") -> dict:
    plan = carregar_cover_master(projeto) or criar_cover_master(projeto)
    plan.setdefault("edicoes_localizadas", {})[locale] = {
        "titulo": titulo, "subtitulo": subtitulo, "sinopse": sinopse, "salvo_em": _agora(),
        "regra": "A arte master permanece a mesma; somente tipografia/textos localizados mudam.",
    }
    return _save(projeto, plan)


def montar_wrap_aprovado(
    projeto: dict,
    pasta_saida: str,
    trim_w: float,
    trim_h: float,
    paginas: int,
    papel: str,
    titulo: str,
    subtitulo: str,
    autora: str,
    colecao: str,
    sinopse: str,
) -> dict:
    plan = carregar_cover_master(projeto)
    front = variacao_selecionada(plan, "frente")
    back = variacao_selecionada(plan, "verso")
    if not front or not back:
        raise ValueError("Aprove e selecione uma variação de frente e uma de contracapa antes de montar o wrap.")
    result = gerar_capa_print_ready(
        front["asset"], back["asset"], pasta_saida,
        trim_w=trim_w, trim_h=trim_h, paginas=paginas, papel=papel,
        titulo=titulo, subtitulo=subtitulo, autora=autora, colecao=colecao,
        sinopse=sinopse, spine_text=titulo,
    )
    plan["ultimo_wrap"] = {**result, "gerado_em": _agora(), "frente_id": front["id"], "verso_id": back["id"]}
    _save(projeto, plan)
    return result


def preflight_cover_master(projeto: dict) -> dict:
    plan = carregar_cover_master(projeto)
    front = variacao_selecionada(plan, "frente")
    back = variacao_selecionada(plan, "verso")
    wrap = plan.get("ultimo_wrap", {})
    checks = {
        "frente_aprovada": bool(front),
        "contracapa_aprovada": bool(back),
        "arte_master_sem_texto": bool(plan.get("arte_master_sem_texto", True)),
        "wrap_gerado": bool(wrap.get("caminho_pdf")),
        "pdf_preflight_ok": bool((wrap.get("pdf_preflight") or {}).get("ok")),
    }
    return {"checks": checks, "aprovado": all(checks.values()), "nota": "Aprovação automática significa apenas checks técnicos deste módulo; ainda requer revisão visual e prova final."}
