"""Exercise the actual heart component script without a browser or microphone."""

import json
import re
import shutil
import subprocess

import pytest

import jarvis_heart_mic as heart


NODE = shutil.which("node")


HARNESS = r"""
import assert from 'node:assert/strict';
const input = JSON.parse(process.argv[1]);
const component = (await import('data:text/javascript;base64,' + Buffer.from(input.script).toString('base64'))).default;

function environment({motion='on', reduced=false, deny=false, deferPermission=false}={}) {
  let clock=1000, permissionResolve;
  const events=[], recordings=[], tracks=[], timers=new Map(), armReturns=[];
  const restingArm='rotate(-18deg)';
  let animatedArm='matrix(0, -1, 1, 0, 0, 0)', committedArm=restingArm;
  let nextTimer=1;
  class Classes {
    constructor(owner, initial=[]) { this.owner=owner; this.values=new Set(initial); }
    add(...names) { for (const name of names) { if (!this.values.has(name)) events.push({kind:'add', owner:this.owner, name}); this.values.add(name); } }
    remove(...names) { for (const name of names) { if (this.values.has(name)) events.push({kind:'remove', owner:this.owner, name}); this.values.delete(name); } }
    contains(name) { return this.values.has(name); }
    toggle(name, force) { const add=force === undefined ? !this.contains(name) : force; if (add) this.add(name); else this.remove(name); return add; }
  }
  class Element {
    constructor(id, classes=[]) { this.id=id; this.classList=new Classes(id,classes); this.listeners={}; this.textContent=''; this.offsetWidth=240; this.style={}; }
    addEventListener(type, handler) { (this.listeners[type] ||= []).push(handler); }
    removeEventListener(type, handler) { this.listeners[type]=(this.listeners[type] || []).filter(item=>item!==handler); }
    emit(type, options={}) { const event={type, target:this, ...options}; this['on'+type]?.(event); for (const listener of this.listeners[type] || []) listener(event); }
  }
  const root=new Element('jh-shell',['jh-shell']), robot=new Element('jh-robot',['jh-robot']);
  const button=new Element('jh-heart',['jh-heart']), status=new Element('jh-status',['jh-status']);
  const arm=new Element('right-arm',['jh-arm','r']), head=new Element('head-group',['jh-head-group']);
  // Model the style boundary that a real browser needs to transition from an
  // interrupted keyframe pose. Without committing that pose, changing only
  // the animation class would return directly to the unchanged resting style.
  arm.style=new Proxy({}, {set(style, property, value) {
    style[property]=value;
    if(property==='transform' && value==='') {
      if(style.transition!=='none' && committedArm!==restingArm) {
        armReturns.push({from:committedArm, to:restingArm});
      }
      committedArm=restingArm;
    }
    return true;
  }});
  Object.defineProperty(arm,'offsetWidth',{get() {
    committedArm=arm.style.transform || (robot.classList.contains('greeting') ? animatedArm : restingArm);
    return 31;
  }});
  globalThis.getComputedStyle=element=> {
    const transform=element===arm ? (robot.classList.contains('greeting') ? animatedArm : restingArm) : 'none';
    events.push({kind:'computed-style', owner:element.id, transform});
    return {transform};
  };
  const elements={'#jh-shell':root,'#jh-robot':robot,'#jh-heart':button,'#jh-status':status,'.jh-arm.r':arm,'.jh-head-group':head};
  root.querySelector=selector=>elements[selector] || null;
  root.querySelectorAll=selector=>Object.entries(elements).filter(([key])=>key===selector).map(([,element])=>element);
  globalThis.document={body:{contains:()=>true}};
  const stream=()=>({getTracks:()=>tracks});
  const mediaDevices={getUserMedia:async()=> {
    events.push({kind:'permission'});
    if (deny) throw Object.assign(new Error('denied'), {name:'NotAllowedError'});
    if (deferPermission) await new Promise(resolve=>permissionResolve=resolve);
    const track={stopped:false, stop(){this.stopped=true;}}; tracks.push(track);
    return stream();
  }};
  Object.defineProperty(globalThis,'navigator',{value:{mediaDevices},configurable:true});
  class Recorder {
    static isTypeSupported(){return true;}
    constructor(_stream, options={}) {this.mimeType=options.mimeType || 'audio/webm'; this.state='inactive'; recordings.push(this);}
    start(timeslice){this.state='recording'; this.timeslice=timeslice; this.onstart?.();}
    stop(){this.state='inactive'; this.ondataavailable?.({data:new Blob(['voice'],{type:this.mimeType})}); this.onstop?.();}
  }
  globalThis.MediaRecorder=Recorder;
  globalThis.window={MediaRecorder:Recorder, matchMedia:()=>({matches:reduced, addEventListener(){}, removeEventListener(){}})};
  globalThis.FileReader=class {readAsDataURL(blob){this.result='data:'+blob.type+';base64,dm9pY2U='; this.onloadend?.();}};
  Date.now=()=>clock;
  globalThis.setTimeout=(callback, delay)=>{const id=nextTimer++; timers.set(id,{callback, at:clock+delay}); return id;};
  globalThis.clearTimeout=id=>timers.delete(id);
  const payloads=[];
  const render=(data={})=>component({parentElement:{querySelector:selector=>elements[selector] || null}, data:{motion,stage:'idle',...data}, setStateValue:(name,payload)=>payloads.push({name,payload})});
  const flush=async()=>{for(let i=0;i<8;i++)await Promise.resolve();};
  const tap=async()=>{button.onclick(); await flush();};
  const advance=milliseconds=>{clock+=milliseconds;};
  const greeted=()=>robot.classList.contains('greeting');
  const greetingCount=()=>events.filter(event=>event.kind==='add' && event.owner==='jh-robot' && event.name==='greeting').length;
  return {root, robot, button, status, arm, head, events, recordings, tracks, payloads, armReturns, render, tap, flush, advance, greeted, greetingCount, poseArm:transform=>animatedArm=transform, resolvePermission:()=>permissionResolve?.()};
}
"""


