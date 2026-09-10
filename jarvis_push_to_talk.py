"""Jarvis premium hero + push-to-talk component.

A experiência visual segue o mockup premium aprovado: escritório futurista,
Jarvis central, status à direita e barra dedicada para falar. STT/TTS continuam
na camada de voz já existente; este módulo cuida somente da interação no navegador.
"""
from __future__ import annotations

import base64
from typing import Any

import streamlit as st

HTML = """
<div class="jarvis-stage">
  <div class="office-grid"></div>
  <div class="city"><i></i><i></i><i></i><i></i><i></i><i></i><i></i></div>
  <div class="hero-copy">
    <div class="hero-wordmark">Jarvis</div>
    <div class="hero-subtitle">PREMIUM FUTURISTA</div>
    <div class="hero-flow">IDEIAS → LIVROS → PESSOAS<br>→ UM MUNDO MELHOR</div>
    <div class="hero-quote">“Mais organização<br>para um mundo<br>com mais propósito.”</div>
  </div>

  <div class="speech" id="speech">Olá, Erica! Que bom ter você aqui. O que vamos fazer hoje?</div>

  <div class="robot-wrap">
    <div class="floor-ring ring-one"></div><div class="floor-ring ring-two"></div>
    <div class="robot">
      <div class="antenna"><span></span></div>
      <div class="head">
        <div class="ear left"></div><div class="ear right"></div>
        <div class="face"><div class="eyes"><span></span><span></span></div><div class="mouth"></div></div>
      </div>
      <div class="neck"></div>
      <div class="body">
        <div class="core"><span>⌄</span></div>
        <div class="shoulder left"></div><div class="shoulder right"></div>
        <div class="arm left"><div class="forearm"></div><div class="hand"><i></i><i></i><i></i></div></div>
        <div class="arm right"><div class="forearm"></div><div class="hand rest"><i></i><i></i><i></i></div></div>
      </div>
    </div>
  </div>

  <div class="status-stack">
    <div class="status-card"><b class="dot online"></b><span><strong>Online</strong><small>Jarvis ativo</small></span></div>
    <div class="status-card"><b class="status-icon">🎙️</b><span><strong>Voz ativa</strong><small>Push-to-talk</small></span></div>
    <div class="status-card"><b class="status-icon">🧠</b><span><strong>Contexto ativo</strong><small>Conversa recente</small></span></div>
    <div class="status-card"><b class="status-icon">🛡️</b><span><strong>Modo seguro</strong><small>Aprovação humana</small></span></div>
  </div>

  <div class="hero-motto">“Sonhe. Organize.<br>Crie. Publique. Impacte.”</div>

  <div class="voice-dock">
    <div class="wave"><i></i><i></i><i></i><i></i><i></i></div>
    <button id="ptt" type="button" aria-label="Segure para falar com o Jarvis"><span class="mic">🎙️</span><span class="ptt-label">Segure para falar</span></button>
    <div id="ptt-status" class="ptt-status">● Jarvis ouvindo e pronto para ajudar</div>
  </div>
</div>
"""

