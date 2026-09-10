"""Jarvis robot-first push-to-talk component.

The robot itself is the voice control. Press/hold the heart to talk, release to
submit automatically. STT/TTS remain in jarvis_voice.py; this file only owns the
browser interaction and visual speaking/listening states.
"""
from __future__ import annotations

import base64
from typing import Any

import streamlit as st

HTML = """
<div class="jarvis-stage">
  <div class="speech" id="speech">Olá! Que bom ter você aqui. Eu sou o Jarvis. O que vamos fazer hoje?</div>
  <button id="ptt" type="button" aria-label="Segure o coração do Jarvis para falar">
    <div class="antenna"><span></span></div>
    <div class="head">
      <div class="ear left"></div><div class="ear right"></div>
      <div class="face">
        <div class="eyes"><span></span><span></span></div>
        <div class="mouth"></div>
      </div>
      <div class="flower">🌷</div>
    </div>
    <div class="body">
      <div class="arm left"></div><div class="arm right"></div>
      <div class="heart"><span>🎙️</span></div>
    </div>
  </button>
  <div class="name">JARVIS</div>
  <div id="ptt-status" class="ptt-status">👆 Segure meu coração, fale e solte</div>
</div>
"""

CSS = """
.jarvis-stage{min-height:560px;border-radius:36px;padding:34px 18px 24px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:13px;background:radial-gradient(circle at 50% 25%,rgba(58,218,220,.20),transparent 30%),linear-gradient(145deg,#0c2b42,#176a70 49%,#4d4694);overflow:hidden;position:relative;font-family:var(--st-font);box-shadow:0 24px 72px rgba(22,57,87,.28)}
.jarvis-stage:before,.jarvis-stage:after{content:"";position:absolute;border-radius:50%;pointer-events:none}.jarvis-stage:before{width:300px;height:300px;right:-130px;top:-130px;background:rgba(255,255,255,.08)}.jarvis-stage:after{width:230px;height:230px;left:-110px;bottom:-125px;background:rgba(236,126,198,.12)}
.speech{position:relative;z-index:3;max-width:640px;padding:15px 20px;border-radius:24px 24px 24px 8px;background:rgba(255,255,255,.96);color:#17324a;font-weight:760;text-align:center;line-height:1.45;box-shadow:0 11px 30px rgba(0,0,0,.17)}
#ptt{position:relative;z-index:3;width:270px;height:345px;border:0;background:transparent;padding:0;cursor:pointer;touch-action:none;user-select:none;-webkit-user-select:none;filter:drop-shadow(0 22px 35px rgba(0,0,0,.30));transition:transform .18s ease}
#ptt:hover{transform:translateY(-3px)}#ptt.recording{transform:scale(1.03)}
.antenna{position:absolute;left:131px;top:2px;width:8px;height:45px;border-radius:8px;background:linear-gradient(#efffff,#6de7ea);box-shadow:0 0 16px rgba(111,234,237,.8)}.antenna span{position:absolute;width:18px;height:18px;border-radius:50%;left:-5px;top:-8px;background:#8df8f2;box-shadow:0 0 20px #7ef0ef}
.head{position:absolute;left:31px;top:39px;width:208px;height:156px;border-radius:48% 48% 43% 43%/43% 43% 54% 54%;background:linear-gradient(145deg,#fff,#dce9f4 62%,#aabdd0);border:3px solid rgba(255,255,255,.95);box-shadow:inset -12px -12px 22px rgba(60,79,109,.16),0 0 29px rgba(72,220,224,.25)}
.face{position:absolute;left:18px;top:18px;width:170px;height:113px;border-radius:50px;background:radial-gradient(circle at 50% 25%,#1b4260,#07131f 70%);border:3px solid rgba(101,223,226,.9);box-shadow:inset 0 0 30px rgba(80,203,235,.16),0 0 18px rgba(101,223,226,.35)}
.eyes{position:absolute;left:32px;right:32px;top:36px;display:flex;justify-content:space-between}.eyes span{width:36px;height:16px;border-top:7px solid #75f6ef;border-radius:50%;filter:drop-shadow(0 0 7px #62e9ef);transition:all .16s ease}.mouth{position:absolute;width:39px;height:18px;border-bottom:6px solid #76f7f0;border-radius:0 0 28px 28px;left:50%;bottom:19px;transform:translateX(-50%);filter:drop-shadow(0 0 6px #62e9ef)}
.ear{position:absolute;top:68px;width:29px;height:53px;border-radius:16px;background:linear-gradient(#e9fbff,#91b6d2);border:2px solid #8eeae8}.ear.left{left:-15px}.ear.right{right:-15px}.flower{position:absolute;right:-2px;top:19px;font-size:29px;animation:bloom 2.6s ease-in-out infinite}
.body{position:absolute;left:64px;top:201px;width:142px;height:111px;border-radius:36px 36px 46px 46px;background:linear-gradient(145deg,#fff,#d9e6f0 68%,#a9bbce);border:3px solid rgba(255,255,255,.92);box-shadow:inset -10px -10px 20px rgba(56,77,105,.14)}
.arm{position:absolute;top:18px;width:32px;height:78px;border-radius:18px;background:linear-gradient(#eef7fd,#a9bfd1);border:2px solid rgba(255,255,255,.85)}.arm.left{left:-30px;transform:rotate(17deg)}.arm.right{right:-30px;transform:rotate(-17deg)}
.heart{position:absolute;left:50%;top:24px;transform:translateX(-50%);width:64px;height:64px;border-radius:50%;background:#0b2133;border:4px solid #66e9ed;box-shadow:0 0 23px rgba(102,233,237,.72);display:flex;align-items:center;justify-content:center}.heart span{font-size:29px}.name{position:relative;z-index:3;color:white;font-weight:900;letter-spacing:.22em;font-size:1rem;margin-top:-6px}.ptt-status{position:relative;z-index:3;color:rgba(255,255,255,.90);font-size:.95rem;font-weight:760;text-align:center;min-height:1.4em}.ptt-status.live{color:#ffd4e5}.ptt-status.error{color:#ffd5d5}
#ptt.recording .eyes span{height:8px;border-top-width:8px;transform:scaleX(.72)}#ptt.recording .mouth,.jarvis-stage.speaking .mouth{animation:talk .35s ease-in-out infinite alternate}#ptt.recording .heart{background:#7c174c;border-color:#ff86cc;box-shadow:0 0 0 10px rgba(255,134,204,.12),0 0 32px rgba(255,134,204,.75);animation:pulse .8s ease-in-out infinite alternate}.jarvis-stage.speaking .heart{box-shadow:0 0 0 8px rgba(102,233,237,.10),0 0 30px rgba(102,233,237,.75)}
@keyframes talk{from{height:7px;width:27px}to{height:26px;width:34px;border-radius:50%;border:5px solid #76f7f0}}@keyframes pulse{from{transform:translateX(-50%) scale(1)}to{transform:translateX(-50%) scale(1.09)}}@keyframes bloom{0%,100%{transform:rotate(-5deg) scale(1)}50%{transform:rotate(8deg) scale(1.08)}}
@media(max-width:640px){.jarvis-stage{min-height:510px;padding:26px 10px 18px}.speech{font-size:.92rem;max-width:92%}#ptt{transform:scale(.9);margin:-10px 0}.name{margin-top:-18px}}
"""

