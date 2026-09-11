"""Interactive heart microphone for the canonical FaithBloom Jarvis.

The heart is the voice control: tap once to listen, tap again to stop. Audio
playback is intentionally handled by the native Streamlit player in the canonical
Jarvis page, which is more reliable on Safari/iPhone. This component owns only
microphone capture and visual state; it must never synthesize or replay speech.
"""
from __future__ import annotations

import base64
from typing import Any

import streamlit as st

HTML = r"""
<div class="jh-shell" id="jh-shell">
  <div class="jh-aura"></div><div class="jh-floor"></div>
  <div class="jh-robot" id="jh-robot" aria-label="Jarvis interativo do FaithBloom">
    <div class="jh-ant"></div>
    <div class="jh-head"><div class="jh-face"><div class="jh-eye l"></div><div class="jh-eye r"></div><div class="jh-smile"></div><div class="jh-scan"></div></div></div>
    <div class="jh-arm l"></div><div class="jh-arm r"></div>
    <div class="jh-body"><button id="jh-heart" class="jh-heart" type="button" aria-label="Falar com Jarvis">♥</button></div>
  </div>
  <div class="jh-status" id="jh-status">Toque no coração para falar</div>
</div>
"""

CSS = r"""
:host{display:block;width:100%;font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}*{box-sizing:border-box}.jh-shell{position:relative;min-height:390px;display:grid;place-items:center;color:#dffcff;overflow:visible}.jh-aura{position:absolute;width:330px;height:330px;border-radius:50%;background:radial-gradient(circle,rgba(72,231,255,.22),rgba(100,83,255,.09) 46%,transparent 70%);animation:jAura 3s ease-in-out infinite}.jh-floor{position:absolute;bottom:42px;width:255px;height:54px;border-radius:50%;background:radial-gradient(ellipse,rgba(83,235,255,.34),transparent 68%);filter:blur(7px);animation:jFloor 2.4s ease-in-out infinite}.jh-robot{position:relative;width:240px;height:335px;animation:jFloat 4.2s ease-in-out infinite;filter:drop-shadow(0 26px 28px rgba(0,0,0,.24));z-index:2}.jh-ant{position:absolute;left:50%;top:4px;transform:translateX(-50%);width:10px;height:44px;border-radius:12px;background:linear-gradient(#e6feff,#5ce5ed);box-shadow:0 0 18px rgba(92,229,237,.8)}.jh-ant:before{content:'';position:absolute;width:18px;height:18px;border-radius:50%;left:-4px;top:-9px;background:#8ff9f3;box-shadow:0 0 22px #8ff9f3}.jh-head{position:absolute;left:17px;top:46px;width:206px;height:150px;border-radius:49% 49% 43% 43%/43% 43% 52% 52%;background:linear-gradient(145deg,#fff,#d8e9f5 62%,#aabdd0);border:2px solid rgba(255,255,255,.95);box-shadow:inset -12px -14px 25px rgba(57,80,110,.16),0 0 35px rgba(83,237,255,.22)}.jh-face{position:absolute;inset:18px 17px 22px;border-radius:51px;background:radial-gradient(circle at 50% 23%,#18476a,#07131f 69%);border:2px solid #76f4ef;box-shadow:inset 0 0 30px rgba(80,219,245,.14),0 0 23px rgba(89,239,242,.36)}.jh-eye{position:absolute;top:47px;width:42px;height:15px;border-top:7px solid #77fff4;border-radius:50%;filter:drop-shadow(0 0 7px #77fff4);animation:jBlink 5s infinite}.jh-eye.l{left:34px}.jh-eye.r{right:34px}.jh-smile{position:absolute;left:50%;bottom:24px;transform:translateX(-50%);width:40px;height:19px;border-bottom:6px solid #78fff5;border-radius:0 0 28px 28px;filter:drop-shadow(0 0 8px #78fff5)}.jh-scan{position:absolute;left:20px;right:20px;top:58px;height:2px;background:linear-gradient(90deg,transparent,#75fff7,transparent);box-shadow:0 0 14px #75fff7;opacity:0}.jh-body{position:absolute;left:51px;top:198px;width:138px;height:112px;border-radius:36px 36px 48px 48px;background:linear-gradient(145deg,#fff,#d9e8f2 67%,#a5b8cb);border:2px solid rgba(255,255,255,.92);box-shadow:inset -11px -13px 22px rgba(55,76,105,.15)}.jh-arm{position:absolute;top:215px;width:31px;height:82px;border-radius:20px;background:linear-gradient(#f6fbff,#a9bed0);border:1px solid rgba(255,255,255,.9)}.jh-arm.l{left:25px;transform:rotate(18deg)}.jh-arm.r{right:25px;transform:rotate(-18deg)}.jh-heart{position:absolute;left:50%;top:24px;transform:translateX(-50%);width:62px;height:62px;border-radius:50%;border:4px solid #66eef1;background:#071927;color:#ff7fd1;font-size:29px;line-height:1;cursor:pointer;box-shadow:0 0 28px rgba(102,238,241,.72),inset 0 0 18px rgba(108,103,255,.22);animation:jCore 1.7s ease-in-out infinite;-webkit-tap-highlight-color:transparent}.jh-heart:focus-visible{outline:3px solid #fff;outline-offset:4px}.jh-heart.listening{color:#fff;background:#a51562;border-color:#ff8bd6;box-shadow:0 0 0 7px rgba(255,88,194,.18),0 0 42px rgba(255,88,194,.78);animation:jListen .72s ease-in-out infinite}.jh-heart.thinking{color:#fff0a8;border-color:#ffe36e;box-shadow:0 0 36px rgba(255,227,110,.72);animation:jThink .75s linear infinite}.jh-heart.speaking{color:#fff;border-color:#c78cff;box-shadow:0 0 46px rgba(199,140,255,.82),0 0 26px rgba(102,238,241,.8);animation:jSpeak .55s ease-in-out infinite}.jh-robot.listening .jh-scan,.jh-robot.thinking .jh-scan{opacity:.9;animation:jScan 1.2s ease-in-out infinite}.jh-status{position:absolute;bottom:8px;z-index:3;padding:.48rem .8rem;border-radius:999px;background:rgba(6,27,43,.72);border:1px solid rgba(117,244,239,.25);font-weight:700;font-size:.82rem;text-align:center;max-width:92%}@keyframes jFloat{0%,100%{transform:translateY(0) rotateY(-2deg)}50%{transform:translateY(-12px) rotateY(2deg)}}@keyframes jAura{0%,100%{transform:scale(.96);opacity:.7}50%{transform:scale(1.06);opacity:1}}@keyframes jFloor{0%,100%{transform:scaleX(.9);opacity:.55}50%{transform:scaleX(1.1);opacity:.9}}@keyframes jCore{0%,100%{transform:translateX(-50%) scale(.95)}50%{transform:translateX(-50%) scale(1.06)}}@keyframes jListen{0%,100%{transform:translateX(-50%) scale(.94)}50%{transform:translateX(-50%) scale(1.12)}}@keyframes jThink{to{transform:translateX(-50%) rotate(360deg)}}@keyframes jSpeak{0%,100%{transform:translateX(-50%) scale(.96)}50%{transform:translateX(-50%) scale(1.13)}}@keyframes jBlink{0%,46%,50%,100%{transform:scaleY(1)}48%{transform:scaleY(.08)}}@keyframes jScan{0%{transform:translateY(0);opacity:.85}100%{transform:translateY(76px);opacity:.15}}@media(max-width:700px){.jh-shell{min-height:330px}.jh-robot{transform:scale(.86);transform-origin:center}.jh-status{font-size:.76rem;bottom:2px}}@media(prefers-reduced-motion:reduce){.jh-robot,.jh-aura,.jh-floor,.jh-heart,.jh-eye,.jh-scan{animation:none!important}}
"""

