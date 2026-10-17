"""Durable media projects, local animatics and an opt-in Replicate adapter.

No network request or paid generation runs on import. Provider/model/cost must
be explicitly configured. Every submission is checkpointed before POST; an
uncertain submission is never retried automatically. Derived media requires
human review and never replaces approved Masters.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import io
import base64
import ipaddress
import json
import math
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import time
from threading import RLock
import uuid
from urllib.parse import urlsplit

from PIL import Image
import requests

from storage_backend import BACKEND, materializar, storage_uri, tenant_local_directory

SCHEMA = "faithbloom.media-studio.v1"
KINDS = {"music", "animation_video"}
_LOCK = RLock()
_PROJECT_LOCKS = {}
_API = "https://api.replicate.com/v1"
_MAX_BYTES = 50 * 1024 * 1024
_ACTIVE = {"submission_pending", "submission_uncertain", "starting", "processing"}
_TERMINAL = {"succeeded", "failed", "canceled"}


class MediaStudioError(RuntimeError):
    """Safe-to-display error, without credentials or raw provider responses."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _identifier(value: str) -> str:
    if not re.fullmatch(r"[a-f0-9]{32}", str(value or "")):
        raise MediaStudioError("Projeto de mídia inválido.")
    return value


def _project_lock(project_id: str):
    project_id = _identifier(project_id)
    with _LOCK:
        return _PROJECT_LOCKS.setdefault(project_id, RLock())


