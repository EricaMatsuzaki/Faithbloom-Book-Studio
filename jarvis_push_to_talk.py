"""Jarvis premium visual shell with push-to-talk and direct text input.

The approved FaithBloom/Jarvis artwork is used as the canonical visual skin so
that the Streamlit page preserves the exact robot and composition chosen by the
user. Interactive hotspots sit on top of the artwork; STT/TTS still live in
``jarvis_voice.py`` and navigation is handled by the Streamlit page.
"""
from __future__ import annotations

import base64
from functools import lru_cache
from pathlib import Path
from typing import Any

import streamlit as st

_SKIN_PATH = Path(__file__).resolve().parent / "assets" / "jarvis_premium_ui_reference.jpg"
_SKIN_TOKEN = "__FAITHBLOOM_JARVIS_SKIN__"


@lru_cache(maxsize=1)
def _skin_b64() -> str:
    try:
        return base64.b64encode(_SKIN_PATH.read_bytes()).decode("ascii")
    except OSError:
        return ""


HTML = r"""
<div class="fb-jarvis-ui" id="fb-jarvis-ui">
  <img id="fb-jarvis-skin" class="fb-jarvis-skin" src="data:image/jpeg;base64,__FAITHBLOOM_JARVIS_SKIN__" alt="FaithBloom Jarvis Premium Futurista">
  <div id="fb-speech" class="fb-speech" aria-live="polite"></div>
  <div id="fb-weather" class="fb-weather-truth" aria-label="Status do clima"></div>
  <div id="fb-agenda" class="fb-agenda-truth" aria-label="Status da agenda"></div>
  <button id="fb-ptt" class="fb-hotspot fb-ptt" type="button" aria-label="Segure para falar com Jarvis"></button>
  <div id="fb-ptt-status" class="fb-ptt-status" aria-live="polite">Jarvis ouvindo e pronto para ajudar</div>
  <form id="fb-text-form" class="fb-text-form" autocomplete="off">
    <input id="fb-text-input" type="text" maxlength="500" aria-label="Digite sua mensagem para Jarvis" placeholder="Digite sua mensagem">
    <button type="submit" aria-label="Enviar mensagem">➤</button>
  </form>
  <button class="fb-hotspot fb-nav nav-orchestrator" data-nav="orchestrator" aria-label="Abrir Orquestrador FaithBloom"></button>
  <button class="fb-hotspot fb-nav nav-create" data-nav="create" aria-label="Criar do Zero"></button>
  <button class="fb-hotspot fb-nav nav-resume" data-nav="resume" aria-label="Retomar Livro"></button>
  <button class="fb-hotspot fb-nav nav-characters" data-nav="characters" aria-label="Abrir Personagens"></button>
  <button class="fb-hotspot fb-nav nav-library" data-nav="library" aria-label="Abrir Biblioteca Editorial"></button>
  <button class="fb-hotspot fb-nav nav-project" data-nav="project" aria-label="Abrir Project Hub"></button>
  <button class="fb-hotspot fb-nav nav-gallery" data-nav="gallery" aria-label="Abrir Galeria e Armazenamento"></button>
  <button class="fb-hotspot fb-nav quick-create" data-nav="create" aria-label="Criar livro"></button>
  <button class="fb-hotspot fb-nav quick-review" data-nav="review" aria-label="Revisar projeto"></button>
  <button class="fb-hotspot fb-nav quick-pending" data-nav="project" aria-label="Ver pendências"></button>
</div>
"""