def run_component(scenario):
    if NODE is None:
        pytest.skip("Node is needed to run the component JavaScript")
    result = subprocess.run(
        [NODE, "--input-type=module", "-e", HARNESS + "\n" + scenario, json.dumps({"script": heart.JS})],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr or result.stdout


def test_idle_mount_and_rerenders_never_wave():
    run_component("""
const env=environment();
env.render();
env.render();
env.render({stage:'thinking'});
env.render({stage:'idle'});
assert.equal(env.greeted(),false);
assert.equal(env.greetingCount(),0);
assert.equal(env.recordings.length,0);
""")


def test_wave_css_only_runs_once_while_greeting_is_active():
    greeting_animations = []
    for selector, declarations in re.findall(r"([^{}]+)\{([^{}]*)\}", heart.CSS):
        animation = re.search(r"(?:^|;)\s*animation\s*:\s*([^;}]+)", declarations)
        if animation is None:
            continue
        tokens = animation.group(1).split()
        if tokens[0] not in {"jWave", "jGreet"}:
            continue
        assert ".greeting" in selector
        assert "infinite" not in tokens
        iterations = [float(token) for token in tokens if re.fullmatch(r"\d+(?:\.\d+)?", token)]
        assert not iterations or iterations == [1]
        greeting_animations.append(tokens[0])
    assert set(greeting_animations) == {"jWave", "jGreet"}


def test_wave_finishes_once_and_only_a_new_conversation_restarts_it():
    run_component("""
const env=environment(); env.render(); await env.tap();
assert.equal(env.greeted(),true);
assert.equal(env.greetingCount(),1);
assert.equal(env.recordings.length,1);
assert.equal(env.recordings[0].state,'recording');
assert.equal(env.robot.classList.contains('listening'),true);
env.robot.emit('animationend',{animationName:'jBlink'});
assert.equal(env.greeted(),true);
env.robot.emit('animationend',{animationName:'jWave'});
assert.equal(env.greeted(),false);
env.advance(1000); await env.tap();
assert.equal(env.greetingCount(),1);
assert.equal(env.greeted(),false);
assert.equal(env.payloads.length,1);
assert.equal(env.payloads[0].name,'recording');
assert.equal(env.payloads[0].payload.data,'dm9pY2U=');
assert.equal(env.payloads[0].payload.duration_ms,1000);
assert.equal(env.tracks.every(track=>track.stopped),true);
env.render({stage:'thinking'}); env.render();
assert.equal(env.greetingCount(),1);
await env.tap();
assert.equal(env.greeted(),true);
assert.equal(env.greetingCount(),2);
env.robot.emit('animationcancel',{animationName:'jWave'});
assert.equal(env.greeted(),false);
""")


def test_pending_microphone_permission_does_not_repeat_greeting_or_capture():
    run_component("""
const env=environment({deferPermission:true}); env.render();
await env.tap(); await env.tap();
assert.equal(env.greetingCount(),1);
assert.equal(env.events.filter(event=>event.kind==='permission').length,1);
env.resolvePermission(); await env.flush();
assert.equal(env.recordings.length,1);
assert.equal(env.recordings[0].state,'recording');
env.advance(1000); await env.tap();
assert.equal(env.greeted(),false);
assert.equal(env.greetingCount(),1);
assert.equal(env.payloads.length,1);
""")


@pytest.mark.parametrize("motion,reduced,expected", [("off", False, False), ("off", True, False), ("auto", True, False), ("auto", False, True), ("on", True, True)])
def test_motion_preference_controls_wave_without_disabling_microphone(motion, reduced, expected):
    run_component(f"""
const env=environment({{motion:{json.dumps(motion)},reduced:{json.dumps(reduced)}}});
env.render(); await env.tap();
assert.equal(env.greeted(),{json.dumps(expected)});
assert.equal(env.recordings[0].state,'recording');
env.advance(1000); await env.tap();
assert.equal(env.payloads.length,1);
assert.equal(env.greeted(),false);
""")


def test_disabling_motion_or_rejecting_microphone_clears_greeting():
    run_component("""
const env=environment(); env.render(); await env.tap();
assert.equal(env.greeted(),true);
env.render({motion:'off'});
assert.equal(env.greeted(),false);
env.render({motion:'on'});
assert.equal(env.greeted(),false);
assert.equal(env.greetingCount(),1);
const denied=environment({deny:true}); denied.render(); await denied.tap();
assert.equal(denied.greeted(),false);
assert.equal(denied.recordings.length,0);
assert.equal(denied.status.textContent,'Permita o microfone no navegador');
""")


@pytest.mark.parametrize("interruption", ["stop", "recorder_error", "thinking"])
def test_interrupted_greeting_returns_from_the_current_arm_pose(interruption):
    actions = {
        "stop": "env.advance(600); await env.tap();",
        "recorder_error": "env.recordings[0].onerror();",
        "thinking": "env.render({stage:'thinking'});",
    }
    run_component("""
const env=environment(); env.render(); await env.tap();
const raised='matrix(-0.173648, -0.984808, 0.984808, -0.173648, 0, 0)';
env.poseArm(raised);
""" + actions[interruption] + """
assert.equal(env.greeted(),false);
assert.deepEqual(env.armReturns,[{from:raised,to:'rotate(-18deg)'}]);
assert.equal(env.arm.style.transform,'');
assert.notEqual(env.arm.style.transition,'none');
assert.equal(env.greetingCount(),1);
// The cancellation event queued by removing the animation must not restart
// the return or request another recording.
env.robot.emit('animationcancel',{animationName:'jWave'});
assert.equal(env.armReturns.length,1);
assert.equal(env.recordings.length,1);
""" + ("""
assert.equal(env.payloads.length,1);
assert.equal(env.payloads[0].payload.duration_ms,600);
assert.equal(env.tracks.every(track=>track.stopped),true);
""" if interruption == "stop" else ""))


@pytest.mark.parametrize("motion", ["off", "auto"])
def test_disabling_greeting_motion_does_not_animate_a_return(motion):
    run_component(f"""
const env=environment({{motion:'on',reduced:true}}); env.render(); await env.tap();
assert.equal(env.greeted(),true);
env.render({{motion:{json.dumps(motion)}}});
assert.equal(env.greeted(),false);
assert.deepEqual(env.armReturns,[]);
assert.equal(env.events.filter(event=>event.kind==='computed-style' && event.owner==='right-arm').length,0);
assert.equal(env.recordings[0].state,'recording');
env.advance(600); await env.tap();
assert.equal(env.payloads.length,1);
assert.equal(env.greetingCount(),1);
""")
