"""Jarvis premium robot-first push-to-talk component.

The robot itself is the voice control. Press/hold the chest microphone to talk,
release to submit automatically. STT/TTS stay in jarvis_voice.py.
"""
from __future__ import annotations

import base64
from typing import Any

import streamlit as st

HTML = """
<div class="jarvis-stage">
  <div class="office-lines"><i></i><i></i><i></i><i></i></div>
  <div class="speech" id="speech">Olá! Que bom ter você aqui. Eu sou o Jarvis. O que vamos fazer hoje?</div>
  <div class="halo"></div>
  <button id="ptt" type="button" aria-label="Segure o peito do Jarvis para falar">
    <div class="antenna"><span></span></div>
    <div class="head">
      <div class="ear left"></div><div class="ear right"></div>
      <div class="face"><div class="eyes"><span></span><span></span></div><div class="mouth"></div></div>
    </div>
    <div class="neck"></div>
    <div class="body">
      <div class="shoulder left"></div><div class="shoulder right"></div>
      <div class="arm left"></div><div class="arm right"></div>
      <div class="core"><span>🎙️</span></div>
    </div>
  </button>
  <div class="name">JARVIS <span>PREMIUM FUTURISTA</span></div>
  <div id="ptt-status" class="ptt-status">👆 Segure o núcleo, fale e solte</div>
</div>
"""

