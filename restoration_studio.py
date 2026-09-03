"""FaithBloom Restoration Studio — Refinamento 04.

Conecta o Book Doctor ao Character Universe, Style DNA e aos motores de
qualidade. Trabalha sempre em versões derivadas: nenhuma função deste módulo
sobrescreve o original importado.

O módulo oferece três camadas distintas:
1. correções técnicas determinísticas (upscale, nitidez/contraste, limpeza de line art);
2. plano de restauração editorial por asset/página;
3. geração assistida por IA opcional, sempre baseada no asset original + Character/Style DNA.
"""
from __future__ import annotations

import json
import time
import uuid
from copy import deepcopy
from pathlib import Path
from typing import Callable

from PIL import Image, ImageEnhance, ImageFilter, ImageOps

from book_doctor import sha256
from character_universe import carregar_personagem_oficial, personagem_para_prompt
from style_dna import carregar_style, style_para_prompt
from emotional_color_director import direcao_emocional, prompt_direcao_visual

ACOES = [
    "manter_original",
    "melhorar_tecnicamente",
    "limpar_line_art",
    "corrigir_personagem",
    "reilustrar",
    "criar_variacao",
]

TIPOS_PROJETO = ["story", "coloring", "activity", "other"]
STATUS_PUBLICACAO = ["publicado", "nao_publicado", "em_desenvolvimento"]


def _agora() -> int:
    return int(time.time())


def _pasta(projeto: dict) -> Path:
    p = Path(projeto["pasta"])
    p.mkdir(parents=True, exist_ok=True)
    return p


def _plan_path(projeto: dict) -> Path:
    return _pasta(projeto) / "restoration_plan.json"


def _save_plan(projeto: dict, plan: dict) -> dict:
    plan["atualizado_em"] = _agora()
    _plan_path(projeto).write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    return plan


def criar_plano_restauracao(
    projeto: dict,
    relatorio: dict | None = None,
    tipo_projeto: str | None = None,
    status_publicacao: str | None = None,
    colecao: str = "",
) -> dict:
    """Cria ou atualiza o plano editorial do projeto sem alterar nenhum asset."""
    existente = carregar_plano_restauracao(projeto)
    if existente:
        plan = existente
    else:
        plan = {
            "id": uuid.uuid4().hex[:12],
            "projeto_id": projeto.get("id", ""),
            "titulo": projeto.get("titulo", ""),
            "criado_em": _agora(),
            "politica": "original_preservado",
            "vinculos": {"characters": [], "style_id": ""},
            "decisoes": [],
            "versoes_assets": [],
        }
    plan["tipo_projeto"] = tipo_projeto or projeto.get("tipo_projeto") or plan.get("tipo_projeto") or "story"
    plan["status_publicacao"] = status_publicacao or projeto.get("status_publicacao") or plan.get("status_publicacao") or "em_desenvolvimento"
    plan["colecao"] = colecao or projeto.get("colecao") or plan.get("colecao") or ""
    if relatorio:
        plan["relatorio_book_doctor"] = str(Path(projeto["pasta"]) / "relatorios" / "book_doctor_report.json")
        plan["assets_detectados"] = extrair_assets_relatorio(relatorio)
    else:
        plan.setdefault("assets_detectados", [])
    return _save_plan(projeto, plan)


