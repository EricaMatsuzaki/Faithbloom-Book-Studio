"""FaithBloom Full Editorial Remaster — ponte segura para obras já publicadas.

Prepara um estado derivado de um projeto do Book Doctor sem duplicar os agentes
especializados. Aceita PDF preservado e também manuscrito textual preservado pelo
Jarvis. Em ambos os casos o original é imutável e verificado por SHA-256.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import uuid

from pypdf import PdfReader

from age_profiles import normalizar_faixa_etaria
from book_doctor import sha256

SCHEMA = "faithbloom.editorial-remaster.v1"

EDITORIAL_REMASTER_ROUTE = [
    "book_doctor", "story_reviewer", "story_editor", "storyteller", "heart_arc",
    "emotional_experience_engine", "prompt_master_compliance",
    "biblical_reference_validator", "emotional_color_director", "originality_guard",
    "character_universe", "restoration_studio", "quality_guardian",
    "publishing_platform_engine", "publishing_distribution_center",
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _manifest_entries(projeto: dict) -> list[dict]:
    path = Path(projeto.get("pasta", "")) / "originais" / "manifest.json"
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    return [x for x in data if isinstance(x, dict)] if isinstance(data, list) else []


def localizar_miolo_original(projeto: dict) -> dict:
    entries = [x for x in _manifest_entries(projeto) if x.get("papel") == "miolo"]
    if not entries:
        raise ValueError("O Book Doctor não possui um miolo original preservado para este projeto.")
    entry = entries[-1]
    path = Path(str(entry.get("arquivo") or ""))
    if not path.exists():
        raise FileNotFoundError(f"Miolo preservado não encontrado: {path}")
    atual = sha256(str(path))
    esperado = str(entry.get("sha256") or "")
    if esperado and atual != esperado:
        raise ValueError("O SHA-256 do miolo preservado diverge do manifest. Revisão bloqueada por segurança.")
    return {**entry, "arquivo": str(path), "sha256": atual}


def extrair_texto_paginas(caminho_pdf: str) -> list[dict]:
    reader = PdfReader(caminho_pdf)
    paginas: list[dict] = []
    for numero, page in enumerate(reader.pages, 1):
        try:
            texto = (page.extract_text() or "").strip()
            erro = ""
        except Exception as exc:
            texto = ""
            erro = str(exc)
        paginas.append({
            "pagina": numero,
            "texto_extraido": texto,
            "tem_texto": bool(texto),
            "erro_extracao": erro,
            "origem": "pdf",
        })
    return paginas


def extrair_texto_manuscrito(caminho: str) -> list[dict]:
    """Lê manuscrito UTF-8 preservando blocos de página quando já estruturados.

    Se houver cabeçalhos PÁGINA/PAGINA/PAGE, cada bloco vira uma página lógica.
    Blocos explicitamente marcados como ILUSTRAÇÃO/ILUSTRACAO não viram texto
    narrativo; permanecem fora do mapeamento textual para não substituir cenas.
    Sem cabeçalhos, o manuscrito inteiro vira uma página lógica e seguirá pelo
    classificador editorial normal.
    """
    raw = Path(caminho).read_text(encoding="utf-8", errors="replace").strip()
    if not raw:
        raise ValueError("O manuscrito textual preservado está vazio.")
    pattern = re.compile(
        r"(?im)^\s*(?:#{1,6}\s*)?(?:P[ÁA]GINA|PAGE)\s+(\d+)\s*(?:[-—–:]\s*([^\n]*))?\s*$"
    )
    matches = list(pattern.finditer(raw))
    if not matches:
        return [{
            "pagina": 1, "texto_extraido": raw, "tem_texto": True,
            "erro_extracao": "", "origem": "jarvis_text",
        }]

    paginas: list[dict] = []
    for i, match in enumerate(matches):
        numero = int(match.group(1))
        rotulo = str(match.group(2) or "").strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(raw)
        corpo = raw[start:end].strip()
        role = rotulo.casefold()
        # Direções de ilustração não devem ser tratadas como prosa narrativa.
        if "ilustra" in role:
            corpo = ""
        paginas.append({
            "pagina": numero,
            "texto_extraido": corpo,
            "tem_texto": bool(corpo),
            "erro_extracao": "",
            "origem": "jarvis_text",
            "rotulo_origem": rotulo,
        })
    return paginas


def _extrair_fonte(original_path: str) -> tuple[list[dict], str]:
    suffix = Path(original_path).suffix.casefold()
    if suffix == ".pdf":
        return extrair_texto_paginas(original_path), "pdf"
    if suffix in {".txt", ".md", ".rtf"}:
        return extrair_texto_manuscrito(original_path), "text"
    raise ValueError(f"Formato de miolo ainda não suportado pelo Full Editorial Remaster: {suffix or 'sem extensão'}")


def criar_rascunho_remaster_editorial(
    projeto: dict,
    relatorio_book_doctor: dict | None = None,
    *,
    faixa_etaria: str = "3-8",
    versiculo_referencia: str = "",
    licao_final: str = "",
    aprendizado_cristao: str = "",
    emocao_central: str = "",
) -> dict:
    if str(projeto.get("tipo_projeto") or "story") != "story":
        raise ValueError("Full Editorial Remaster textual está disponível somente para Story Book nesta etapa.")

    original = localizar_miolo_original(projeto)
    before_hash = original["sha256"]
    paginas, source_format = _extrair_fonte(original["arquivo"])
    after_hash = sha256(original["arquivo"])
    if before_hash != after_hash:
        raise RuntimeError("O original mudou durante a preparação do remaster. Operação interrompida.")

    remaster_id = uuid.uuid4().hex[:12]
    faixa = normalizar_faixa_etaria(faixa_etaria)
    estado = {
        "schema": SCHEMA,
        "remaster_id": remaster_id,
        "projeto_book_doctor_id": projeto.get("id", ""),
        "titulo": projeto.get("titulo", ""),
        "colecao": projeto.get("colecao", ""),
        "idioma": projeto.get("idioma", "pt-BR"),
        "status_publicacao_origem": projeto.get("status_publicacao", ""),
        "faixa_etaria": faixa,
        "age_profile_id": faixa,
        "versiculo_referencia": str(versiculo_referencia or "").strip(),
        "licao_final": str(licao_final or "").strip(),
        "aprendizado_cristao": str(aprendizado_cristao or "").strip(),
        "emocao_central": str(emocao_central or "").strip(),
        "original": {"arquivo": original["arquivo"], "sha256": before_hash, "imutavel": True},
        "source_format": source_format,
        "book_doctor_report_snapshot": deepcopy(relatorio_book_doctor or {}),
        "paginas_texto_extraido": paginas,
        "cenas_texto": [],
        "mapeamento_cenas_confirmado": False,
        "revisao_aprovada": False,
        "rota_editorial": list(EDITORIAL_REMASTER_ROUTE),
        "politica_revisao": {
            "revisor_primeiro": True,
            "editor_apenas_pontual": True,
            "roteirista_apenas_quando_necessario": True,
            "preservar_alma_da_obra": True,
            "preservar_original": True,
            "revisao_textual_antes_visual": True,
            "masters_oficiais_no_visual": True,
            "aprovacao_humana_obrigatoria": True,
            "auto_publicar": False,
        },
        "status": "aguardando_mapeamento_e_confirmacao",
        "criado_em": _now_iso(),
    }

    pasta = Path(projeto["pasta"]) / "remastered" / "editorial" / remaster_id
    pasta.mkdir(parents=True, exist_ok=True)
    path = pasta / "editorial_remaster.json"
    estado["arquivo_estado"] = str(path)
    path.write_text(json.dumps(estado, ensure_ascii=False, indent=2), encoding="utf-8")
    return estado


def confirmar_mapeamento_cenas(estado: dict, paginas_historia: list[int]) -> dict:
    paginas_ok = {int(x) for x in paginas_historia}
    if not paginas_ok:
        raise ValueError("Selecione ao menos uma página de história antes de confirmar o mapeamento.")
    por_pagina = {
        int(x.get("pagina")): x
        for x in (estado.get("paginas_texto_extraido") or []) if isinstance(x, dict)
    }
    faltantes = sorted(p for p in paginas_ok if p not in por_pagina)
    if faltantes:
        raise ValueError(f"Páginas não encontradas no material importado: {faltantes}")

    cenas = []
    origem = "jarvis_text" if estado.get("source_format") == "text" else "book_doctor_pdf"
    for p in sorted(paginas_ok):
        texto = str(por_pagina[p].get("texto_extraido") or "").strip()
        if not texto:
            continue
        cenas.append({
            "numero": len(cenas) + 1,
            "texto": texto,
            "pagina_origem": p,
            "origem": origem,
        })
    if not cenas:
        raise ValueError("As páginas selecionadas não possuem texto para revisão.")

    novo = deepcopy(estado)
    novo["cenas_texto"] = cenas
    novo["mapeamento_cenas_confirmado"] = True
    novo["status"] = "pronto_para_revisao_editorial"
    novo["mapeamento_confirmado_em"] = _now_iso()
    return novo


def gate_revisao_editorial(estado: dict) -> dict:
    bloqueios = []
    original = estado.get("original") or {}
    path = str(original.get("arquivo") or "")
    esperado = str(original.get("sha256") or "")
    if not path or not Path(path).exists():
        bloqueios.append("original_ausente")
    elif esperado and sha256(path) != esperado:
        bloqueios.append("original_sha_divergente")
    if not estado.get("mapeamento_cenas_confirmado"):
        bloqueios.append("mapeamento_cenas_nao_confirmado")
    if not estado.get("cenas_texto"):
        bloqueios.append("cenas_texto_ausentes")
    return {
        "ok": not bloqueios,
        "bloqueios": bloqueios,
        "requires_human_approval": True,
        "next_step": "story_reviewer" if not bloqueios else "aguardar_confirmacao",
    }


def gerar_dossie_revisao(estado: dict, chamar_llm) -> dict:
    gate = gate_revisao_editorial(estado)
    if not gate["ok"]:
        raise ValueError("Revisão editorial bloqueada: " + ", ".join(gate["bloqueios"]))

    original = estado.get("original") or {}
    original_path = str(original.get("arquivo") or "")
    before_hash = sha256(original_path)
    cenas_antes = deepcopy(estado.get("cenas_texto") or [])

    from agents.revisor import revisor_node
    from prompt_master_compliance import avaliar_prompt_mestre

    work = deepcopy(estado)
    revisado = revisor_node(work, chamar_llm)
    if (revisado.get("cenas_texto") or []) != cenas_antes:
        raise RuntimeError("O Revisor alterou cenas durante a fase de diagnóstico. Operação bloqueada.")

    compliance = avaliar_prompt_mestre(dict(revisado))
    after_hash = sha256(original_path)
    if before_hash != after_hash or after_hash != str(original.get("sha256") or after_hash):
        raise RuntimeError("O original foi alterado durante a revisão. Operação interrompida.")

    notas = deepcopy(revisado.get("notas_revisor") or [])
    precisa_revisao_textual = not bool(revisado.get("revisao_aprovada"))
    proximos = []
    if precisa_revisao_textual:
        proximos.extend(["story_editor", "storyteller"])
    proximos.extend([
        "heart_arc", "emotional_experience_engine", "prompt_master_compliance",
        "biblical_reference_validator", "emotional_color_director", "originality_guard",
    ])

    dossie = {
        "schema": "faithbloom.editorial-remaster-dossier.v1",
        "remaster_id": estado.get("remaster_id", ""),
        "titulo": estado.get("titulo", ""),
        "gerado_em": _now_iso(),
        "original_sha256": before_hash,
        "original_preservado": True,
        "revisor": {"status": "APROVADO" if revisado.get("revisao_aprovada") else "REVISAR", "notas": notas},
        "prompt_mestre": compliance,
        "precisa_revisao_textual": precisa_revisao_textual,
        "proximos_especialistas": proximos,
        "alteracoes_aplicadas": False,
        "aprovacao_humana_pendente": True,
        "politica": (
            "Diagnóstico primeiro. Nenhuma cena é reescrita e nenhuma ilustração é regenerada "
            "até a próxima etapa autorizada do fluxo."
        ),
    }

    state_path = Path(str(estado.get("arquivo_estado") or ""))
    if state_path:
        pasta = state_path.parent if state_path.suffix else state_path
        pasta.mkdir(parents=True, exist_ok=True)
        dossier_path = pasta / "editorial_dossier.json"
        dossier_path.write_text(json.dumps(dossie, ensure_ascii=False, indent=2), encoding="utf-8")
        dossie["arquivo_dossie"] = str(dossier_path)
    return dossie