def _digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def _setting(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        try:
            import streamlit as st
            value = str(st.secrets.get(name, "") or "").strip()
        except Exception:
            value = ""
    return value


def _number(value: str) -> float | None:
    try:
        number = float(value)
        return number if math.isfinite(number) and number > 0 else None
    except (TypeError, ValueError):
        return None


def provider_configuration(kind: str) -> dict:
    if kind not in KINDS:
        raise MediaStudioError("Tipo de mídia desconhecido.")
    prefix = "FAITHBLOOM_MUSIC" if kind == "music" else "FAITHBLOOM_VIDEO"
    model = _setting(f"{prefix}_REPLICATE_MODEL")
    try:
        fields = json.loads(_setting(f"{prefix}_INPUT_FIELDS") or "[]")
    except ValueError:
        fields = []
    if not isinstance(fields, list) or not fields or not all(isinstance(k, str) and re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", k) for k in fields):
        fields = []
    estimate = _number(_setting(f"{prefix}_ESTIMATED_COST_USD"))
    cap = _number(_setting("FAITHBLOOM_MEDIA_MAX_COST_USD"))
    model_valid = bool(re.fullmatch(r"[A-Za-z0-9_-]+/[A-Za-z0-9_.-]+", model))
    image_field = _setting("FAITHBLOOM_VIDEO_IMAGE_INPUT_FIELD") if kind == "animation_video" else ""
    enabled = _setting("FAITHBLOOM_MEDIA_GENERATION_ENABLED").casefold() in {"true", "1", "yes", "on"}
    single_worker = _setting("FAITHBLOOM_MEDIA_SINGLE_WORKER_CONFIRMED").casefold() in {"true", "1", "yes", "on"}
    configured = bool(_setting("REPLICATE_API_TOKEN") and model_valid and fields and estimate and cap and estimate <= cap
                      and (kind != "animation_video" or image_field in fields))
    return {"kind": kind, "provider": "replicate", "model": model if model_valid else "", "input_fields": fields,
            "estimated_cost_usd": estimate, "max_cost_usd": cap, "configured": configured,
            "enabled": enabled, "available": configured and enabled and single_worker, "image_input_field": image_field,
            "single_worker_declared": single_worker, "distributed_dispatch": False, "live_tested": False,
            "status": "configured_not_live_tested" if configured else "configuration_missing"}


def media_readiness() -> dict:
    return {"local_animatic": {"available": bool(shutil.which("ffmpeg") and shutil.which("ffprobe")),
                               "character_animation": False, "paid_provider": False},
            "music": provider_configuration("music"), "animation_video": provider_configuration("animation_video")}


def _image(data: bytes) -> str:
    if not data or len(data) > 20 * 1024 * 1024:
        raise MediaStudioError("Imagem ausente ou maior que 20 MB.")
    try:
        with Image.open(io.BytesIO(data)) as image:
            fmt = image.format
            if fmt not in {"PNG", "JPEG", "WEBP"} or image.width * image.height > 25_000_000:
                raise ValueError
            image.verify()
        return {"PNG": ".png", "JPEG": ".jpg", "WEBP": ".webp"}[fmt]
    except (OSError, ValueError, Image.DecompressionBombError):
        raise MediaStudioError("Use uma imagem PNG, JPEG ou WebP válida.") from None


def inspect_media(path: str, kind: str) -> dict:
    if not shutil.which("ffprobe"):
        raise MediaStudioError("Instale ffmpeg/ffprobe para validar a mídia.")
    try:
        result = subprocess.run(["ffprobe", "-v", "error", "-protocol_whitelist", "file,pipe", "-show_format", "-show_streams", "-of", "json", path],
                                capture_output=True, timeout=20, check=True)
        info = json.loads(result.stdout)
        streams = info.get("streams", [])
        duration = float(info.get("format", {}).get("duration", 0))
        formats = set(str(info.get("format", {}).get("format_name", "")).split(","))
        allowed = {"wav", "mp3"} if kind == "music" else {"mov", "mp4"}
        matching = [s for s in streams if s.get("codec_type") == ("audio" if kind == "music" else "video")]
        if not matching or not formats.intersection(allowed) or not math.isfinite(duration) or not 0 < duration <= 3600:
            raise ValueError
        if kind == "music" and any(s.get("codec_type") == "video" for s in streams):
            raise ValueError
        return {"duration_seconds": duration, "format": sorted(formats), "streams": [
            {key: stream[key] for key in ("codec_type", "codec_name", "width", "height", "sample_rate") if key in stream} for stream in streams]}
    except (OSError, ValueError, subprocess.SubprocessError):
        raise MediaStudioError("O arquivo não é um áudio WAV/MP3 ou vídeo MP4 válido para este projeto.") from None


class MediaStudioStore:
    def __init__(self, backend=None):
        self.backend = backend if backend is not None else BACKEND

    def _path(self, project_id: str) -> str:
        return f"media_studio/projects/{_identifier(project_id)}.json"

    def create(self, title: str, kind: str, *, source_ref: str = "", uses_personal_data: bool = False) -> dict:
        title = str(title or "").strip()
        if not title or len(title) > 240 or kind not in KINDS:
            raise MediaStudioError("Informe um título e um tipo de mídia válidos.")
        state = {"schema": SCHEMA, "id": uuid.uuid4().hex, "title": title, "kind": kind, "source_ref": str(source_ref or "")[:1000],
                 "created_at": _now(), "status": "draft", "sources": [], "jobs": [], "outputs": [],
                 "auto_promote_master": False, "auto_publish": False, "uses_personal_data": uses_personal_data is True}
        self.save(state)
        return state

    def load(self, project_id: str) -> dict:
        value = self.backend.get_json(self._path(project_id), {})
        if not value or value.get("id") != project_id or value.get("schema") != SCHEMA:
            raise MediaStudioError("Projeto de mídia não encontrado.")
        return deepcopy(value)

    def save(self, state: dict) -> None:
        state = deepcopy(state)
        state["updated_at"] = _now()
        state["auto_promote_master"] = False
        state["auto_publish"] = False
        self.backend.put_json(self._path(state["id"]), state)

    def list_projects(self) -> list[dict]:
        return [self.backend.get_json(path, {}) for path in self.backend.list("media_studio/projects") if path.endswith(".json")]

    def _asset(self, project_id: str, data: bytes, ext: str, category: str) -> str:
        digest = hashlib.sha256(data).hexdigest()
        path = f"media_studio/assets/{_identifier(project_id)}/{category}/{digest}{ext}"
        self.backend.put_bytes(path, data)
        return storage_uri(path)

    def add_image(self, project_id: str, data: bytes, *, approved: bool, provenance: str = "uploaded_original") -> dict:
        if not approved:
            raise MediaStudioError("Confirme a aprovação e o direito de usar a imagem antes de adicioná-la.")
        ext = _image(data)
        with _project_lock(project_id):
            state = self.load(project_id)
            if state["kind"] != "animation_video":
                raise MediaStudioError("Imagens do animatic pertencem a um projeto de vídeo.")
            digest = hashlib.sha256(data).hexdigest()
            if any(s.get("sha256") == digest for s in state["sources"]):
                return state
            if len(state["sources"]) >= 20:
                raise MediaStudioError("Use até 20 imagens por animatic.")
            uri = self._asset(project_id, data, ext, "sources")
            state["sources"].append({"id": uuid.uuid4().hex, "asset": uri, "sha256": digest, "approved": True,
                                     "provenance": str(provenance)[:1000], "approved_at": _now()})
            self.save(state)
            return state

    def add_audio(self, project_id: str, data: bytes, *, approved: bool) -> dict:
        if not approved or not data or len(data) > _MAX_BYTES:
            raise MediaStudioError("Confirme um áudio aprovado de até 50 MB.")
        root = tenant_local_directory("outputs") / f"media-{uuid.uuid4().hex}"
        root.mkdir(parents=True)
        path = root / "audio.bin"
        try:
            path.write_bytes(data)
            info = inspect_media(str(path), "music")
            ext = ".wav" if "wav" in info["format"] else ".mp3"
            with _project_lock(project_id):
                state = self.load(project_id)
                state["audio"] = {"asset": self._asset(project_id, data, ext, "sources"), "sha256": hashlib.sha256(data).hexdigest(),
                                  "approved": True, "approved_at": _now(), "inspection": info}
                self.save(state)
                return state
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def record_output(self, project_id: str, data: bytes, ext: str, info: dict, provenance: dict) -> dict:
        state = self.load(project_id)
        digest = hashlib.sha256(data).hexdigest()
        existing = next((o for o in state["outputs"] if o["sha256"] == digest), None)
        if existing:
            return existing
        output = {"id": uuid.uuid4().hex, "asset": self._asset(project_id, data, ext, "outputs"), "sha256": digest,
                  "status": "needs_review", "approved": False, "created_at": _now(), "inspection": info,
                  "provenance": deepcopy(provenance)}
        state["outputs"].append(output)
        state["status"] = "needs_review"
        self.save(state)
        return output

    def approve_output(self, project_id: str, output_id: str, *, confirmed: bool) -> dict:
        if not confirmed:
            raise MediaStudioError("Revise a mídia e confirme a aprovação.")
        with _project_lock(project_id):
            state = self.load(project_id)
            output = next((o for o in state["outputs"] if o["id"] == output_id), None)
            if not output:
                raise MediaStudioError("Resultado não encontrado neste projeto.")
            output.update(status="approved", approved=True, approved_at=_now())
            state["status"] = "approved"
            self.save(state)
            return output

    def capture_idea(self, text: str, *, title: str = "") -> dict:
        if not str(text or "").strip() or len(text) > 20000:
            raise MediaStudioError("Escreva uma ideia de até 20 mil caracteres.")
        idea = {"id": uuid.uuid4().hex, "schema": "faithbloom.idea-vault.v1", "title": str(title or "Nova ideia")[:240],
                "text": text.strip(), "status": "captured", "created_at": _now(), "auto_publish": False}
        self.backend.put_json(f"media_studio/ideas/{idea['id']}.json", idea)
        return idea

    def list_ideas(self) -> list[dict]:
        return [self.backend.get_json(path, {}) for path in self.backend.list("media_studio/ideas") if path.endswith(".json")]

    def approve_idea(self, idea_id: str, *, confirmed: bool) -> dict:
        if not confirmed:
            raise MediaStudioError("Confirme a escolha desta ideia.")
        path = f"media_studio/ideas/{_identifier(idea_id)}.json"
        idea = self.backend.get_json(path, {})
        if not idea or idea.get("id") != idea_id:
            raise MediaStudioError("Ideia não encontrada.")
        idea.update(status="approved", approved_at=_now())
        self.backend.put_json(path, idea)
        return idea


def render_animatic(store: MediaStudioStore, project_id: str, *, seconds_per_image: float = 3.0, width: int = 640, height: int = 360) -> dict:
    if not media_readiness()["local_animatic"]["available"]:
        raise MediaStudioError("O render local precisa de ffmpeg e ffprobe instalados no servidor.")
    if not isinstance(width, int) or not isinstance(height, int) or width % 2 or height % 2 or not 128 <= width <= 1280 or not 128 <= height <= 720:
        raise MediaStudioError("Use dimensões pares entre 128×128 e 1280×720.")
    try:
        duration = float(seconds_per_image)
    except (TypeError, ValueError):
        raise MediaStudioError("Duração inválida.") from None
    state = store.load(project_id)
    sources = state.get("sources", [])
    if not sources or not all(s.get("approved") for s in sources) or not math.isfinite(duration) or not 1 <= duration <= 10 or len(sources) * duration > 120:
        raise MediaStudioError("Adicione imagens aprovadas e escolha entre 1 e 10 segundos por imagem, até 120 segundos no total.")
    root = tenant_local_directory("outputs") / f"media-{uuid.uuid4().hex}"
    root.mkdir(parents=True)
    try:
        command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y"]
        filters = []
        # 10% padding keeps the whole source visible during the subtle zoom.
        fit_w, fit_h = int(width * .9) // 2 * 2, int(height * .9) // 2 * 2
        frames = int(duration * 24)
        for index, source in enumerate(sources):
            expected = f"fb://media_studio/assets/{project_id}/sources/"
            if not str(source.get("asset", "")).startswith(expected):
                raise MediaStudioError("Uma imagem pertence a outro projeto.")
            data = store.backend.get_bytes(source["asset"].removeprefix("fb://"))
            ext = _image(data)
            if hashlib.sha256(data).hexdigest() != source["sha256"]:
                raise MediaStudioError("Uma imagem mudou desde a aprovação.")
            path = root / f"source-{index}{ext}"
            path.write_bytes(data)
            command.extend(["-protocol_whitelist", "file,pipe", "-loop", "1", "-i", str(path)])
            filters.append(f"[{index}:v]scale={fit_w}:{fit_h}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=white,setsar=1,zoompan=z='min(1+on*0.0005,1.03)':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d={frames}:s={width}x{height}:fps=24,trim=duration={duration},setpts=PTS-STARTPTS[v{index}]")
        filters.append("".join(f"[v{i}]" for i in range(len(sources))) + f"concat=n={len(sources)}:v=1:a=0[v]")
        audio = state.get("audio")
        if audio:
            if not audio.get("approved") or not str(audio.get("asset", "")).startswith(f"fb://media_studio/assets/{project_id}/sources/"):
                raise MediaStudioError("Áudio não aprovado para este projeto.")
            data = store.backend.get_bytes(audio["asset"].removeprefix("fb://"))
            if hashlib.sha256(data).hexdigest() != audio["sha256"]:
                raise MediaStudioError("O áudio mudou desde a aprovação.")
            audio_path = root / "audio.bin"
            audio_path.write_bytes(data)
            inspect_media(str(audio_path), "music")
            command.extend(["-protocol_whitelist", "file,pipe", "-i", str(audio_path)])
        path = root / "animatic.mp4"
        command.extend(["-filter_complex_threads", "1", "-filter_complex", ";".join(filters), "-map", "[v]"])
        if audio:
            command.extend(["-map", f"{len(sources)}:a:0", "-af", "apad", "-c:a", "aac"])
        command.extend(["-t", str(len(sources) * duration), "-c:v", "libx264", "-threads", "1", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(path)])
        try:
            subprocess.run(command, capture_output=True, timeout=180, check=True)
        except (OSError, subprocess.SubprocessError):
            raise MediaStudioError("Não foi possível renderizar o animatic. As imagens aprovadas foram preservadas.") from None
        info = inspect_media(str(path), "animation_video")
        return store.record_output(project_id, path.read_bytes(), ".mp4", info,
                                   {"renderer": "ffmpeg_local_animatic", "character_animation": False,
                                    "source_sha256": [s["sha256"] for s in sources], "original_images_preserved": True,
                                    "seconds_per_image": duration, "audio_sha256": audio.get("sha256") if audio else None})
    finally:
        shutil.rmtree(root, ignore_errors=True)


def _public_output_url(url: str) -> str:
    try:
        parts = urlsplit(url)
        host = str(parts.hostname or "").lower()
        if parts.scheme != "https" or parts.username or parts.password or parts.port not in (None, 443) or not host or parts.fragment:
            raise ValueError
        if not any(host == base or host.endswith("." + base) for base in ("replicate.delivery", "replicateusercontent.com")):
            raise ValueError
        addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        if not addresses or any(not ipaddress.ip_address(item[4][0]).is_global for item in addresses):
            raise ValueError
    except (ValueError, OSError):
        raise MediaStudioError("O provedor retornou um endereço de mídia não autorizado.") from None
    return url


class ReplicateMediaClient:
    def __init__(self, store: MediaStudioStore, session=None):
        self.store = store
        self.session = session if session is not None else requests.Session()

    def draft(self, project_id: str, model_input: dict, *, source_id: str = "") -> dict:
        state = self.store.load(project_id)
        config = provider_configuration(state["kind"])
        if not config["available"]:
            raise MediaStudioError("Configure e habilite o modelo, seus campos de entrada e o orçamento antes da geração.")
        if not isinstance(model_input, dict) or not model_input or set(model_input) - set(config["input_fields"]):
            raise MediaStudioError("Os campos de entrada não correspondem ao modelo configurado.")
        model_input = deepcopy(model_input)
        source_hash = ""
        if state["kind"] == "animation_video":
            source = next((s for s in state["sources"] if s["id"] == source_id and s.get("approved")), None)
            if not source or not str(source.get("asset", "")).startswith(f"fb://media_studio/assets/{project_id}/sources/"):
                raise MediaStudioError("Selecione uma imagem original aprovada deste projeto para o vídeo.")
            data = self.store.backend.get_bytes(source["asset"].removeprefix("fb://"))
            ext = _image(data)
            source_hash = hashlib.sha256(data).hexdigest()
            if source_hash != source["sha256"]:
                raise MediaStudioError("A imagem mudou desde a aprovação.")
            if config["image_input_field"] in model_input:
                raise MediaStudioError("A imagem será fornecida pela fonte aprovada, sem URL substituta no JSON.")
            mime = {".png": "image/png", ".jpg": "image/jpeg", ".webp": "image/webp"}[ext]
            model_input[config["image_input_field"]] = f"data:{mime};base64," + base64.b64encode(data).decode("ascii")
        try:
            serialized = json.dumps(model_input, allow_nan=False)
            if len(serialized) > 10_000_000:
                raise ValueError
        except (TypeError, ValueError):
            raise MediaStudioError("Entrada JSON inválida ou maior que 10 MB.") from None
        draft = {"project_id": project_id, "kind": state["kind"], "model": config["model"], "input": deepcopy(model_input),
                 "estimated_cost_usd": config["estimated_cost_usd"], "max_cost_usd": config["max_cost_usd"],
                 "source_id": source_id, "source_sha256": source_hash, "uses_personal_data": state.get("uses_personal_data") is True}
        draft["fingerprint"] = _digest(draft)
        return draft

    def _json(self, response) -> dict:
        try:
            response.raise_for_status()
            if not 200 <= response.status_code < 300:
                raise ValueError
            value = response.json()
            if not isinstance(value, dict):
                raise ValueError
            return value
        except (requests.RequestException, ValueError):
            raise MediaStudioError("Não foi possível confirmar a resposta do provedor. Consulte o processamento antes de iniciar outro.") from None

    def submit(self, draft: dict, *, confirmed_fingerprint: str, consent_confirmed: bool = False) -> dict:
        with _project_lock(draft.get("project_id", "")):
            original_input = deepcopy(draft.get("input"))
            if draft.get("kind") == "animation_video" and isinstance(original_input, dict):
                original_input.pop(provider_configuration("animation_video")["image_input_field"], None)
            expected = self.draft(draft.get("project_id", ""), original_input, source_id=draft.get("source_id", ""))
            if draft != expected or confirmed_fingerprint != expected["fingerprint"]:
                raise MediaStudioError("Revise e confirme a entrada, o modelo e o custo desta geração.")
            state = self.store.load(expected["project_id"])
            prior = next((j for j in state["jobs"] if j.get("fingerprint") == expected["fingerprint"]), None)
            if prior:
                return prior
            if any(j.get("status") in _ACTIVE for j in state["jobs"]):
                raise MediaStudioError("Há um processamento pendente ou incerto. Não será enviada outra geração paga.")
            estimated_total = sum(float(j.get("estimated_cost_usd") or 0) for j in state["jobs"]) + expected["estimated_cost_usd"]
            if estimated_total > expected["max_cost_usd"]:
                raise MediaStudioError("O orçamento estimado deste projeto foi atingido. Nenhuma nova geração foi enviada.")
            job = {"id": uuid.uuid4().hex, "fingerprint": expected["fingerprint"], "model": expected["model"],
                   "input": deepcopy(expected["input"]), "estimated_cost_usd": expected["estimated_cost_usd"],
                   "status": "submission_pending", "created_at": _now(), "prediction_id": "",
                   "source_id": expected["source_id"], "source_sha256": expected["source_sha256"]}
            from governance_runtime import authorize_generation
            job["governance"] = authorize_generation(
                "media.generate", confirmed=True, projected_cost=expected["estimated_cost_usd"],
                provider_configured=provider_configuration(state["kind"])["available"],
                operation_id=job["id"], source_module="media_studio.py", state=state,
                budget_remaining=expected["max_cost_usd"] - (estimated_total - expected["estimated_cost_usd"]),
                uses_personal_data=bool(state.get("uses_personal_data")),
                consent_confirmed=consent_confirmed is True,
            )
            state["jobs"].append(job)
            # A failed checkpoint stops BEFORE POST; an interrupted POST remains
            # pending/uncertain and cannot be duplicated by rerun or restart.
            self.store.save(state)
            try:
                response = self.session.post(f"{_API}/models/{job['model']}/predictions", json={"input": job["input"]},
                                             headers={"Authorization": f"Bearer {_setting('REPLICATE_API_TOKEN')}"},
                                             timeout=(5, 20), allow_redirects=False)
                value = self._json(response)
                prediction_id = str(value.get("id", ""))
                if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", prediction_id):
                    raise MediaStudioError("Não foi possível confirmar o identificador da geração.")
                job.update(prediction_id=prediction_id, status="starting", submitted_at=_now())
                # Provider ID is saved BEFORE any status/output request.
                self.store.save(state)
            except (requests.RequestException, MediaStudioError):
                job["status"] = "submission_uncertain"
                self.store.save(state)
                raise MediaStudioError("O envio ficou incerto. Nenhuma geração paga será repetida automaticamente; confira o painel do provedor.") from None
            return deepcopy(job)

    def poll(self, project_id: str, job_id: str) -> dict:
        with _project_lock(project_id):
            state = self.store.load(project_id)
            job = next((j for j in state["jobs"] if j["id"] == job_id), None)
            if not job:
                raise MediaStudioError("Processamento não encontrado neste projeto.")
            prediction_id = job.get("prediction_id", "")
            if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", prediction_id):
                raise MediaStudioError("Sem identificador confirmado; confira o painel do provedor antes de qualquer novo envio.")
            if job.get("output_id") or job.get("status") in {"failed", "canceled"}:
                return deepcopy(job)
            try:
                response = self.session.get(f"{_API}/predictions/{prediction_id}",
                                            headers={"Authorization": f"Bearer {_setting('REPLICATE_API_TOKEN')}"},
                                            timeout=(5, 15), allow_redirects=False)
                value = self._json(response)
            except requests.RequestException:
                raise MediaStudioError("Não foi possível consultar o processamento agora. O identificador foi preservado.") from None
            if str(value.get("id")) != prediction_id or value.get("status") not in {"starting", "processing"} | _TERMINAL:
                raise MediaStudioError("Resposta de processamento inválida; o identificador foi preservado.")
            job.update(status=value["status"], checked_at=_now())
            self.store.save(state)
            if job["status"] == "succeeded":
                output = value.get("output")
                if isinstance(output, dict):
                    output = output.get("audio" if state["kind"] == "music" else "video") or output.get("url")
                if isinstance(output, list):
                    output = output[0] if len(output) == 1 else None
                if not isinstance(output, str):
                    raise MediaStudioError("O modelo não retornou um único arquivo de mídia compatível.")
                url = _public_output_url(output)
                root = tenant_local_directory("outputs") / f"media-{uuid.uuid4().hex}"
                root.mkdir(parents=True)
                path = root / "provider-output.bin"
                try:
                    # No bearer token is ever forwarded to a media CDN.
                    response = self.session.get(url, stream=True, timeout=(5, 20), allow_redirects=False)
                    if 300 <= response.status_code < 400:
                        raise MediaStudioError("Redirecionamentos de mídia não são autorizados.")
                    response.raise_for_status()
                    size = 0
                    started = time.monotonic()
                    with path.open("wb") as target:
                        for chunk in response.iter_content(65536):
                            size += len(chunk)
                            if size > _MAX_BYTES or time.monotonic() - started > 30:
                                raise MediaStudioError("A mídia do provedor excedeu o limite de 50 MB.")
                            target.write(chunk)
                    info = inspect_media(str(path), state["kind"])
                    ext = ".mp4" if state["kind"] == "animation_video" else (".wav" if "wav" in info["format"] else ".mp3")
                    result = self.store.record_output(project_id, path.read_bytes(), ext, info,
                                                     {"provider": "replicate", "model": job["model"], "prediction_id": prediction_id,
                                                      "request_fingerprint": job["fingerprint"], "estimated_cost_usd": job["estimated_cost_usd"]})
                    # Reload to retain the output appended by record_output.
                    state = self.store.load(project_id)
                    job = next(j for j in state["jobs"] if j["id"] == job_id)
                    job["output_id"] = result["id"]
                    self.store.save(state)
                except requests.RequestException:
                    raise MediaStudioError("Não foi possível baixar a mídia. Atualize este processamento para tentar somente o download.") from None
                finally:
                    if 'response' in locals() and hasattr(response, "close"):
                        response.close()
                    shutil.rmtree(root, ignore_errors=True)
            return deepcopy(job)
