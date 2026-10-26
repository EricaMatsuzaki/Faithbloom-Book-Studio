"""Engenheiro de Code Review Profundo — execução real de correções.

Diferença em relação ao diagnóstico anterior (que só descrevia um plano em
texto): este módulo efetivamente lê o código real do repositório, usa o
modelo de texto já configurado (Gemini/OpenRouter, via
openrouter_client.chamar_llm) para propor uma correção mínima e cirúrgica,
aplica essa correção numa branch nova e isolada, e abre um Pull Request
(Draft) para revisão humana.

Regra de segurança inegociável, herdada do contrato do Engenheiro de Code
Review Profundo: nunca commitar direto na feature branch nem na release;
nunca fazer merge sozinho. self_code_patch continua "proposto, não aplicado
sem aprovação" — a diferença é que agora a proposta já chega como PR
revisável, com diff real e CI rodando, em vez de só um parágrafo.
"""
from __future__ import annotations

import base64
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone

import requests

from openrouter_client import chamar_llm

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN") or os.environ.get("FAITHBLOOM_GITHUB_TOKEN")
GITHUB_API = "https://api.github.com"
REPO = os.environ.get("FAITHBLOOM_REPO", "EricaMatsuzaki/Faithbloom-Book-Studio")
BRANCH_BASE_PADRAO = os.environ.get("FAITHBLOOM_BRANCH_BASE", "feature/refinamento-24-prompt-mestre-compliance")


class EngenheiroError(RuntimeError):
    pass


