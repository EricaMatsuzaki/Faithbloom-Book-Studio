"""FaithBloom Full Editorial Remaster — ponte segura para obras já publicadas.

Este módulo NÃO duplica Roteirista, Revisor, Heart Arc, Emotional Experience
Engine, Prompt-Mestre, Character Universe ou Quality Guardian. Ele prepara um
estado derivado de um projeto do Book Doctor e registra a rota canônica que deve
ser usada depois da confirmação humana do texto/cenas importados.

Princípios:
- original preservado e verificado por SHA-256;
- nenhuma reescrita automática durante a importação;
- texto extraído do PDF é rascunho de mapeamento, não verdade editorial;
- agentes só podem rodar depois de confirmação explícita da autora;
- revisão textual vem antes da remasterização visual;
- versão revisada permanece derivada e versionada.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import uuid

from pypdf import PdfReader

from age_profiles import normalizar_faixa_etaria
from book_doctor import sha256

SCHEMA = "faithbloom.editorial-remaster.v1"

# Ordem editorial para obra existente: diagnosticar antes de reescrever.
EDITORIAL_REMASTER_ROUTE = [
    "book_doctor",
    "story_reviewer",
    "story_editor",
    "storyteller",
    "heart_arc",
    "emotional_experience_engine",
    "prompt_master_compliance",
    "biblical_reference_validator",
    "emotional_color_director",
    "originality_guard",
    "character_universe",
    "restoration_studio",
    "quality_guardian",
    "publishing_platform_engine",
    "publishing_distribution_center",
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
    """Retorna o miolo preservado e valida o hash registrado no Book Doctor."""
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
    """Extrai texto por página sem alterar o PDF e sem inventar conteúdo."""
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
        })
    return paginas


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
    """Cria rascunho derivado e seguro para revisão editorial completa.

    Não chama LLM, não modifica o original e não transforma páginas em cenas
    automaticamente. O texto extraído precisa ser confirmado/mapeado pela autora.
    """
    if str(projeto.get("tipo_projeto") or "story") != "story":
        raise ValueError("Full Editorial Remaster textual está disponível somente para Story Book nesta etapa.")

    original = localizar_miolo_original(projeto)
    before_hash = original["sha256"]
    paginas = extrair_texto_paginas(original["arquivo"])
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
        "original": {
            "arquivo": original["arquivo"],
            "sha256": before_hash,
            "imutavel": True,
        },
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
    path.write_text(json.dumps(estado, ensure_ascii=False, indent=2), encoding="utf-8")
    estado["arquivo_estado"] = str(path)
    return estado


def confirmar_mapeamento_cenas(estado: dict, paginas_historia: list[int]) -> dict:
    """Converte somente páginas explicitamente aprovadas em cenas revisáveis."""
    paginas_ok = {int(x) for x in paginas_historia}
    if not paginas_ok:
        raise ValueError("Selecione ao menos uma página de história antes de confirmar o mapeamento.")

    por_pagina = {
        int(x.get("pagina")): x
        for x in (estado.get("paginas_texto_extraido") or [])
        if isinstance(x, dict)
    }
    faltantes = sorted(p for p in paginas_ok if p not in por_pagina)
    if faltantes:
        raise ValueError(f"Páginas não encontradas no PDF importado: {faltantes}")

    cenas = []
    for p in sorted(paginas_ok):
        texto = str(por_pagina[p].get("texto_extraido") or "").strip()
        if not texto:
            continue
        cenas.append({
            "numero": len(cenas) + 1,
            "texto": texto,
            "pagina_origem": p,
            "origem": "book_doctor_pdf",
        })
    if not cenas:
        raise ValueError("As páginas selecionadas não possuem texto extraível para revisão.")

    novo = deepcopy(estado)
    novo["cenas_texto"] = cenas
    novo["mapeamento_cenas_confirmado"] = True
    novo["status"] = "pronto_para_revisao_editorial"
    novo["mapeamento_confirmado_em"] = _now_iso()
    return novo


def gate_revisao_editorial(estado: dict) -> dict:
    """Gate fail-closed antes de qualquer chamada aos agentes editoriais."""
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
    """Executa apenas o diagnóstico editorial inicial, sem reescrever a obra.

    Ordem desta etapa:
    1. valida o gate e o hash do original;
    2. chama o Revisor Editorial independente;
    3. roda o Prompt-Mestre Compliance determinístico;
    4. devolve/salva um dossiê com problemas e próximos especialistas.

    O Editor de História e o Roteirista NÃO são chamados aqui. Assim, a autora
    vê o diagnóstico antes de aprovar qualquer alteração textual.
    """
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

    # O Revisor não tem autorização para reescrever a obra nesta fase.
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
        "heart_arc",
        "emotional_experience_engine",
        "prompt_master_compliance",
        "biblical_reference_validator",
        "emotional_color_director",
        "originality_guard",
    ])

    dossie = {
        "schema": "faithbloom.editorial-remaster-dossier.v1",
        "remaster_id": estado.get("remaster_id", ""),
        "titulo": estado.get("titulo", ""),
        "gerado_em": _now_iso(),
        "original_sha256": before_hash,
        "original_preservado": True,
        "revisor": {
            "status": "APROVADO" if revisado.get("revisao_aprovada") else "REVISAR",
            "notas": notas,
        },
        "prompt_mestre": compliance,
        "precisa_revisao_textual": precisa_revisao_textual,
        "proximos_especialistas": proximos,
        "alteracoes_aplicadas": False,
        "aprovacao_humana_pendente": True,
        "politica": (
            "Diagnóstico primeiro. Nenhuma cena é reescrita e nenhuma ilustração é regenerada "
            "até a autora revisar o dossiê e aprovar a próxima etapa."
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
