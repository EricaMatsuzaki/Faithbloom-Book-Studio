"""FaithBloom 2.0 — Fase 14: fila persistente de produção.

A fila é *cooperativa*: um claim persistido permite somente um item em voo por
job. Chamadas cujo resultado não foi confirmado exigem conferência, nunca
reenvio automático. O piloto legado serializa os escritores no mesmo host;
isso não constitui uma fila distribuída nem habilita o SaaS comercial.
"""
from __future__ import annotations

from copy import deepcopy
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Callable
import os
import socket
import threading
import uuid

from storage_backend import BACKEND, materializar_assets_em_objeto, persistir_assets_em_objeto
from storage_backend import StorageConflict
from storage_updates import update_json_document
from controle_geracao import POLITICA, validar_lote_imagens, validar_lote_audio

JOB_PREFIX = "producao/jobs"

STATUS_ATIVOS = {"fila", "executando", "pausado"}
STATUS_FINAIS = {"concluido", "cancelado", "erro"}
ITEM_PENDENTE = {"pendente", "erro"}
ITEM_INDEFINIDO = {"executando", "incerto"}
_ACTIVE_CLAIMS: set[str] = set()
_ACTIVE_GUARD = threading.Lock()


class QueueCheckpointError(RuntimeError):
    """Retain an already-received result when its final checkpoint fails."""
    def __init__(self, message, *, job_id, attempt_token, state, item_updates):
        super().__init__(message)
        self.job_id = job_id
        self.attempt_token = attempt_token
        self.state = deepcopy(state)
        self.item_updates = deepcopy(item_updates)


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat()


def _path(job_id: str) -> str:
    return f"{JOB_PREFIX}/{job_id}.json"


def _indefinido(job: dict) -> bool:
    return bool(job.get("execution_claim")) or any(
        item.get("status") in ITEM_INDEFINIDO for item in job.get("itens", [])
    )


@contextmanager
def _claim_owner(token):
    with _ACTIVE_GUARD:
        _ACTIVE_CLAIMS.add(token)
    try:
        yield
    finally:
        with _ACTIVE_GUARD:
            _ACTIVE_CLAIMS.discard(token)


def _owner_ativo(job):
    """Conservative local liveness, never an expiring permission to buy again."""
    claim = job.get('execution_claim') or {}
    if not claim:
        return False
    with _ACTIVE_GUARD:
        if claim.get('token') in _ACTIVE_CLAIMS:
            return True
    if claim.get('host') != socket.gethostname():
        return claim.get('owner_active') is not False
    pid = claim.get('pid')
    if pid == os.getpid():
        return False
    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
        return claim.get('owner_active') is not False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except OSError:
        return True
    return True


def _validar_job(job: dict, job_id: str) -> None:
    if not isinstance(job, dict) or job.get("id") != job_id or not isinstance(job.get("itens"), list):
        raise ValueError("A fila salva não está disponível ou possui um registro inválido.")


def _atualizar_job(job_id: str, mutator) -> dict:
    """Only JSON transitions run in the retryable callback; media stays outside."""
    now = _agora()
    def update(current):
        _validar_job(current, job_id)
        updated = mutator(deepcopy(current))
        _validar_job(updated, job_id)
        if updated == current:
            return current
        updated["atualizado_em"] = now
        updated["revision"] = int(current.get("revision", 0)) + 1
        return updated
    saved = update_json_document(BACKEND, _path(job_id), update, None, allow_legacy_pilot=True)
    return materializar_assets_em_objeto(saved)


def salvar_job(job: dict) -> dict:
    """Create or save an exact snapshot; stale replacements cannot erase claims."""
    job = deepcopy(job)
    job["atualizado_em"] = _agora()
    expected = int(job.get("revision", 0))
    prepared = persistir_assets_em_objeto(job, f"assets/jobs/{job['id']}")
    def save(current):
        if current is not None:
            _validar_job(current, job["id"])
            if int(current.get("revision", 0)) != expected or _indefinido(current):
                raise StorageConflict(expected, current.get("revision", 0))
        elif expected:
            raise StorageConflict(expected, None)
        updated = deepcopy(prepared)
        updated["revision"] = expected + 1
        return updated
    saved = update_json_document(BACKEND, _path(job["id"]), save, None, allow_legacy_pilot=True)
    return materializar_assets_em_objeto(saved)


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
    state = deepcopy(state)
    state.setdefault('book_id', uuid.uuid4().hex)
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
    def pause(job):
        if job.get("status") not in STATUS_FINAIS:
            job["status"] = "pausado"
        return job
    return _atualizar_job(job_id, pause)