CSS = """
.jarvis-stage{min-height:610px;border-radius:32px;padding:32px 18px 26px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:12px;background:radial-gradient(circle at 50% 37%,rgba(44,223,238,.20),transparent 27%),linear-gradient(180deg,rgba(3,17,31,.98),rgba(5,31,48,.98) 46%,rgba(10,27,53,.99));overflow:hidden;position:relative;font-family:var(--st-font);box-shadow:0 25px 70px rgba(6,20,40,.32);border:1px solid rgba(111,224,255,.20)}
.jarvis-stage:before{content:"";position:absolute;inset:0;background:linear-gradient(90deg,transparent 0 7%,rgba(77,222,255,.07) 7.3% 7.6%,transparent 8% 92%,rgba(135,112,255,.08) 92.3% 92.6%,transparent 93%),linear-gradient(180deg,transparent 0 17%,rgba(255,255,255,.025) 17.2% 17.5%,transparent 18% 80%,rgba(255,255,255,.025) 80.2% 80.5%,transparent 81%);pointer-events:none}.office-lines{position:absolute;inset:0;overflow:hidden;opacity:.72}.office-lines i{position:absolute;display:block;background:linear-gradient(90deg,transparent,#5df2ff,transparent);height:2px;width:180px;box-shadow:0 0 15px rgba(93,242,255,.65)}.office-lines i:nth-child(1){left:4%;top:18%;transform:rotate(-8deg)}.office-lines i:nth-child(2){right:2%;top:24%;transform:rotate(8deg)}.office-lines i:nth-child(3){left:8%;bottom:17%;width:240px}.office-lines i:nth-child(4){right:7%;bottom:13%;width:220px}.halo{position:absolute;z-index:1;width:390px;height:390px;border-radius:50%;border:1px solid rgba(78,228,246,.30);box-shadow:0 0 50px rgba(52,214,241,.09),inset 0 0 40px rgba(73,99,255,.08);top:150px}.halo:before,.halo:after{content:"";position:absolute;border-radius:50%;border:1px solid rgba(116,120,255,.18);inset:28px}.halo:after{inset:67px;border-color:rgba(65,238,230,.16)}
.speech{position:relative;z-index:5;max-width:620px;padding:15px 22px;border-radius:23px 23px 23px 7px;background:linear-gradient(135deg,rgba(12,63,86,.98),rgba(55,43,108,.97));color:white;font-weight:760;text-align:center;line-height:1.45;box-shadow:0 0 0 1px rgba(105,235,255,.55),0 14px 34px rgba(0,0,0,.26),0 0 22px rgba(70,205,246,.12)}
#ptt{position:relative;z-index:4;width:310px;height:385px;border:0;background:transparent;padding:0;cursor:pointer;touch-action:none;user-select:none;-webkit-user-select:none;filter:drop-shadow(0 26px 34px rgba(0,0,0,.38));transition:transform .18s ease}#ptt:hover{transform:translateY(-3px)}#ptt.recording{transform:scale(1.025)}
.antenna{position:absolute;left:151px;top:3px;width:8px;height:43px;border-radius:8px;background:linear-gradient(#fff,#65e7f1);box-shadow:0 0 17px rgba(91,233,246,.85)}.antenna span{position:absolute;width:17px;height:17px;border-radius:50%;left:-4px;top:-7px;background:#8ff8ff;box-shadow:0 0 20px #65eff8}
.head{position:absolute;left:35px;top:40px;width:240px;height:169px;border-radius:48% 48% 44% 44%/43% 43% 54% 54%;background:linear-gradient(145deg,#ffffff,#e3edf6 58%,#9eb2c8);border:3px solid rgba(255,255,255,.94);box-shadow:inset -14px -14px 23px rgba(45,62,87,.18),0 0 28px rgba(75,225,237,.22)}.face{position:absolute;left:20px;top:19px;width:194px;height:123px;border-radius:49px;background:radial-gradient(circle at 50% 20%,#173f5b,#040c14 72%);border:3px solid rgba(82,229,239,.95);box-shadow:inset 0 0 28px rgba(67,193,235,.15),0 0 18px rgba(82,229,239,.30)}
.eyes{position:absolute;left:36px;right:36px;top:38px;display:flex;justify-content:space-between}.eyes span{width:39px;height:17px;border-top:7px solid #7af8f4;border-radius:50%;filter:drop-shadow(0 0 7px #63e9ef);transition:all .16s ease}.mouth{position:absolute;width:41px;height:18px;border-bottom:6px solid #79f9f5;border-radius:0 0 28px 28px;left:50%;bottom:20px;transform:translateX(-50%);filter:drop-shadow(0 0 6px #61e9ef)}
.ear{position:absolute;top:72px;width:31px;height:56px;border-radius:16px;background:linear-gradient(#f4fbff,#92b1ca);border:2px solid #7ce5ec}.ear.left{left:-16px}.ear.right{right:-16px}.neck{position:absolute;z-index:3;left:135px;top:202px;width:40px;height:29px;border-radius:8px;background:linear-gradient(90deg,#637d96,#d9e7ef,#668198)}
.body{position:absolute;left:70px;top:226px;width:170px;height:124px;border-radius:43px 43px 50px 50px;background:linear-gradient(145deg,#fff,#dde9f1 66%,#9fb3c9);border:3px solid rgba(255,255,255,.92);box-shadow:inset -12px -12px 20px rgba(50,68,94,.15),0 0 28px rgba(48,207,229,.12)}.shoulder{position:absolute;top:18px;width:35px;height:44px;border-radius:18px;background:linear-gradient(#f7fbff,#9fb9ce);border:2px solid rgba(255,255,255,.8)}.shoulder.left{left:-22px}.shoulder.right{right:-22px}.arm{position:absolute;top:45px;width:34px;height:72px;border-radius:18px;background:linear-gradient(#eef7fd,#9fb8cc);border:2px solid rgba(255,255,255,.82)}.arm.left{left:-28px;transform:rotate(19deg)}.arm.right{right:-28px;transform:rotate(-19deg)}
.core{position:absolute;left:50%;top:28px;transform:translateX(-50%);width:72px;height:72px;border-radius:50%;background:radial-gradient(circle,#143a50,#06121e 72%);border:4px solid #5fe8ef;box-shadow:0 0 26px rgba(95,232,239,.70),inset 0 0 15px rgba(72,218,255,.18);display:flex;align-items:center;justify-content:center}.core span{font-size:30px}.name{position:relative;z-index:5;color:white;font-weight:900;letter-spacing:.18em;font-size:.95rem;margin-top:-9px;text-align:center}.name span{display:block;color:#85dce8;font-size:.58rem;letter-spacing:.28em;margin-top:5px}.ptt-status{position:relative;z-index:5;color:rgba(255,255,255,.88);font-size:.94rem;font-weight:760;text-align:center;min-height:1.4em}.ptt-status.live{color:#ffbddb}.ptt-status.error{color:#ffc8c8}
#ptt.recording .eyes span{height:8px;border-top-width:8px;transform:scaleX(.72)}#ptt.recording .mouth,.jarvis-stage.speaking .mouth{animation:talk .34s ease-in-out infinite alternate}#ptt.recording .core{background:#511536;border-color:#ff79c8;box-shadow:0 0 0 10px rgba(255,121,200,.11),0 0 32px rgba(255,121,200,.72);animation:pulse .78s ease-in-out infinite alternate}.jarvis-stage.speaking .core{box-shadow:0 0 0 8px rgba(93,232,239,.09),0 0 32px rgba(93,232,239,.78)}
@keyframes talk{from{height:7px;width:27px}to{height:26px;width:34px;border-radius:50%;border:5px solid #76f7f0}}@keyframes pulse{from{transform:translateX(-50%) scale(1)}to{transform:translateX(-50%) scale(1.09)}}@media(max-width:640px){.jarvis-stage{min-height:560px;padding:24px 10px 18px}.speech{font-size:.90rem;max-width:92%}#ptt{transform:scale(.88);margin:-15px 0}.name{margin-top:-28px}.halo{transform:scale(.82);top:140px}}
"""

