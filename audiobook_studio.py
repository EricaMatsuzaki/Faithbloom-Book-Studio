"""FaithBloom Refinamento 09 — Audiobook Studio Professional.

Objetivos:
- separar texto aprovado de direção de voz, sem reescrever a história;
- narrador único ou narrador + personagens, com Voice Profiles reutilizáveis;
- preview e geração por cena/segmento antes do lote completo;
- dicionário de pronúncia, ritmo, pausas, emoção e ênfase;
- versões A/B/C de áudio, favoritos e aprovação explícita da autora;
- fila cooperativa com pause/resume/cancel via ``fila_producao``;
- QA objetivo de arquivos de áudio e montagem final quando FFmpeg existir;
- exportar pacote de estúdio sem fingir conformidade com plataformas externas;
- manter Bible Guard: IA nunca traduz/inventa texto bíblico.

O módulo é provider-neutral. IDs de voz são salvos como configuração e enviados
apenas quando o conector TTS escolhido os suporta.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any
import csv
import io
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import unicodedata
import uuid
import zipfile

from armazenamento import _json, _save_json
from storage_backend import materializar_assets_em_objeto, persistir_assets_em_objeto
from translation_localization import normalize_locale, texto_biblico_para_exportacao
from controle_geracao import estimar_custo

AUDIOBOOK_INDEX = "audiobook_studio/index.json"
VOICE_LIBRARY_PATH = "audiobook_studio/voice_library.json"

STUDIO_MODES = {
    "automatic": "Automático — o Voice Director sugere direção, mas a autora ainda aprova o roteiro e o áudio.",
    "studio": "Studio — controle detalhado cena a cena, segmentos, voz, ritmo, pausas e pronúncia.",
}
CAST_MODES = {
    "single_narrator": "Narrador único",
    "narrator_characters": "Narrador + personagens",
}
VOICE_STYLE_PRESETS = {
    "warm_storyteller": {"label":"Contador(a) acolhedor(a)", "energy":"medium", "pace_wpm":140, "notes":"calor, clareza e musicalidade natural"},
    "gentle_bedtime": {"label":"Suave / bedtime", "energy":"low", "pace_wpm":115, "notes":"calmo, macio e sem dramatização excessiva"},
    "playful": {"label":"Divertido(a) / brincalhão(ona)", "energy":"high", "pace_wpm":155, "notes":"leve, sorridente e ótimo para humor/onomatopeias"},
    "cinematic": {"label":"Narrativo / cinematográfico", "energy":"medium_high", "pace_wpm":135, "notes":"contrastes emocionais controlados e pausas de cena"},
    "devotional_gentle": {"label":"Devocional suave", "energy":"low_medium", "pace_wpm":125, "notes":"respeitoso, sereno e claro em reflexão/oração"},
    "neutral": {"label":"Neutro profissional", "energy":"medium", "pace_wpm":145, "notes":"dicção clara e pouca interpretação"},
}
EMOTION_PRESETS = ["neutra", "alegria", "ternura", "curiosidade", "tristeza", "ansiedade", "esperança", "surpresa", "humor", "fé", "gratidão", "reflexão"]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _version_label(n: int) -> str:
    return chr(64+n) if 1 <= n <= 26 else f"V{n}"


def _canonical_text(text: str) -> str:
    """Compara conteúdo verbal ignorando pontuação/espaçamento, não palavras."""
    text = unicodedata.normalize("NFKC", text or "").casefold()
    return "".join(ch for ch in text if ch.isalnum())


def text_fingerprint(text: str) -> str:
    return sha256((text or "").encode("utf-8")).hexdigest()


def estimate_duration_seconds(text: str, pace_wpm: int | float = 145) -> float:
    words = max(1, len(re.findall(r"\S+", text or "")))
    wpm = max(60.0, min(240.0, float(pace_wpm or 145)))
    return round((words / wpm) * 60.0, 2)


@dataclass
class VoiceProfile:
    name: str
    locale: str = "pt-BR"
    role: str = "narrator"
    provider_voice_id: str = ""
    style_id: str = "warm_storyteller"
    pace_wpm: int = 140
    speed: float = 1.0
    notes: str = ""
    favorite: bool = False
    id: str = ""

    def normalized(self) -> dict:
        if self.style_id not in VOICE_STYLE_PRESETS:
            raise ValueError("Preset de voz inválido.")
        if not 75 <= int(self.pace_wpm) <= 220:
            raise ValueError("Ritmo deve ficar entre 75 e 220 palavras/minuto.")
        if not 0.75 <= float(self.speed) <= 1.30:
            raise ValueError("Velocidade deve ficar entre 0.75× e 1.30×.")
        d = asdict(self)
        d["id"] = self.id or uuid.uuid4().hex
        d["locale"] = normalize_locale(self.locale)
        d["created_at"] = _now_iso()
        return d


def create_voice_profile(name: str, locale: str="pt-BR", *, role: str="narrator", provider_voice_id: str="",
                         style_id: str="warm_storyteller", pace_wpm: int|None=None, speed: float=1.0,
                         notes: str="", favorite: bool=False) -> dict:
    default_pace = VOICE_STYLE_PRESETS.get(style_id, VOICE_STYLE_PRESETS["warm_storyteller"])["pace_wpm"]
    return VoiceProfile(name=name.strip() or "Voz sem nome", locale=locale, role=role,
                        provider_voice_id=provider_voice_id.strip(), style_id=style_id,
                        pace_wpm=int(pace_wpm or default_pace), speed=float(speed), notes=notes.strip(),
                        favorite=bool(favorite)).normalized()


def list_voice_profiles(locale: str|None=None) -> list[dict]:
    rows = _json(VOICE_LIBRARY_PATH, []) or []
    if locale:
        loc=normalize_locale(locale); rows=[x for x in rows if normalize_locale(x.get("locale",""))==loc]
    return sorted(rows, key=lambda x:(not bool(x.get("favorite")), x.get("name","").casefold()))


def save_voice_profile(profile: dict) -> dict:
    p=deepcopy(profile)
    if not p.get("id"):
        p["id"]=uuid.uuid4().hex
    p["locale"]=normalize_locale(p.get("locale","pt-BR"))
    p["updated_at"]=_now_iso()
    rows=_json(VOICE_LIBRARY_PATH,[]) or []
    for i,row in enumerate(rows):
        if row.get("id")==p["id"]:
            rows[i]=p; break
    else:
        rows.append(p)
    _save_json(VOICE_LIBRARY_PATH,rows)
    return p


def get_voice_profile(profile_id: str, *, project: dict|None=None) -> dict:
    if project:
        local=(project.get("voice_profiles") or {}).get(profile_id)
        if local: return deepcopy(local)
    return deepcopy(next((x for x in list_voice_profiles() if x.get("id")==profile_id),{}))


def _safe_translation(state: dict, locale: str) -> dict:
    loc=normalize_locale(locale)
    raw=(state.get("traducoes") or {}).get(loc) or {}
    if isinstance(raw,dict) and isinstance(raw.get("cenas_texto"),list):
        return raw
    # Alguns projetos guardam versões por locale; só usa explicitamente aprovada.
    versions=(state.get("translation_versions") or {}).get(loc) or []
    approved_id=((state.get("traducoes_aprovadas") or {}).get(loc) if isinstance(state.get("traducoes_aprovadas"),dict) else "")
    if approved_id:
        for v in versions:
            if v.get("versao_id")==approved_id and isinstance(v.get("cenas_texto"),list):
                return v
    return {}


def build_audio_source(state: dict, locale: str|None=None) -> dict:
    """Cria fonte narrável. Bíblia só entra via BibleVerseRecord aprovado.

    ``versiculo_texto_original`` e similares nunca são usados diretamente.
    """
    loc=normalize_locale(locale or state.get("idioma_original") or "pt-BR")
    original=normalize_locale(state.get("idioma_original") or "pt-BR")
    edition=_safe_translation(state,loc) if loc != original else {}
    scenes=deepcopy(edition.get("cenas_texto") or state.get("cenas_texto") or [])
    out=[]
    for i,c in enumerate(scenes,1):
        if isinstance(c,dict):
            text=str(c.get("texto") or c.get("text") or "").strip()
            num=int(c.get("numero") or i)
            emotion=str(c.get("emocao") or c.get("emotion") or "neutra")
        else:
            text=str(c).strip(); num=i; emotion="neutra"
        if text:
            out.append({"numero":num,"scene_type":"story","texto":text,"emocao":emotion})
    lesson=str(edition.get("licao_final") or state.get("licao_final") or "").strip()
    if lesson:
        out.append({"numero":len(out)+1,"scene_type":"lesson","texto":lesson,"emocao":"reflexão"})
    bible_records=state.get("bible_records") or {}
    record=bible_records.get(loc) if isinstance(bible_records,dict) else None
    ref=(record or {}).get("referencia") or edition.get("versiculo_referencia") or state.get("versiculo_referencia") or ""
    safe=texto_biblico_para_exportacao(record) if record else {"referencia":ref,"texto":"","pode_exportar_texto":False,"versao":""}
    if ref:
        if safe.get("pode_exportar_texto"):
            # Texto exato aprovado; não passa por Voice Director para reescrita.
            text=f"{safe.get('texto','')}".strip()
            out.append({"numero":len(out)+1,"scene_type":"scripture","texto":text,"referencia":ref,"versao":safe.get("versao",""),"emocao":"reflexão","immutable_text":True})
        else:
            out.append({"numero":len(out)+1,"scene_type":"scripture_reference","texto":ref,"referencia":ref,"emocao":"reflexão","immutable_text":True})
    return {"locale":loc,"title":edition.get("titulo") or state.get("titulo","") ,"scenes":out,
            "bible_guard":{"ai_translation_allowed":False,"reference":ref,"approved_text_used":bool(safe.get("pode_exportar_texto"))}}


def create_script_scene(number: int, text: str, *, scene_type: str="story", emotion: str="neutra",
                        speaker: str="narrator", immutable_text: bool=False) -> dict:
    text=(text or "").strip()
    return {
        "id":uuid.uuid4().hex,"numero":int(number),"scene_type":scene_type,
        "source_text":text,"source_sha256":text_fingerprint(text),"immutable_text":bool(immutable_text),
        "emotion":emotion or "neutra","pace_wpm":140,"pause_before_ms":0,"pause_after_ms":650,
        "emphasis":[],"segments":[{"speaker":speaker,"text":text,"emotion":emotion or "neutra","pace_wpm":140,"pause_after_ms":0}],
        "status":"draft","author_approval":None,"version":1,"version_label":"A","revisions":[],"created_at":_now_iso(),"updated_at":_now_iso(),
    }


def build_script_from_source(source: dict) -> list[dict]:
    return [create_script_scene(x["numero"],x["texto"],scene_type=x.get("scene_type","story"),emotion=x.get("emocao","neutra"),immutable_text=x.get("immutable_text",False)) for x in source.get("scenes",[])]


def script_integrity(scene: dict) -> dict:
    source=str(scene.get("source_text") or "")
    segments=scene.get("segments") or []
    rendered=" ".join(str(s.get("text") or "") for s in segments)
    ok=_canonical_text(source)==_canonical_text(rendered)
    return {"ok":ok,"source_sha256":text_fingerprint(source),"rendered_sha256":text_fingerprint(rendered),
            "message":"Texto preservado." if ok else "Os segmentos alteraram/omitiram palavras do texto aprovado."}


def revise_script_scene(scene: dict, *, change_request: str, patch: dict|None=None, preserve_text: bool=True) -> dict:
    out=deepcopy(scene)
    snapshot={k:deepcopy(v) for k,v in scene.items() if k!="revisions"}
    out.setdefault("revisions",[]).append({"version":scene.get("version",1),"version_label":scene.get("version_label","A"),"snapshot":snapshot,"change_request":change_request,"saved_at":_now_iso()})
    protected={"id","revisions","created_at","source_sha256"}
    for k,v in (patch or {}).items():
        if k in protected: continue
        if preserve_text and k=="source_text": continue
        out[k]=deepcopy(v)
    if preserve_text:
        out["source_text"]=scene.get("source_text","")
    if out.get("immutable_text") and _canonical_text(out.get("source_text","")) != _canonical_text(scene.get("source_text","")):
        raise ValueError("Texto bíblico/referência protegida não pode ser reescrito no Audiobook Studio.")
    out["version"]=int(scene.get("version",1))+1; out["version_label"]=_version_label(out["version"])
    out["status"]="draft"; out["author_approval"]=None; out["updated_at"]=_now_iso(); out["last_change_request"]=change_request
    return out


def approve_script_scene(scene: dict, approved_by: str="autora") -> dict:
    out=deepcopy(scene); integrity=script_integrity(out)
    if not integrity["ok"]:
        raise ValueError(integrity["message"])
    if text_fingerprint(out.get("source_text","")) != out.get("source_sha256"):
        raise ValueError("O texto-fonte aprovado foi modificado. Crie uma nova edição textual antes de narrar.")
    out["status"]="approved"; out["author_approval"]={"approved":True,"by":approved_by,"at":_now_iso()}; out["updated_at"]=_now_iso()
    return out


def voice_director_prompt(scene: dict, project: dict) -> tuple[str,str]:
    cast=project.get("cast_mode","single_narrator")
    names=sorted((project.get("casting") or {}).keys())
    bible=scene.get("scene_type") in {"scripture","scripture_reference"}
    system=f"""Você é o AI Voice Director do FaithBloom. Direcione uma leitura em voz alta sem reescrever UMA palavra do texto aprovado.