def continuar_job(job_id: str) -> dict:
    def resume(job):
        if not _indefinido(job) and job.get("status") in {"pausado", "erro", "fila"}:
            job["status"] = "fila"
            job["ultimo_erro"] = ""
        return job
    return _atualizar_job(job_id, resume)


def cancelar_job(job_id: str) -> dict:
    now = _agora()
    def cancel(job):
        if job.get("status") not in STATUS_FINAIS:
            job["status"] = "cancelado"
            job["finalizado_em"] = now
        return job
    return _atualizar_job(job_id, cancel)


def recuperar_jobs_interrompidos(job_id: str | None = None, *, confirmed: bool = False,
                                attempt_token: str | None = None, shutdown_note: str = '') -> list[str]:
    """Flag interrupted work as uncertain; shutdown evidence never permits a resend.

    A claimed attempt requires its exact job and token. An active foreign host
    cannot be probed locally: the operator must additionally record evidence of
    that owner's shutdown. No attestation can override a live local owner.
    """
    if confirmed is not True:
        raise PermissionError("Confirme a interrupção da execução antes de encaminhar a tentativa para conferência.")
    jobs = [carregar_job(job_id)] if job_id is not None else listar_jobs(1000)
    recovered = []
    note = str(shutdown_note or '').strip()
    def validate_owner(job):
        claim = job.get('execution_claim') or {}
        if claim and (job_id != job.get('id') or not attempt_token or claim.get('token') != attempt_token):
            raise PermissionError('Informe a fila e a tentativa exatas cujo responsável foi encerrado. Reabra a fila.')
        if not _owner_ativo(job):
            return False
        # Even a foreign-looking record cannot override a locally held token.
        with _ACTIVE_GUARD:
            locally_held = claim.get('token') in _ACTIVE_CLAIMS
        if claim.get('host') == socket.gethostname() or locally_held:
            raise PermissionError('A execução ainda possui um responsável ativo. Aguarde seu término antes de recuperar a tentativa.')
        if not note:
            raise PermissionError('Registre a evidência de encerramento do processo no outro host para esta tentativa exata.')
        return True
    for snapshot in jobs:
        _validar_job(snapshot, snapshot.get('id') if job_id is None else job_id)
        if job_id is None and snapshot.get('execution_claim'):
            # Bulk recovery has no exact-attempt shutdown attestation.
            continue
        validate_owner(snapshot)
        expected_revision = int(snapshot.get('revision', 0))
        legacy_tokens = {item['id']: uuid.uuid4().hex for item in snapshot.get('itens', [])}
        now = _agora()
        def recover(job):
            if int(job.get('revision', 0)) != expected_revision:
                raise StorageConflict(expected_revision, job.get('revision', 0))
            foreign_shutdown = validate_owner(job)
            running = [item for item in job["itens"] if item.get("status") == "executando"]
            if not running and job.get("status") != "executando":
                return job
            for item in running:
                item["status"] = "incerto"
                item.setdefault('attempt_token', legacy_tokens[item['id']])
                item["erro"] = "A chamada pode ter chegado ao provedor. Confira o resultado e o custo antes de qualquer nova geração."
            if job.get('execution_claim'):
                if foreign_shutdown:
                    claim = job['execution_claim']
                    job.setdefault('shutdown_attestations', []).append({
                        'job_id': job['id'], 'attempt_token': attempt_token,
                        'host': claim.get('host'), 'pid': claim.get('pid'),
                        'note': note[:1000], 'at': now})
                job['execution_claim']['owner_active'] = False
            if job.get("status") not in STATUS_FINAIS:
                job["status"] = "pausado"
            job["ultimo_erro"] = "Execução interrompida: confira as tentativas no provedor. Nenhuma chamada será reenviada automaticamente."
            return job
        updated = _atualizar_job(snapshot["id"], recover)
        if updated.get("revision", 0) != snapshot.get("revision", 0):
            recovered.append(snapshot["id"])
    return recovered