CSS = r"""
:host{display:block;width:100%}*{box-sizing:border-box}.fb-jarvis-ui{position:relative;width:100%;max-width:1672px;aspect-ratio:1672/941;margin:0 auto;overflow:hidden;background:#f7fbff;font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}.fb-jarvis-skin{position:absolute;inset:0;width:100%;height:100%;object-fit:contain;display:block;pointer-events:none;user-select:none;-webkit-user-drag:none}.fb-hotspot{position:absolute;border:0;background:transparent;cursor:pointer;padding:0;margin:0;outline:none;-webkit-tap-highlight-color:transparent}.fb-hotspot:focus-visible{outline:3px solid rgba(44,226,255,.85);outline-offset:2px;border-radius:18px}.fb-nav:hover{background:rgba(60,190,255,.045);border-radius:18px}.fb-speech{position:absolute;left:57.55%;top:11.55%;width:20.75%;height:15.05%;padding:1.1% 1.35%;display:flex;align-items:flex-start;justify-content:center;text-align:left;color:#fff;font-weight:600;line-height:1.27;font-size:clamp(9px,1.02vw,18px);overflow:hidden;border-radius:28px;background:linear-gradient(135deg,rgba(6,87,124,.98),rgba(77,42,147,.98));border:1.5px solid rgba(94,244,255,.95);box-shadow:0 0 22px rgba(69,225,255,.35),inset 0 0 24px rgba(91,91,255,.18);z-index:3}.fb-speech:after{content:"";position:absolute;left:14%;bottom:-12%;width:9%;height:19%;background:linear-gradient(145deg,rgba(5,114,155,.98),rgba(39,65,167,.98));clip-path:polygon(0 0,100% 0,15% 100%)}.fb-weather-truth,.fb-agenda-truth{position:absolute;left:86.25%;width:9.15%;height:4.1%;display:flex;align-items:center;color:white;font-size:clamp(7px,.72vw,12px);line-height:1.15;background:linear-gradient(90deg,rgba(15,58,101,.97),rgba(19,46,88,.97));z-index:4;padding-left:.15%}.fb-weather-truth{top:28.8%}.fb-agenda-truth{top:37.1%}.fb-ptt{left:41.35%;top:67.2%;width:27.05%;height:7.7%;border-radius:999px;z-index:5}.fb-ptt:hover{box-shadow:0 0 0 3px rgba(89,231,255,.16),0 0 28px rgba(117,72,255,.24)}.fb-ptt.recording{background:rgba(255,50,135,.12);box-shadow:0 0 0 4px rgba(255,92,176,.20),0 0 34px rgba(255,75,177,.42)}.fb-ptt-status{position:absolute;left:43.5%;top:75.25%;width:24%;height:2.7%;display:flex;align-items:center;justify-content:center;z-index:5;color:#173b70;font-weight:600;font-size:clamp(7px,.72vw,12px);background:rgba(247,252,255,.93);border-radius:999px;white-space:nowrap}.fb-ptt-status.live{color:#b01862}.fb-ptt-status.error{color:#b42318}.fb-ptt-status.thinking{color:#5138a8}.fb-text-form{position:absolute;left:80.4%;top:67.95%;width:14.75%;height:6.45%;z-index:6;display:flex;align-items:center;gap:2%;padding:.4% .55%;border-radius:18px;background:rgba(247,251,255,.97);border:1px solid rgba(149,184,229,.42)}.fb-text-form input{min-width:0;flex:1;border:0;outline:0;background:transparent;color:#183a72;font:inherit;font-size:clamp(8px,.78vw,13px);padding:0 .25rem}.fb-text-form input::placeholder{color:#6e82aa;opacity:.95}.fb-text-form button{width:22%;height:72%;border:0;border-radius:999px;background:transparent;color:#173b70;font-size:clamp(9px,1vw,17px);cursor:pointer}.fb-text-form button:hover{background:rgba(90,143,235,.10)}.nav-orchestrator{left:1.0%;top:18.1%;width:15.2%;height:4.3%}.nav-create{left:1.0%;top:32.0%;width:15.2%;height:4.7%}.nav-resume{left:1.0%;top:36.7%;width:15.2%;height:4.7%}.nav-characters{left:1.0%;top:47.6%;width:15.2%;height:4.7%}.nav-library{left:1.0%;top:52.2%;width:15.2%;height:4.7%}.nav-project{left:1.0%;top:56.8%;width:15.2%;height:4.7%}.nav-gallery{left:1.0%;top:74.0%;width:15.2%;height:4.8%}.quick-create{left:18.45%;top:80.25%;width:25.35%;height:11.45%}.quick-review{left:44.75%;top:80.25%;width:25.45%;height:11.45%}.quick-pending{left:71.0%;top:80.25%;width:26.0%;height:11.45%}@media(max-width:820px){.fb-speech{font-size:clamp(6px,1.55vw,12px);border-radius:16px}.fb-agenda-truth{font-size:clamp(5px,1vw,8px)}.fb-text-form{border-radius:11px}.fb-ptt-status{font-size:clamp(5px,1vw,8px)}}
"""

