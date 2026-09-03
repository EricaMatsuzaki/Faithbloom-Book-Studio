import json
import os
import tempfile
import unittest
import zipfile
from pathlib import Path

import platform_registry as registry
from platform_format_engine import (
    BookMasterSpec,
    compatibility,
    calculate_print_geometry,
    build_derivative_plan,
    preflight_target,
)
from epub_exporter import export_epub, inspect_epub
from pacote_publicacao import gerar_manifesto_multiplataforma


class Refinamento07Tests(unittest.TestCase):
    def master(self, **kwargs):
        base=BookMasterSpec(title="Quando Mel Aprendeu a Esperar",trim_width_in=8.5,trim_height_in=8.5,page_count=32,binding="paperback").to_dict()
        base.update(kwargs)
        return base

    def test_registry_tem_plataformas_principais(self):
        reg=registry.get_registry(include_custom=False)
        for pid in ("amazon_kdp","ingramspark","lulu","kobo_writing_life","apple_books","google_play_books","draft2digital","barnes_noble_press","etsy","hotmart","kiwify"):
            self.assertIn(pid,reg)
        self.assertGreaterEqual(len(reg),15)

    def test_custom_platform_persiste_sem_alterar_builtin(self):
        with tempfile.TemporaryDirectory() as td:
            old_path=registry.CUSTOM_PATH; old_dir=registry.DATA_DIR
            registry.DATA_DIR=Path(td); registry.CUSTOM_PATH=Path(td)/"custom.json"
            try:
                rec=registry.register_custom_platform(name="Minha Plataforma",products=["ebook"],accepted_formats={"ebook":["epub"]})
                self.assertFalse(rec["builtin"])
                self.assertIn(rec["id"],registry.get_registry())
                with self.assertRaises(ValueError):
                    registry.remove_custom_platform("amazon_kdp")
                self.assertTrue(registry.remove_custom_platform(rec["id"]))
            finally:
                registry.CUSTOM_PATH=old_path; registry.DATA_DIR=old_dir

    def test_override_oficial_tem_historico_e_preserva_baseline(self):
        with tempfile.TemporaryDirectory() as td:
            old=(registry.DATA_DIR,registry.CUSTOM_PATH,registry.OVERRIDE_PATH,registry.HISTORY_PATH)
            registry.DATA_DIR=Path(td); registry.CUSTOM_PATH=Path(td)/"custom.json"; registry.OVERRIDE_PATH=Path(td)/"overrides.json"; registry.HISTORY_PATH=Path(td)/"history.json"
            try:
                before=registry.BUILTIN_PLATFORMS["amazon_kdp"]["spec_version"]
                rec=registry.update_platform_spec("amazon_kdp",{"print":{"target_ppi":310}},spec_version="test-2",last_verified="2026-09-03",note="qa")
                self.assertEqual(rec["print"]["target_ppi"],310)
                self.assertEqual(rec["spec_version"],"test-2")
                self.assertEqual(registry.BUILTIN_PLATFORMS["amazon_kdp"]["spec_version"],before)
                self.assertEqual(len(registry.platform_history("amazon_kdp")),1)
            finally:
                registry.DATA_DIR,registry.CUSTOM_PATH,registry.OVERRIDE_PATH,registry.HISTORY_PATH=old

    def test_kdp_square_preset_compativel(self):
        r=compatibility(self.master(),"amazon_kdp","paperback")
        self.assertTrue(r["supported"])
        self.assertEqual(r["status"],"compatible")
        self.assertAlmostEqual(r["nearest_trim"]["width_in"],8.5)
        self.assertAlmostEqual(r["nearest_trim"]["height_in"],8.5)

    def test_kdp_select_bloqueia_ebook_fora_amazon(self):
        r=compatibility(self.master(kdp_select_active=True,binding="ebook"),"kobo_writing_life","ebook")
        self.assertEqual(r["status"],"blocked")
        self.assertTrue(any(a["code"]=="digital_exclusivity" for a in r["alerts"]))

    def test_ingram_nao_inventa_lombada(self):
        g=calculate_print_geometry(self.master(),"ingramspark","paperback")
        self.assertIsNone(g["spine_width_in"])
        self.assertEqual(g["calculation"],"official_template_required")

    def test_lulu_formula_tem_geometria(self):
        g=calculate_print_geometry(self.master(),"lulu","paperback")
        self.assertGreater(g["spine_width_in"],0)
        self.assertGreater(g["cover_width_in"],17)
        self.assertEqual(g["target_ppi"],300)

    def test_derivative_plan_marca_layout_quando_aspecto_muda(self):
        plan=build_derivative_plan(self.master(),[{"platform_id":"barnes_noble_press","product":"paperback"}])
        self.assertEqual(plan["policy"],"never_resize_silently")
        self.assertTrue(plan["editions"][0]["needs_layout_derivative"])

    def test_epub_gera_container_valido_e_nao_injeta_texto_biblico_separado(self):
        with tempfile.TemporaryDirectory() as td:
            state={
                "titulo":"Mel Teste","autora":"Erica Matsuzaki","idioma_original":"pt-BR",
                "cenas_texto":[{"numero":1,"texto":"Mel esperou com alegria."}],
                "licao_final":"Esperar é confiar.","versiculo_referencia":"Eclesiastes 3:1",
                "versiculo_texto_original":"TEXTO BIBLICO NAO AUTORIZADO PARA TRADUCAO",
            }
            out=os.path.join(td,"book.epub")
            result=export_epub(state,out,mode="reflowable")
            self.assertTrue(os.path.exists(out))
            self.assertTrue(inspect_epub(out)["ok"])
            with zipfile.ZipFile(out) as z:
                blob="\n".join(z.read(n).decode("utf-8",errors="ignore") for n in z.namelist() if n.endswith((".xhtml",".opf")))
            self.assertIn("Eclesiastes 3:1",blob)
            self.assertNotIn("TEXTO BIBLICO NAO AUTORIZADO",blob)
            self.assertFalse(result["epubcheck_passed"])

    def test_apple_preflight_exige_epubcheck(self):
        with tempfile.TemporaryDirectory() as td:
            epub=os.path.join(td,"x.epub"); Path(epub).write_bytes(b"dummy")
            r=preflight_target(self.master(binding="ebook"),"apple_books","ebook",{"epub":epub,"epubcheck_passed":False})
            self.assertFalse(r["ready"])
            self.assertTrue(any(a["code"]=="epubcheck_required" for a in r["alerts"]))

    def test_manifesto_multiplataforma_nao_finge_prontidao(self):
        state={"titulo":"Teste","idioma_original":"pt-BR","paginas_fisicas":32,"trim_largura_in":8.5,"trim_altura_in":8.5}
        targets=[{"platform_id":"amazon_kdp","product":"paperback"},{"platform_id":"apple_books","product":"ebook"}]
        m=gerar_manifesto_multiplataforma(state,targets)
        self.assertEqual(m["blocked_count"],2)
        self.assertEqual(m["ready_count"],0)


if __name__=="__main__":
    unittest.main()
