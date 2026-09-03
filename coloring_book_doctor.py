"""FaithBloom Coloring Book Doctor — Refinamento 05.

Camada especializada do Book Doctor para livros de colorir/line art.

Princípios:
- diagnosticar antes de corrigir;
- métricas objetivas/heurísticas declaradas, sem notas estéticas inventadas;
- análise por faixa etária e complexidade;
- recuperação em lote somente em CÓPIAS derivadas;
- original preservado e decisões rastreáveis;
- preparação de capa/acabamento sem misturar arte da IA com geometria de impressão.
"""
from __future__ import annotations

import json
import math
import time
from collections import deque
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageFilter

from qualidade_impressao import analisar_imagem
from restoration_studio import limpar_line_art, melhorar_imagem_tecnicamente


AGE_PROFILES: dict[str, dict] = {
    "3-4": {
        "nome": "3–4 anos · Primeiros traços",
        "faixa": "3–4 anos",
        "complexidade_max": 34,
        "componentes_max": 75,
        "tons_cinza_max_pct": 1.5,
        "borda_tinta_max_pct": 1.5,
        "espessuras_ideais": {"grosso", "muito grosso"},
        "orientacao": "Poucos elementos, áreas muito grandes, contornos grossos e fundos mínimos.",
    },
    "5-6": {
        "nome": "5–6 anos · Simples e fofo",
        "faixa": "5–6 anos",
        "complexidade_max": 48,
        "componentes_max": 110,
        "tons_cinza_max_pct": 2.0,
        "borda_tinta_max_pct": 1.8,
        "espessuras_ideais": {"médio", "grosso", "muito grosso"},
        "orientacao": "Áreas grandes/médias, cenários simples e poucos microdetalhes.",
    },
    "7-8": {
        "nome": "7–8 anos · Equilibrado",
        "faixa": "7–8 anos",
        "complexidade_max": 62,
        "componentes_max": 160,
        "tons_cinza_max_pct": 2.5,
        "borda_tinta_max_pct": 2.0,
        "espessuras_ideais": {"fino", "médio", "grosso"},
        "orientacao": "Mais objetos e expressão, mantendo áreas confortáveis para colorir.",
    },
    "9-12": {
        "nome": "9–12 anos · Mais detalhes",
        "faixa": "9–12 anos",
        "complexidade_max": 80,
        "componentes_max": 240,
        "tons_cinza_max_pct": 3.0,
        "borda_tinta_max_pct": 2.2,
        "espessuras_ideais": {"muito fino", "fino", "médio", "grosso"},
        "orientacao": "Detalhes moderados/altos são aceitáveis, sem comprometer legibilidade ou impressão.",
    },
    "teen-adult": {
        "nome": "Adolescente / Adulto · Detalhado",
        "faixa": "Adolescente/Adulto",
        "complexidade_max": 100,
        "componentes_max": 9999,
        "tons_cinza_max_pct": 4.0,
        "borda_tinta_max_pct": 2.5,
        "espessuras_ideais": {"muito fino", "fino", "médio", "grosso", "muito grosso"},
        "orientacao": "Pode ter alta complexidade, desde que os contornos permaneçam nítidos e imprimíveis.",
    },
    "custom": {
        "nome": "Personalizado",
        "faixa": "Personalizado",
        "complexidade_max": 100,
        "componentes_max": 9999,
        "tons_cinza_max_pct": 5.0,
        "borda_tinta_max_pct": 3.0,
        "espessuras_ideais": {"muito fino", "fino", "médio", "grosso", "muito grosso"},
        "orientacao": "Use os indicadores como diagnóstico e valide manualmente conforme o objetivo editorial.",
    },
}

ESSENCIAIS_CAPA_ACABAMENTO = [
    "Capa frontal",
    "Contracapa",
    "Wrap físico calculado",
    "Bleed",
    "Safe zones",
    "Área reservada para código de barras",
    "Título, subtítulo e autora",
    "Preflight de dimensões e resolução",
]

OPCIONAIS_INTERIOR_COLORING = [
    "Página de rosto",
    "Copyright",
    "Este livro pertence a",
    "Mensagem de boas-vindas",
    "Instruções para colorir",
    "Teste de cores",
    "Página de exemplo colorido",
    "Apresentação dos personagens",
    "Dedicatória",
    "Certificado — Eu terminei meu livro!",
    "Página final de agradecimento",
    "Conheça outros livros",
    "QR code / site da autora",
    "Páginas extras para desenho livre",
]


def perfil_faixa_etaria(perfil_id: str) -> dict:
    return dict(AGE_PROFILES.get(perfil_id, AGE_PROFILES["custom"]))


