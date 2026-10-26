"""Personal assistant connectors and durable, profile-scoped routines.

Imports never authenticate or send messages. Gmail and WhatsApp mutations need
an enabled write flag and confirmation of the exact draft shown to the author.
Workspace profiles organize data; authentication/tenant ACL remain backend duties.
No background scheduler or public webhook server is started by this module.
"""
from __future__ import annotations

import base64
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from email.policy import SMTP
from email.utils import parseaddr
import hashlib
import hmac
import json
import math
import os
import re
from threading import RLock
from typing import Any, Callable, MutableMapping
import uuid
from zoneinfo import ZoneInfo

import requests

from jarvis_daily_intelligence import OAUTH_ENDPOINT
from storage_backend import BACKEND, StorageError

DEFAULT_TIMEZONE = "Asia/Tokyo"
GMAIL_URL = "https://gmail.googleapis.com/gmail/v1/users/me"
AUTONOMY_MODES = {"assistant": "Assistente", "copilot": "Copiloto", "manager": "Gerente"}
SCHEMA = "faithbloom.assistant-services.v1"
_DISPATCH_LOCK = RLock()


class AssistantServiceError(RuntimeError):
    """Safe-to-display service failure, without provider payload/credentials."""


class ConfirmationRequired(AssistantServiceError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime, timezone_name: str = DEFAULT_TIMEZONE) -> datetime:
    tz = ZoneInfo(timezone_name)
    return value.astimezone(tz) if value.tzinfo else value.replace(tzinfo=tz)


def _flag(name: str) -> bool:
    return os.environ.get(name, "").strip().casefold() in {"1", "true", "yes", "on"}


def _profile_id(value: str) -> str:
    clean = str(value or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", clean):
        raise ValueError("Selecione um perfil de workspace válido.")
    return clean


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def _whatsapp_pricing() -> dict:
    """Server-configured estimate, never an invented free-message tariff."""
    raw = os.environ.get("WHATSAPP_ESTIMATED_COST_USD", "").strip()
    try:
        cost = float(raw)
        if not math.isfinite(cost) or cost < 0:
            raise ValueError
    except (TypeError, ValueError, OverflowError):
        cost = None
    return {"currency": "USD", "estimated_cost_usd": cost,
            "configured": cost is not None, "source": "operator_configuration", "actual_billing_verified": False}


def _google_credentials() -> dict[str, str]:
    # Reuse the existing Google OAuth deployment; Gmail scopes must be granted
    # when issuing the refresh token. Never infer Gmail permission from Calendar.
    names = ("client_id", "client_secret", "refresh_token")
    prefix = "GOOGLE_GMAIL" if any(os.environ.get(f"GOOGLE_GMAIL_{name.upper()}", "").strip() for name in names) else "GOOGLE_CALENDAR"
    return {name: os.environ.get(f"{prefix}_{name.upper()}", "").strip() for name in names}


def _whatsapp_credentials() -> dict[str, str]:
    return {
        "access_token": os.environ.get("WHATSAPP_ACCESS_TOKEN", "").strip(),
        "phone_number_id": os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "").strip(),
        "app_secret": os.environ.get("WHATSAPP_APP_SECRET", "").strip(),
        "verify_token": os.environ.get("WHATSAPP_WEBHOOK_VERIFY_TOKEN", "").strip(),
        "api_version": os.environ.get("WHATSAPP_GRAPH_API_VERSION", "v23.0").strip(),
    }


def connector_readiness() -> dict[str, dict[str, Any]]:
    """Configuration evidence only. A configured connector is not live-tested."""
    google, whatsapp = _google_credentials(), _whatsapp_credentials()
    missing_gmail = [f"GOOGLE_GMAIL_{key.upper()} (ou GOOGLE_CALENDAR_{key.upper()})" for key, value in google.items() if not value]
    missing_wa = [f"WHATSAPP_{key.upper()}" for key in ("access_token", "phone_number_id") if not whatsapp[key]]
    if whatsapp["phone_number_id"] and not re.fullmatch(r"\d+", whatsapp["phone_number_id"]):
        missing_wa.append("WHATSAPP_PHONE_NUMBER_ID válido (somente dígitos)")
    if not re.fullmatch(r"v\d{1,3}\.0", whatsapp["api_version"]):
        missing_wa.append("WHATSAPP_GRAPH_API_VERSION válida")
    return {
        "gmail": {"configured": not missing_gmail, "status": "configured_not_tested" if not missing_gmail else "configuration_missing", "missing": missing_gmail,
                  "write_enabled": _flag("JARVIS_GMAIL_WRITE_ENABLED"), "live_tested": False,
                  "required_scopes": ["https://www.googleapis.com/auth/gmail.readonly", "https://www.googleapis.com/auth/gmail.send"]},
        "whatsapp": {"configured": not missing_wa, "status": "configured_not_tested" if not missing_wa else "configuration_missing", "missing": missing_wa,
                     "write_enabled": _flag("JARVIS_WHATSAPP_WRITE_ENABLED"), "live_tested": False,
                     "pricing": _whatsapp_pricing(),
                     "webhook_signature_configured": bool(whatsapp["app_secret"]), "webhook_verification_configured": bool(whatsapp["verify_token"]),
                     "webhook_receiver_status": "infrastructure_pending"},
        "routines": {"configured": True, "status": "on_demand", "scheduler_status": "infrastructure_pending", "timezone": DEFAULT_TIMEZONE},
    }