def reconciliar_item_job(job_id: str, item_id: str, *, attempt_token: str,
                        provider_outcome: str, note: str, confirmed: bool = False,
                        recovered_state: dict | None = None, item_updates: dict | None = None) -> dict:
    """Record provider evidence; rearming never executes or restores old consent."""
    if confirmed is not True or not str(note or '').strip():
        raise PermissionError('Confirme o resultado no provedor e registre a justificativa da conferência.')
    if provider_outcome not in {'not_sent', 'failed', 'succeeded'}:
        raise ValueError('Resultado de conferência inválido.')
    if not attempt_token:
        raise ValueError('Informe a tentativa exata que foi conferida.')
    snapshot = carregar_job(job_id)
    if _owner_ativo(snapshot):
        raise PermissionError('A execução ainda está ativa. Aguarde seu término antes de conferir a tentativa.')
    expected_revision = int(snapshot.get('revision', 0))
    prepared_state = prepared_updates = None
    if provider_outcome == 'succeeded':
        if not isinstance(recovered_state, dict):
            raise ValueError('Recupere o resultado recebido antes de concluir esta tentativa.')
        prepared_state = persistir_assets_em_objeto(recovered_state, f'assets/jobs/{job_id}')
        prepared_updates = persistir_assets_em_objeto(item_updates or {}, f'assets/jobs/{job_id}')
    now = _agora()
    evidence = {'attempt_token': attempt_token, 'provider_outcome': provider_outcome,
                'note': str(note).strip()[:1000], 'at': now}
    def reconcile(job):
        if int(job.get('revision', 0)) != expected_revision:
            raise StorageConflict(expected_revision, job.get('revision', 0))
        target = next((item for item in job['itens'] if item['id'] == item_id), None)
        if not target or target.get('status') != 'incerto' or target.get('attempt_token') != attempt_token:
            raise PermissionError('Esta tentativa não corresponde ao item incerto atual. Reabra a fila.')
        target.setdefault('attempt_history', []).append(deepcopy(evidence))
        if provider_outcome == 'succeeded':
            job['state'] = deepcopy(prepared_state)
            target.update(deepcopy(prepared_updates))
            target.update(id=item_id, attempt_token=attempt_token, status='concluido', erro='', concluido_em=now)
        else:
            target.update(status='pendente', erro='')
            target.pop('attempt_token', None)
        if (job.get('execution_claim') or {}).get('token') == attempt_token:
            job.pop('execution_claim', None)
        if job.get('status') not in STATUS_FINAIS:
            job['status'] = 'pausado'
        job['ultimo_erro'] = ''
        return job
    return _atualizar_job(job_id, reconcile)


def _proximo_item(job: dict) -> dict | None:
    return next((i for i in job.get("itens",[]) if i.get("status") in ITEM_PENDENTE), None)


def processar_proximo(job_id: str, executor: Callable[[dict, dict], tuple[dict, dict]]) -> dict:
    """Executa exatamente um item. executor(job, item) -> (job_state_atualizado, item_updates)."""
    job=carregar_job(job_id)
    _validar_job(job, job_id)
    if job.get("status") in STATUS_FINAIS | {"pausado", "executando"} or _indefinido(job):
        return job
    item=_proximo_item(job)
    if not item:
        now = _agora()
        def finish_empty(current):
            if current.get("status") in STATUS_FINAIS | {"pausado", "executando"} or _indefinido(current):
                return current
            if all(row.get("status") == "concluido" for row in current["itens"]):
                current.update(status="concluido", finalizado_em=now)
            return current
        return _atualizar_job(job_id, finish_empty)
    expected_revision = int(job.get("revision", 0))
    preflight = getattr(executor, 'preflight', None)
    if callable(preflight):
        try:
            preflight(job, deepcopy(item))
        except Exception as exc:
            error = str(exc)[:400]
            def reject(current):
                if int(current.get("revision", 0)) != expected_revision or _indefinido(current):
                    return current
                target = next(row for row in current["itens"] if row["id"] == item["id"])
                target.update(status="erro", erro=error)
                current.update(status="pausado", ultimo_erro=error)
                return current
            return _atualizar_job(job_id, reject)
    token = uuid.uuid4().hex
    with _claim_owner(token):
        return _executar_item_claim(job_id, executor, job, item, expected_revision, token)


