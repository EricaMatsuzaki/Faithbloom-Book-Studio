"""FaithBloom 2.0 — Fase 13: custos, segurança e controle de geração.

Objetivos:
- evitar cliques duplicados e rajadas acidentais de chamadas pagas;
- registrar cada chamada de IA sem salvar prompts completos nem segredos;
- impor limites de lote e orçamento diário configuráveis;
- oferecer estimativas conservadoras quando o provedor não devolve custo;
- centralizar retry/backoff e mensagens de erro sanitizadas.

Os valores de custo abaixo são *estimativas configuráveis*, não preços oficiais.
Use Secrets/variáveis de ambiente para ajustar conforme os modelos/provedores escolhidos.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any
import json
import os
import threading
import time
import uuid

DATA_DIR = Path(os.environ.get("FAITHBLOOM_RUNTIME_DIR", ".faithbloom_data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
LOG_PATH = DATA_DIR / "geracoes.jsonl"

_LOCK = threading.Lock()
_IN_FLIGHT: set[str] = set()
_RECENT: dict[str, float] = {}


def _env_float(nome: str, padrao: float) -> float:
    try:
        return float(os.environ.get(nome, padrao))
    except (TypeError, ValueError):
        return padrao


def _env_int(nome: str, padrao: int) -> int:
    try:
        return int(os.environ.get(nome, padrao))
    except (TypeError, ValueError):
        return padrao


@dataclass(frozen=True)
class PoliticaGeracao:
    orcamento_diario_usd: float = _env_float("FAITHBLOOM_BUDGET_DIARIO_USD", 25.0)
    max_imagens_lote: int = _env_int("FAITHBLOOM_MAX_IMAGENS_LOTE", 5)
    max_audio_segmentos_lote: int = _env_int("FAITHBLOOM_MAX_AUDIO_SEGMENTOS_LOTE", 10)
    cooldown_duplicado_seg: float = _env_float("FAITHBLOOM_COOLDOWN_DUPLICADO_SEG", 3.0)
    tentativas_http: int = _env_int("FAITHBLOOM_HTTP_RETRIES", 3)
    backoff_inicial_seg: float = _env_float("FAITHBLOOM_HTTP_BACKOFF_SEG", 1.25)
    estimativa_texto_usd: float = _env_float("FAITHBLOOM_EST_TEXTO_USD", 0.03)
    estimativa_imagem_usd: float = _env_float("FAITHBLOOM_EST_IMAGEM_USD", 0.08)
    estimativa_audio_min_usd: float = _env_float("FAITHBLOOM_EST_AUDIO_MIN_USD", 0.03)


POLITICA = PoliticaGeracao()


class GeracaoBloqueada(RuntimeError):
    """A chamada não foi executada porque uma proteção do FaithBloom bloqueou-a."""


@dataclass
class RegistroGeracao:
    request_id: str
    criado_em: str
    modalidade: str
    modelo: str
    status: str
    assinatura: str
    estimativa_usd: float
    custo_reportado_usd: float | None = None
    duracao_ms: int | None = None
    detalhe: str = ""


def assinatura_requisicao(modalidade: str, modelo: str, conteudo: str) -> str:
    base = f"{modalidade}|{modelo}|{conteudo}".encode("utf-8", errors="ignore")
    return sha256(base).hexdigest()[:24]


def _gravar(registro: RegistroGeracao) -> None:
    # O log nunca recebe prompt completo, API key, headers ou payload bruto.
    with _LOCK:
        with LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(registro), ensure_ascii=False) + "\n")


def ler_registros(limite: int = 250) -> list[dict[str, Any]]:
    if not LOG_PATH.exists():
        return []
    linhas = LOG_PATH.read_text(encoding="utf-8").splitlines()[-limite:]
    saida=[]
    for linha in linhas:
        try:
            saida.append(json.loads(linha))
        except json.JSONDecodeError:
            continue
    return saida


def custo_hoje_usd() -> float:
    hoje = datetime.now(timezone.utc).date().isoformat()
    total=0.0
    for r in ler_registros(5000):
        if not str(r.get("criado_em", "")).startswith(hoje):
            continue
        if r.get("status") != "sucesso":
            continue
        custo = r.get("custo_reportado_usd")
        if custo is None:
            custo = r.get("estimativa_usd", 0)
        try:
            total += float(custo or 0)
        except (TypeError, ValueError):
            pass
    return round(total, 6)


def estimar_custo(modalidade: str, quantidade: int = 1, minutos_audio: float = 0.0) -> float:
    quantidade=max(1,int(quantidade or 1))
    if modalidade == "imagem":
        return round(POLITICA.estimativa_imagem_usd * quantidade, 6)
    if modalidade == "audio":
        mins=max(0.1,float(minutos_audio or 0.1))
        return round(POLITICA.estimativa_audio_min_usd * mins * quantidade, 6)
    return round(POLITICA.estimativa_texto_usd * quantidade, 6)


def validar_lote_imagens(quantidade: int) -> None:
    if quantidade < 1:
        raise GeracaoBloqueada("O lote precisa ter pelo menos 1 imagem.")
    if quantidade > POLITICA.max_imagens_lote:
        raise GeracaoBloqueada(
            f"Lote de {quantidade} imagens bloqueado. Limite de segurança atual: "
            f"{POLITICA.max_imagens_lote}. Gere em lotes menores para validar qualidade e custo."
        )




def validar_lote_audio(quantidade: int) -> None:
    if quantidade < 1:
        raise GeracaoBloqueada("O lote precisa ter pelo menos 1 segmento de áudio.")
    if quantidade > POLITICA.max_audio_segmentos_lote:
        raise GeracaoBloqueada(
            f"Lote de {quantidade} segmentos de áudio bloqueado. Limite de segurança atual: "
            f"{POLITICA.max_audio_segmentos_lote}. Gere em lotes menores para validar voz, pronúncia e custo."
        )

def validar_orcamento(estimativa_usd: float) -> None:
    usado=custo_hoje_usd()
    if usado + estimativa_usd > POLITICA.orcamento_diario_usd:
        raise GeracaoBloqueada(
            f"Orçamento diário protegido. Uso estimado hoje: US${usado:.2f}; "
            f"nova chamada: ~US${estimativa_usd:.2f}; limite: US${POLITICA.orcamento_diario_usd:.2f}."
        )


def iniciar_requisicao(modalidade: str, modelo: str, conteudo_assinatura: str,
                       estimativa_usd: float | None = None) -> tuple[str,str,float,float]:
    estimativa = estimativa_usd if estimativa_usd is not None else estimar_custo(modalidade)
    validar_orcamento(estimativa)
    assinatura = assinatura_requisicao(modalidade, modelo, conteudo_assinatura)
    agora=time.monotonic()
    with _LOCK:
        if assinatura in _IN_FLIGHT:
            raise GeracaoBloqueada("Esta mesma geração já está em andamento. Aguarde o resultado antes de clicar novamente.")
        ultimo=_RECENT.get(assinatura)
        if ultimo is not None and agora-ultimo < POLITICA.cooldown_duplicado_seg:
            restante=POLITICA.cooldown_duplicado_seg-(agora-ultimo)
            raise GeracaoBloqueada(f"Clique duplicado bloqueado. Aguarde cerca de {restante:.1f}s e tente novamente se desejar.")
        _IN_FLIGHT.add(assinatura)
        _RECENT[assinatura]=agora
    return uuid.uuid4().hex, assinatura, float(estimativa), time.perf_counter()


def finalizar_requisicao(request_id: str, assinatura: str, modalidade: str, modelo: str,
                         estimativa_usd: float, inicio_perf: float, status: str,
                         custo_reportado_usd: float | None = None, detalhe: str = "") -> None:
    with _LOCK:
        _IN_FLIGHT.discard(assinatura)
    # Remover qualquer sequência que pareça uma chave OpenRouter de detalhes/logs.
    detalhe = sanitizar_texto(detalhe)[:500]
    _gravar(RegistroGeracao(
        request_id=request_id,
        criado_em=datetime.now(timezone.utc).isoformat(),
        modalidade=modalidade,
        modelo=modelo,
        status=status,
        assinatura=assinatura,
        estimativa_usd=round(float(estimativa_usd),6),
        custo_reportado_usd=None if custo_reportado_usd is None else round(float(custo_reportado_usd),6),
        duracao_ms=int((time.perf_counter()-inicio_perf)*1000),
        detalhe=detalhe,
    ))


def sanitizar_texto(texto: str) -> str:
    if not texto:
        return ""
    import re
    texto = re.sub(r"sk-or-v1-[A-Za-z0-9_-]+", "[CHAVE-REDACTED]", str(texto))
    texto = re.sub(r"Bearer\s+[A-Za-z0-9._-]+", "Bearer [REDACTED]", texto, flags=re.I)
    return texto


def extrair_custo_reportado(dados: Any) -> float | None:
    """Aceita formatos comuns sem depender de um único schema do provedor."""
    if not isinstance(dados, dict):
        return None
    candidatos=[
        dados.get("cost"),
        (dados.get("usage") or {}).get("cost") if isinstance(dados.get("usage"),dict) else None,
        (dados.get("usage") or {}).get("total_cost") if isinstance(dados.get("usage"),dict) else None,
    ]
    for c in candidatos:
        try:
            if c is not None:
                return float(c)
        except (TypeError, ValueError):
            pass
    return None


def resumo_financeiro() -> dict[str, Any]:
    gasto=custo_hoje_usd()
    limite=POLITICA.orcamento_diario_usd
    return {
        "gasto_estimado_hoje_usd": gasto,
        "limite_diario_usd": limite,
        "saldo_protegido_usd": max(0.0, round(limite-gasto,6)),
        "percentual_usado": 0 if limite <= 0 else min(100.0, (gasto/limite)*100),
        "max_imagens_lote": POLITICA.max_imagens_lote,
        "max_audio_segmentos_lote": POLITICA.max_audio_segmentos_lote,
        "estimativas": {
            "texto_usd_chamada": POLITICA.estimativa_texto_usd,
            "imagem_usd_unidade": POLITICA.estimativa_imagem_usd,
            "audio_usd_minuto": POLITICA.estimativa_audio_min_usd,
        },
    }