def _response_json(response: Any, operation: str) -> dict:
    try:
        response.raise_for_status()
        result = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise AssistantServiceError(f"Não foi possível {operation}. Verifique a conexão e as permissões do serviço.") from exc
    if not isinstance(result, dict):
        raise AssistantServiceError(f"O serviço retornou uma resposta inválida ao {operation}.")
    return result


def _stored_json(backend: Any, path: str, *, default: Any = None) -> Any:
    """A network failure is never an empty personal workspace or missing receipt."""
    try:
        raw = backend.get_bytes(path)
    except FileNotFoundError:
        return deepcopy(default)
    except StorageError as exc:
        if "download falhou (404)" in str(exc):
            return deepcopy(default)
        raise AssistantServiceError("Não foi possível consultar o armazenamento do assistente. Tente novamente antes de alterar ou enviar.") from exc
    try:
        return json.loads(raw)
    except (ValueError, UnicodeError) as exc:
        raise AssistantServiceError("Um registro do assistente está inválido. Preserve o registro e solicite revisão.") from exc


class AutonomyPolicy:
    """Executable, closed action catalog: modes never elevate protected actions."""
    ACTIONS = {
        "gmail.read": "read", "whatsapp.webhook.read": "read", "calendar.read": "read", "routines.read": "read",
        "routines.priority.save": "local", "routines.reminder.save": "local", "routines.complete": "local", "routines.briefing.save": "local", "routines.day_close.save": "local",
        "gmail.send": "protected", "whatsapp.send": "protected", "calendar.write": "protected", "ai.generate": "protected", "data.delete": "protected",
    }

    def __init__(self, mode: str = "assistant"):
        if mode not in AUTONOMY_MODES:
            raise ValueError("Modo de autonomia inválido.")
        self.mode = mode

    def evaluate(self, action: str, *, confirmed: bool = False) -> dict[str, Any]:
        kind = self.ACTIONS.get(action)
        requires = kind == "protected" or (kind == "local" and self.mode != "manager")
        allowed = kind is not None and (not requires or confirmed)
        return {"mode": self.mode, "action": action, "allowed": allowed, "requires_confirmation": requires,
                "reason": "unknown_action" if kind is None else "confirmation_required" if not allowed else "allowed"}

    def execute(self, action: str, callback: Callable[[], Any], *, confirmed: bool = False) -> Any:
        verdict = self.evaluate(action, confirmed=confirmed)
        if not verdict["allowed"]:
            raise ConfirmationRequired("Confirme esta ação antes de executar." if verdict["requires_confirmation"] else "Ação não registrada na política de autonomia.")
        return callback()


def _draft(channel: str, profile_id: str, payload: dict, account: str, now: datetime | None, *, pricing: dict | None = None) -> dict:
    stamp = _aware(now or _now(), "UTC")
    core = {"channel": channel, "profile_id": _profile_id(profile_id), "payload": deepcopy(payload), "account": account,
            "id": uuid.uuid4().hex, "created_at": stamp.isoformat(), "expires_at": (stamp + timedelta(minutes=10)).isoformat()}
    if pricing is not None:
        core["pricing"] = deepcopy(pricing)
    return {**core, "fingerprint": _fingerprint(core), "status": "draft"}