def _executar_item_claim(job_id, executor, job, item, expected_revision, token):
    now = _agora()
    owner = {'host': socket.gethostname(), 'pid': os.getpid(), 'owner_active': True}
    def claim(current):
        if int(current.get("revision", 0)) != expected_revision:
            return current
        if current.get("status") in STATUS_FINAIS | {"pausado", "executando"} or _indefinido(current):
            return current
        target = _proximo_item(current)
        if not target or target["id"] != item["id"]:
            return current
        target.update(status="executando", tentativas=int(target.get("tentativas", 0)) + 1,
                      attempt_token=token)
        current["execution_claim"] = {"token": token, "item_id": target["id"], "started_at": now, **owner}
        current["status"] = "executando"
        current["iniciado_em"] = current.get("iniciado_em") or now
        return current
    # A failed or uncertain claim acknowledgement exits before the executor.
    job = _atualizar_job(job_id, claim)
    if (job.get("execution_claim") or {}).get("token") != token:
        return job
    item = next(row for row in job["itens"] if row["id"] == item["id"])
    def failure(current, error):
        if (current.get("execution_claim") or {}).get("token") != token:
            return current
        target = next(row for row in current["itens"] if row["id"] == item["id"])
        if target.get("attempt_token") != token or target.get("status") not in ITEM_INDEFINIDO:
            return current
        target.update(status="incerto", erro=error)
        current['execution_claim']['owner_active'] = False
        current["ultimo_erro"] = error
        if current.get("status") not in STATUS_FINAIS:
            current["status"] = "pausado"
        return current
    try:
        novo_state, updates = executor(job, deepcopy(item))
    except Exception as exc:
        error = "A tentativa exige conferência no provedor antes de gerar novamente. " + str(exc)[:300]
        return _atualizar_job(job_id, lambda current: failure(current, error))
    try:
        prepared_state = persistir_assets_em_objeto(novo_state, f"assets/jobs/{job_id}")
        prepared_updates = persistir_assets_em_objeto(updates or {}, f"assets/jobs/{job_id}")
        completed_at = _agora()
        def complete(current):
            if (current.get("execution_claim") or {}).get("token") != token:
                return current
            target = next(row for row in current["itens"] if row["id"] == item["id"])
            if target.get("attempt_token") != token or target.get("status") not in ITEM_INDEFINIDO:
                return current
            current["state"] = deepcopy(prepared_state)
            target.update(deepcopy(prepared_updates))
            target.update(id=item["id"], attempt_token=token, status="concluido", erro="", concluido_em=completed_at)
            current.pop("execution_claim", None)
            current["ultimo_erro"] = ""
            if current.get("status") not in STATUS_FINAIS | {"pausado"}:
                if all(row.get("status") == "concluido" for row in current["itens"]):
                    current.update(status="concluido", finalizado_em=completed_at)
                else:
                    current["status"] = "fila"
            return current
        return _atualizar_job(job_id, complete)
    except Exception as exc:
        try:
            _atualizar_job(job_id, lambda current: failure(current, "Resultado recebido; a persistência precisa de conferência. Nenhuma geração foi reenviada."))
        except Exception:
            pass  # The pre-call claim remains durable and prevents a resend.
        raise QueueCheckpointError("O resultado foi recebido, mas seu checkpoint exige recuperação. Nenhuma geração foi reenviada.",
            job_id=job_id, attempt_token=token, state=novo_state, item_updates=updates or {}) from exc


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


def preparar_revisao_emocional_job(job_id: str) -> dict:
    """Give a legacy snapshot a durable identity, without granting approval."""
    job = carregar_job(job_id)
    if job.get('tipo') != 'story_ilustracoes' or not job.get('state', {}).get('cenas_texto'):
        raise ValueError('Esta fila não possui uma história para revisar.')
    identity = uuid.uuid4().hex
    def prepare(current):
        if _indefinido(current):
            raise PermissionError('A execução desta fila ainda exige conferência antes de alterar sua fonte.')
        current['state'].setdefault('book_id', identity)
        return current
    return _atualizar_job(job_id, prepare)