JS = r"""
export default function(component) {
  const { parentElement, setStateValue, setTriggerValue, data } = component;
  const root=parentElement.querySelector('#fb-jarvis-ui');if(!root)return;
  const speech=root.querySelector('#fb-speech'),ptt=root.querySelector('#fb-ptt'),status=root.querySelector('#fb-ptt-status'),form=root.querySelector('#fb-text-form'),input=root.querySelector('#fb-text-input'),weather=root.querySelector('#fb-weather'),agenda=root.querySelector('#fb-agenda');
  const greeting=(data&&data.greeting)||'Olá, Erica! O que vamos fazer hoje?',reply=(data&&data.reply_text)||'',replyAudio=(data&&data.reply_audio)||'',replyToken=(data&&data.reply_token)||'',weatherStatus=(data&&data.weather_status)||'Pronto para consultar',agendaStatus=(data&&data.agenda_status)||'Ainda não conectada';
  if(speech)speech.textContent=reply||greeting;if(weather)weather.textContent=weatherStatus;if(agenda)agenda.textContent=agendaStatus;
  const setStatus=(text,cls='')=>{if(!status)return;status.textContent=text;status.className='fb-ptt-status'+(cls?' '+cls:'');};
  const speakNative=(text)=>{if(!('speechSynthesis'in window)||!text)return;try{window.speechSynthesis.cancel();const u=new SpeechSynthesisUtterance(text);const voices=window.speechSynthesis.getVoices?.()||[];const preferred=voices.find(v=>/pt[-_]BR/i.test(v.lang)&&/male|mascul/i.test(v.name))||voices.find(v=>/pt[-_]BR/i.test(v.lang))||voices.find(v=>/pt[-_]PT/i.test(v.lang));if(preferred)u.voice=preferred;u.lang=preferred?.lang||'pt-BR';u.rate=.93;u.pitch=.88;u.onstart=()=>setStatus('Jarvis está falando…');u.onend=()=>setStatus('Jarvis ouvindo e pronto para ajudar');u.onerror=()=>setStatus('Resposta pronta');window.speechSynthesis.speak(u);}catch(_){}};
  const speakReply=()=>{if(replyAudio){try{const a=new Audio('data:audio/mpeg;base64,'+replyAudio);a.onplay=()=>setStatus('Jarvis está falando…');a.onended=()=>setStatus('Jarvis ouvindo e pronto para ajudar');a.onerror=()=>speakNative(reply);const p=a.play();if(p&&p.catch)p.catch(()=>speakNative(reply));return;}catch(_){}}if(reply)speakNative(reply);};
  try{if(reply&&replyToken&&sessionStorage.getItem('faithbloom_jarvis_reply')!==replyToken){sessionStorage.setItem('faithbloom_jarvis_reply',replyToken);setTimeout(speakReply,160);}}catch(_){if(reply)setTimeout(speakReply,160);}if(root.dataset.bound==='1')return;root.dataset.bound='1';
  let recorder=null,stream=null,chunks=[],startedAt=0,activePointer=null;const cleanup=()=>{if(stream){stream.getTracks().forEach(t=>t.stop());stream=null;}recorder=null;activePointer=null;ptt?.classList.remove('recording');};
  const begin=async(e)=>{e.preventDefault();if(recorder&&recorder.state==='recording')return;window.speechSynthesis?.cancel();activePointer=e.pointerId;try{ptt?.setPointerCapture?.(e.pointerId);stream=await navigator.mediaDevices.getUserMedia({audio:true});chunks=[];const preferred=['audio/webm;codecs=opus','audio/webm','audio/mp4','audio/ogg;codecs=opus'].find(t=>window.MediaRecorder&&MediaRecorder.isTypeSupported?.(t));recorder=preferred?new MediaRecorder(stream,{mimeType:preferred}):new MediaRecorder(stream);recorder.ondataavailable=ev=>{if(ev.data&&ev.data.size)chunks.push(ev.data);};recorder.onerror=()=>{setStatus('Microfone indisponível','error');cleanup();};recorder.onstop=()=>{const duration=Date.now()-startedAt,mime=recorder?.mimeType||chunks[0]?.type||'audio/webm',blob=new Blob(chunks,{type:mime});if(!blob.size||duration<350){setStatus('Fale um pouco mais e tente novamente','error');cleanup();return;}const reader=new FileReader();reader.onloadend=()=>{const dataUrl=String(reader.result||''),encoded=dataUrl.includes(',')?dataUrl.split(',',2)[1]:'';if(!encoded){setStatus('Não consegui preparar o áudio','error');cleanup();return;}const id=`${Date.now()}-${blob.size}`;setStateValue('recording',{id,data:encoded,mime_type:mime,duration_ms:duration});setStatus('Pensando e executando…','thinking');setTriggerValue('submitted',id);cleanup();};reader.readAsDataURL(blob);};recorder.start(120);startedAt=Date.now();ptt?.classList.add('recording');setStatus('Ouvindo… solte quando terminar','live');}catch(err){cleanup();setStatus(String(err?.name||'').includes('NotAllowed')?'Permita o microfone no navegador':'Não consegui acessar o microfone','error');}};
  const finish=(e)=>{if(activePointer!==null&&e.pointerId!==undefined&&e.pointerId!==activePointer)return;e.preventDefault();if(recorder&&recorder.state==='recording'){setStatus('Enviando sua fala…','thinking');recorder.stop();}else cleanup();};ptt?.addEventListener('pointerdown',begin);ptt?.addEventListener('pointerup',finish);ptt?.addEventListener('pointercancel',finish);ptt?.addEventListener('lostpointercapture',e=>{if(recorder&&recorder.state==='recording')finish(e);});
  form?.addEventListener('submit',e=>{e.preventDefault();const text=String(input?.value||'').trim();if(!text)return;const id=`text-${Date.now()}`;setStateValue('typed_request',{id,text});setTriggerValue('typed_submitted',id);if(input)input.value='';setStatus('Pensando e executando…','thinking');});
  root.querySelectorAll('[data-nav]').forEach(el=>el.addEventListener('click',()=>{const destination=el.getAttribute('data-nav');if(!destination)return;const id=`nav-${Date.now()}-${destination}`;setStateValue('navigation',{id,destination});setTriggerValue('navigation_submitted',id);}));return()=>{try{if(recorder&&recorder.state==='recording')recorder.stop();}catch(_){}cleanup();};
}
"""