def carregar_plano_restauracao(projeto: dict) -> dict:
    p = _plan_path(projeto)
    if not p.exists():
        return {}
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def extrair_assets_relatorio(relatorio: dict) -> list[dict]:
    assets: list[dict] = []
    miolo = relatorio.get("miolo") or {}
    for item in miolo.get("imagens", []) or []:
        caminho = item.get("arquivo_extraido") or ""
        assets.append({
            "id": f"p{int(item.get('pagina',0)):03d}-i{int(item.get('indice',0)):02d}",
            "tipo": "miolo",
            "pagina": item.get("pagina"),
            "indice": item.get("indice"),
            "arquivo": caminho,
            "largura_px": item.get("largura_px"),
            "altura_px": item.get("altura_px"),
            "ppi_estimado": item.get("ppi_estimado_full_page"),
            "status_tecnico": item.get("status", "indeterminado"),
        })
    capa = relatorio.get("capa") or {}
    if capa.get("arquivo"):
        assets.append({
            "id": "capa",
            "tipo": "capa",
            "pagina": None,
            "indice": None,
            "arquivo": capa.get("arquivo"),
            "largura_px": capa.get("largura_px"),
            "altura_px": capa.get("altura_px"),
            "ppi_estimado": capa.get("ppi_efetivo"),
            "status_tecnico": capa.get("status", "indeterminado"),
        })
    return assets


def vincular_character(plan: dict, character_id: str, papel: str = "personagem_detectado") -> dict:
    p = deepcopy(plan)
    vinculos = p.setdefault("vinculos", {})
    itens = vinculos.setdefault("characters", [])
    if not any(x.get("character_id") == character_id for x in itens):
        ch = carregar_personagem_oficial(character_id)
        itens.append({
            "character_id": character_id,
            "nome": ch.get("nome", "") if ch else "",
            "papel": papel,
            "vinculado_em": _agora(),
        })
    return p


def vincular_style(plan: dict, style_id: str) -> dict:
    p = deepcopy(plan)
    st = carregar_style(style_id) if style_id else {}
    p.setdefault("vinculos", {})["style_id"] = style_id or ""
    p["vinculos"]["style_nome"] = st.get("nome", "") if st else ""
    return p


def salvar_vinculos(projeto: dict, plan: dict) -> dict:
    return _save_plan(projeto, plan)


def registrar_decisao(
    projeto: dict,
    asset_id: str,
    acao: str,
    character_id: str = "",
    style_id: str = "",
    instrucao_autora: str = "",
    metadata: dict | None = None,
) -> dict:
    if acao not in ACOES:
        raise ValueError(f"Ação inválida: {acao}")
    plan = carregar_plano_restauracao(projeto) or criar_plano_restauracao(projeto)
    decisao = {
        "id": uuid.uuid4().hex[:12],
        "asset_id": asset_id,
        "acao": acao,
        "character_id": character_id,
        "style_id": style_id,
        "instrucao_autora": instrucao_autora.strip(),
        "metadata": metadata or {},
        "criada_em": _agora(),
        "status": "aprovada_para_execucao" if acao in {"manter_original", "melhorar_tecnicamente", "limpar_line_art"} else "aguardando_geracao",
    }
    # Uma nova decisão não apaga a anterior: mantém histórico.
    plan.setdefault("decisoes", []).append(decisao)
    _save_plan(projeto, plan)
    return decisao


def _remastered_path(projeto: dict, origem: str, sufixo: str, ext: str = ".png") -> Path:
    base = Path(origem).stem if origem else "asset"
    pasta = _pasta(projeto) / "remastered"
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta / f"{base}_{sufixo}_{uuid.uuid4().hex[:8]}{ext}"


def _registrar_versao(
    projeto: dict,
    origem: str,
    derivado: str,
    operacao: str,
    metadata: dict | None = None,
) -> dict:
    plan = carregar_plano_restauracao(projeto) or criar_plano_restauracao(projeto)
    registro = {
        "id": uuid.uuid4().hex[:12],
        "origem": origem,
        "origem_sha256": sha256(origem) if origem and Path(origem).exists() else "",
        "derivado": derivado,
        "derivado_sha256": sha256(derivado) if derivado and Path(derivado).exists() else "",
        "operacao": operacao,
        "metadata": metadata or {},
        "criada_em": _agora(),
        "aprovada": False,
    }
    plan.setdefault("versoes_assets", []).append(registro)
    _save_plan(projeto, plan)
    return registro


