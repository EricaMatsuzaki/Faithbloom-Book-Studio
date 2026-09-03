"""FaithBloom 2.0 — Fase 14: fila persistente de produção.

A fila é *cooperativa*: cada item é concluído e persistido antes do próximo.
Isso permite pausar, continuar, cancelar e recuperar após reinício do Streamlit
sem repetir etapas já concluídas. Para um SaaS com muitos usuários/produção
24x7, a mesma API pode depois ser executada por um worker externo (Celery/RQ).
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Callable
import os
import uuid

from storage_backend import BACKEND, materializar_assets_em_objeto, persistir_assets_em_objeto
from controle_geracao import POLITICA, validar_lote_imagens, validar_lote_audio

JOB_PREFIX = "producao/jobs"

STATUS_ATIVOS = {"fila", "executando", "pausado"}
STATUS_FINAIS = {"concluido", "cancelado", "erro"}
ITEM_PENDENTE = {"pendente", "erro"}


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat()


def _path(job_id: str) -> str:
    return f"{JOB_PREFIX}/{job_id}.json"


def salvar_job(job: dict) -> dict:
    job = deepcopy(job)
    job["atualizado_em"] = _agora()
    BACKEND.put_json(_path(job["id"]), persistir_assets_em_objeto(job, f"assets/jobs/{job['id']}"))
    return carregar_job(job["id"])


def carregar_job(job_id: str) -> dict:
    dados = BACKEND.get_json(_path(job_id), {}) or {}
    return materializar_assets_em_objeto(dados)


def listar_jobs(limite: int = 100) -> list[dict]:
    out=[]
    for path in BACKEND.list(JOB_PREFIX):
        if not path.endswith(".json"):
            continue
        dados = materializar_assets_em_objeto(BACKEND.get_json(path, {}) or {})
        if dados:
            out.append(dados)
    return sorted(out, key=lambda j: j.get("criado_em", ""), reverse=True)[:limite]


def criar_job(
    nome: str,
    tipo: str,
    itens: list[dict],
    state: dict | None = None,
    metadata: dict | None = None,
) -> dict:
    if not itens:
        raise ValueError("O job precisa ter pelo menos um item.")
    job_id=uuid.uuid4().hex
    normalizados=[]
    for i,item in enumerate(itens, start=1):
        x=deepcopy(item)
        x.setdefault("id", f"item-{i:04d}")
        x.setdefault("status", "pendente")
        x.setdefault("tentativas", 0)
        x.setdefault("erro", "")
        normalizados.append(x)
    job={
        "id":job_id,
        "nome":nome or "Produção sem nome",
        "tipo":tipo,
        "status":"fila",
        "criado_em":_agora(),
        "atualizado_em":_agora(),
        "iniciado_em":"",
        "finalizado_em":"",
        "itens":normalizados,
        "state":deepcopy(state or {}),
        "metadata":deepcopy(metadata or {}),
        "ultimo_erro":"",
    }
    return salvar_job(job)


def criar_job_ilustracoes(state: dict, somente_nao_aprovadas: bool = True) -> dict:
    """Cria fila de cenas sem gerar nada e sem aprovar automaticamente."""
    existentes={int(i.get("numero")):i for i in (state.get("cenas_imagem") or []) if i.get("numero") is not None}
    itens=[]
    for cena in state.get("cenas_texto") or []:
        n=int(cena["numero"])
        atual=existentes.get(n)
        if somente_nao_aprovadas and atual and atual.get("aprovado"):
            continue
        itens.append({"kind":"cena_imagem","numero":n,"status":"pendente"})
    if not itens:
        raise ValueError("Não há cenas pendentes para colocar na fila.")
    return criar_job(
        nome=f"Ilustrações · {state.get('titulo','Livro')}",
        tipo="story_ilustracoes",
        itens=itens,
        state=state,
        metadata={"titulo":state.get("titulo",""),"colecao":state.get("colecao","")},
    )


def resumo_job(job: dict) -> dict[str, Any]:
    itens=job.get("itens") or []
    total=len(itens)
    concluidos=sum(1 for i in itens if i.get("status")=="concluido")
    erros=sum(1 for i in itens if i.get("status")=="erro")
    pendentes=sum(1 for i in itens if i.get("status") in {"pendente","erro"})
    return {
        "total":total,
        "concluidos":concluidos,
        "pendentes":pendentes,
        "erros":erros,
        "percentual":0.0 if not total else (concluidos/total)*100,
    }


def pausar_job(job_id: str) -> dict:
    job=carregar_job(job_id)
    if job.get("status") not in STATUS_FINAIS:
        job["status"]="pausado"
    return salvar_job(job)


def continuar_job(job_id: str) -> dict:
    job=carregar_job(job_id)
    if job.get("status") in {"pausado","erro","fila"}:
        job["status"]="fila"
        job["ultimo_erro"]=""
    return salvar_job(job)


def cancelar_job(job_id: str) -> dict:
    job=carregar_job(job_id)
    if job.get("status") not in STATUS_FINAIS:
        job["status"]="cancelado"
        job["finalizado_em"]=_agora()
    return salvar_job(job)


def recuperar_jobs_interrompidos() -> list[str]:
    """Após restart, jobs deixados como executando voltam para pausado, nunca repetem item concluído."""
    recuperados=[]
    for job in listar_jobs(1000):
        if job.get("status")=="executando":
            job["status"]="pausado"
            job["ultimo_erro"]="Sessão anterior foi interrompida. Job recuperado e pausado com segurança."
            salvar_job(job)
            recuperados.append(job["id"])
    return recuperados


def _proximo_item(job: dict) -> dict | None:
    return next((i for i in job.get("itens",[]) if i.get("status") in ITEM_PENDENTE), None)


def processar_proximo(job_id: str, executor: Callable[[dict, dict], tuple[dict, dict]]) -> dict:
    """Executa exatamente um item. executor(job, item) -> (job_state_atualizado, item_updates)."""
    job=carregar_job(job_id)
    if job.get("status")=="pausado":
        return job
    if job.get("status") in STATUS_FINAIS:
        return job
    item=_proximo_item(job)
    if not item:
        job["status"]="concluido"; job["finalizado_em"]=_agora()
        return salvar_job(job)
    if not job.get("iniciado_em"):
        job["iniciado_em"]=_agora()
    job["status"]="executando"
    item["status"]="executando"
    item["tentativas"]=int(item.get("tentativas",0))+1
    salvar_job(job)  # checkpoint antes da chamada paga
    try:
        novo_state, updates = executor(job, deepcopy(item))
        job=carregar_job(job_id)  # respeita eventual cancelamento entre checkpoints
        if job.get("status")=="cancelado":
            return job
        job["state"]=novo_state
        alvo=next(i for i in job["itens"] if i["id"]==item["id"])
        alvo.update(updates or {})
        alvo["status"]="concluido"
        alvo["erro"]=""
        alvo["concluido_em"]=_agora()
        job["ultimo_erro"]=""
        if not _proximo_item(job):
            job["status"]="concluido"; job["finalizado_em"]=_agora()
        else:
            job["status"]="fila"
        return salvar_job(job)
    except Exception as exc:
        job=carregar_job(job_id)
        alvo=next(i for i in job["itens"] if i["id"]==item["id"])
        alvo["status"]="erro"
        alvo["erro"]=str(exc)[:400]
        job["ultimo_erro"]=str(exc)[:400]
        job["status"]="pausado"  # falha pausa o lote; usuário decide quando retomar
        return salvar_job(job)


def processar_lote(job_id: str, executor: Callable[[dict, dict], tuple[dict, dict]], quantidade: int | None = None) -> dict:
    job=carregar_job(job_id)
    if job.get("tipo") == "audiobook_tts":
        quantidade=int(quantidade or POLITICA.max_audio_segmentos_lote)
        validar_lote_audio(quantidade)
    else:
        quantidade=int(quantidade or POLITICA.max_imagens_lote)
        validar_lote_imagens(quantidade)
    for _ in range(quantidade):
        if job.get("status") in {"pausado","cancelado","concluido","erro"}:
            break
        job=processar_proximo(job_id, executor)
    return job


def executor_ilustracao_story(gerar_imagem):
    """Cria executor compatível com processar_proximo/lote, usando a lógica cena-a-cena da Fase 4."""
    from retomar_fluxo import gerar_cena_unica, obter_imagem_cena
    def _exec(job: dict, item: dict) -> tuple[dict, dict]:
        state=deepcopy(job.get("state") or {})
        n=int(item["numero"])
        instrucao=(item.get("instrucao") or "").strip()
        gerar_cena_unica(state,n,gerar_imagem,instrucao)
        atual=obter_imagem_cena(state,n) or {}
        return state, {"caminho_arquivo":atual.get("caminho_arquivo",""),"origem":atual.get("origem","")}
    return _exec