def _format_from_mime(mime_type: str | None) -> str:
    mime=(mime_type or "").casefold()
    if "wav" in mime:return "wav"
    if "mpeg" in mime or "mp3" in mime:return "mp3"
    if "mp4" in mime or "m4a" in mime:return "m4a"
    if "ogg" in mime:return "ogg"
    if "aac" in mime:return "aac"
    return "webm"


def decode_recording(payload: dict[str, Any] | None) -> tuple[bytes, str, str] | None:
    if not payload or not payload.get("data"):return None
    raw=base64.b64decode(str(payload["data"]),validate=True)
    if not raw:return None
    return raw,_format_from_mime(payload.get("mime_type")),str(payload.get("id") or "")


def _inline_css() -> str:
    """Force Streamlit 1.63+ to classify this CSS as inline, not as an asset path."""
    return CSS + "\n/* faithbloom-inline-css */"


def _html_with_skin() -> str:
    """Embed the canonical image before component registration.

    Passing a large base64 image through component ``data`` can be dropped by the
    frontend transport on some browsers/Streamlit deployments. Embedding it in
    the HTML avoids that failure while keeping the exact approved artwork.
    """
    skin = _skin_b64()
    if not skin:
        return HTML.replace(f"data:image/jpeg;base64,{_SKIN_TOKEN}", "")
    return HTML.replace(_SKIN_TOKEN, skin)


def push_to_talk(*,key: str="jarvis_push_to_talk",greeting: str="",reply_text: str="",reply_audio: str="",reply_token: str="",weather_status: str="Pronto para consultar",agenda_status: str="Ainda não conectada"):
    components=getattr(st,"components",None);v2=getattr(components,"v2",None) if components else None;factory=getattr(v2,"component",None) if v2 else None
    if factory is None:return None
    widget=factory("faithbloom_jarvis_premium_shell",html=_html_with_skin(),css=_inline_css(),js=JS)
    return widget(key=key,data={"greeting":greeting,"reply_text":reply_text,"reply_audio":reply_audio,"reply_token":reply_token,"weather_status":weather_status,"agenda_status":agenda_status},default={"recording":None,"submitted":None,"typed_request":None,"typed_submitted":None,"navigation":None,"navigation_submitted":None},on_recording_change=lambda:None,on_submitted_change=lambda:None,on_typed_request_change=lambda:None,on_typed_submitted_change=lambda:None,on_navigation_change=lambda:None,on_navigation_submitted_change=lambda:None)