JS = r"""
export default function(component){
 const {parentElement,setStateValue,data}=component;const root=parentElement.querySelector('#jh-shell');if(!root)return;
 const heart=root.querySelector('#jh-heart'),robot=root.querySelector('#jh-robot'),status=root.querySelector('#jh-status');
 const stage=(data&&data.stage)||'idle';
 const setVisual=(mode,text)=>{['listening','thinking','speaking'].forEach(c=>{heart?.classList.remove(c);robot?.classList.remove(c)});if(mode&&mode!=='idle'){heart?.classList.add(mode);robot?.classList.add(mode)}if(status&&text)status.textContent=text;};
 if(stage==='thinking')setVisual('thinking','Pensando…');
 else if(stage==='speaking')setVisual('idle','Toque no coração para falar');
 else setVisual('idle','Toque no coração para falar');
 if(root.dataset.bound==='1')return;root.dataset.bound='1';let rec=null,stream=null,chunks=[],started=0;
 const cleanup=()=>{if(stream){stream.getTracks().forEach(t=>t.stop());stream=null}rec=null};
 const stop=()=>{if(rec&&rec.state==='recording'){setVisual('thinking','Enviando e preparando resposta…');rec.stop()}};
 const start=async()=>{try{stream=await navigator.mediaDevices.getUserMedia({audio:true});chunks=[];const types=['audio/webm;codecs=opus','audio/webm','audio/mp4','audio/ogg;codecs=opus'];const mime=types.find(t=>window.MediaRecorder&&MediaRecorder.isTypeSupported?.(t));rec=mime?new MediaRecorder(stream,{mimeType:mime}):new MediaRecorder(stream);rec.ondataavailable=e=>{if(e.data&&e.data.size)chunks.push(e.data)};rec.onerror=()=>{setVisual('idle','Microfone indisponível');cleanup()};rec.onstop=()=>{const duration=Date.now()-started,mt=rec?.mimeType||chunks[0]?.type||'audio/webm',blob=new Blob(chunks,{type:mt});if(!blob.size||duration<350){setVisual('idle','Fale um pouco mais e tente novamente');cleanup();return}const reader=new FileReader();reader.onloadend=()=>{const s=String(reader.result||''),encoded=s.includes(',')?s.split(',',2)[1]:'';if(encoded){setStateValue('recording',{id:`heart-${Date.now()}-${blob.size}`,data:encoded,mime_type:mt,duration_ms:duration});setVisual('thinking','Pensando…')}else setVisual('idle','Não consegui preparar o áudio');cleanup()};reader.readAsDataURL(blob)};rec.start(120);started=Date.now();setVisual('listening','Ouvindo… toque novamente para terminar')}catch(e){cleanup();setVisual('idle',String(e?.name||'').includes('NotAllowed')?'Permita o microfone no navegador':'Não consegui acessar o microfone')}};
 heart?.addEventListener('click',()=>{if(rec&&rec.state==='recording')stop();else start()});return()=>{try{if(rec&&rec.state==='recording')rec.stop()}catch(_){}cleanup()};
}
"""