def aplicar_mapa_emocional_job(job_id: str, approved: dict, *, expected_source_fingerprint: str) -> dict:
    """Apply only a reviewed exact snapshot; completed items/assets stay intact."""
    from emotional_visual_binding import book_emotional_review_key
    from emotional_review_ui import merge_emotional_approval
    job = carregar_job(job_id)
    if job.get('tipo') != 'story_ilustracoes':
        raise ValueError('Esta fila não é uma fila de ilustrações de história.')
    if not expected_source_fingerprint or book_emotional_review_key(job.get('state') or {}) != expected_source_fingerprint:
        raise PermissionError('A fonte desta fila mudou durante a revisão. Reabra o mapa a partir da fila atual.')
    expected_revision = int(job.get('revision', 0))
    prepared = persistir_assets_em_objeto(merge_emotional_approval(job['state'], approved), f'assets/jobs/{job_id}')
    def apply(current):
        if int(current.get('revision', 0)) != expected_revision:
            raise StorageConflict(expected_revision, current.get('revision', 0))
        if _indefinido(current):
            raise PermissionError('A execução desta fila ainda exige conferência antes de alterar sua fonte.')
        current['state'] = deepcopy(prepared)
        return current
    return _atualizar_job(job_id, apply)


def executor_ilustracao_story(gerar_imagem, *, consent_confirmed=False, job_id=None,
                              source_fingerprint=None, max_items=1):
    """Cria executor compatível com processar_proximo/lote, usando a lógica cena-a-cena da Fase 4."""
    from agents.ilustrador import gerar_cena_unica, obter_imagem_cena
    from emotional_visual_binding import require_book_emotional_map, book_emotional_review_key
    from governance_callbacks import source_uses_personal_data
    remaining = int(max_items)
    if remaining < 1:
        raise ValueError('Confirme uma quantidade positiva de cenas para esta ação.')
    def _preflight(job, item):
        state = job.get('state') or {}
        if job_id is not None and job.get('id') != job_id:
            raise PermissionError('A autorização desta ação pertence a outra fila.')
        if source_fingerprint is not None and book_emotional_review_key(state) != source_fingerprint:
            raise PermissionError('O conteúdo da fila mudou. Confirme novamente esta geração.')
        require_book_emotional_map(state)
        if source_uses_personal_data(state) and consent_confirmed is not True:
            raise PermissionError('Autorize o envio dos dados pessoais para esta execução da fila.')
        if remaining < 1:
            raise PermissionError('A autorização deste lote já foi utilizada. Confirme uma nova execução.')
        # Scene AutoSave writes back to its Book Master. Validate the exact
        # durable source before allowing it to replace anything there.
        reference = str(state.get('storage_path') or '')
        if not reference:
            raise PermissionError('Revise e salve o mapa no Book Master desta fila antes de gerar imagens.')
        import storage_backend as storage
        canonical = reference if storage.is_storage_uri(reference) else storage.storage_uri(reference)
        saved = BACKEND.get_json(storage.uri_to_path(canonical), None)
        if not isinstance(saved, dict) or not saved:
            raise PermissionError('O Book Master exato desta fila não está disponível. Reabra a fonte antes de gerar imagens.')
        saved = materializar_assets_em_objeto(saved)
        saved['storage_path'] = canonical
        require_book_emotional_map(saved)
        current = deepcopy(state)
        current['storage_path'] = canonical
        if book_emotional_review_key(saved) != book_emotional_review_key(current):
            raise PermissionError('A narrativa, os personagens, o estilo ou o mapa do Book Master mudou. Recrie a fila a partir da versão atual.')
    def _exec(job: dict, item: dict) -> tuple[dict, dict]:
        nonlocal remaining
        _preflight(job, item)
        remaining -= 1
        state=deepcopy(job.get("state") or {})
        n=int(item["numero"])
        instrucao=(item.get("instrucao") or "").strip()
        gerar_cena_unica(state,n,gerar_imagem,instrucao,consent_confirmed=consent_confirmed)
        atual=obter_imagem_cena(state,n) or {}
        return state, {"caminho_arquivo":atual.get("caminho_arquivo",""),"origem":atual.get("origem","")}
    _exec.preflight = _preflight
    return _exec