JS = r"""
export default function(component) {
  const { parentElement, setStateValue, setTriggerValue, data } = component;
  const stage=parentElement.querySelector('.jarvis-stage'),button=parentElement.querySelector('#ptt'),status=parentElement.querySelector('#ptt-status'),speech=parentElement.querySelector('#speech');
  if(!button)return;
  const greeting=(data&&data.greeting)||'Olá! Que bom ter você aqui. Eu sou o Jarvis. O que vamos fazer hoje?';
  const reply=(data&&data.reply_text)||'';
  const replyAudio=(data&&data.reply_audio)||'';
  const replyToken=(data&&data.reply_token)||'';
  speech.textContent=reply||greeting;
  const setStatus=(text,cls='')=>{status.textContent=text;status.className='ptt-status'+(cls?' '+cls:'');};
  const speakNative=(text)=>{if(!('speechSynthesis'in window)||!text)return;try{window.speechSynthesis.cancel();const u=new SpeechSynthesisUtterance(text);u.lang='pt-BR';u.rate=.95;u.pitch=.92;u.onstart=()=>{stage.classList.add('speaking');setStatus('🔊 Jarvis está falando…');};u.onend=()=>{stage.classList.remove('speaking');setStatus('👆 Segure o núcleo, fale e solte');};u.onerror=()=>stage.classList.remove('speaking');window.speechSynthesis.speak(u);}catch(_){stage.classList.remove('speaking');}};
  const speakReply=()=>{if(replyAudio){try{const a=new Audio('data:audio/mpeg;base64,'+replyAudio);a.onplay=()=>{stage.classList.add('speaking');setStatus('🔊 Jarvis está falando…');};a.onended=()=>{stage.classList.remove('speaking');setStatus('👆 Segure o núcleo, fale e solte');};a.onerror=()=>speakNative(reply);const p=a.play();if(p&&p.catch)p.catch(()=>speakNative(reply));return;}catch(_){}}speakNative(reply);};
  try{if(reply&&replyToken&&sessionStorage.getItem('faithbloom_jarvis_reply')!==replyToken){sessionStorage.setItem('faithbloom_jarvis_reply',replyToken);setTimeout(speakReply,180);}else if(!reply&&!sessionStorage.getItem('faithbloom_jarvis_greeted')){sessionStorage.setItem('faithbloom_jarvis_greeted','1');setTimeout(()=>speakNative(greeting),400);}}catch(_){if(reply)setTimeout(speakReply,180);else setTimeout(()=>speakNative(greeting),400);}
  if(button.dataset.bound==='1')return;button.dataset.bound='1';
  let recorder=null,stream=null,chunks=[],startedAt=0,activePointer=null;
  const cleanup=()=>{if(stream){stream.getTracks().forEach(t=>t.stop());stream=null;}recorder=null;activePointer=null;button.classList.remove('recording');};
  const begin=async(e)=>{e.preventDefault();if(recorder&&recorder.state==='recording')return;window.speechSynthesis?.cancel();stage.classList.remove('speaking');activePointer=e.pointerId;try{button.setPointerCapture?.(e.pointerId);stream=await navigator.mediaDevices.getUserMedia({audio:true});chunks=[];const preferred=['audio/webm;codecs=opus','audio/webm','audio/mp4','audio/ogg;codecs=opus'].find(t=>window.MediaRecorder&&MediaRecorder.isTypeSupported?.(t));recorder=preferred?new MediaRecorder(stream,{mimeType:preferred}):new MediaRecorder(stream);recorder.ondataavailable=ev=>{if(ev.data&&ev.data.size)chunks.push(ev.data)};recorder.onerror=()=>{speech.textContent='Não consegui ouvir você.';setStatus('Verifique a permissão do microfone.','error');cleanup();};recorder.onstop=()=>{const duration=Date.now()-startedAt,mime=recorder?.mimeType||chunks[0]?.type||'audio/webm',blob=new Blob(chunks,{type:mime});if(!blob.size||duration<250){speech.textContent='Fale um pouco mais e tente novamente.';setStatus('👆 Segure o núcleo e fale.','error');cleanup();return;}const reader=new FileReader();reader.onloadend=()=>{const dataUrl=String(reader.result||''),encoded=dataUrl.includes(',')?dataUrl.split(',',2)[1]:'';if(!encoded){speech.textContent='Não consegui preparar o áudio.';setStatus('Tente novamente.','error');cleanup();return;}const id=`${Date.now()}-${blob.size}`;setStateValue('recording',{id,data:encoded,mime_type:mime,duration_ms:duration});speech.textContent='Entendi. Só um instante enquanto cuido disso…';setStatus('🧠 Pensando e executando…');setTriggerValue('submitted',id);cleanup();};reader.readAsDataURL(blob);};recorder.start(120);startedAt=Date.now();button.classList.add('recording');speech.textContent='Estou ouvindo você…';setStatus('🔴 Ouvindo… solte quando terminar','live');}catch(err){cleanup();speech.textContent='Preciso da permissão do microfone para conversar com você.';setStatus(String(err?.name||'').includes('NotAllowed')?'Microfone bloqueado. Permita o acesso no navegador.':'Não consegui acessar o microfone.','error');}};
  const finish=(e)=>{if(activePointer!==null&&e.pointerId!==undefined&&e.pointerId!==activePointer)return;e.preventDefault();if(recorder&&recorder.state==='recording'){speech.textContent='Certo. Estou processando…';setStatus('⏳ Enviando sua fala…');recorder.stop();}else cleanup();};
  button.addEventListener('pointerdown',begin);button.addEventListener('pointerup',finish);button.addEventListener('pointercancel',finish);button.addEventListener('lostpointercapture',e=>{if(recorder&&recorder.state==='recording')finish(e);});
  return()=>{try{if(recorder&&recorder.state==='recording')recorder.stop();}catch(_){}cleanup();};
}
"""