def _confirm_draft(draft: dict, channel: str, profile_id: str, account: str, confirmation_fingerprint: str, now: datetime | None) -> None:
    if draft.get("channel") != channel or draft.get("profile_id") != _profile_id(profile_id) or draft.get("account") != account:
        raise ConfirmationRequired("O rascunho não pertence ao perfil e à conexão atuais. Prepare-o novamente.")
    core = {key: draft.get(key) for key in ("channel", "profile_id", "payload", "account", "id", "created_at", "expires_at")}
    if "pricing" in draft:
        core["pricing"] = draft["pricing"]
    expected = _fingerprint(core)
    if not confirmation_fingerprint or not hmac.compare_digest(expected, str(draft.get("fingerprint") or "")) or not hmac.compare_digest(expected, confirmation_fingerprint):
        raise ConfirmationRequired("A confirmação não corresponde ao destinatário e conteúdo deste rascunho.")
    try:
        expires = datetime.fromisoformat(draft["expires_at"])
        if expires.tzinfo is None or _aware(now or _now(), "UTC") >= expires:
            raise ConfirmationRequired("A confirmação expirou. Prepare e revise um novo rascunho.")
    except (KeyError, ValueError) as exc:
        raise ConfirmationRequired("Rascunho de envio inválido.") from exc


def _send_once(draft: dict, receipts: MutableMapping, callback: Callable[[], dict], *, authorize: Callable[[], dict] | None = None) -> dict:
    """Persist dispatch intent first; network uncertainty must never auto-retry."""
    # Streamlit can run concurrent session threads. Serialize the receipt claim
    # within this worker; a multi-worker deployment still needs an atomic remote
    # claim/transaction, which is explicitly reported as infrastructure pending.
    with _DISPATCH_LOCK:
        return _send_once_locked(draft, receipts, callback, authorize=authorize)


def _send_once_locked(draft: dict, receipts: MutableMapping, callback: Callable[[], dict], *, authorize: Callable[[], dict] | None = None) -> dict:
    key = draft["id"]
    old = receipts.get(key)
    if old:
        if old.get("fingerprint") != draft["fingerprint"]:
            raise ConfirmationRequired("Esse identificador já pertence a outro envio.")
        if old.get("status") == "sent":
            return deepcopy(old["result"])
        raise AssistantServiceError("Esse envio já foi iniciado. Confira o provedor antes de preparar outro, para evitar duplicidade.")
    # A blocked preflight did not dispatch anything: keep it retryable after
    # correcting the configuration. A previous successful send needs no new
    # authorization or network call.
    evidence = authorize() if authorize is not None else {}
    receipts[key] = {"fingerprint": draft["fingerprint"], "status": "dispatching", "created_at": _now().isoformat(), "governance": evidence}
    try:
        result = callback()
        receipts[key] = {"fingerprint": draft["fingerprint"], "status": "sent", "result": deepcopy(result), "created_at": _now().isoformat(), "governance": evidence}
        return result
    except Exception:
        # Includes a failed receipt write after success: retaining dispatching
        # prevents blind retry if the external provider already accepted it.
        try:
            receipts[key] = {"fingerprint": draft["fingerprint"], "status": "unknown", "created_at": _now().isoformat(), "governance": evidence}
        except Exception:
            pass
        raise


def _email_address(value: str) -> str:
    value = str(value or "").strip()
    _, address = parseaddr(value)
    if "\r" in value or "\n" in value or value.count("@") != 1 or "," in value or ";" in value or not re.fullmatch(r"[^\s@,;<>]+@[^\s@,;<>]+\.[^\s@,;<>]+", address):
        raise ValueError("Informe um único endereço de e-mail válido.")
    return address


