"""Biblioteca Editorial — visão de Projeto-Mestre + edições por idioma."""
from __future__ import annotations
import time, uuid
from armazenamento import _json,_save_json
MASTER_INDEX='biblioteca_editorial/index.json'

def _idx():
    x=_json(MASTER_INDEX,[]); return x if isinstance(x,list) else []

def criar_projeto_mestre(titulo:str,colecao:str='',idioma_master:str='pt-BR')->dict:
    pid=uuid.uuid4().hex
    p={"id":pid,"titulo":titulo,"colecao":colecao,"idioma_master":idioma_master,"personagens_oficiais":[],"edicoes":{},"assets_master":{},"historico":[],"criado_em":int(time.time())}
    _save_json(f'biblioteca_editorial/{pid}.json',p); idx=_idx(); idx.append({k:p[k] for k in ('id','titulo','colecao','idioma_master')}); _save_json(MASTER_INDEX,idx); return p

def listar_projetos_mestre(): return list(reversed(_idx()))
def carregar_projeto_mestre(pid): return _json(f'biblioteca_editorial/{pid}.json',{}) or {}
def salvar_projeto_mestre(p):
    p=dict(p); p['atualizado_em']=int(time.time()); _save_json(f"biblioteca_editorial/{p['id']}.json",p); return p

def adicionar_edicao(pid:str,locale:str,dados:dict)->dict:
    p=carregar_projeto_mestre(pid); p.setdefault('edicoes',{})[locale]=dados; return salvar_projeto_mestre(p)
