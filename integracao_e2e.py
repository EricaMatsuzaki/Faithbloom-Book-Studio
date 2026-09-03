"""FaithBloom 2.0 — Fase 11: integração e testes end-to-end.

Este módulo NÃO gasta créditos por padrão. Ele valida contratos entre módulos,
estrutura do estado, readiness do projeto de Natal, dependências e preflight.
Chamadas reais à OpenRouter só acontecem quando a interface pede explicitamente.
"""
from __future__ import annotations

import importlib
import os
import sys
import traceback
from copy import deepcopy
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any


@dataclass
class Check:
    nome: str
    ok: bool
    detalhe: str = ""
    nivel: str = "erro"  # erro | aviso | info

    def to_dict(self) -> dict:
        return asdict(self)


def _check(nome: str, ok: bool, detalhe: str = "", nivel: str = "erro") -> dict:
    return Check(nome, ok, detalhe, nivel).to_dict()


def verificar_imports() -> list[dict]:
    modulos = [
        "state", "state_colorir", "armazenamento", "storage_backend",
        "openrouter_client", "graph", "qualidade_impressao",
        "renderizador_editorial", "capa_profissional", "coloring_studio",
        "retomar_fluxo", "agents.editor_historia", "agents.ilustrador",
        "agents.personagens_variacoes", "agents.atividades_colorir",
        "agents.audiobook", "agents.dedicatoria", "agents.tradutor",
        "agents.sinopse", "agents.diagramador", "agents.capa",
    ]
    out = []
    for nome in modulos:
        try:
            importlib.import_module(nome)
            out.append(_check(f"Import {nome}", True, "OK", "info"))
        except Exception as exc:
            out.append(_check(f"Import {nome}", False, f"{type(exc).__name__}: {exc}"))
    return out


def verificar_dependencias() -> list[dict]:
    deps = {
        "streamlit": "streamlit",
        "langgraph": "langgraph",
        "requests": "requests",
        "Pillow": "PIL",
        "reportlab": "reportlab",
        "pypdf": "pypdf",
    }
    out=[]
    for rotulo, modulo in deps.items():
        try:
            m=importlib.import_module(modulo)
            versao=getattr(m, "__version__", "instalado")
            out.append(_check(rotulo, True, str(versao), "info"))
        except Exception as exc:
            out.append(_check(rotulo, False, str(exc)))
    return out


def verificar_ambiente() -> list[dict]:
    out=[]
    out.append(_check("Python", sys.version_info >= (3, 11), sys.version.split()[0], "info"))
    tem_key=bool(os.environ.get("OPENROUTER_API_KEY"))
    out.append(_check("OPENROUTER_API_KEY", tem_key,
                      "Configurada no ambiente." if tem_key else "Não configurada. Testes offline continuam disponíveis.",
                      "info" if tem_key else "aviso"))
    try:
        from storage_backend import backend_status
        status=backend_status()
        modo=status.get("mode") or status.get("modo") or str(status)
        out.append(_check("Storage backend", True, f"Ativo: {modo}", "info"))
    except Exception as exc:
        out.append(_check("Storage backend", False, str(exc)))
    return out


def validar_state_story(state: dict) -> list[dict]:
    out=[]
    obrigatorios=["titulo","colecao","versiculo_referencia","aprendizado_cristao","cenas_texto","personagens"]
    for campo in obrigatorios:
        valor=state.get(campo)
        out.append(_check(f"State · {campo}", bool(valor), "Preenchido" if valor else "Ausente/vazio"))

    cenas=state.get("cenas_texto") or []
    numeros=[c.get("numero") for c in cenas]
    sem_num=[i+1 for i,c in enumerate(cenas) if c.get("numero") is None]
    duplicados=sorted({n for n in numeros if n is not None and numeros.count(n)>1})
    ordem=[n for n in numeros if isinstance(n,int)]
    sequencial=ordem == list(range(1, len(ordem)+1)) if ordem else False
    out.append(_check("Cenas · numeração", not sem_num and not duplicados,
                      f"{len(cenas)} cenas; duplicados={duplicados or 'nenhum'}"))
    out.append(_check("Cenas · sequência 1..N", sequencial,
                      "Sequencial" if sequencial else f"Encontrada: {ordem[:30]}", "aviso" if not sequencial else "info"))

    personagens=state.get("personagens") or {}
    nomes=set(personagens.keys())
    faltas=[]
    avisos=[]
    protagonista_padrao=next((n for n,p in personagens.items() if p.get("papel")=="protagonista"), None)
    for cena in cenas:
        n=cena.get("numero","?")
        for campo in ("texto","emocao","figurino","contexto_visual"):
            if not cena.get(campo):
                faltas.append(f"Cena {n}: {campo}")
        foco=cena.get("personagem_principal") or protagonista_padrao
        if foco and foco not in nomes:
            avisos.append(f"Cena {n}: personagem_principal '{foco}' não está na biblioteca do livro")
    out.append(_check("Cenas · campos editoriais", not faltas,
                      "Todos preenchidos" if not faltas else "; ".join(faltas[:12]) + ("..." if len(faltas)>12 else "")))
    out.append(_check("Cenas · personagens referenciados", not avisos,
                      "Referências válidas" if not avisos else "; ".join(avisos[:10]), "aviso" if avisos else "info"))

    # readiness sem gerar imagens
    ps=list(personagens.values())
    aprovados=sum(bool(p.get("aparencia_aprovada") and p.get("imagem_referencia")) for p in ps)
    out.append(_check("Personagens · aprovação visual", bool(ps) and aprovados==len(ps),
                      f"{aprovados}/{len(ps)} aprovados", "aviso" if aprovados!=len(ps) else "info"))
    return out