class GmailClient:
    def __init__(self, *, getter: Callable | None = None, poster: Callable | None = None):
        self.getter, self.poster = getter or requests.get, poster or requests.post

    def _account(self) -> str:
        credentials = _google_credentials()
        return _fingerprint({"client_id": credentials["client_id"], "refresh_token": credentials["refresh_token"]})

    def _token(self) -> str:
        creds = _google_credentials()
        if not all(creds.values()):
            raise AssistantServiceError("Conecte o Gmail com OAuth antes de consultar ou enviar mensagens.")
        try:
            result = _response_json(self.poster(OAUTH_ENDPOINT, data={**creds, "grant_type": "refresh_token"}, timeout=10), "autenticar o Gmail")
        except requests.RequestException as exc:
            raise AssistantServiceError("Não foi possível autenticar o Gmail.") from exc
        token = str(result.get("access_token") or "").strip()
        if not token:
            raise AssistantServiceError("O Gmail não retornou um token de acesso.")
        return token

    def _get(self, suffix: str, params: dict | None = None) -> dict:
        token = self._token()
        try:
            return _response_json(self.getter(f"{GMAIL_URL}/{suffix}", headers={"Authorization": f"Bearer {token}"}, params=params or {}, timeout=10), "consultar o Gmail")
        except requests.RequestException as exc:
            raise AssistantServiceError("Não foi possível consultar o Gmail agora.") from exc

    def check_connection(self) -> dict:
        result = self._get("profile")
        if not result.get("emailAddress"):
            raise AssistantServiceError("O Gmail não confirmou a conta conectada.")
        return {"status": "read_test_passed", "email": result["emailAddress"], "tested_at": _now().isoformat(), "send_tested": False}

    def list_messages(self, *, query: str = "in:inbox", max_results: int = 10, page_token: str = "") -> dict:
        params = {"q": str(query)[:500], "maxResults": max(1, min(int(max_results), 50))}
        if page_token:
            params["pageToken"] = page_token
        result = self._get("messages", params)
        messages = result.get("messages") or []
        if not isinstance(messages, list):
            raise AssistantServiceError("O Gmail retornou uma lista inválida de mensagens.")
        return {"messages": [{"id": str(row["id"]), "thread_id": str(row.get("threadId") or "")} for row in messages if isinstance(row, dict) and row.get("id")],
                "next_page_token": str(result.get("nextPageToken") or "")}

    def get_message(self, message_id: str) -> dict:
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,256}", str(message_id or "")):
            raise ValueError("Identificador de mensagem inválido.")
        result = self._get(f"messages/{message_id}", {"format": "full"})
        payload = result.get("payload") or {}
        if not isinstance(payload, dict):
            raise AssistantServiceError("O Gmail retornou uma mensagem inválida.")
        headers = {str(row.get("name") or "").lower(): str(row.get("value") or "") for row in payload.get("headers", []) if isinstance(row, dict)}
        bodies: list[str] = []

        def collect(part: dict, depth: int = 0) -> None:
            if depth > 10 or not isinstance(part, dict):
                return
            body = (part.get("body") or {}).get("data")
            if part.get("mimeType") == "text/plain" and body:
                try:
                    bodies.append(base64.urlsafe_b64decode(str(body) + "=" * (-len(str(body)) % 4)).decode("utf-8", errors="replace"))
                except (ValueError, TypeError):
                    pass
            for child in part.get("parts") or []:
                collect(child, depth + 1)

        collect(payload)
        return {"id": str(result.get("id") or message_id), "subject": headers.get("subject", ""), "from": headers.get("from", ""), "to": headers.get("to", ""),
                "snippet": str(result.get("snippet") or ""), "body": "\n".join(bodies), "content_trust": "untrusted_external_content"}

    def prepare_send(self, profile_id: str, recipient: str, subject: str, body: str, *, now: datetime | None = None) -> dict:
        recipient = _email_address(recipient)
        subject, body = str(subject or "").strip(), str(body or "").strip()
        if not subject or not body or "\r" in subject or "\n" in subject:
            raise ValueError("Informe assunto e mensagem válidos antes de preparar o envio.")
        if len(subject) > 998 or len(body) > 100_000:
            raise ValueError("A mensagem ultrapassa o limite permitido nesta interface.")
        return _draft("gmail", profile_id, {"to": recipient, "subject": subject, "body": body}, self._account(), now)

    def send_confirmed(self, draft: dict, *, profile_id: str, confirmation_fingerprint: str, receipts: MutableMapping, now: datetime | None = None) -> dict:
        _confirm_draft(draft, "gmail", profile_id, self._account(), confirmation_fingerprint, now)
        if not _flag("JARVIS_GMAIL_WRITE_ENABLED"):
            raise AssistantServiceError("O envio pelo Gmail ainda não está habilitado na configuração do FaithBloom.")

        def send() -> dict:
            token = self._token()
            payload = draft["payload"]
            message = EmailMessage(policy=SMTP)
            message["To"], message["Subject"] = payload["to"], payload["subject"]
            message["Message-ID"] = f"<faithbloom-{draft['id']}@faithbloom.local>"
            message.set_content(payload["body"])
            raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
            try:
                result = _response_json(self.poster(f"{GMAIL_URL}/messages/send", headers={"Authorization": f"Bearer {token}"}, json={"raw": raw}, timeout=15), "enviar a mensagem pelo Gmail")
            except requests.RequestException as exc:
                raise AssistantServiceError("O envio pelo Gmail não foi confirmado. Confira a pasta Enviados antes de tentar novamente.") from exc
            if not result.get("id"):
                raise AssistantServiceError("O Gmail não confirmou o identificador do envio. Confira a pasta Enviados.")
            return {"id": str(result["id"]), "thread_id": str(result.get("threadId") or ""), "status": "sent"}

        def authorize():
            from governance_runtime import authorize_external_action
            return authorize_external_action("gmail.send", confirmed=True, paid=False,
                provider_configured=connector_readiness()["gmail"]["configured"],
                operation_id=draft["id"], source_module="assistant_services.py", state=draft,
                uses_personal_data=True, consent_confirmed=True)

        return _send_once(draft, receipts, send, authorize=authorize)


