"""Botão push-to-talk do Jarvis para Streamlit.

Este componente não duplica STT/TTS. Ele resolve apenas a captura no navegador:
pressionar -> gravar -> soltar -> devolver áudio ao Python automaticamente.
A transcrição e a voz continuam em ``jarvis_voice.py``.
"""
from __future__ import annotations

import base64
from typing import Any

import streamlit as st


HTML = """
<div class="ptt-wrap">
  <button id="ptt" type="button" aria-label="Segure para falar com Jarvis">
    <span class="ptt-icon">🎙️</span>
    <span class="ptt-label">Segure para falar</span>
  </button>
  <div id="ptt-status" class="ptt-status">Toque e segure. Solte quando terminar.</div>
</div>
"""

CSS = """
.ptt-wrap{display:flex;flex-direction:column;align-items:center;gap:.65rem;padding:.4rem 0 .15rem;font-family:var(--st-font)}
#ptt{width:min(100%,420px);min-height:74px;border:0;border-radius:999px;padding:.85rem 1.2rem;display:flex;align-items:center;justify-content:center;gap:.8rem;background:linear-gradient(135deg,#176e76,#6457d7);color:white;font-weight:800;font-size:1.05rem;box-shadow:0 14px 32px rgba(40,84,130,.22);cursor:pointer;touch-action:none;user-select:none;-webkit-user-select:none;transition:transform .15s ease,box-shadow .15s ease,filter .15s ease}
#ptt:active,#ptt.recording{transform:scale(.985);filter:brightness(1.08);box-shadow:0 0 0 7px rgba(75,220,218,.14),0 15px 34px rgba(40,84,130,.26)}
#ptt.recording{background:linear-gradient(135deg,#b83263,#7453d8)}
.ptt-icon{font-size:1.55rem}.ptt-status{text-align:center;font-size:.84rem;color:var(--st-text-color);opacity:.72;min-height:1.2em}.ptt-status.error{color:#c43f62;opacity:1}.ptt-status.live{color:#b83263;opacity:1;font-weight:800}
"""

JS = r"""
export default function(component) {
  const { parentElement, setTriggerValue } = component;
  const button = parentElement.querySelector('#ptt');
  const label = parentElement.querySelector('.ptt-label');
  const status = parentElement.querySelector('#ptt-status');
  if (!button || button.dataset.bound === '1') return;
  button.dataset.bound = '1';

  let recorder = null;
  let stream = null;
  let chunks = [];
  let startedAt = 0;
  let activePointer = null;

  const setStatus = (text, cls='') => {
    status.textContent = text;
    status.className = 'ptt-status' + (cls ? ' ' + cls : '');
  };

  const cleanup = () => {
    if (stream) {
      stream.getTracks().forEach(track => track.stop());
      stream = null;
    }
    recorder = null;
    activePointer = null;
    button.classList.remove('recording');
    label.textContent = 'Segure para falar';
  };

  const begin = async (e) => {
    e.preventDefault();
    if (recorder && recorder.state === 'recording') return;
    activePointer = e.pointerId;
    try {
      button.setPointerCapture?.(e.pointerId);
      stream = await navigator.mediaDevices.getUserMedia({audio:true});
      chunks = [];
      const preferred = [
        'audio/webm;codecs=opus',
        'audio/webm',
        'audio/mp4',
        'audio/ogg;codecs=opus'
      ].find(t => window.MediaRecorder && MediaRecorder.isTypeSupported && MediaRecorder.isTypeSupported(t));
      recorder = preferred ? new MediaRecorder(stream,{mimeType:preferred}) : new MediaRecorder(stream);
      recorder.ondataavailable = ev => { if (ev.data && ev.data.size) chunks.push(ev.data); };
      recorder.onerror = () => {
        setStatus('Não consegui gravar. Verifique a permissão do microfone.', 'error');
        cleanup();
      };
      recorder.onstop = () => {
        const duration = Date.now() - startedAt;
        const mime = recorder?.mimeType || chunks[0]?.type || 'audio/webm';
        const blob = new Blob(chunks,{type:mime});
        if (!blob.size || duration < 250) {
          setStatus('Fale por um pouco mais de tempo e tente novamente.', 'error');
          cleanup();
          return;
        }
        const reader = new FileReader();
        reader.onloadend = () => {
          const dataUrl = String(reader.result || '');
          const base64Data = dataUrl.includes(',') ? dataUrl.split(',',2)[1] : '';
          if (!base64Data) {
            setStatus('Não consegui preparar o áudio. Tente novamente.', 'error');
            cleanup();
            return;
          }
          setStatus('✅ Recebi. Jarvis está processando...');
          setTriggerValue('recording', {
            id: `${Date.now()}-${blob.size}`,
            data: base64Data,
            mime_type: mime,
            duration_ms: duration
          });
          cleanup();
        };
        reader.readAsDataURL(blob);
      };
      recorder.start(120);
      startedAt = Date.now();
      button.classList.add('recording');
      label.textContent = 'Ouvindo… solte para enviar';
      setStatus('🔴 Ouvindo você…', 'live');
    } catch (err) {
      cleanup();
      if (String(err?.name || '').includes('NotAllowed')) {
        setStatus('Microfone bloqueado. Permita o acesso ao microfone no navegador.', 'error');
      } else {
        setStatus('Não consegui acessar o microfone neste navegador.', 'error');
      }
    }
  };

  const finish = (e) => {
    if (activePointer !== null && e.pointerId !== undefined && e.pointerId !== activePointer) return;
    e.preventDefault();
    if (recorder && recorder.state === 'recording') {
      label.textContent = 'Enviando…';
      setStatus('⏳ Preparando sua mensagem…');
      recorder.stop();
    } else {
      cleanup();
    }
  };

  button.addEventListener('pointerdown', begin);
  button.addEventListener('pointerup', finish);
  button.addEventListener('pointercancel', finish);
  button.addEventListener('lostpointercapture', (e) => {
    if (recorder && recorder.state === 'recording') finish(e);
  });

  return () => {
    try { if (recorder && recorder.state === 'recording') recorder.stop(); } catch (_) {}
    cleanup();
  };
}
"""


def _format_from_mime(mime_type: str | None) -> str:
    mime = (mime_type or "").casefold()
    if "wav" in mime:
        return "wav"
    if "mpeg" in mime or "mp3" in mime:
        return "mp3"
    if "mp4" in mime or "m4a" in mime:
        return "m4a"
    if "ogg" in mime:
        return "ogg"
    if "aac" in mime:
        return "aac"
    return "webm"


def decode_recording(payload: dict[str, Any] | None) -> tuple[bytes, str, str] | None:
    """Decodifica o payload do navegador em bytes, formato e id estável."""
    if not payload or not payload.get("data"):
        return None
    raw = base64.b64decode(str(payload["data"]), validate=True)
    if not raw:
        return None
    return raw, _format_from_mime(payload.get("mime_type")), str(payload.get("id") or "")


def push_to_talk(*, key: str = "jarvis_push_to_talk"):
    """Renderiza push-to-talk V2. Retorna ``result.recording`` ao soltar.

    Em Streamlit antigo, retorna ``None`` para que a página use o fallback nativo.
    """
    components = getattr(st, "components", None)
    v2 = getattr(components, "v2", None) if components else None
    component_factory = getattr(v2, "component", None) if v2 else None
    if component_factory is None:
        return None
    widget = component_factory(
        "faithbloom_jarvis_push_to_talk",
        html=HTML,
        css=CSS,
        js=JS,
    )
    return widget(
        key=key,
        default={"recording": None},
        on_recording_change=lambda: None,
    )