def _headers() -> dict:
    if not GITHUB_TOKEN:
        raise EngenheiroError(
            "GITHUB_TOKEN não configurado. Defina um token do GitHub com permissão de "
            "escrita neste repositório nos Secrets do ambiente para habilitar correções reais. "
            "Sem isso, o Engenheiro só pode diagnosticar, não corrigir."
        )
    return {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _api(method: str, path: str, **kwargs) -> dict:
    resp = requests.request(method, f"{GITHUB_API}{path}", headers=_headers(), timeout=30, **kwargs)
    if resp.status_code >= 400:
        raise EngenheiroError(f"GitHub API {method} {path} falhou (HTTP {resp.status_code}): {resp.text[:300]}")
    return resp.json() if resp.content else {}


def _obter_conteudo_arquivo(caminho: str, ref: str) -> tuple[str, str]:
    """Retorna (conteúdo_texto, sha_do_blob) do arquivo na branch indicada."""
    dados = _api("GET", f"/repos/{REPO}/contents/{caminho}", params={"ref": ref})
    conteudo = base64.b64decode(dados["content"]).decode("utf-8")
    return conteudo, dados["sha"]


def _criar_branch(nome_novo: str, a_partir_de: str) -> None:
    ref_base = _api("GET", f"/repos/{REPO}/git/ref/heads/{a_partir_de}")
    sha_base = ref_base["object"]["sha"]
    _api("POST", f"/repos/{REPO}/git/refs", json={"ref": f"refs/heads/{nome_novo}", "sha": sha_base})


def _commitar_arquivo(caminho: str, novo_conteudo: str, sha_atual: str, branch: str, mensagem: str) -> None:
    _api("PUT", f"/repos/{REPO}/contents/{caminho}", json={
        "message": mensagem,
        "content": base64.b64encode(novo_conteudo.encode("utf-8")).decode("ascii"),
        "sha": sha_atual,
        "branch": branch,
    })


def _abrir_pr(branch: str, base: str, titulo: str, corpo: str) -> dict:
    return _api("POST", f"/repos/{REPO}/pulls", json={
        "title": titulo, "head": branch, "base": base, "body": corpo, "draft": True,
    })


SISTEMA_ENGENHEIRO = """Você é o Engenheiro de Code Review Profundo do FaithBloom Book Studio.
Seu contrato:
1. Reproduzir ou caracterizar a falha antes de corrigir, a partir da descrição e do código fornecidos.
2. Ler o arquivo completo, entender chamadores e efeitos colaterais antes de decidir.
3. Preservar contratos públicos e histórico; nunca apagar/consolidar módulos por semelhança.
4. Preferir a correção mínima, reversível e cirúrgica — nunca reescrever o arquivo inteiro
   se a correção real cabe em poucas linhas.
5. Nunca mascarar o erro com um fallback enganoso que finja sucesso.
6. Nunca alterar a release protegida.
Responda APENAS em JSON com este formato exato, sem markdown:
{
  "diagnostico": "causa raiz em 1-3 frases, em português",
  "confianca": "alta" | "media" | "baixa",
  "conteudo_novo_do_arquivo": "conteúdo COMPLETO do arquivo já corrigido, ou null",
  "resumo_da_mudanca": "o que mudou e por quê, em 1-3 frases",
  "risco": "o que pode dar errado com esta correção, em 1 frase"
}
Se a confiança não for alta, ou a correção exigir mudanças em mais de um arquivo, ou você não
tiver certeza suficiente do código real (nunca invente código que não viu), responda com
"confianca": "baixa" ou "media" e deixe "conteudo_novo_do_arquivo" como null."""


@dataclass
class ResultadoEngenheiro:
    sucesso: bool
    diagnostico: str
    resumo: str = ""
    pr_url: str | None = None
    branch: str | None = None
    motivo_bloqueio: str = ""


def investigar_e_corrigir(
    descricao_do_bug: str,
    caminho_arquivo_suspeito: str,
    *,
    branch_base: str = BRANCH_BASE_PADRAO,
) -> ResultadoEngenheiro:
    """Ponto único: recebe a descrição do bug e o caminho do arquivo onde o
    problema provavelmente está, lê o código real, propõe a correção via IA
    e — só se a IA relatar confiança alta — cria uma branch, commita e abre
    um PR (Draft) para revisão humana. Nunca commita direto na branch base
    nem mescla sozinho.
    """
    try:
        conteudo_atual, sha_atual = _obter_conteudo_arquivo(caminho_arquivo_suspeito, branch_base)
    except EngenheiroError as exc:
        return ResultadoEngenheiro(False, f"Não consegui ler {caminho_arquivo_suspeito}: {exc}")

    instrucao = (
        f"Descrição do problema relatado:\n{descricao_do_bug}\n\n"
        f"Conteúdo atual de {caminho_arquivo_suspeito}:\n```python\n{conteudo_atual}\n```"
    )
    try:
        resposta = chamar_llm(SISTEMA_ENGENHEIRO, instrucao)
    except Exception as exc:
        return ResultadoEngenheiro(False, f"O modelo de análise não respondeu: {exc}")

    if not isinstance(resposta, dict):
        return ResultadoEngenheiro(False, "Resposta do engenheiro em formato inesperado.")

    diagnostico = str(resposta.get("diagnostico", "")).strip()
    confianca = str(resposta.get("confianca", "")).strip().lower()
    novo_conteudo = resposta.get("conteudo_novo_do_arquivo")
    resumo = str(resposta.get("resumo_da_mudanca", "")).strip()
    risco = str(resposta.get("risco", "")).strip()

    if confianca != "alta" or not novo_conteudo:
        return ResultadoEngenheiro(
            False, diagnostico or "Sem diagnóstico claro.",
            motivo_bloqueio=(
                f"Confiança '{confianca or 'desconhecida'}' — abaixo do necessário para abrir "
                "PR automaticamente. Nenhuma alteração foi feita no repositório."
            ),
        )

    if novo_conteudo.strip() == conteudo_atual.strip():
        return ResultadoEngenheiro(
            False, diagnostico, motivo_bloqueio="A correção proposta é idêntica ao código atual; nada foi alterado."
        )

    carimbo = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    slug = re.sub(r"[^a-z0-9]+", "-", caminho_arquivo_suspeito.lower()).strip("-")
    branch_nova = f"auto-fix/{slug}-{carimbo}"

    try:
        _criar_branch(branch_nova, branch_base)
        _commitar_arquivo(
            caminho_arquivo_suspeito, novo_conteudo, sha_atual, branch_nova,
            mensagem=f"fix: {resumo or 'correção automática do Engenheiro de Code Review Profundo'}",
        )
        corpo_pr = (
            f"**Diagnóstico:** {diagnostico}\n\n**O que mudou:** {resumo}\n\n"
            f"**Risco conhecido:** {risco or 'não informado'}\n\n"
            "---\n"
            "Aberto automaticamente pelo Engenheiro de Code Review Profundo. "
            "Este PR começa como Draft de propósito: **não mesclar sem revisão humana e sem "
            "conferir o CI.**"
        )
        pr = _abrir_pr(
            branch_nova, branch_base,
            titulo=f"[auto-fix] {resumo or diagnostico[:60] or caminho_arquivo_suspeito}",
            corpo=corpo_pr,
        )
    except EngenheiroError as exc:
        return ResultadoEngenheiro(False, diagnostico, motivo_bloqueio=f"Falha ao abrir o PR: {exc}")

    return ResultadoEngenheiro(
        True, diagnostico, resumo=resumo, pr_url=pr.get("html_url"), branch=branch_nova,
    )