class WhatsAppBusinessClient:
    def __init__(self, *, getter: Callable | None = None, poster: Callable | None = None):
        self.getter, self.poster = getter or requests.get, poster or requests.post

    def _account(self) -> str:
        c = _whatsapp_credentials()
        return _fingerprint({"phone_number_id": c["phone_number_id"], "token": c["access_token"]})

    def _url(self, suffix: str = "") -> str:
        c = _whatsapp_credentials()
        if not c["access_token"] or not re.fullmatch(r"\d+", c["phone_number_id"]):
            raise AssistantServiceError("Configure uma conta WhatsApp Business válida antes de usar o serviço.")
        if not re.fullmatch(r"v\d{1,3}\.0", c["api_version"]):
            raise AssistantServiceError("A versão configurada da API do WhatsApp é inválida.")
        return f"https://graph.facebook.com/{c['api_version']}/{c['phone_number_id']}{suffix}"

    def check_connection(self) -> dict:
        url = self._url()
        try:
            result = _response_json(self.getter(url, headers={"Authorization": f"Bearer {_whatsapp_credentials()['access_token']}"}, params={"fields": "id,display_phone_number,verified_name"}, timeout=10), "verificar o WhatsApp Business")
        except requests.RequestException as exc:
            raise AssistantServiceError("Não foi possível verificar a conexão WhatsApp Business.") from exc
        if str(result.get("id") or "") != _whatsapp_credentials()["phone_number_id"]:
            raise AssistantServiceError("O WhatsApp não confirmou o número conectado.")
        return {"status": "read_test_passed", "phone": str(result.get("display_phone_number") or ""), "name": str(result.get("verified_name") or ""), "tested_at": _now().isoformat(), "send_tested": False}

    def prepare_send(self, profile_id: str, recipient: str, body: str = "", *, template_name: str = "", template_language: str = "pt_BR", now: datetime | None = None) -> dict:
        recipient = re.sub(r"[ +().-]", "", str(recipient or ""))
        if not re.fullmatch(r"[1-9]\d{7,14}", recipient):
            raise ValueError("Informe o número com código do país, incluindo DDI.")
        payload: dict = {"messaging_product": "whatsapp", "to": recipient}
        if template_name:
            if not re.fullmatch(r"[a-z0-9_]{1,512}", template_name) or not re.fullmatch(r"[a-z]{2}(?:_[A-Z]{2})?", template_language):
                raise ValueError("Modelo ou idioma WhatsApp inválido.")
            payload.update({"type": "template", "template": {"name": template_name, "language": {"code": template_language}}})
        else:
            body = str(body or "").strip()
            if not body or len(body) > 4096:
                raise ValueError("Informe uma mensagem WhatsApp de até 4096 caracteres.")
            payload.update({"type": "text", "text": {"preview_url": False, "body": body}})
        return _draft("whatsapp", profile_id, payload, self._account(), now, pricing=_whatsapp_pricing())

    def send_confirmed(self, draft: dict, *, profile_id: str, confirmation_fingerprint: str, receipts: MutableMapping, recipient_opt_in: bool = False, customer_window_open: bool = False, now: datetime | None = None) -> dict:
        _confirm_draft(draft, "whatsapp", profile_id, self._account(), confirmation_fingerprint, now)
        if not _flag("JARVIS_WHATSAPP_WRITE_ENABLED"):
            raise AssistantServiceError("O envio pelo WhatsApp ainda não está habilitado na configuração do FaithBloom.")
        if not recipient_opt_in:
            raise ConfirmationRequired("Confirme que o destinatário autorizou receber mensagens desta conta.")
        if draft["payload"]["type"] == "text" and not customer_window_open:
            raise ConfirmationRequired("Uma mensagem livre exige conversa iniciada pelo cliente nas últimas 24 horas; fora dessa janela use um modelo aprovado pela Meta.")

        pricing = _whatsapp_pricing()
        if not pricing["configured"]:
            raise AssistantServiceError("Configure WHATSAPP_ESTIMATED_COST_USD com a estimativa por mensagem antes de enviar. A tarifa não é presumida como gratuita.")
        if draft.get("pricing") != pricing:
            raise ConfirmationRequired("A estimativa de envio mudou. Prepare e revise um novo rascunho com o custo atual.")

        def send() -> dict:
            url = self._url("/messages")
            try:
                result = _response_json(self.poster(url, headers={"Authorization": f"Bearer {_whatsapp_credentials()['access_token']}"}, json=draft["payload"], timeout=15), "enviar pelo WhatsApp Business")
            except requests.RequestException as exc:
                raise AssistantServiceError("O envio WhatsApp não foi confirmado. Confira o provedor antes de tentar novamente.") from exc
            rows = result.get("messages") or []
            if not rows or not isinstance(rows[0], dict) or not rows[0].get("id"):
                raise AssistantServiceError("O WhatsApp não confirmou o identificador do envio.")
            return {"id": str(rows[0]["id"]), "status": "accepted", "delivery_confirmed": False}

        def authorize():
            from governance_runtime import authorize_external_action
            cost = pricing["estimated_cost_usd"]
            return authorize_external_action("whatsapp.send", confirmed=True, paid=cost > 0,
                projected_cost=cost, provider_configured=connector_readiness()["whatsapp"]["configured"],
                operation_id=draft["id"], source_module="assistant_services.py", state=draft,
                uses_personal_data=True, consent_confirmed=True)

        return _send_once(draft, receipts, send, authorize=authorize)