def preparar_state_retomada(state: dict) -> dict:
    """Cópia segura com defaults usados pelo fluxo Retomar; não altera o módulo fonte."""
    s=deepcopy(dict(state))
    s.setdefault("cenas_imagem", [])
    s.setdefault("historico_imagens_cenas", {})
    s.setdefault("cenas_imagem_aprovadas", [])
    s.setdefault("imagens_cenas_enviadas", {})
    s.setdefault("instrucoes_imagens_cenas", {})
    s.setdefault("paginas_colorir", [])
    s.setdefault("dedicatoria_texto", "")
    s.setdefault("autora", "")
    s.setdefault("trim_largura_in", 8.5)
    s.setdefault("trim_altura_in", 8.5)
    for p in s.get("personagens", {}).values():
        p.setdefault("variacoes_visuais", [])
        p.setdefault("variacao_selecionada_id", "")
        p.setdefault("aparencia_aprovada", False)
        p.setdefault("dna_visual_travado", False)
    return s


def diagnostico_natal() -> dict:
    try:
        from historia_natal import ESTADO_INICIAL_NATAL
        s=preparar_state_retomada(ESTADO_INICIAL_NATAL)
        checks=validar_state_story(s)
        checks.append(_check("Natal · retomada sem Roteirista/Revisor", bool(s.get("revisao_aprovada")),
                             "Roteiro marcado como já revisado." if s.get("revisao_aprovada") else "Roteiro ainda não aprovado.",
                             "info" if s.get("revisao_aprovada") else "aviso"))
        checks.append(_check("Natal · pronto para etapa de personagens", bool(s.get("personagens")) and bool(s.get("cenas_texto")),
                             f"{len(s.get('personagens',{}))} personagens · {len(s.get('cenas_texto',[]))} cenas"))
        return {"ok": not any((not c["ok"] and c["nivel"]=="erro") for c in checks), "checks":checks, "state":s}
    except Exception as exc:
        return {"ok":False,"checks":[_check("Carregar historia_natal",False,f"{type(exc).__name__}: {exc}")],"state":{}}


def verificar_contratos_funcoes() -> list[dict]:
    """Confere que funções-chave das fases 2–9 continuam disponíveis."""
    contratos = {
        "agents.editor_historia": ["editar_cena","sugerir_versiculos","sugerir_licoes"],
        "agents.personagens_variacoes": ["gerar_multiplas_variacoes","gerar_variacao","aprovar_variacao"],
        "agents.ilustrador": ["gerar_cena_unica","criar_variacao_cena","aprovar_imagem_cena","restaurar_ultima_imagem_cena"],
        "qualidade_impressao": ["analisar_imagem","preflight_livro","analisar_pdf_miolo"],
        "renderizador_editorial": ["renderizar_miolo_pdf"],
        "capa_profissional": ["gerar_capa_print_ready","analisar_capa_pdf"],
        "armazenamento": ["salvar_livro","salvar_na_galeria","listar_galeria"],
    }
    out=[]
    for modulo, funcoes in contratos.items():
        try:
            m=importlib.import_module(modulo)
            ausentes=[f for f in funcoes if not callable(getattr(m,f,None))]
            out.append(_check(f"Contrato · {modulo}", not ausentes,
                              "OK" if not ausentes else f"Ausentes: {', '.join(ausentes)}"))
        except Exception as exc:
            out.append(_check(f"Contrato · {modulo}", False, str(exc)))
    return out


def rodar_diagnostico_completo() -> dict:
    grupos={
        "Ambiente": verificar_ambiente(),
        "Dependências": verificar_dependencias(),
        "Imports": verificar_imports(),
        "Contratos": verificar_contratos_funcoes(),
    }
    natal=diagnostico_natal()
    grupos["Livro de Natal"] = natal["checks"]
    todos=[c for cs in grupos.values() for c in cs]
    erros=[c for c in todos if not c["ok"] and c["nivel"]=="erro"]
    avisos=[c for c in todos if not c["ok"] and c["nivel"]=="aviso"]
    return {"ok":not erros,"erros":erros,"avisos":avisos,"grupos":grupos,"natal_state":natal.get("state",{})}


def testar_openrouter_texto() -> dict:
    """Teste mínimo e barato, só quando acionado manualmente pela autora."""
    if not os.environ.get("OPENROUTER_API_KEY"):
        return {"ok":False,"erro":"OPENROUTER_API_KEY não configurada."}
    try:
        from openrouter_client import chamar_llm
        r=chamar_llm(
            "Você é um teste técnico. Responda APENAS JSON válido.",
            'Retorne exatamente um objeto JSON com as chaves "status" e "mensagem"; status deve ser "ok".',
        )
        return {"ok": isinstance(r,dict) and r.get("status")=="ok", "resposta":r}
    except Exception as exc:
        return {"ok":False,"erro":f"{type(exc).__name__}: {exc}"}