def _format_from_mime(mime_type: str | None) -> str:
    mime=(mime_type or '').casefold()
    if 'wav' in mime:return 'wav'
    if 'mpeg' in mime or 'mp3' in mime:return 'mp3'
    if 'mp4' in mime or 'm4a' in mime:return 'm4a'
    if 'ogg' in mime:return 'ogg'
    if 'aac' in mime:return 'aac'
    return 'webm'


def decode_recording(payload: dict[str,Any] | None) -> tuple[bytes,str,str] | None:
    if not payload or not payload.get('data'):return None
    raw=base64.b64decode(str(payload['data']),validate=True)
    if not raw:return None
    return raw,_format_from_mime(payload.get('mime_type')),str(payload.get('id') or '')


def push_to_talk(*,key: str='jarvis_push_to_talk',greeting: str='',reply_text: str='',reply_audio: str='',reply_token: str=''):
    components=getattr(st,'components',None);v2=getattr(components,'v2',None) if components else None;factory=getattr(v2,'component',None) if v2 else None
    if factory is None:return None
    widget=factory('faithbloom_jarvis_push_to_talk',html=HTML,css=CSS,js=JS)
    return widget(key=key,data={'greeting':greeting,'reply_text':reply_text,'reply_audio':reply_audio,'reply_token':reply_token},default={'recording':None,'submitted':None},on_recording_change=lambda:None,on_submitted_change=lambda:None)