def verify_whatsapp_webhook(query: dict, *, verify_token: str | None = None) -> str:
    token = verify_token if verify_token is not None else _whatsapp_credentials()["verify_token"]
    if not token or query.get("hub.mode") != "subscribe" or not hmac.compare_digest(str(query.get("hub.verify_token") or ""), token):
        raise AssistantServiceError("Verificação do webhook WhatsApp recusada.")
    challenge = str(query.get("hub.challenge") or "")
    if not challenge or len(challenge) > 256 or not re.fullmatch(r"[A-Za-z0-9_-]+", challenge):
        raise AssistantServiceError("Desafio de webhook inválido.")
    return challenge


def parse_whatsapp_webhook(raw_body: bytes, signature: str, *, app_secret: str | None = None, phone_number_id: str | None = None) -> dict:
    """Authenticate the exact raw body before decoding external message text."""
    secret = app_secret if app_secret is not None else _whatsapp_credentials()["app_secret"]
    if not secret or not isinstance(raw_body, bytes) or len(raw_body) > 1_000_000:
        raise AssistantServiceError("Corpo ou assinatura do webhook WhatsApp inválidos.")
    expected = "sha256=" + hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, str(signature or "")):
        raise AssistantServiceError("Assinatura do webhook WhatsApp recusada.")
    try:
        data = json.loads(raw_body)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise AssistantServiceError("O webhook WhatsApp contém JSON inválido.") from exc
    if not isinstance(data, dict) or data.get("object") != "whatsapp_business_account":
        raise AssistantServiceError("Evento WhatsApp inválido.")
    phone = phone_number_id if phone_number_id is not None else _whatsapp_credentials()["phone_number_id"]
    if not phone:
        raise AssistantServiceError("Configure o número WhatsApp destinatário do webhook.")

    def rows(value: Any) -> list:
        if value is None:
            return []
        if not isinstance(value, list):
            raise AssistantServiceError("O webhook WhatsApp contém uma lista de eventos inválida.")
        return value

    messages, statuses = [], []
    for entry in rows(data.get("entry")):
        for change in rows(entry.get("changes")) if isinstance(entry, dict) else []:
            value = (change.get("value") or {}) if isinstance(change, dict) else {}
            metadata = value.get("metadata") if isinstance(value, dict) else {}
            if not isinstance(value, dict) or not isinstance(metadata, dict) or str(metadata.get("phone_number_id") or "") != phone:
                continue
            for item in rows(value.get("messages")):
                if isinstance(item, dict) and item.get("id"):
                    text = item.get("text") if isinstance(item.get("text"), dict) else {}
                    messages.append({"id": str(item["id"]), "from": str(item.get("from") or ""), "timestamp": str(item.get("timestamp") or ""),
                                     "type": str(item.get("type") or ""), "text": str(text.get("body") or ""), "content_trust": "untrusted_external_content"})
            for item in rows(value.get("statuses")):
                if isinstance(item, dict) and item.get("id"):
                    statuses.append({"id": str(item["id"]), "status": str(item.get("status") or ""), "timestamp": str(item.get("timestamp") or "")})
    return {"messages": messages, "statuses": statuses}


