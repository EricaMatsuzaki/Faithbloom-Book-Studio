from pathlib import Path
import json

from PIL import Image, ImageDraw

import book_doctor
from book_doctor import criar_projeto, preservar_original
from restoration_studio import (
    criar_plano_restauracao, registrar_decisao, carregar_plano_restauracao,
    melhorar_imagem_tecnicamente, limpar_line_art, auditar_line_art,
    montar_prompt_restauracao, resumo_restauracao,
)


def _img_color(path: Path):
    im=Image.new('RGB',(120,120),'white')
    d=ImageDraw.Draw(im)
    d.ellipse((25,25,95,95),fill=(220,170,150),outline=(30,30,30),width=2)
    im.save(path)


def _img_line(path: Path):
    im=Image.new('L',(120,120),255)
    d=ImageDraw.Draw(im)
    d.rectangle((20,20,100,100),outline=80,width=2)
    d.ellipse((40,40,80,80),outline=0,width=2)
    im.save(path)


def test_projeto_ref4_guarda_tipo_status_e_manifest(tmp_path, monkeypatch):
    monkeypatch.setattr(book_doctor,'ROOT',tmp_path/'projects')
    p=criar_projeto('Teste','pt-BR','coloring','nao_publicado','Cute Friends','Sem capa')
    assert p['tipo_projeto']=='coloring'
    assert p['status_publicacao']=='nao_publicado'
    src=tmp_path/'x.png'; _img_color(src)
    dst=preservar_original(p,str(src),'miolo')
    manifest=Path(p['pasta'])/'originais'/'manifest.json'
    dados=json.loads(manifest.read_text())
    assert dados[-1]['arquivo']==dst
    assert len(dados[-1]['sha256'])==64


def test_plano_e_decisoes_nao_apagam_historico(tmp_path, monkeypatch):
    monkeypatch.setattr(book_doctor,'ROOT',tmp_path/'projects')
    p=criar_projeto('Teste')
    plan=criar_plano_restauracao(p, {'miolo':{'imagens':[]}}, 'story','em_desenvolvimento','Colecao')
    assert plan['politica']=='original_preservado'
    registrar_decisao(p,'p001-i01','manter_original')
    registrar_decisao(p,'p001-i01','criar_variacao',instrucao_autora='mais alegre')
    atual=carregar_plano_restauracao(p)
    assert len(atual['decisoes'])==2
    assert atual['decisoes'][0]['acao']=='manter_original'


def test_melhoria_tecnica_cria_derivado_sem_tocar_original(tmp_path, monkeypatch):
    monkeypatch.setattr(book_doctor,'ROOT',tmp_path/'projects')
    p=criar_projeto('Teste')
    src=tmp_path/'color.png'; _img_color(src)
    antes=src.read_bytes()
    criar_plano_restauracao(p)
    out=melhorar_imagem_tecnicamente(p,str(src),2,1.1,1.0,False,2,2)
    assert Path(out['caminho']).exists()
    assert Image.open(out['caminho']).size==(240,240)
    assert src.read_bytes()==antes
    assert out['ppi_depois']['ppi_efetivo']==120.0
    assert resumo_restauracao(p)['versoes_geradas']==1


def test_line_art_qa_e_limpeza(tmp_path, monkeypatch):
    monkeypatch.setattr(book_doctor,'ROOT',tmp_path/'projects')
    p=criar_projeto('Color','pt-BR','coloring')
    src=tmp_path/'line.png'; _img_line(src)
    criar_plano_restauracao(p)
    qa=auditar_line_art(str(src))
    assert 'tons_cinza_pct' in qa
    out=limpar_line_art(p,str(src),205,True,'manter',2)
    im=Image.open(out['caminho']).convert('L')
    hist=im.histogram()
    valores={i for i,n in enumerate(hist) if n}
    assert valores.issubset({0,255})
    assert src.exists()


def test_prompt_restauracao_explicita_preservacao():
    p=montar_prompt_restauracao('reilustrar',instrucao_autora='manter o jardim')
    assert 'não substituir' in p.lower()
    assert 'nova variação' in p.lower()
    assert 'manter o jardim' in p