def aprovar_versao(projeto: dict, versao_id: str) -> dict:
    plan = carregar_plano_restauracao(projeto)
    for v in plan.get("versoes_assets", []):
        if v.get("id") == versao_id:
            v["aprovada"] = True
            v["aprovada_em"] = _agora()
    _save_plan(projeto, plan)
    return plan


def avaliar_ppi(caminho: str, largura_final_in: float | None, altura_final_in: float | None) -> dict:
    with Image.open(caminho) as im:
        w, h = im.size
    ppi = None
    if largura_final_in and altura_final_in and largura_final_in > 0 and altura_final_in > 0:
        ppi = min(w / largura_final_in, h / altura_final_in)
    if ppi is None:
        status = "indeterminado"
    elif ppi >= 300:
        status = "excelente"
    elif ppi >= 200:
        status = "atencao"
    else:
        status = "reprovada"
    return {"largura_px": w, "altura_px": h, "ppi_efetivo": round(ppi, 1) if ppi else None, "status": status}


def melhorar_imagem_tecnicamente(
    projeto: dict,
    origem: str,
    fator_upscale: int = 2,
    nitidez: float = 1.15,
    contraste: float = 1.05,
    autocontraste: bool = False,
    largura_final_in: float | None = None,
    altura_final_in: float | None = None,
) -> dict:
    """Cria cópia técnica melhorada, sem prometer recuperar detalhe inexistente.

    Lanczos melhora amostragem/serrilhado, mas não cria informação semântica nova.
    O registro deixa essa limitação explícita para o Quality Guardian.
    """
    fator = max(1, min(4, int(fator_upscale)))
    destino = _remastered_path(projeto, origem, f"technical-x{fator}")
    with Image.open(origem) as im:
        alpha = "A" in im.getbands()
        work = im.convert("RGBA" if alpha else "RGB")
        before = work.size
        if fator > 1:
            work = work.resize((work.width * fator, work.height * fator), Image.Resampling.LANCZOS)
        if autocontraste:
            if alpha:
                r, g, b, a = work.split()
                rgb = Image.merge("RGB", (r, g, b))
                rgb = ImageOps.autocontrast(rgb)
                r, g, b = rgb.split()
                work = Image.merge("RGBA", (r, g, b, a))
            else:
                work = ImageOps.autocontrast(work)
        if abs(float(contraste) - 1.0) > 1e-6:
            work = ImageEnhance.Contrast(work).enhance(float(contraste))
        if abs(float(nitidez) - 1.0) > 1e-6:
            work = ImageEnhance.Sharpness(work).enhance(float(nitidez))
        work.save(destino, format="PNG", dpi=(300, 300))
        after = work.size
    meta = {
        "antes_px": list(before),
        "depois_px": list(after),
        "fator_upscale": fator,
        "nitidez": nitidez,
        "contraste": contraste,
        "autocontraste": autocontraste,
        "limitacao": "Upscale determinístico melhora amostragem e tamanho de arquivo, mas não inventa detalhe visual perdido. Revisar antes de aprovar para impressão.",
        "ppi_depois": avaliar_ppi(str(destino), largura_final_in, altura_final_in),
    }
    versao = _registrar_versao(projeto, origem, str(destino), "melhorar_tecnicamente", meta)
    return {"caminho": str(destino), "versao": versao, **meta}