Modo de elenco: {cast}. Personagens/vozes disponíveis: {', '.join(names) if names else 'narrator'}.
Retorne JSON com emotion, pace_wpm, pause_before_ms, pause_after_ms, emphasis e segments.
Cada segment deve ter speaker, text, emotion, pace_wpm e pause_after_ms. A concatenação dos textos dos segments deve preservar exatamente todas as palavras do texto-fonte, podendo mudar apenas espaços ao separar falas.
Nunca acrescente falas, explicações, efeitos não existentes ou texto narrativo novo.
BÍBLIA: {'ESTA CENA É PROTEGIDA; não altere, traduza ou parafraseie seu texto.' if bible else 'Se houver referência bíblica em contexto, não invente texto de versículo.'}
Onomatopeias já aprovadas/localizadas no texto devem ser interpretadas com naturalidade e equilíbrio; não crie novas onomatopeias por conta própria.
"""
    user=json.dumps({"numero":scene.get("numero"),"scene_type":scene.get("scene_type"),"emotion_hint":scene.get("emotion"),"source_text":scene.get("source_text")},ensure_ascii=False)
    return system,user


def normalize_voice_director_result(scene: dict, result: Any) -> dict:
    out=deepcopy(scene)
    if not isinstance(result,dict):
        return {**out,"voice_director_alert":"Resposta do Voice Director não era um objeto JSON; nenhuma alteração aplicada."}
    allowed={"emotion","pace_wpm","pause_before_ms","pause_after_ms","emphasis","segments"}
    for k in allowed:
        if k in result: out[k]=deepcopy(result[k])
    # Limites para evitar valores absurdos.
    try: out["pace_wpm"]=max(75,min(220,int(out.get("pace_wpm",140))))
    except Exception: out["pace_wpm"]=140
    for k in ("pause_before_ms","pause_after_ms"):
        try: out[k]=max(0,min(5000,int(out.get(k,0))))
        except Exception: out[k]=0
    integ=script_integrity(out)
    if not integ["ok"]:
        out["segments"]=deepcopy(scene.get("segments") or [{"speaker":"narrator","text":scene.get("source_text","")}])
        out["voice_director_alert"]="Sugestão descartada porque alterava/omitia palavras do texto aprovado. Direção geral preservada; segmentos voltaram ao original."
    out["status"]="draft"; out["author_approval"]=None; out["updated_at"]=_now_iso()
    return out


def create_audiobook_project(title: str, locale: str="pt-BR", *, collection: str="", source_ref: str="",
                             mode: str="studio", cast_mode: str="single_narrator", source_state: dict|None=None) -> dict:
    if mode not in STUDIO_MODES: raise ValueError("Modo de estúdio inválido.")
    if cast_mode not in CAST_MODES: raise ValueError("Modo de elenco inválido.")
    pid=uuid.uuid4().hex; loc=normalize_locale(locale)
    source=build_audio_source(source_state or {},loc) if source_state else {"locale":loc,"title":title,"scenes":[],"bible_guard":{"ai_translation_allowed":False}}
    p={
        "id":pid,"title":title.strip() or source.get("title") or "Audiobook sem título","collection":collection,"locale":loc,"source_ref":source_ref,
        "mode":mode,"cast_mode":cast_mode,"source":source,"script_scenes":build_script_from_source(source),
        "known_speakers":["narrator"]+sorted((source_state.get("personagens") or {}).keys()) if source_state else ["narrator"],
        "voice_profiles":{},"casting":{},"pronunciations":[],"audio_versions":{},"approved_audio":{},"final_mix":"","final_mix_qa":{},
        "status":"draft","history":[],"created_at":_now_iso(),"updated_at":_now_iso(),
        "bible_guard":{"ai_translation_allowed":False,"source":source.get("bible_guard",{})},
    }
    return p


def _index() -> list[dict]:
    x=_json(AUDIOBOOK_INDEX,[]) or []
    return x if isinstance(x,list) else []


def save_audiobook_project(project: dict) -> dict:
    p=deepcopy(project); p["updated_at"]=_now_iso()
    serial=persistir_assets_em_objeto(p,f"assets/audiobooks/{p['id']}")
    _save_json(f"audiobook_studio/{p['id']}.json",serial)
    idx=_index(); item={"id":p["id"],"title":p.get("title",""),"locale":p.get("locale",""),"status":p.get("status","draft"),"updated_at":p["updated_at"]}
    for i,x in enumerate(idx):
        if x.get("id")==p["id"]: idx[i]=item; break
    else: idx.append(item)
    _save_json(AUDIOBOOK_INDEX,idx)
    return p


def load_audiobook_project(project_id: str) -> dict:
    return materializar_assets_em_objeto(_json(f"audiobook_studio/{project_id}.json",{}) or {})


def list_audiobook_projects() -> list[dict]:
    return sorted(_index(),key=lambda x:x.get("updated_at",x.get("created_at","")),reverse=True)


def upsert_project_voice(project: dict, profile: dict) -> dict:
    out=deepcopy(project); p=deepcopy(profile); p.setdefault("id",uuid.uuid4().hex)
    out.setdefault("voice_profiles",{})[p["id"]]=p; out["updated_at"]=_now_iso(); return out


def assign_voice(project: dict, speaker: str, profile_id: str) -> dict:
    if profile_id not in (project.get("voice_profiles") or {}) and not get_voice_profile(profile_id):
        raise ValueError("Voice Profile não encontrado.")
    out=deepcopy(project); out.setdefault("casting",{})[speaker.strip() or "narrator"]=profile_id; out["updated_at"]=_now_iso(); return out


def add_pronunciation(project: dict, term: str, spoken_as: str, *, locale: str|None=None, scope: str="all", note: str="") -> dict:
    if not term.strip() or not spoken_as.strip(): raise ValueError("Termo e pronúncia são obrigatórios.")
    out=deepcopy(project); loc=normalize_locale(locale or out.get("locale") or "pt-BR")
    item={"id":uuid.uuid4().hex,"term":term.strip(),"spoken_as":spoken_as.strip(),"locale":loc,"scope":scope,"note":note.strip(),"enabled":True}
    # Substitui entrada do mesmo termo/locale, preservando apenas uma regra ativa.
    rows=[x for x in out.get("pronunciations",[]) if not (x.get("term","").casefold()==term.strip().casefold() and normalize_locale(x.get("locale",""))==loc)]
    rows.append(item); out["pronunciations"]=rows; out["updated_at"]=_now_iso(); return out


def apply_pronunciations(text: str, project: dict, *, locale: str|None=None) -> tuple[str,list[dict]]:
    loc=normalize_locale(locale or project.get("locale") or "pt-BR"); out=text or ""; applied=[]
    for row in project.get("pronunciations",[]) or []:
        if not row.get("enabled",True) or normalize_locale(row.get("locale",""))!=loc: continue
        term=row.get("term",""); repl=row.get("spoken_as","")
        if not term or not repl: continue
        pattern=re.compile(r"(?<!\w)"+re.escape(term)+r"(?!\w)",flags=re.I)
        new,n=pattern.subn(repl,out)
        if n: out=new; applied.append({"term":term,"spoken_as":repl,"occurrences":n})
    return out,applied


def _profile_for_speaker(project: dict, speaker: str) -> dict:
    casting=project.get("casting") or {}
    pid=casting.get(speaker) or casting.get("narrator") or ""
    return get_voice_profile(pid,project=project) if pid else {}


def build_generation_units(project: dict, *, only_approved_scripts: bool=True, scene_numbers: list[int]|None=None) -> list[dict]:
    wanted=set(int(x) for x in (scene_numbers or []))
    units=[]
    for scene in sorted(project.get("script_scenes",[]) or [],key=lambda x:int(x.get("numero",0))):
        n=int(scene.get("numero",0))
        if wanted and n not in wanted: continue
        if only_approved_scripts and scene.get("status")!="approved": continue
        segments=scene.get("segments") or [{"speaker":"narrator","text":scene.get("source_text","")}]
        for idx,seg in enumerate(segments,1):
            speaker="narrator" if project.get("cast_mode")=="single_narrator" else (seg.get("speaker") or "narrator")
            profile=_profile_for_speaker(project,speaker)
            pace=int(seg.get("pace_wpm") or scene.get("pace_wpm") or profile.get("pace_wpm") or 140)
            speed=float(profile.get("speed") or 1.0)
            text=str(seg.get("text") or "").strip()
            tts_text,pron=apply_pronunciations(text,project)
            unit_id=f"scene-{n:04d}-segment-{idx:03d}"
            units.append({"id":unit_id,"kind":"audiobook_segment","scene_number":n,"segment_index":idx,"speaker":speaker,
                          "text":text,"tts_text":tts_text,"text_sha256":text_fingerprint(text),"pronunciations_applied":pron,
                          "emotion":seg.get("emotion") or scene.get("emotion","neutra"),"pace_wpm":pace,"speed":speed,
                          "pause_after_ms":int(seg.get("pause_after_ms") or (scene.get("pause_after_ms") if idx==len(segments) else 180) or 0),
                          "voice_profile_id":profile.get("id",""),"provider_voice_id":profile.get("provider_voice_id",""),
                          "voice_style_id":profile.get("style_id","neutral"),"estimated_seconds":estimate_duration_seconds(text,pace)})
    return units


def estimate_project_audio(project: dict) -> dict:
    units=build_generation_units(project,only_approved_scripts=False)
    secs=sum(float(u.get("estimated_seconds",0)) for u in units)
    mins=secs/60.0
    return {"segments":len(units),"estimated_seconds":round(secs,1),"estimated_minutes":round(mins,2),"estimated_cost_usd":estimar_custo("audio",1,mins) if mins else 0.0,
            "note":"Estimativa configurável do FaithBloom; não é preço oficial do provedor."}


def add_audio_version(project: dict, unit: dict, path: str, *, metadata: dict|None=None) -> tuple[dict,dict]:
    out=deepcopy(project); versions=out.setdefault("audio_versions",{}).setdefault(unit["id"],[])
    n=len(versions)+1; item={"id":uuid.uuid4().hex,"unit_id":unit["id"],"scene_number":unit["scene_number"],"segment_index":unit["segment_index"],
        "speaker":unit.get("speaker","narrator"),"version":n,"version_label":_version_label(n),"path":path,"favorite":False,"approved":False,
        "text_sha256":unit.get("text_sha256",""),"voice_profile_id":unit.get("voice_profile_id",""),"created_at":_now_iso(),"metadata":deepcopy(metadata or {})}
    versions.append(item); out["updated_at"]=_now_iso(); return out,item


def approve_audio_version(project: dict, unit_id: str, version_id: str, *, favorite: bool=False) -> dict:
    out=deepcopy(project); versions=out.setdefault("audio_versions",{}).get(unit_id) or []
    target=next((x for x in versions if x.get("id")==version_id),None)
    if not target: raise ValueError("Versão de áudio não encontrada.")
    for v in versions: v["approved"]=(v.get("id")==version_id)
    target["favorite"]=bool(favorite or target.get("favorite")); out.setdefault("approved_audio",{})[unit_id]=version_id; out["updated_at"]=_now_iso(); return out


def favorite_audio_version(project: dict, unit_id: str, version_id: str, value: bool=True) -> dict:
    out=deepcopy(project)
    for v in out.setdefault("audio_versions",{}).get(unit_id) or []:
        if v.get("id")==version_id: v["favorite"]=bool(value)
    out["updated_at"]=_now_iso(); return out


def _ffmpeg_binary() -> str:
    return shutil.which("ffmpeg") or ""


def _ffprobe_binary() -> str:
    return shutil.which("ffprobe") or ""


def inspect_audio(path: str) -> dict:
    p=Path(path or "")
    if not p.exists() or not p.is_file(): return {"ok":False,"path":path,"error":"Arquivo de áudio não encontrado."}
    info={"ok":True,"path":str(p),"size_bytes":p.stat().st_size,"duration_seconds":None,"codec":"","sample_rate":None,"channels":None,"bit_rate":None}
    ffprobe=_ffprobe_binary()
    if ffprobe:
        try:
            cmd=[ffprobe,"-v","error","-select_streams","a:0","-show_entries","stream=codec_name,sample_rate,channels,bit_rate:format=duration","-of","json",str(p)]
            data=json.loads(subprocess.check_output(cmd,stderr=subprocess.STDOUT,timeout=20).decode("utf-8"))
            stream=(data.get("streams") or [{}])[0]; fmt=data.get("format") or {}
            info.update({"duration_seconds":round(float(fmt.get("duration") or 0),3),"codec":stream.get("codec_name",""),
                         "sample_rate":int(stream.get("sample_rate") or 0) or None,"channels":int(stream.get("channels") or 0) or None,
                         "bit_rate":int(stream.get("bit_rate") or 0) or None})
        except Exception as exc: info["probe_warning"]=str(exc)[:200]
    elif p.suffix.lower()==".wav":
        try:
            import wave
            with wave.open(str(p),"rb") as w:
                info["sample_rate"]=w.getframerate(); info["channels"]=w.getnchannels(); info["codec"]="pcm"; info["duration_seconds"]=round(w.getnframes()/w.getframerate(),3)
        except Exception as exc: info["probe_warning"]=str(exc)[:200]
    return info


def _volume_metrics(path: str) -> dict:
    ffmpeg=_ffmpeg_binary()
    if not ffmpeg: return {"available":False}
    try:
        proc=subprocess.run([ffmpeg,"-hide_banner","-nostats","-i",path,"-af","volumedetect","-f","null","-"],capture_output=True,text=True,timeout=30)
        blob=(proc.stderr or "")+(proc.stdout or "")
        mean=re.search(r"mean_volume:\s*([\-\d.]+) dB",blob); maxv=re.search(r"max_volume:\s*([\-\d.]+) dB",blob)
        return {"available":True,"mean_db":float(mean.group(1)) if mean else None,"max_db":float(maxv.group(1)) if maxv else None}
    except Exception as exc: return {"available":False,"warning":str(exc)[:160]}


def qa_audio_clip(path: str, *, expected_text: str="", expected_pace_wpm: int=145) -> dict:
    info=inspect_audio(path); alerts=[]
    if not info.get("ok"):
        return {"ok":False,"blocking":1,"alerts":[{"severity":"blocking","code":"missing_audio","message":info.get("error","Áudio ausente.")}],"technical":info}
    if info.get("size_bytes",0)<512: alerts.append({"severity":"blocking","code":"tiny_file","message":"Arquivo muito pequeno para ser um áudio final válido."})
    dur=info.get("duration_seconds")
    if dur is not None and dur<=0.05: alerts.append({"severity":"blocking","code":"zero_duration","message":"Duração de áudio inválida."})
    if dur and expected_text:
        words=len(re.findall(r"\S+",expected_text)); actual=(words/dur)*60 if dur>0 else 0
        info["observed_wpm"]=round(actual,1); info["expected_pace_wpm"]=int(expected_pace_wpm)
        if actual>225: alerts.append({"severity":"attention","code":"too_fast","message":f"Ritmo observado ~{actual:.0f} ppm; revisar naturalidade/clareza."})
        elif actual<70: alerts.append({"severity":"attention","code":"too_slow","message":f"Ritmo observado ~{actual:.0f} ppm; revisar pausas excessivas."})
    vol=_volume_metrics(path); info["volume"]=vol
    if vol.get("available"):
        if vol.get("max_db") is not None and vol["max_db"]>=-0.1: alerts.append({"severity":"attention","code":"near_clipping","message":"Pico muito próximo de 0 dB; revisar clipping/limiter."})
        if vol.get("mean_db") is not None and vol["mean_db"]<-35: alerts.append({"severity":"attention","code":"very_quiet","message":"Nível médio muito baixo; revisar loudness."})
    blocking=sum(1 for a in alerts if a["severity"]=="blocking")
    return {"ok":blocking==0,"blocking":blocking,"alerts":alerts,"technical":info,"requires_listening_review":True,
            "note":"QA técnico não substitui escuta humana para pronúncia, emoção, ruído, naturalidade ou interpretação."}


def postprocess_speed(path: str, speed: float) -> str:
    speed=float(speed or 1.0)
    if abs(speed-1.0)<0.01: return path
    ffmpeg=_ffmpeg_binary()
    if not ffmpeg: return path
    if not 0.75<=speed<=1.30: raise ValueError("Velocidade fora da faixa segura do Studio.")
    p=Path(path); out=str(p.with_name(p.stem+f"_x{speed:.2f}"+p.suffix))
    subprocess.run([ffmpeg,"-y","-i",str(p),"-filter:a",f"atempo={speed:.4f}","-vn",out],check=True,capture_output=True,timeout=120)
    return out


def _call_tts(gerar_audio_func, text: str, name: str, *, voice: str="") -> str:
    # Backward compatible com o conector antigo de dois argumentos.
    try:
        return gerar_audio_func(texto_com_marcacoes=text,nome_arquivo=name,voice=voice or None)
    except TypeError:
        return gerar_audio_func(texto_com_marcacoes=text,nome_arquivo=name)


def executor_audiobook(gerar_audio_func):
    """Executor para ``fila_producao.processar_proximo``."""
    def _exec(job: dict, item: dict) -> tuple[dict,dict]:
        project=deepcopy(job.get("state") or {})
        name=f"fb_{project.get('id','audio')[:8]}_s{int(item['scene_number']):03d}_p{int(item['segment_index']):02d}_{uuid.uuid4().hex[:8]}"
        path=_call_tts(gerar_audio_func,item.get("tts_text") or item.get("text",""),name,voice=item.get("provider_voice_id",""))
        path=postprocess_speed(path,float(item.get("speed") or 1.0))
        qa=qa_audio_clip(path,expected_text=item.get("text",""),expected_pace_wpm=int(item.get("pace_wpm") or 145))
        project,version=add_audio_version(project,item,path,metadata={"qa":qa,"pronunciations_applied":item.get("pronunciations_applied",[]),"emotion":item.get("emotion"),"pace_wpm":item.get("pace_wpm")})
        return project,{"caminho_arquivo":path,"audio_version_id":version["id"],"qa":qa}
    return _exec


def create_audiobook_job(project: dict, scene_numbers: list[int]|None=None) -> dict:
    from fila_producao import criar_job
    units=build_generation_units(project,only_approved_scripts=True,scene_numbers=scene_numbers)
    if not units: raise ValueError("Não há cenas de roteiro aprovadas para narrar.")
    return criar_job(nome=f"Audiobook · {project.get('title','Livro')}",tipo="audiobook_tts",itens=units,state=project,
                     metadata={"project_id":project.get("id"),"locale":project.get("locale"),"segments":len(units)})


def _approved_version(project: dict, unit_id: str) -> dict:
    vid=(project.get("approved_audio") or {}).get(unit_id)
    return deepcopy(next((v for v in (project.get("audio_versions") or {}).get(unit_id,[]) if v.get("id")==vid),{})) if vid else {}


def audio_readiness(project: dict) -> dict:
    alerts=[]; units=build_generation_units(project,only_approved_scripts=True)
    scripts=project.get("script_scenes",[]) or []
    draft=sum(1 for s in scripts if s.get("status")!="approved")
    if draft: alerts.append({"severity":"blocking","code":"script_not_approved","message":f"{draft} cena(s) de roteiro ainda não foram aprovadas pela autora."})
    if not units: alerts.append({"severity":"blocking","code":"no_units","message":"Nenhum segmento aprovado para produção."})
    missing=[]
    for u in units:
        v=_approved_version(project,u["id"])
        if not v: missing.append(u["id"]); continue
        qa=(v.get("metadata") or {}).get("qa") or qa_audio_clip(v.get("path",""),expected_text=u["text"],expected_pace_wpm=u["pace_wpm"])
        if not qa.get("ok"): alerts.append({"severity":"blocking","code":"audio_qa","message":f"Áudio aprovado de {u['id']} possui bloqueio técnico."})
    if missing: alerts.append({"severity":"blocking","code":"audio_not_approved","message":f"{len(missing)} segmento(s) ainda não têm versão de áudio aprovada."})
    blocking=sum(1 for a in alerts if a["severity"]=="blocking")
    return {"ready":blocking==0,"blocking":blocking,"alerts":alerts,"approved_segments":len(units)-len(missing),"total_segments":len(units),
            "human_listening_required":True,"note":"A prontidão técnica sempre exige escuta final da autora; o sistema não finge avaliar interpretação humana apenas por metadados."}


def merge_approved_audio(project: dict, output_path: str, *, normalize: bool=True) -> dict:
    ready=audio_readiness(project)
    if not ready["ready"]: raise ValueError("O Audiobook ainda possui bloqueios antes da montagem final.")
    ffmpeg=_ffmpeg_binary()
    if not ffmpeg: raise RuntimeError("FFmpeg não está disponível neste ambiente; mantenha os clips separados ou instale FFmpeg no ambiente de produção.")
    units=build_generation_units(project,only_approved_scripts=True)
    files=[]
    with tempfile.TemporaryDirectory() as td:
        # Gera pequenos silêncios de acordo com a direção aprovada entre clips.
        for i,u in enumerate(units):
            v=_approved_version(project,u["id"]); files.append(v["path"])
            pause=max(0,int(u.get("pause_after_ms") or 0))
            if pause and i < len(units)-1:
                silence=os.path.join(td,f"silence_{i:04d}.mp3")
                subprocess.run([ffmpeg,"-y","-f","lavfi","-i","anullsrc=r=44100:cl=stereo","-t",f"{pause/1000:.3f}","-q:a","9",silence],check=True,capture_output=True,timeout=30)
                files.append(silence)
        concat=os.path.join(td,"concat.txt")
        with open(concat,"w",encoding="utf-8") as f:
            for p in files: f.write("file '"+str(Path(p).resolve()).replace("'","'\\''")+"'\n")
        Path(output_path).parent.mkdir(parents=True,exist_ok=True)
        cmd=[ffmpeg,"-y","-f","concat","-safe","0","-i",concat,"-vn"]
        if normalize: cmd += ["-af","loudnorm=I=-18:LRA=11:TP=-1.5"]
        cmd += ["-ar","44100","-ac","2","-b:a","192k",output_path]
        subprocess.run(cmd,check=True,capture_output=True,timeout=600)
    qa=qa_audio_clip(output_path,expected_text=" ".join(u["text"] for u in units),expected_pace_wpm=140)
    return {"path":output_path,"qa":qa,"segments":len(units),"normalized":bool(normalize),"ffmpeg_used":True}


def export_audiobook_package(project: dict, output_zip: str) -> dict:
    Path(output_zip).parent.mkdir(parents=True,exist_ok=True)
    readiness=distribution_readiness(project)
    manifest={"faithbloom":"Audiobook Studio Professional","project_id":project.get("id"),"title":project.get("title"),"locale":project.get("locale"),
              "cast_mode":project.get("cast_mode"),"exported_at":_now_iso(),"readiness":readiness,
              "bible_guard":{"ai_translation_allowed":False,"source":project.get("bible_guard",{})},
              "disclaimer":"Pacote de estúdio. Requisitos específicos de ACX/Audible/Kobo/Apple/Spotify e outros destinos devem passar pelo Publishing & Distribution Center antes do upload."}
    script_lines=[]
    for s in sorted(project.get("script_scenes",[]) or [],key=lambda x:int(x.get("numero",0))):
        script_lines.append(f"CENA {s.get('numero')} · {s.get('scene_type','story')} · {s.get('emotion','')}\n{s.get('source_text','')}\n")
    with zipfile.ZipFile(output_zip,"w",zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifest.json",json.dumps(manifest,ensure_ascii=False,indent=2))
        z.writestr("script/roteiro_aprovacao.json",json.dumps(project.get("script_scenes",[]),ensure_ascii=False,indent=2))
        z.writestr("script/roteiro_leitura.txt","\n".join(script_lines))
        csvbuf=io.StringIO(); w=csv.writer(csvbuf); w.writerow(["term","spoken_as","locale","scope","note"])
        for p in project.get("pronunciations",[]) or []: w.writerow([p.get("term",""),p.get("spoken_as",""),p.get("locale",""),p.get("scope",""),p.get("note","")])
        z.writestr("script/pronunciation_dictionary.csv",csvbuf.getvalue())
        for unit in build_generation_units(project,only_approved_scripts=True):
            v=_approved_version(project,unit["id"])
            path=v.get("path","") if v else ""
            if path and Path(path).exists(): z.write(path,f"audio/approved/{unit['id']}{Path(path).suffix.lower() or '.mp3'}")
        final=project.get("final_mix","")
        if final and Path(final).exists(): z.write(final,"audio/final/"+Path(final).name)
        z.writestr("qa/readiness.json",json.dumps(readiness,ensure_ascii=False,indent=2))
    return {"path":output_zip,"readiness":readiness,"size_bytes":Path(output_zip).stat().st_size}


def approve_final_mix(project: dict, approved_by: str="autora") -> dict:
    out=deepcopy(project)
    path=out.get("final_mix","")
    if not path or not Path(path).exists():
        raise ValueError("Gere o mix final antes da aprovação.")
    qa=out.get("final_mix_qa") or qa_audio_clip(path)
    if not qa.get("ok"):
        raise ValueError("O mix final possui bloqueios técnicos.")
    out["final_mix_qa"]=qa
    out["final_author_approval"]={"approved":True,"by":approved_by,"at":_now_iso(),"listening_required":True}
    out["status"]="approved"
    out["updated_at"]=_now_iso()
    return out


def distribution_readiness(project: dict) -> dict:
    base=audio_readiness(project); alerts=list(base.get("alerts",[]))
    final=project.get("final_mix","")
    if not final or not Path(final).exists():
        alerts.append({"severity":"blocking","code":"final_mix_missing","message":"Mix final completo ainda não foi gerado."})
    else:
        qa=project.get("final_mix_qa") or qa_audio_clip(final)
        if not qa.get("ok"):
            alerts.append({"severity":"blocking","code":"final_mix_qa","message":"Mix final possui bloqueios técnicos."})
    if not (project.get("final_author_approval") or {}).get("approved"):
        alerts.append({"severity":"blocking","code":"final_listening_not_approved","message":"A autora ainda não confirmou a escuta e aprovação do mix final."})
    blocking=sum(1 for a in alerts if a.get("severity")=="blocking")
    return {"ready":blocking==0,"blocking":blocking,"alerts":alerts,"human_listening_required":True,
            "note":"Pronto para seguir ao Publishing & Distribution Center; ainda não significa aceitação automática por uma plataforma específica."}

AUTO_DIRECTION = {
    "alegria": {"pace_wpm":155,"pause_after_ms":450},
    "humor": {"pace_wpm":160,"pause_after_ms":400},
    "surpresa": {"pace_wpm":150,"pause_after_ms":650},
    "curiosidade": {"pace_wpm":145,"pause_after_ms":550},
    "tristeza": {"pace_wpm":118,"pause_after_ms":900},
    "ansiedade": {"pace_wpm":148,"pause_after_ms":600},
    "esperança": {"pace_wpm":135,"pause_after_ms":750},
    "fé": {"pace_wpm":122,"pause_after_ms":950},
    "gratidão": {"pace_wpm":128,"pause_after_ms":850},
    "reflexão": {"pace_wpm":115,"pause_after_ms":1100},
    "ternura": {"pace_wpm":120,"pause_after_ms":800},
    "neutra": {"pace_wpm":140,"pause_after_ms":650},
}


def apply_automatic_direction(scene: dict) -> dict:
    """Direção conservadora, sem LLM e sem alterar texto; fica como rascunho."""
    out=deepcopy(scene); cfg=AUTO_DIRECTION.get(str(out.get("emotion","neutra")).casefold(),AUTO_DIRECTION["neutra"])
    out["pace_wpm"]=cfg["pace_wpm"]; out["pause_after_ms"]=cfg["pause_after_ms"]
    for seg in out.get("segments",[]) or []:
        seg["pace_wpm"]=cfg["pace_wpm"]; seg.setdefault("emotion",out.get("emotion","neutra"))
    out["status"]="draft"; out["author_approval"]=None; out["auto_direction_applied"]=True; out["updated_at"]=_now_iso()
    return out


def apply_automatic_direction_project(project: dict, *, only_unapproved: bool=True) -> dict:
    out=deepcopy(project); scenes=[]
    for s in out.get("script_scenes",[]) or []:
        if only_unapproved and s.get("status")=="approved": scenes.append(s)
        else: scenes.append(apply_automatic_direction(s))
    out["script_scenes"]=scenes; out["updated_at"]=_now_iso(); return out
