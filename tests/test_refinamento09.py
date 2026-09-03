import os
import shutil
import tempfile
import unittest
import wave
from pathlib import Path

from audiobook_studio import (
    create_voice_profile, create_audiobook_project, upsert_project_voice, assign_voice,
    build_audio_source, approve_script_scene, normalize_voice_director_result,
    add_pronunciation, apply_pronunciations, build_generation_units,
    add_audio_version, approve_audio_version, qa_audio_clip, audio_readiness,
    merge_approved_audio, approve_final_mix, distribution_readiness, export_audiobook_package,
)
from openrouter_client import converter_marcacoes_para_texto_natural


def make_wav(path, seconds=0.45, rate=16000):
    frames=int(seconds*rate)
    with wave.open(str(path),'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate); w.writeframes(b'\x00\x00'*frames)


class Refinamento09Tests(unittest.TestCase):
    def story(self, approved_bible=False):
        rec={"referencia":"Eclesiastes 3:1","locale":"pt-BR","status":"reference_only","versao":"","texto_aprovado":"","fonte":"","licenca_nota":"","aprovado_pela_autora":False}
        if approved_bible:
            rec.update({"status":"approved_text","versao":"Versão Teste Autorizada","texto_aprovado":"Há um tempo certo para cada propósito.","aprovado_pela_autora":True})
        return {
            "titulo":"Quando Mel Aprendeu a Esperar","colecao":"Pequenas Histórias, Grandes Lições","idioma_original":"pt-BR",
            "cenas_texto":[{"numero":1,"texto":"Mel esperou com alegria.","emocao":"esperança"},{"numero":2,"texto":"Téo sorriu para Mel.","emocao":"alegria"}],
            "licao_final":"Esperar também é confiar.","versiculo_referencia":"Eclesiastes 3:1",
            "versiculo_texto_original":"TEXTO LIVRE QUE NAO PODE ENTRAR",
            "bible_records":{"pt-BR":rec},"personagens":{"Mel":{},"Téo":{}},
        }

    def project_with_voice(self):
        p=create_audiobook_project("Mel",source_state=self.story(),locale="pt-BR")
        vp=create_voice_profile("Narradora","pt-BR",provider_voice_id="voice-demo",style_id="warm_storyteller")
        p=upsert_project_voice(p,vp); p=assign_voice(p,"narrator",vp["id"])
        p["script_scenes"]=[approve_script_scene(s) for s in p["script_scenes"]]
        return p

    def test_bible_guard_ignora_texto_legado_nao_aprovado(self):
        src=build_audio_source(self.story(False),"pt-BR")
        blob=" ".join(x["texto"] for x in src["scenes"])
        self.assertIn("Eclesiastes 3:1",blob)
        self.assertNotIn("TEXTO LIVRE",blob)
        self.assertFalse(src["bible_guard"]["approved_text_used"])

    def test_bible_guard_usa_exatamente_texto_aprovado(self):
        src=build_audio_source(self.story(True),"pt-BR")
        scripture=[x for x in src["scenes"] if x["scene_type"]=="scripture"][0]
        self.assertIn("Há um tempo certo para cada propósito.",scripture["texto"])
        self.assertEqual(scripture["texto"],"Há um tempo certo para cada propósito.")
        self.assertEqual(scripture["versao"],"Versão Teste Autorizada")
        self.assertTrue(scripture["immutable_text"])

    def test_voice_profile_limites(self):
        p=create_voice_profile("Voz","en-US",pace_wpm=145,speed=1.1)
        self.assertEqual(p["locale"],"en-US")
        with self.assertRaises(ValueError): create_voice_profile("Voz","pt-BR",pace_wpm=300)

    def test_voice_director_descarta_reescrita(self):
        p=create_audiobook_project("Mel",source_state=self.story())
        s=p["script_scenes"][0]
        r=normalize_voice_director_result(s,{"emotion":"alegria","segments":[{"speaker":"narrator","text":"Texto completamente diferente."}]})
        self.assertIn("descartada",r.get("voice_director_alert",""))
        self.assertEqual(r["segments"][0]["text"],s["source_text"])

    def test_pronuncia_altera_apenas_input_tts(self):
        p=self.project_with_voice(); original=p["script_scenes"][1]["source_text"]
        p=add_pronunciation(p,"Téo","Tê-o",locale="pt-BR")
        spoken,applied=apply_pronunciations(original,p)
        self.assertIn("Tê-o",spoken); self.assertEqual(original,p["script_scenes"][1]["source_text"]); self.assertEqual(applied[0]["occurrences"],1)

    def test_units_respeitam_casting_e_aprovacao(self):
        p=self.project_with_voice(); units=build_generation_units(p)
        self.assertGreaterEqual(len(units),4)  # 2 cenas + lição + referência
        self.assertTrue(all(u["speaker"]=="narrator" for u in units))
        self.assertTrue(all(u["voice_profile_id"] for u in units))

    def test_versoes_audio_preservadas_e_aprovacao_escolhe_uma(self):
        p=self.project_with_voice(); u=build_generation_units(p)[0]
        p,a=add_audio_version(p,u,"/tmp/a.mp3"); p,b=add_audio_version(p,u,"/tmp/b.mp3")
        self.assertEqual([x["version_label"] for x in p["audio_versions"][u["id"]]],["A","B"])
        p=approve_audio_version(p,u["id"],b["id"],favorite=True)
        self.assertEqual(p["approved_audio"][u["id"]],b["id"]); self.assertTrue(p["audio_versions"][u["id"]][1]["favorite"])

    def test_audio_qa_objetivo_em_wav(self):
        with tempfile.TemporaryDirectory() as td:
            f=Path(td)/"a.wav"; make_wav(f,0.5)
            qa=qa_audio_clip(str(f),expected_text="Olá Mel",expected_pace_wpm=140)
            self.assertTrue(qa["ok"]); self.assertGreater(qa["technical"]["duration_seconds"],0)
            self.assertTrue(qa["requires_listening_review"])

    def test_readiness_bloqueia_sem_audio_aprovado(self):
        p=self.project_with_voice(); r=audio_readiness(p)
        self.assertFalse(r["ready"]); self.assertTrue(any(a["code"]=="audio_not_approved" for a in r["alerts"]))

    def test_mix_final_e_aprovacao_humana(self):
        if not shutil.which("ffmpeg"):
            self.skipTest("ffmpeg indisponível")
        with tempfile.TemporaryDirectory() as td:
            p=self.project_with_voice()
            for i,u in enumerate(build_generation_units(p)):
                f=Path(td)/f"{i}.wav"; make_wav(f,0.25)
                qa=qa_audio_clip(str(f),expected_text=u["text"],expected_pace_wpm=u["pace_wpm"])
                p,v=add_audio_version(p,u,str(f),metadata={"qa":qa}); p=approve_audio_version(p,u["id"],v["id"])
            out=Path(td)/"master.mp3"; result=merge_approved_audio(p,str(out),normalize=False)
            self.assertTrue(out.exists()); p["final_mix"]=result["path"]; p["final_mix_qa"]=result["qa"]
            self.assertFalse(distribution_readiness(p)["ready"])
            p=approve_final_mix(p); self.assertTrue(distribution_readiness(p)["ready"])
            z=Path(td)/"pkg.zip"; exp=export_audiobook_package(p,str(z)); self.assertTrue(z.exists()); self.assertTrue(exp["readiness"]["ready"])

    def test_conversor_nao_deixa_tts_ler_marcadores(self):
        x=converter_marcacoes_para_texto_natural("[voz suave] Olá [pausa curta] Mel [ênfase: fé] [pausa: 800ms]")
        self.assertNotIn("voz suave",x); self.assertNotIn("pausa",x); self.assertIn("fé",x)


if __name__=='__main__': unittest.main()
