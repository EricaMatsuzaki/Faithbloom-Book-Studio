"""FaithBloom 2.0 — Fase 12: validação visual piloto antes da produção em massa.

Cria um quality gate visual: personagens aprovados -> 1 cena piloto -> 3 cenas
representativas -> liberação do lote completo. Não dispara geração em massa sozinho.
"""
from __future__ import annotations
from copy import deepcopy
from pathlib import Path
from typing import Iterable
from PIL import Image, ImageOps, ImageDraw


def personagens_aprovados(state: dict) -> tuple[bool, list[str]]:
    pendentes=[]
    for nome,p in (state.get("personagens") or {}).items():
        if not (p.get("aparencia_aprovada") and p.get("imagem_referencia")):
            pendentes.append(nome)
    return (bool(state.get("personagens")) and not pendentes), pendentes


def cenas_recomendadas_piloto(state: dict) -> list[int]:
    """Escolhe início/meio/final, priorizando cenas com personagens explicitamente citados."""
    cenas=state.get("cenas_texto") or []
    if not cenas: return []
    nums=[int(c["numero"]) for c in cenas]
    alvos=[nums[0], nums[len(nums)//2], nums[-1]]
    # Para o Natal, cena 8 é particularmente útil: Mel + Manu + Max juntos.
    if {"Mel","Manu","Max"}.issubset(set((state.get("personagens") or {}).keys())) and 8 in nums:
        alvos[0]=8
    return list(dict.fromkeys(alvos))


def detectar_personagens_cena(state: dict, cena: dict) -> list[str]:
    texto=(cena.get("texto","")+" "+cena.get("contexto_visual","")).lower()
    nomes=[]
    for nome in (state.get("personagens") or {}):
        if nome.lower() in texto:
            nomes.append(nome)
    principal=cena.get("personagem_principal")
    if principal and principal in (state.get("personagens") or {}) and principal not in nomes:
        nomes.insert(0,principal)
    if not nomes:
        protagonista=next((n for n,p in (state.get("personagens") or {}).items() if p.get("papel")=="protagonista"),None)
        if protagonista: nomes=[protagonista]
    return nomes


def montar_folha_referencias(state: dict, nomes: Iterable[str], destino: str) -> str | None:
    """Combina várias referências aprovadas em uma única folha para modelos que aceitam 1 imagem-base."""
    itens=[]
    for nome in nomes:
        p=(state.get("personagens") or {}).get(nome,{})
        arq=p.get("imagem_referencia")
        if arq and Path(arq).exists(): itens.append((nome,arq))
    if not itens: return None
    cell=768; label=70
    canvas=Image.new("RGB",(cell*len(itens),cell+label),"white")
    draw=ImageDraw.Draw(canvas)
    for i,(nome,arq) in enumerate(itens):
        with Image.open(arq) as im:
            im=im.convert("RGB")
            fitted=ImageOps.contain(im,(cell-32,cell-32))
            x=i*cell+(cell-fitted.width)//2; y=16+(cell-fitted.height)//2
            canvas.paste(fitted,(x,y))
        draw.text((i*cell+20,cell+20),nome,fill="black")
    Path(destino).parent.mkdir(parents=True,exist_ok=True)
    canvas.save(destino,quality=95)
    return destino


def prompt_piloto(state: dict, numero: int, instrucao: str="") -> tuple[str,list[str]]:
    cena=next(c for c in state.get("cenas_texto",[]) if int(c.get("numero"))==int(numero))
    nomes=detectar_personagens_cena(state,cena)
    dnas=[]
    for nome in nomes:
        p=state["personagens"][nome]
        dnas.append(f"{nome}: {p.get('descricao_fixa','')}")
    prompt=(
        "FAITHBLOOM — TESTE VISUAL PILOTO. Não inserir texto na imagem.\n"
        "Preserve com alta fidelidade a identidade de TODOS os personagens da folha de referência. "
        "Não fundir características entre personagens; manter espécie, rosto, olhos, cores, proporções e acessórios fixos.\n"
        + "\n".join(dnas) + "\n"
        f"Cena {numero}: {cena.get('texto','')}\n"
        f"Contexto visual: {cena.get('contexto_visual','')}\n"
        f"Figurino: {cena.get('figurino','')}\n"
        "Objetivo do piloto: consistência de personagem, legibilidade visual, emoção clara e composição adequada a livro infantil."
    )
    if instrucao.strip(): prompt += "\nPedido específico da autora: "+instrucao.strip()+"\nAltere somente o solicitado."
    return prompt,nomes


def checklist_avaliacao() -> dict:
    return {
        "identidade_personagens": False,
        "cores_marcas_acessorios": False,
        "proporcoes": False,
        "figurino": False,
        "emocao": False,
        "cenario": False,
        "sem_texto_embutido": False,
        "qualidade_visual": False,
    }


def piloto_aprovado(avaliacao: dict) -> bool:
    return bool(avaliacao) and all(bool(v) for v in avaliacao.values())


def readiness_producao(state: dict) -> dict:
    ok_p,pendentes=personagens_aprovados(state)
    piloto=state.get("piloto_visual",{})
    lote=piloto.get("lote_validacao",{})
    cenas_lote=cenas_recomendadas_piloto(state)
    lote_ok=bool(cenas_lote) and all(bool(lote.get(str(n),{}).get("aprovado")) for n in cenas_lote)
    return {
        "personagens_ok":ok_p,
        "personagens_pendentes":pendentes,
        "cena_piloto_ok":bool(piloto.get("cena_piloto_aprovada")),
        "lote_piloto_ok":lote_ok,
        "cenas_lote":cenas_lote,
        "liberado_producao_completa":ok_p and bool(piloto.get("cena_piloto_aprovada")) and lote_ok,
    }