def auditar_line_art(caminho: str) -> dict:
    """Métricas objetivas simples para line art, sem inferir gosto/estilo.

    Mede presença de tons de cinza, cobertura de tinta e proximidade do conteúdo
    às bordas. Não tenta decidir sozinho se a complexidade é adequada à idade.
    """
    with Image.open(caminho) as im:
        g=im.convert("L")
        w,h=g.size
        hist=g.histogram()
    total=max(1,w*h)
    quase_preto=sum(hist[:32])
    quase_branco=sum(hist[224:])
    cinzas=max(0,total-quase_preto-quase_branco)
    tinta=sum(hist[:245])
    # bbox de conteúdo: pixels abaixo de 245 são tratados como tinta/conteúdo.
    mask=g.point(lambda p:255 if p<245 else 0,mode="L")
    bbox=mask.getbbox()
    margens=None
    toca_borda=False
    if bbox:
        l,t,r,b=bbox
        margens={
            "esquerda_pct":round(100*l/w,2),
            "topo_pct":round(100*t/h,2),
            "direita_pct":round(100*(w-r)/w,2),
            "base_pct":round(100*(h-b)/h,2),
        }
        toca_borda=min(margens.values()) < 1.0
    cinza_pct=100*cinzas/total
    ink_pct=100*tinta/total
    alertas=[]
    if cinza_pct > 5:
        alertas.append("Há quantidade relevante de tons de cinza; para line art pura, revisar/binarizar.")
    if toca_borda:
        alertas.append("Conteúdo chega muito perto da borda da imagem; revisar safe area/corte.")
    if ink_pct > 45:
        alertas.append("Cobertura de tinta é alta para uma página de colorir; revisar áreas preenchidas/densidade.")
    return {
        "largura_px":w,"altura_px":h,
        "tons_cinza_pct":round(cinza_pct,2),
        "cobertura_tinta_pct":round(ink_pct,2),
        "margens_conteudo_pct":margens,
        "toca_borda":toca_borda,
        "alertas":alertas,
        "status":"atencao" if alertas else "tecnicamente_limpa",
        "nota":"Métricas objetivas de pixels. Adequação estética, faixa etária e Style DNA continuam exigindo revisão editorial/visual.",
    }

def limpar_line_art(
    projeto: dict,
    origem: str,
    threshold: int = 205,
    reduzir_ruido: bool = True,
    espessura: str = "manter",
    fator_upscale: int = 2,
    largura_final_in: float | None = None,
    altura_final_in: float | None = None,
) -> dict:
    """Normaliza line art para preto/branco puro em uma cópia separada."""
    threshold = max(1, min(254, int(threshold)))
    fator = max(1, min(4, int(fator_upscale)))
    destino = _remastered_path(projeto, origem, f"lineart-{espessura}-x{fator}")
    with Image.open(origem) as im:
        work = im.convert("L")
        before = work.size
        if fator > 1:
            work = work.resize((work.width * fator, work.height * fator), Image.Resampling.LANCZOS)
        if reduzir_ruido:
            work = work.filter(ImageFilter.MedianFilter(size=3))
        work = ImageOps.autocontrast(work)
        # 0 = preto, 255 = branco.
        work = work.point(lambda p: 0 if p < threshold else 255, mode="1").convert("L")
        if espessura == "engrossar":
            work = work.filter(ImageFilter.MinFilter(size=3))
        elif espessura == "afinar":
            work = work.filter(ImageFilter.MaxFilter(size=3))
        work.save(destino, format="PNG", dpi=(300, 300), optimize=True)
        after = work.size
    meta = {
        "antes_px": list(before),
        "depois_px": list(after),
        "threshold": threshold,
        "reduzir_ruido": reduzir_ruido,
        "espessura": espessura,
        "fator_upscale": fator,
        "preto_branco_puro": True,
        "ppi_depois": avaliar_ppi(str(destino), largura_final_in, altura_final_in),
    }
    versao = _registrar_versao(projeto, origem, str(destino), "limpar_line_art", meta)
    return {"caminho": str(destino), "versao": versao, **meta}