def _hist_metric(hist: list[int], inicio: int, fim: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(sum(hist[inicio:fim + 1]) * 100.0 / total, 3)


def _connected_components(img: Image.Image, threshold: int = 180, max_side: int = 256) -> dict:
    """Conta componentes de tinta numa miniatura binária.

    É uma heurística de complexidade geométrica, não uma avaliação artística.
    """
    work = img.copy().convert("L")
    work.thumbnail((max_side, max_side), Image.Resampling.BILINEAR)
    w, h = work.size
    vals = list(work.get_flattened_data()) if hasattr(work, "get_flattened_data") else list(work.getdata())
    ink = [v < threshold for v in vals]
    seen = bytearray(w * h)
    comps = 0
    small = 0
    largest = 0
    # 4-conectividade evita juntar detalhes diagonais sem contato real.
    for start, is_ink in enumerate(ink):
        if not is_ink or seen[start]:
            continue
        q = deque([start]); seen[start] = 1; size = 0
        while q:
            idx = q.popleft(); size += 1
            x, y = idx % w, idx // w
            for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if nx < 0 or nx >= w or ny < 0 or ny >= h:
                    continue
                ni = ny * w + nx
                if ink[ni] and not seen[ni]:
                    seen[ni] = 1; q.append(ni)
        if size >= 2:
            comps += 1
            largest = max(largest, size)
            if size <= 10:
                small += 1
    return {"componentes": comps, "componentes_pequenos": small, "maior_componente_px_thumb": largest, "thumb": [w, h]}


def _edge_density(img: Image.Image) -> float:
    work = img.copy().convert("L")
    work.thumbnail((900, 900), Image.Resampling.BILINEAR)
    edges = work.filter(ImageFilter.FIND_EDGES)
    hist = edges.histogram(); total = max(1, work.width * work.height)
    strong = sum(hist[42:])
    return round(strong * 100.0 / total, 3)


def _border_ink_pct(img: Image.Image, threshold: int = 180, band_pct: float = 0.035) -> float:
    work = img.copy().convert("L")
    work.thumbnail((900, 900), Image.Resampling.BILINEAR)
    w, h = work.size
    band = max(1, round(min(w, h) * band_pct))
    pix = work.load(); ink = 0; total = 0
    for y in range(h):
        for x in range(w):
            if x < band or x >= w - band or y < band or y >= h - band:
                total += 1
                if pix[x, y] < threshold:
                    ink += 1
    return round(ink * 100.0 / max(1, total), 3)


def _espessura_relativa(ink_pct: float, edge_pct: float) -> tuple[float, str]:
    idx = ink_pct / max(edge_pct, 0.05)
    if idx < 0.70:
        classe = "muito fino"
    elif idx < 1.10:
        classe = "fino"
    elif idx < 1.75:
        classe = "médio"
    elif idx < 2.70:
        classe = "grosso"
    else:
        classe = "muito grosso"
    return round(idx, 3), classe


def analisar_line_art_avancada(
    caminho: str,
    perfil_id: str = "5-6",
    largura_final_in: float | None = None,
    altura_final_in: float | None = None,
) -> dict:
    """Audita uma line art com métricas reprodutíveis e adequação heurística por idade."""
    p = Path(caminho)
    if not p.exists():
        return {"arquivo": caminho, "status": "bloqueante", "alertas": ["Arquivo não encontrado."], "perfil_id": perfil_id}
    profile = perfil_faixa_etaria(perfil_id)
    with Image.open(p) as raw:
        img = raw.convert("L")
        w, h = img.size
        hist = img.histogram(); total = max(1, w * h)
        preto_pct = _hist_metric(hist, 0, 63, total)
        cinza_pct = _hist_metric(hist, 64, 239, total)
        branco_pct = _hist_metric(hist, 240, 255, total)
        tinta_pct = round((sum(hist[:180]) * 100.0 / total), 3)
        edge_pct = _edge_density(img)
        border_pct = _border_ink_pct(img)
        comps = _connected_components(img)
        thick_idx, thick_class = _espessura_relativa(tinta_pct, edge_pct)

    # Score é deliberadamente uma heurística explicável, não "nota de qualidade".
    comp_term = min(comps["componentes"], 260) / 260 * 38
    edge_term = min(edge_pct, 22) / 22 * 36
    ink_term = min(tinta_pct, 35) / 35 * 26
    complexity = round(min(100.0, comp_term + edge_term + ink_term), 1)

    print_q = None
    if largura_final_in and altura_final_in:
        print_q = analisar_imagem(caminho, largura_final_in, altura_final_in)

    alertas: list[dict] = []
    if cinza_pct > profile["tons_cinza_max_pct"]:
        alertas.append({"gravidade": "ajuste", "codigo": "cinzas", "mensagem": f"{cinza_pct}% de pixels em tons intermediários; para line art de impressão, revise preto/branco puro."})
    if border_pct > profile["borda_tinta_max_pct"]:
        alertas.append({"gravidade": "atencao", "codigo": "borda", "mensagem": f"Há tinta relevante na faixa externa ({border_pct}%). Revisar safe area/cortes."})
    if complexity > profile["complexidade_max"]:
        alertas.append({"gravidade": "atencao", "codigo": "complexidade", "mensagem": f"Complexidade heurística {complexity}/100 acima do alvo deste perfil ({profile['complexidade_max']})."})
    if comps["componentes"] > profile["componentes_max"]:
        alertas.append({"gravidade": "ajuste", "codigo": "fragmentacao", "mensagem": f"Foram detectados {comps['componentes']} componentes de tinta na miniatura; pode haver excesso de detalhes/ruído para {profile['faixa']}."})
    if thick_class not in profile["espessuras_ideais"]:
        alertas.append({"gravidade": "ajuste", "codigo": "espessura", "mensagem": f"Índice relativo de traço sugere '{thick_class}', fora do conjunto preferido para {profile['faixa']}."})
    if print_q and print_q.get("status") == "reprovada":
        alertas.append({"gravidade": "bloqueante", "codigo": "ppi", "mensagem": f"PPI efetivo {print_q.get('ppi_efetivo')} no tamanho informado: abaixo de 200 PPI."})
    elif print_q and print_q.get("status") == "atencao":
        alertas.append({"gravidade": "atencao", "codigo": "ppi", "mensagem": f"PPI efetivo {print_q.get('ppi_efetivo')} no tamanho informado: abaixo do alvo de 300 PPI."})

    severidades = {a["gravidade"] for a in alertas}
    if "bloqueante" in severidades:
        status = "bloqueante"
    elif "atencao" in severidades:
        status = "atencao"
    elif "ajuste" in severidades:
        status = "ajustes"
    else:
        status = "adequada"

    sugestoes: list[str] = []
    codigos = {a["codigo"] for a in alertas}
    if "cinzas" in codigos: sugestoes.append("Normalizar para preto/branco puro em cópia derivada.")
    if "borda" in codigos: sugestoes.append("Reenquadrar/reduzir a arte ou aumentar a margem segura.")
    if "complexidade" in codigos or "fragmentacao" in codigos: sugestoes.append("Simplificar detalhes pequenos sem alterar o Character/Style DNA.")
    if "espessura" in codigos: sugestoes.append("Ajustar espessura do contorno ao preset etário escolhido.")
    if "ppi" in codigos: sugestoes.append("Gerar/remasterizar em resolução maior; upscale determinístico deve ser sinalizado como interpolação.")

    return {
        "arquivo": caminho,
        "largura_px": w,
        "altura_px": h,
        "perfil_id": perfil_id,
        "perfil": profile["nome"],
        "preto_pct": preto_pct,
        "cinza_pct": cinza_pct,
        "branco_pct": branco_pct,
        "tinta_pct": tinta_pct,
        "edge_density_pct": edge_pct,
        "borda_tinta_pct": border_pct,
        "componentes": comps["componentes"],
        "componentes_pequenos": comps["componentes_pequenos"],
        "espessura_indice": thick_idx,
        "espessura_classe": thick_class,
        "complexidade_heuristica": complexity,
        "print_qa": print_q,
        "status": status,
        "alertas": alertas,
        "sugestoes": sugestoes,
        "nota_metodologica": "Complexidade e espessura são heurísticas geométricas para triagem editorial; não são notas de beleza/qualidade artística.",
    }


def _asset_path(asset: dict) -> str:
    return str(asset.get("arquivo") or asset.get("arquivo_extraido") or "")


def auditar_lote_colorir(
    assets: Iterable[dict],
    perfil_id: str = "5-6",
    largura_final_in: float | None = None,
    altura_final_in: float | None = None,
) -> dict:
    linhas = []
    for i, asset in enumerate(assets, 1):
        caminho = _asset_path(asset)
        if not caminho or not Path(caminho).exists():
            continue
        qa = analisar_line_art_avancada(caminho, perfil_id, largura_final_in, altura_final_in)
        qa["asset_id"] = asset.get("id") or f"asset-{i:03d}"
        qa["pagina"] = asset.get("pagina")
        qa["indice"] = asset.get("indice")
        linhas.append(qa)
    counts = {k: 0 for k in ("adequada", "ajustes", "atencao", "bloqueante")}
    for row in linhas:
        counts[row.get("status", "atencao")] = counts.get(row.get("status", "atencao"), 0) + 1
    total = len(linhas)
    return {
        "gerado_em": int(time.time()),
        "perfil_id": perfil_id,
        "perfil": perfil_faixa_etaria(perfil_id),
        "total_assets": total,
        "resumo": counts,
        "assets": linhas,
        "aprovacao_automatica": False,
        "politica": "Triagem automática não substitui revisão da autora. Nenhuma correção foi aplicada.",
    }


def salvar_relatorio_colorir(projeto: dict, relatorio: dict) -> str:
    pasta = Path(projeto["pasta"]) / "relatorios"
    pasta.mkdir(parents=True, exist_ok=True)
    path = pasta / "coloring_book_doctor_report.json"
    path.write_text(json.dumps(relatorio, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


def carregar_relatorio_colorir(projeto: dict) -> dict:
    path = Path(projeto.get("pasta", "")) / "relatorios" / "coloring_book_doctor_report.json"
    if not path.exists(): return {}
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def gerar_plano_recuperacao(relatorio: dict) -> dict:
    itens = []
    for row in relatorio.get("assets", []):
        codigos = {a.get("codigo") for a in row.get("alertas", [])}
        if row.get("status") == "adequada":
            acao = "manter_original"
        elif "ppi" in codigos and row.get("status") == "bloqueante":
            acao = "revisar_resolucao_ou_reilustrar"
        elif codigos & {"cinzas", "espessura", "fragmentacao"}:
            acao = "normalizar_line_art"
        elif "borda" in codigos:
            acao = "revisar_enquadramento"
        else:
            acao = "revisar_manual"
        itens.append({
            "asset_id": row.get("asset_id"), "pagina": row.get("pagina"), "arquivo": row.get("arquivo"),
            "status": row.get("status"), "acao_sugerida": acao,
            "motivos": [a.get("mensagem") for a in row.get("alertas", [])],
            "aprovada_pela_autora": False,
        })
    return {"gerado_em": int(time.time()), "itens": itens, "politica": "Plano apenas sugere; execução em lote exige seleção/aprovação explícita."}


def executar_recuperacao_lote(
    projeto: dict,
    relatorio: dict,
    asset_ids: list[str],
    threshold: int = 205,
    espessura: str = "manter",
    fator_upscale: int = 1,
) -> dict:
    """Executa apenas limpeza determinística em assets explicitamente selecionados."""
    selecionados = set(asset_ids or [])
    resultados = []
    for row in relatorio.get("assets", []):
        if row.get("asset_id") not in selecionados:
            continue
        caminho = row.get("arquivo")
        if not caminho or not Path(caminho).exists():
            resultados.append({"asset_id": row.get("asset_id"), "ok": False, "erro": "arquivo ausente"})
            continue
        out = limpar_line_art(
            projeto, caminho, threshold=threshold, reduzir_ruido=True,
            espessura=espessura, fator_upscale=fator_upscale,
        )
        resultados.append({"asset_id": row.get("asset_id"), "ok": True, "resultado": out})
    return {"executados": len(resultados), "resultados": resultados, "original_preservado": True}


def plano_acabamento_colorir(opcionais: list[str] | None = None, incluir_lombada: bool = False) -> dict:
    essenciais = list(ESSENCIAIS_CAPA_ACABAMENTO)
    if incluir_lombada:
        essenciais.insert(2, "Lombada (quando aplicável)")
    selecionados = [x for x in (opcionais or []) if x in OPCIONAIS_INTERIOR_COLORING]
    return {
        "essenciais": essenciais,
        "opcionais_selecionados": selecionados,
        "opcionais_disponiveis": list(OPCIONAIS_INTERIOR_COLORING),
        "nota": "A lombada e o texto de lombada dependem do formato, papel e quantidade de páginas; o wrap deve ser calculado matematicamente.",
    }


def salvar_plano_editorial_colorir(projeto: dict, plano: dict) -> str:
    pasta = Path(projeto["pasta"]) / "planos"
    pasta.mkdir(parents=True, exist_ok=True)
    path = pasta / "coloring_editorial_plan.json"
    payload = {**plano, "salvo_em": int(time.time()), "original_preservado": True}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


def carregar_plano_editorial_colorir(projeto: dict) -> dict:
    path = Path(projeto.get("pasta", "")) / "planos" / "coloring_editorial_plan.json"
    if not path.exists(): return {}
    try:
        d = json.loads(path.read_text(encoding="utf-8")); return d if isinstance(d, dict) else {}
    except Exception: return {}