JS = r"""
export default function(component) {
  const { parentElement, setStateValue, setTriggerValue } = component;
  const stage = parentElement.querySelector('.jarvis-stage');
  const button = parentElement.querySelector('#ptt');
  const status = parentElement.querySelector('#ptt-status');
  const speech = parentElement.querySelector('#speech');
  if (!button || button.dataset.bound === '1') return;
  button.dataset.bound = '1';

  let recorder=null, stream=null, chunks=[], startedAt=0, activePointer=null;
  const setStatus=(text,cls='')=>{status.textContent=text;status.className='ptt-status'+(cls?' '+cls:'');};
  const speak=(text)=>{
    if(!('speechSynthesis' in window)||!text)return;
    try{
      window.speechSynthesis.cancel();
      const u=new SpeechSynthesisUtterance(text);
      u.lang='pt-BR';u.rate=.98;u.pitch=1.03;
      u.onstart=()=>{stage.classList.add('speaking');setStatus('🔊 Jarvis está falando…');};
      u.onend=()=>{stage.classList.remove('speaking');setStatus('👆 Segure meu coração, fale e solte');};
      u.onerror=()=>{stage.classList.remove('speaking');};
      window.speechSynthesis.speak(u);
    }catch(_){stage.classList.remove('speaking');}
  };
  const cleanup=()=>{if(stream){stream.getTracks().forEach(t=>t.stop());stream=null;}recorder=null;activePointer=null;button.classList.remove('recording');};

  // Greeting is visual immediately and spoken when browser policy permits it.
  try{
    if(!sessionStorage.getItem('faithbloom_jarvis_greeted')){
      sessionStorage.setItem('faithbloom_jarvis_greeted','1');
      setTimeout(()=>speak('Olá! Que bom ter você aqui. Eu sou o Jarvis. O que vamos fazer hoje?'),450);
    }
  }catch(_){setTimeout(()=>speak('Olá! Que bom ter você aqui. Eu sou o Jarvis. O que vamos fazer hoje?'),450);}

  const begin=async(e)=>{
    e.preventDefault();
    if(recorder&&recorder.state==='recording')return;
    window.speechSynthesis?.cancel();stage.classList.remove('speaking');activePointer=e.pointerId;
    try{
      button.setPointerCapture?.(e.pointerId);
      stream=await navigator.mediaDevices.getUserMedia({audio:true});chunks=[];
      const preferred=['audio/webm;codecs=opus','audio/webm','audio/mp4','audio/ogg;codecs=opus'].find(t=>window.MediaRecorder&&MediaRecorder.isTypeSupported?.(t));
      recorder=preferred?new MediaRecorder(stream,{mimeType:preferred}):new MediaRecorder(stream);
      recorder.ondataavailable=ev=>{if(ev.data&&ev.data.size)chunks.push(ev.data)};
      recorder.onerror=()=>{speech.textContent='Não consegui ouvir você.';setStatus('Verifique a permissão do microfone.','error');cleanup();};
      recorder.onstop=()=>{
        const duration=Date.now()-startedAt,mime=recorder?.mimeType||chunks[0]?.type||'audio/webm',blob=new Blob(chunks,{type:mime});
        if(!blob.size||duration<250){speech.textContent='Fale um pouco mais e tente novamente.';setStatus('👆 Segure meu coração e fale.','error');cleanup();return;}
        const reader=new FileReader();reader.onloadend=()=>{
          const dataUrl=String(reader.result||''),data=dataUrl.includes(',')?dataUrl.split(',',2)[1]:'';
          if(!data){speech.textContent='Não consegui preparar o áudio.';setStatus('Tente novamente.','error');cleanup();return;}
          const id=`${Date.now()}-${blob.size}`;
          setStateValue('recording',{id,data,mime_type:mime,duration_ms:duration});
          speech.textContent='Entendi. Só um instante enquanto cuido disso…';setStatus('🧠 Pensando e executando…');
          setTriggerValue('submitted',id);cleanup();
        };reader.readAsDataURL(blob);
      };
      recorder.start(120);startedAt=Date.now();button.classList.add('recording');speech.textContent='Estou ouvindo você…';setStatus('🔴 Ouvindo… solte quando terminar','live');
    }catch(err){cleanup();speech.textContent='Preciso da permissão do microfone para conversar com você.';setStatus(String(err?.name||'').includes('NotAllowed')?'Microfone bloqueado. Permita o acesso no navegador.':'Não consegui acessar o microfone.','error');}
  };
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


def decode_recording(payload: dict[str, Any] | None) -> tuple[bytes,str,str] | None:
    if not payload or not payload.get('data'):return None
    raw=base64.b64decode(str(payload['data']),validate=True)
    if not raw:return None
    return raw,_format_from_mime(payload.get('mime_type')),str(payload.get('id') or '')


def push_to_talk(*,key: str='jarvis_push_to_talk'):
    components=getattr(st,'components',None);v2=getattr(components,'v2',None) if components else None;factory=getattr(v2,'component',None) if v2 else None
    if factory is None:return None
    widget=factory('faithbloom_jarvis_push_to_talk',html=HTML,css=CSS,js=JS)
    return widget(key=key,default={'recording':None,'submitted':None},on_recording_change=lambda:None,on_submitted_change=lambda:None)
