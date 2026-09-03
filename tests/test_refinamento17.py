import tempfile
from pathlib import Path
from unittest.mock import patch

import author_profiles as ap
import integration_ux as ux
import armazenamento
import stable_hardening as sh
import storage_backend
import pacote_publicacao
import quality_guardian
from storage_backend import LocalStorageBackend


def isolated(tmp_path, monkeypatch):
    backend=LocalStorageBackend(str(tmp_path/'data'))
    for mod in (storage_backend, ap, armazenamento, sh):
        monkeypatch.setattr(mod,'BACKEND',backend)
    return backend


def test_profiles_are_reusable_and_not_users(tmp_path, monkeypatch):
    isolated(tmp_path,monkeypatch)
    a=ap.create_author_profile('Larissa Ayumi',locales=['ja-JP','en-US'])
    b=ap.create_author_profile('Kleber')
    assert {ap.profile_display_name(x) for x in ap.list_author_profiles()}=={'Larissa Ayumi','Kleber'}
    assert 'role' not in a and 'role' not in b  # perfil editorial não é papel de autenticação


def test_project_authorship_order_and_coauthor(tmp_path, monkeypatch):
    isolated(tmp_path,monkeypatch)
    a=ap.create_author_profile('Erica Matsuzaki')
    b=ap.create_author_profile('Larissa Ayumi')
    s=ap.set_project_authors({'titulo':'Livro'},[a['id'],b['id']])
    assert s['authorship']['authors'][0]['role']=='author'
    assert s['authorship']['authors'][1]['role']=='coauthor'
    assert ap.author_display_from_state(s)=='Erica Matsuzaki & Larissa Ayumi'
    assert s['autora']=='Erica Matsuzaki & Larissa Ayumi'


def test_profile_change_does_not_rewrite_snapshot(tmp_path, monkeypatch):
    isolated(tmp_path,monkeypatch)
    a=ap.create_author_profile('Nome A')
    s=ap.set_project_authors({'titulo':'Livro'},[a['id']])
    ap.update_author_profile(a['id'],display_name='Nome B')
    assert ap.author_display_from_state(s)=='Nome A'
    s2=ap.set_project_authors(s,[a['id']])
    assert ap.author_display_from_state(s2)=='Nome B'


def test_contributors_and_cover_override(tmp_path, monkeypatch):
    isolated(tmp_path,monkeypatch)
    a=ap.create_author_profile('Autora')
    i=ap.create_author_profile('Ilustradora')
    s=ap.set_project_authors({},[a['id']])
    s=ap.add_project_contributor(s,i['id'],'illustrator')
    assert ap.authorship_summary(s)['contributors'][0]['role']=='illustrator'
    s=ap.set_cover_credit_override(s,'A. Example')
    assert ap.cover_credit_from_state(s)=='A. Example'


def test_legacy_author_migrates_to_schema4():
    r=sh.migrate_project_state({'titulo':'Antigo','autora':'Autora Legada'})
    assert r['to_version']==4
    assert r['state']['authorship']['authors'][0]['credit_as']=='Autora Legada'
    assert r['state']['authorship']['authors'][0]['legacy_snapshot'] is True


def test_metadata_uses_structured_authorship(tmp_path, monkeypatch):
    isolated(tmp_path,monkeypatch)
    a=ap.create_author_profile('Pessoa A')
    b=ap.create_author_profile('Pessoa B')
    s=ap.set_project_authors({'titulo':'X'},[a['id'],b['id']])
    md=pacote_publicacao.normalizar_metadata(s)
    assert md['autora']=='Pessoa A & Pessoa B'
    assert [x['name'] for x in md['autores']]==['Pessoa A','Pessoa B']


def test_authorship_changes_project_fingerprint(tmp_path, monkeypatch):
    isolated(tmp_path,monkeypatch)
    a=ap.create_author_profile('Pessoa A')
    b=ap.create_author_profile('Pessoa B')
    base={'titulo':'X','cenas_texto':[{'numero':1,'texto':'Oi'}]}
    s1=ap.set_project_authors(base,[a['id']]); s2=ap.set_project_authors(base,[b['id']])
    assert quality_guardian.project_fingerprint(s1)!=quality_guardian.project_fingerprint(s2)


def test_handoff_contracts():
    h=ux.make_handoff('asset_library','restoration',project={'titulo':'Livro','colecao':'C'},asset={'id':'a1','nome':'Mel','caminho_arquivo':'x.png','media_kind':'image'})
    v=ux.validate_handoff(h)
    assert v['valid'] is True
    assert v['target_page'].endswith('Restoration_Studio.py')
    bad=ux.make_handoff('asset_library','translation',asset={'id':'a1'})
    assert any('asset' in x for x in bad['warnings'])
    assert ux.validate_handoff(bad)['valid'] is False


def test_explicit_update_existing_book(tmp_path, monkeypatch):
    backend=isolated(tmp_path,monkeypatch)
    backend.put_json('livros/test/livro.json',{'titulo':'Livro','colecao':'Test','autora':'A'})
    state=armazenamento.carregar_livro('Test','livros/test/livro.json')
    state['subtitulo']='Novo'
    uri=armazenamento.atualizar_livro_salvo('livros/test/livro.json',state)
    assert uri=='fb://livros/test/livro.json'
    assert backend.get_json('livros/test/livro.json',{})['subtitulo']=='Novo'

def test_fingerprint_ignores_authorship_operational_timestamps():
    base={
        'titulo':'X','cenas_texto':[{'numero':1,'texto':'Oi'}],
        'authorship':{'authors':[{'profile_id':'1','role':'author','order':1,'credit_as':'Pessoa'}],'contributors':[],'updated_at':'2026-01-01T00:00:00Z'}
    }
    other={**base,'authorship':{**base['authorship'],'updated_at':'2027-02-02T00:00:00Z'}}
    assert quality_guardian.project_fingerprint(base)==quality_guardian.project_fingerprint(other)


def test_explicit_update_existing_coloring_book(tmp_path, monkeypatch):
    backend=isolated(tmp_path,monkeypatch)
    backend.put_json('livros_colorir/livro.json',{'titulo':'Colorir','autora':'Pessoa'})
    state=armazenamento.carregar_livro_colorir('livros_colorir/livro.json')
    state['tema_geral']='Animais'
    uri=armazenamento.atualizar_livro_colorir_salvo('livros_colorir/livro.json',state)
    assert uri=='fb://livros_colorir/livro.json'
    assert backend.get_json('livros_colorir/livro.json',{})['tema_geral']=='Animais'

def test_handoff_preserves_active_project_storage_path():
    ctx={'title':'Livro','collection':'C','storage_path':'livros/c/livro.json','language':'pt-BR'}
    h=ux.make_handoff('project_hub','authors',project=ctx)
    assert h['project']['title']=='Livro'
    assert h['project']['storage_path']=='livros/c/livro.json'