class _PersistentReceipts(MutableMapping):
    def __init__(self, store: "AssistantRoutineStore"):
        self.store = store

    def __getitem__(self, key):
        if not re.fullmatch(r"[a-f0-9]{32}", str(key)):
            raise KeyError(key)
        # StorageBackend.get_json suppresses network/parse errors. For external
        # dispatch, fail closed instead of treating an unavailable receipt as new.
        try:
            value = _stored_json(self.store.backend, f"{self.store.prefix}/receipts/{key}.json")
        except AssistantServiceError as exc:
            raise AssistantServiceError("Não foi possível validar o recibo desse envio. Nenhuma mensagem será repetida.") from exc
        if value is None:
            raise KeyError(key)
        if not isinstance(value, dict):
            raise AssistantServiceError("O recibo de envio está inválido.")
        return value

    def __setitem__(self, key, value):
        if not re.fullmatch(r"[a-f0-9]{32}", str(key)):
            raise ValueError("Identificador de envio inválido.")
        self.store.backend.put_json(f"{self.store.prefix}/receipts/{key}.json", value)

    def __delitem__(self, key):
        raise AssistantServiceError("Recibos de envio não podem ser excluídos pelo assistente.")

    def __iter__(self):
        return iter([path.rsplit("/", 1)[-1].removesuffix(".json") for path in self.store.backend.list(f"{self.store.prefix}/receipts")])

    def __len__(self):
        return len(list(iter(self)))