def decode_recording(payload: dict[str, Any] | None) -> tuple[bytes, str, str] | None:
    if not payload or not payload.get("data"):
        return None
    raw = base64.b64decode(str(payload["data"]), validate=True)
    if not raw:
        return None
    mime = str(payload.get("mime_type") or "").casefold()
    fmt = "wav" if "wav" in mime else "mp3" if ("mpeg" in mime or "mp3" in mime) else "m4a" if ("mp4" in mime or "m4a" in mime) else "ogg" if "ogg" in mime else "aac" if "aac" in mime else "webm"
    return raw, fmt, str(payload.get("id") or "")


def heart_mic(*, key: str = "jarvis_heart_mic", stage: str = "idle", reply_text: str = "", reply_audio: str = "", reply_token: str = ""):
    components = getattr(st, "components", None)
    v2 = getattr(components, "v2", None) if components else None
    factory = getattr(v2, "component", None) if v2 else None
    if factory is None:
        return None
    widget = factory("faithbloom_jarvis_heart_mic", html=HTML, css=CSS + "\n/* inline */", js=JS)
    return widget(
        key=key,
        data={"stage": stage, "reply_text": reply_text, "reply_audio": reply_audio, "reply_token": reply_token},
        default={"recording": None},
        on_recording_change=lambda: None,
    )