def montar_prompt_restauracao(
    acao: str,
    character_id: str = "",
    style_id: str = "",
    contexto: str = "story",
    variaveis: dict | None = None,
    emocao: str = "",
    preset_emocional: str = "Erica Matsuzaki · Pastel Faith",
    instrucao_autora: str = "",
) -> str:
    partes = [
        "FAITHBLOOM RESTORATION STUDIO. Trabalhe a partir da imagem-base fornecida.",
        "REGRA DE PRESERVAÇÃO: não substituir composição, personagem ou elementos que não foram solicitados. Manter a versão original intacta e gerar uma nova variação.",
    ]
    if acao == "corrigir_personagem":
        partes.append("Objetivo: restaurar SOMENTE a identidade visual do personagem apontado, preservando cenário, enquadramento, ação e demais elementos sempre que possível.")
    elif acao == "reilustrar":
        partes.append("Objetivo: reilustrar a cena em qualidade editorial superior mantendo intenção narrativa, personagens oficiais e Style DNA.")
    elif acao == "criar_variacao":
        partes.append("Objetivo: criar uma alternativa da mesma cena sem apagar nem substituir a versão anterior.")
    elif acao == "limpar_line_art":
        partes.append("Objetivo: recriar como line art limpa e imprimível, preservando sujeito/pose/composição e eliminando cinzas, artefatos e linhas indecisas.")

    if character_id:
        ch = carregar_personagem_oficial(character_id)
        if ch:
            partes.append(personagem_para_prompt(ch, "line_art" if contexto == "coloring" else "color", variaveis or {}, contexto))
    if style_id:
        st = carregar_style(style_id)
        if st:
            partes.append(style_para_prompt(st, contexto))
    if emocao:
        item = {
            "expressao": emocao,
            "instrucao_autora": "",
            "direcao": direcao_emocional(emocao, preset_emocional),
        }
        partes.append(prompt_direcao_visual(item))
    if instrucao_autora.strip():
        partes.append("INSTRUÇÃO ESPECÍFICA DA AUTORA: " + instrucao_autora.strip())
    partes.append("Saída: uma nova imagem de alta qualidade para revisão humana. Não inserir texto editorial automaticamente.")
    return "\n\n".join(x for x in partes if x)


def gerar_variacao_ia(
    projeto: dict,
    origem: str,
    prompt: str,
    gerar_imagem: Callable,
    operacao: str,
    imagens_referencia: list[str] | None = None,
) -> dict:
    """Executa geração externa somente quando a UI/autora solicitar explicitamente.

    O asset auditado é a referência principal; Character Masters adicionais podem
    ser enviados como referências visuais separadas para reforçar consistência.
    """
    try:
        caminho_gerado = gerar_imagem(prompt=prompt, imagem_base=origem, imagens_referencia=imagens_referencia or [])
    except TypeError:
        # Compatibilidade com callbacks antigos usados em testes/mocks.
        caminho_gerado = gerar_imagem(prompt=prompt, imagem_base=origem)
    src = Path(caminho_gerado)
    destino = _remastered_path(projeto, origem, operacao, src.suffix or ".png")
    destino.write_bytes(src.read_bytes())
    meta = {"prompt": prompt, "origem_geracao": caminho_gerado, "referencias_visuais": imagens_referencia or [], "revisao_humana_obrigatoria": True}
    versao = _registrar_versao(projeto, origem, str(destino), operacao, meta)
    return {"caminho": str(destino), "versao": versao, "prompt": prompt}


def resumo_restauracao(projeto: dict) -> dict:
    plan = carregar_plano_restauracao(projeto)
    versoes = plan.get("versoes_assets", [])
    decisoes = plan.get("decisoes", [])
    aprovadas = [v for v in versoes if v.get("aprovada")]
    por_operacao: dict[str, int] = {}
    for v in versoes:
        por_operacao[v.get("operacao", "")] = por_operacao.get(v.get("operacao", ""), 0) + 1
    return {
        "decisoes_total": len(decisoes),
        "versoes_geradas": len(versoes),
        "versoes_aprovadas": len(aprovadas),
        "por_operacao": por_operacao,
        "original_preservado": plan.get("politica") == "original_preservado",
    }