class AssistantRoutineStore:
    def __init__(self, profile_id: str, *, backend=None, timezone_name: str = DEFAULT_TIMEZONE):
        self.profile_id = _profile_id(profile_id)
        ZoneInfo(timezone_name)
        self.timezone_name = timezone_name
        self.backend = backend if backend is not None else BACKEND
        self.prefix = f"assistant/profiles/{self.profile_id}"

    def receipts(self) -> MutableMapping:
        return _PersistentReceipts(self)

    def preferences(self) -> dict:
        value = _stored_json(self.backend, f"{self.prefix}/preferences.json", default={})
        value = value if isinstance(value, dict) else {}
        mode = value.get("autonomy_mode", "assistant")
        zone = value.get("timezone") or self.timezone_name
        try:
            ZoneInfo(zone)
        except (ValueError, TypeError, KeyError):
            zone = self.timezone_name
        return {"autonomy_mode": mode if mode in AUTONOMY_MODES else "assistant", "timezone": zone}

    def save_preferences(self, *, autonomy_mode: str, timezone_name: str = DEFAULT_TIMEZONE) -> dict:
        AutonomyPolicy(autonomy_mode)
        ZoneInfo(timezone_name)
        result = {"autonomy_mode": autonomy_mode, "timezone": timezone_name, "updated_at": _now().isoformat()}
        self.backend.put_json(f"{self.prefix}/preferences.json", result)
        self.timezone_name = timezone_name
        return result

    def add_item(self, title: str, *, kind: str = "priority", due_at: datetime | None = None, priority: int = 2, notes: str = "", now: datetime | None = None) -> dict:
        title = str(title or "").strip()
        if not title or len(title) > 500 or kind not in {"priority", "reminder"}:
            raise ValueError("Informe uma prioridade ou lembrete válido.")
        if priority not in {1, 2, 3}:
            raise ValueError("A prioridade precisa ser alta, média ou baixa.")
        if kind == "reminder" and due_at is None:
            raise ValueError("Um lembrete precisa de data e horário.")
        stamp = _aware(now or _now(), self.timezone_name)
        result = {"schema": SCHEMA, "id": uuid.uuid4().hex, "profile_id": self.profile_id, "kind": kind, "title": title,
                  "due_at": _aware(due_at, self.timezone_name).isoformat() if due_at else "", "priority": priority, "notes": str(notes)[:10_000],
                  "status": "pending", "created_at": stamp.isoformat(), "timezone": self.timezone_name}
        self.backend.put_json(f"{self.prefix}/items/{result['id']}.json", result)
        return result

    def list_items(self, *, include_completed: bool = False) -> list[dict]:
        results = []
        for path in self.backend.list(f"{self.prefix}/items"):
            value = _stored_json(self.backend, path)
            if not isinstance(value, dict) or value.get("profile_id") != self.profile_id:
                continue
            if include_completed or value.get("status") == "pending":
                results.append(value)
        return sorted(results, key=lambda item: (item.get("priority", 2), item.get("due_at") or "9999", item.get("created_at", "")))

    def complete_item(self, item_id: str, *, now: datetime | None = None) -> dict:
        if not re.fullmatch(r"[a-f0-9]{32}", str(item_id)):
            raise ValueError("Lembrete ou prioridade inválidos.")
        path = f"{self.prefix}/items/{item_id}.json"
        item = _stored_json(self.backend, path)
        if not isinstance(item, dict) or item.get("profile_id") != self.profile_id:
            raise KeyError("Lembrete ou prioridade não encontrados neste perfil.")
        item["status"], item["completed_at"] = "completed", _aware(now or _now(), self.timezone_name).isoformat()
        self.backend.put_json(path, item)
        return item

    def due_reminders(self, *, now: datetime | None = None) -> list[dict]:
        stamp = _aware(now or _now(), self.timezone_name)
        results = []
        for item in self.list_items():
            if item.get("kind") != "reminder" or not item.get("due_at"):
                continue
            try:
                if _aware(datetime.fromisoformat(item["due_at"]), self.timezone_name) <= stamp:
                    results.append(item)
            except (ValueError, TypeError):
                continue
        return results

    def daily_briefing(self, *, now: datetime | None = None, daily_intelligence: dict | None = None, editorial_next_steps: list[str] | None = None, persist: bool = True) -> dict:
        stamp = _aware(now or _now(), self.timezone_name)
        items = self.list_items()
        result = {"schema": SCHEMA, "id": uuid.uuid4().hex, "profile_id": self.profile_id, "date": stamp.date().isoformat(), "timezone": self.timezone_name,
                  "created_at": stamp.isoformat(), "priorities": [item for item in items if item.get("kind") == "priority"], "due_reminders": self.due_reminders(now=stamp),
                  "editorial_next_steps": list(editorial_next_steps or []), "daily_intelligence": deepcopy(daily_intelligence or {}), "execution": "on_demand"}
        if persist:
            self.backend.put_json(f"{self.prefix}/briefings/{result['id']}.json", result)
        return result

    def close_day(self, *, reflection: str = "", now: datetime | None = None) -> dict:
        stamp = _aware(now or _now(), self.timezone_name)
        date = stamp.date()
        items = self.list_items(include_completed=True)
        completed = []
        for item in items:
            if not item.get("completed_at"):
                continue
            try:
                if _aware(datetime.fromisoformat(item["completed_at"]), self.timezone_name).date() == date:
                    completed.append(item)
            except (ValueError, TypeError):
                continue
        result = {"schema": SCHEMA, "id": uuid.uuid4().hex, "profile_id": self.profile_id, "date": date.isoformat(), "timezone": self.timezone_name,
                  "created_at": stamp.isoformat(), "completed": completed, "pending": [item for item in items if item.get("status") == "pending"],
                  "reflection": str(reflection)[:10_000], "execution": "on_demand"}
        self.backend.put_json(f"{self.prefix}/day_closings/{result['id']}.json", result)
        return result

    def history(self, kind: str) -> list[dict]:
        if kind not in {"briefings", "day_closings"}:
            raise ValueError("Histórico inválido.")
        result = [_stored_json(self.backend, path) for path in self.backend.list(f"{self.prefix}/{kind}")]
        return sorted([item for item in result if isinstance(item, dict) and item.get("profile_id") == self.profile_id], key=lambda item: item.get("created_at", ""), reverse=True)


def assistant_services_diagnostics(profile_id: str = "", *, backend=None) -> dict:
    result = {"schema": SCHEMA, "connectors": connector_readiness(), "implemented": ["gmail_oauth_read_send_confirmed", "whatsapp_send_confirmed", "whatsapp_webhook_signature_parser", "profile_priorities_reminders", "daily_briefing", "day_closing", "autonomy_policy"],
              "infrastructure_pending": ["public_whatsapp_webhook_receiver", "background_reminder_scheduler", "distributed_dispatch_transaction_for_multiworker", "account_authentication_and_tenant_acl"], "production_validated": False}
    if profile_id:
        store = AssistantRoutineStore(profile_id, backend=backend)
        result["routines"] = {"profile_id": profile_id, "pending_count": len(store.list_items()), "preferences": store.preferences()}
    return result