CSS = """
:root{--cyan:#5ff6ff;--blue:#288bff;--violet:#8354ff;--ink:#07182b}
*{box-sizing:border-box}.jarvis-stage{min-height:690px;border-radius:28px;padding:34px 34px 116px;overflow:hidden;position:relative;font-family:var(--st-font);background:radial-gradient(circle at 52% 52%,rgba(41,201,255,.17),transparent 28%),linear-gradient(180deg,#071829 0%,#0a2238 58%,#10253e 100%);border:1px solid rgba(93,222,255,.2);box-shadow:0 24px 75px rgba(12,35,69,.28);color:#fff}
.jarvis-stage:before{content:"";position:absolute;inset:0;background:linear-gradient(90deg,rgba(3,12,24,.72),rgba(4,23,39,.08) 35%,rgba(4,19,35,.05) 67%,rgba(5,13,29,.72)),linear-gradient(180deg,transparent 62%,rgba(18,38,63,.55));pointer-events:none}.office-grid{position:absolute;inset:0;background:linear-gradient(90deg,transparent 10%,rgba(88,229,255,.10) 10.2%,transparent 10.4%,transparent 28%,rgba(88,229,255,.06) 28.2%,transparent 28.4%,transparent 72%,rgba(116,91,255,.08) 72.2%,transparent 72.4%,transparent 90%,rgba(88,229,255,.08) 90.2%,transparent 90.4%),linear-gradient(180deg,transparent 19%,rgba(255,255,255,.035) 19.2%,transparent 19.4%,transparent 78%,rgba(255,255,255,.035) 78.2%,transparent 78.4%)}
.city{position:absolute;left:35%;right:8%;bottom:110px;height:185px;opacity:.65;display:flex;gap:15px;align-items:flex-end}.city i{display:block;width:8%;min-width:34px;border:1px solid rgba(105,232,255,.16);background:linear-gradient(180deg,rgba(30,86,126,.32),rgba(5,31,56,.75));box-shadow:0 0 18px rgba(57,168,255,.06)}.city i:nth-child(1){height:42%}.city i:nth-child(2){height:76%}.city i:nth-child(3){height:54%}.city i:nth-child(4){height:94%}.city i:nth-child(5){height:62%}.city i:nth-child(6){height:81%}.city i:nth-child(7){height:47%}
.hero-copy{position:absolute;z-index:4;left:5.2%;top:52px;width:255px}.hero-wordmark{font-family:Georgia,serif;font-size:66px;line-height:.9;font-weight:700;letter-spacing:-.04em;background:linear-gradient(90deg,#8cfbff,#fff 48%,#b78fff);-webkit-background-clip:text;color:transparent;filter:drop-shadow(0 0 14px rgba(111,231,255,.25))}.hero-subtitle{margin-top:12px;font-size:13px;letter-spacing:.34em;font-weight:800}.hero-flow{margin-top:25px;font-size:11px;letter-spacing:.28em;line-height:1.8;color:#dce8f7}.hero-quote{margin-top:54px;padding-left:3px;font-size:16px;line-height:1.22;color:#e8eff8}.hero-quote:after{content:"";display:block;width:62px;height:2px;margin-top:16px;background:linear-gradient(90deg,#5ff6ff,transparent)}
.speech{position:absolute;z-index:7;top:52px;left:61%;transform:translateX(-50%);width:min(340px,30vw);padding:17px 19px;border-radius:27px 27px 27px 8px;background:linear-gradient(135deg,rgba(13,73,105,.95),rgba(64,42,126,.96));border:1px solid rgba(106,239,255,.85);box-shadow:0 0 0 1px rgba(111,112,255,.24),0 12px 30px rgba(1,10,26,.36),0 0 26px rgba(58,198,255,.15);font-size:16px;font-weight:760;line-height:1.34}.speech:after{content:"";position:absolute;left:34px;bottom:-24px;border:13px solid transparent;border-top-color:#184c77;border-left-color:#184c77;filter:drop-shadow(-1px 1px 0 rgba(91,229,255,.45))}
.robot-wrap{position:absolute;z-index:5;left:50%;top:93px;transform:translateX(-50%);width:430px;height:480px}.floor-ring{position:absolute;left:50%;bottom:5px;transform:translateX(-50%);border-radius:50%;border:3px solid rgba(70,232,255,.9);box-shadow:0 0 20px rgba(47,201,255,.52)}.ring-one{width:390px;height:56px}.ring-two{width:270px;height:37px;bottom:14px;opacity:.65}.robot{position:absolute;left:50%;top:10px;transform:translateX(-50%);width:330px;height:440px;filter:drop-shadow(0 24px 28px rgba(0,0,0,.4))}.antenna{position:absolute;left:161px;top:0;width:8px;height:44px;border-radius:8px;background:linear-gradient(#fff,#65e7f1);box-shadow:0 0 17px rgba(91,233,246,.85)}.antenna span{position:absolute;width:18px;height:18px;border-radius:50%;left:-5px;top:-8px;background:#9afcff;border:2px solid #fff;box-shadow:0 0 20px #65eff8}.head{position:absolute;left:35px;top:38px;width:260px;height:184px;border-radius:48% 48% 44% 44%/43% 43% 54% 54%;background:linear-gradient(145deg,#fff,#e5eef6 55%,#9fb4c9);border:3px solid rgba(255,255,255,.95);box-shadow:inset -15px -15px 25px rgba(39,56,84,.2),0 0 34px rgba(75,225,237,.24)}.face{position:absolute;left:20px;top:20px;width:214px;height:135px;border-radius:55px;background:radial-gradient(circle at 50% 20%,#173f5b,#030a12 72%);border:3px solid rgba(82,229,239,.95);box-shadow:inset 0 0 30px rgba(67,193,235,.15),0 0 18px rgba(82,229,239,.30)}.eyes{position:absolute;left:39px;right:39px;top:42px;display:flex;justify-content:space-between}.eyes span{width:42px;height:18px;border-top:7px solid #7af8f4;border-radius:50%;filter:drop-shadow(0 0 7px #63e9ef);transition:.16s}.mouth{position:absolute;width:43px;height:19px;border-bottom:6px solid #79f9f5;border-radius:0 0 28px 28px;left:50%;bottom:22px;transform:translateX(-50%);filter:drop-shadow(0 0 6px #61e9ef)}.ear{position:absolute;top:78px;width:33px;height:60px;border-radius:17px;background:linear-gradient(#f7fcff,#91b0ca);border:2px solid #7ce5ec}.ear.left{left:-17px}.ear.right{right:-17px}.neck{position:absolute;z-index:2;left:145px;top:215px;width:42px;height:31px;border-radius:8px;background:linear-gradient(90deg,#637d96,#e5f0f5,#668198)}
.body{position:absolute;left:71px;top:239px;width:190px;height:145px;border-radius:52px 52px 63px 63px;background:linear-gradient(145deg,#fff,#e0ebf3 64%,#9fb4c8);border:3px solid rgba(255,255,255,.94);box-shadow:inset -14px -14px 23px rgba(46,64,90,.17),0 0 28px rgba(48,207,229,.13)}.core{position:absolute;left:50%;top:32px;transform:translateX(-50%);width:76px;height:76px;border-radius:50%;background:radial-gradient(circle,#183e56,#06121e 72%);border:4px solid #5fe8ef;box-shadow:0 0 28px rgba(95,232,239,.72),inset 0 0 16px rgba(72,218,255,.18);display:flex;align-items:center;justify-content:center}.core span{font-size:36px;color:#fff;line-height:.7}.shoulder{position:absolute;top:18px;width:38px;height:47px;border-radius:20px;background:linear-gradient(#f8fcff,#9fb9ce);border:2px solid rgba(255,255,255,.82)}.shoulder.left{left:-26px}.shoulder.right{right:-26px}.arm{position:absolute;width:43px;height:112px}.arm .forearm{position:absolute;width:35px;height:78px;border-radius:20px;background:linear-gradient(#f4f9fd,#9db7ca);border:2px solid rgba(255,255,255,.82)}.arm.left{left:-73px;top:-8px;transform:rotate(-40deg)}.arm.left .forearm{top:0}.arm.right{right:-55px;top:37px;transform:rotate(22deg)}.arm.right .forearm{top:0}.hand{position:absolute;left:-8px;top:-28px;width:48px;height:35px;border-radius:18px;background:linear-gradient(#263c50,#071422);border:2px solid #57dce9;box-shadow:0 0 13px rgba(70,223,239,.35)}.hand i{position:absolute;display:block;width:8px;height:27px;border-radius:6px;background:#12283a;border:1px solid #6ceaf1;top:-20px}.hand i:nth-child(1){left:8px;transform:rotate(-16deg)}.hand i:nth-child(2){left:20px;top:-26px}.hand i:nth-child(3){left:32px;transform:rotate(16deg)}.hand.rest{top:68px;left:-3px;transform:rotate(45deg)}
.status-stack{position:absolute;z-index:6;right:3%;top:44px;width:198px;display:grid;gap:11px}.status-card{display:flex;align-items:center;gap:12px;padding:13px 14px;border-radius:19px;background:linear-gradient(135deg,rgba(15,62,100,.9),rgba(15,42,79,.82));border:1px solid rgba(103,196,255,.66);box-shadow:inset 0 0 18px rgba(67,130,240,.08),0 9px 24px rgba(0,0,0,.23);backdrop-filter:blur(7px)}.status-card span{display:flex;flex-direction:column}.status-card strong{font-size:15px}.status-card small{font-size:11px;color:#dbe8f8;margin-top:2px}.dot{width:30px;height:30px;border-radius:50%;display:block;background:#36e8cf;box-shadow:0 0 0 9px rgba(54,232,207,.10),0 0 18px rgba(54,232,207,.85)}.status-icon{font-size:23px;width:30px;text-align:center}.hero-motto{position:absolute;z-index:4;right:4.2%;bottom:150px;font-size:14px;line-height:1.3;color:#e6edf8;text-align:left}.hero-motto:after{content:"";display:block;width:34px;height:2px;margin-top:12px;background:#63edf7}
.voice-dock{position:absolute;z-index:10;left:50%;bottom:20px;transform:translateX(-50%);width:min(780px,72%);padding:12px 18px 10px;border-radius:22px;background:rgba(239,248,255,.96);border:1px solid rgba(105,181,230,.30);box-shadow:0 14px 35px rgba(0,8,25,.25);display:grid;grid-template-columns:90px 1fr;grid-template-rows:auto auto;align-items:center;gap:3px 10px}.wave{display:flex;align-items:center;justify-content:center;gap:4px;height:48px}.wave i{display:block;width:4px;border-radius:5px;background:#388cff}.wave i:nth-child(1){height:12px}.wave i:nth-child(2){height:25px}.wave i:nth-child(3){height:38px}.wave i:nth-child(4){height:24px}.wave i:nth-child(5){height:14px}#ptt{grid-column:2;border:0;border-radius:999px;min-height:55px;padding:0 28px;cursor:pointer;color:#fff;font-weight:850;font-size:18px;background:linear-gradient(90deg,#04babc,#138ed4 42%,#7c35ef);box-shadow:0 10px 26px rgba(59,77,223,.27),inset 0 1px 0 rgba(255,255,255,.25);display:flex;align-items:center;justify-content:center;gap:12px;touch-action:none;user-select:none;-webkit-user-select:none;transition:.16s}#ptt:hover{transform:translateY(-1px);filter:brightness(1.05)}#ptt.recording{background:linear-gradient(90deg,#e34378,#7b3cec);box-shadow:0 0 0 8px rgba(226,67,120,.10),0 10px 30px rgba(111,45,174,.28)}.mic{font-size:25px}.ptt-status{grid-column:1/3;text-align:center;color:#214d6f;font-size:12px;font-weight:700;min-height:18px}.ptt-status.live{color:#b51f58}.ptt-status.error{color:#b52c2c}
.jarvis-stage.recording .eyes span{height:8px;border-top-width:8px;transform:scaleX(.72)}.jarvis-stage.recording .mouth,.jarvis-stage.speaking .mouth{animation:talk .34s ease-in-out infinite alternate}.jarvis-stage.recording .core{background:#511536;border-color:#ff79c8;box-shadow:0 0 0 10px rgba(255,121,200,.11),0 0 32px rgba(255,121,200,.72);animation:pulse .78s ease-in-out infinite alternate}.jarvis-stage.speaking .core{box-shadow:0 0 0 8px rgba(93,232,239,.09),0 0 32px rgba(93,232,239,.78)}
@keyframes talk{from{height:7px;width:27px}to{height:26px;width:34px;border-radius:50%;border:5px solid #76f7f0}}@keyframes pulse{from{transform:translateX(-50%) scale(1)}to{transform:translateX(-50%) scale(1.09)}}
@media(max-width:920px){.jarvis-stage{min-height:760px;padding-bottom:125px}.hero-copy{left:5%;top:28px;width:210px}.hero-wordmark{font-size:48px}.hero-flow,.hero-quote{display:none}.status-stack{right:3%;top:25px;width:180px}.robot-wrap{top:150px}.speech{top:112px;left:50%;width:min(360px,68vw)}.hero-motto{display:none}.voice-dock{width:90%}}
@media(max-width:640px){.jarvis-stage{min-height:780px;padding:18px 8px 126px}.hero-copy{position:relative;left:auto;top:auto;text-align:center;width:auto}.hero-wordmark{font-size:44px}.hero-subtitle{font-size:10px}.status-stack{display:none}.speech{top:130px;width:88%;font-size:13px}.robot-wrap{top:200px;transform:translateX(-50%) scale(.82)}.voice-dock{width:94%;grid-template-columns:55px 1fr;padding:10px}.ptt-label{font-size:15px}}
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
  const speakNative=(text)=>{if(!('speechSynthesis'in window)||!text)return;try{window.speechSynthesis.cancel();const u=new SpeechSynthesisUtterance(text);u.lang='pt-BR';u.rate=.95;u.pitch=.92;u.onstart=()=>{stage.classList.add('speaking');setStatus('🔊 Jarvis está falando…');};u.onend=()=>{stage.classList.remove('speaking');setStatus('● Jarvis ouvindo e pronto para ajudar');};u.onerror=()=>stage.classList.remove('speaking');window.speechSynthesis.speak(u);}catch(_){stage.classList.remove('speaking');}};
  const speakReply=()=>{if(replyAudio){try{const a=new Audio('data:audio/mpeg;base64,'+replyAudio);a.onplay=()=>{stage.classList.add('speaking');setStatus('🔊 Jarvis está falando…');};a.onended=()=>{stage.classList.remove('speaking');setStatus('● Jarvis ouvindo e pronto para ajudar');};a.onerror=()=>speakNative(reply);const p=a.play();if(p&&p.catch)p.catch(()=>speakNative(reply));return;}catch(_){}}speakNative(reply);};
  try{if(reply&&replyToken&&sessionStorage.getItem('faithbloom_jarvis_reply')!==replyToken){sessionStorage.setItem('faithbloom_jarvis_reply',replyToken);setTimeout(speakReply,180);}else if(!reply&&!sessionStorage.getItem('faithbloom_jarvis_greeted')){sessionStorage.setItem('faithbloom_jarvis_greeted','1');setTimeout(()=>speakNative(greeting),400);}}catch(_){if(reply)setTimeout(speakReply,180);else setTimeout(()=>speakNative(greeting),400);}
  if(button.dataset.bound==='1')return;button.dataset.bound='1';
  let recorder=null,stream=null,chunks=[],startedAt=0,activePointer=null;
  const cleanup=()=>{if(stream){stream.getTracks().forEach(t=>t.stop());stream=null;}recorder=null;activePointer=null;button.classList.remove('recording');stage.classList.remove('recording');};
  const begin=async(e)=>{e.preventDefault();if(recorder&&recorder.state==='recording')return;window.speechSynthesis?.cancel();stage.classList.remove('speaking');activePointer=e.pointerId;try{button.setPointerCapture?.(e.pointerId);stream=await navigator.mediaDevices.getUserMedia({audio:true});chunks=[];const preferred=['audio/webm;codecs=opus','audio/webm','audio/mp4','audio/ogg;codecs=opus'].find(t=>window.MediaRecorder&&MediaRecorder.isTypeSupported?.(t));recorder=preferred?new MediaRecorder(stream,{mimeType:preferred}):new MediaRecorder(stream);recorder.ondataavailable=ev=>{if(ev.data&&ev.data.size)chunks.push(ev.data)};recorder.onerror=()=>{speech.textContent='Não consegui ouvir você.';setStatus('Verifique a permissão do microfone.','error');cleanup();};recorder.onstop=()=>{const duration=Date.now()-startedAt,mime=recorder?.mimeType||chunks[0]?.type||'audio/webm',blob=new Blob(chunks,{type:mime});if(!blob.size||duration<250){speech.textContent='Fale um pouco mais e tente novamente.';setStatus('Segure para falar e tente de novo.','error');cleanup();return;}const reader=new FileReader();reader.onloadend=()=>{const dataUrl=String(reader.result||''),encoded=dataUrl.includes(',')?dataUrl.split(',',2)[1]:'';if(!encoded){speech.textContent='Não consegui preparar o áudio.';setStatus('Tente novamente.','error');cleanup();return;}const id=`${Date.now()}-${blob.size}`;setStateValue('recording',{id,data:encoded,mime_type:mime,duration_ms:duration});speech.textContent='Entendi. Só um instante enquanto cuido disso…';setStatus('🧠 Pensando e executando…');setTriggerValue('submitted',id);cleanup();};reader.readAsDataURL(blob);};recorder.start(120);startedAt=Date.now();button.classList.add('recording');stage.classList.add('recording');speech.textContent='Estou ouvindo você…';setStatus('🔴 Ouvindo… solte quando terminar','live');}catch(err){cleanup();speech.textContent='Preciso da permissão do microfone para conversar com você.';setStatus(String(err?.name||'').includes('NotAllowed')?'Microfone bloqueado. Permita o acesso no navegador.':'Não consegui acessar o microfone.','error');}};
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