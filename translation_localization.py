"""FaithBloom Refinamento 06 — Translation & Localization Studio.

Princípios:
- traduzir/localizar a HISTÓRIA por locale/mercado, não apenas por idioma;
- preservar nomes, Character DNA, emoção, moral e intenção narrativa;
- localizar onomatopeias de modo infantil, equilibrado e aprovável;
- NUNCA pedir ao modelo para traduzir livremente um versículo bíblico;
- manter versões A/B/C e revisão linguística separada.

O módulo é deliberadamente conservador com Bíblia: texto de versículo só entra
no pacote final quando a autora fornece/seleciona um texto previamente aprovado
com metadados de versão/fonte/licença. Sem isso, usa-se apenas a referência.
"""
from __future__ import annotations

import copy
import json
import re
import time
import uuid
from dataclasses import dataclass, asdict
from typing import Any

from armazenamento import _json, _save_json, _slug

TRANSLATION_INDEX = "translation_studio/index.json"

LOCALIZACOES: dict[str, dict[str, Any]] = {
    "en-US": {"idioma":"English","mercado":"United States","ortografia":"American English","idade_padrao":"3–8","guia":"Use spelling and everyday child vocabulary natural in the US (e.g. color, favorite, mom when context calls for it)."},
    "en-CA": {"idioma":"English","mercado":"Canada","ortografia":"Canadian English","idade_padrao":"3–8","guia":"Use Canadian spelling and natural Canadian child vocabulary; do not simply copy en-US or en-GB conventions."},
    "en-GB": {"idioma":"English","mercado":"United Kingdom","ortografia":"British English","idade_padrao":"3–8","guia":"Use British spelling and child vocabulary (e.g. colour, favourite, mum when context calls for it) without forced slang."},
    "en-AU": {"idioma":"English","mercado":"Australia","ortografia":"Australian English","idade_padrao":"3–8","guia":"Use Australian spelling and natural child vocabulary, avoiding stereotyped or excessive Australian slang."},
    "en-INT": {"idioma":"English","mercado":"International","ortografia":"neutral international English","idade_padrao":"3–8","guia":"Prefer globally understandable English and avoid strongly regional vocabulary when a neutral option exists."},
    "pt-BR": {"idioma":"Português","mercado":"Brasil","ortografia":"português brasileiro","idade_padrao":"3–8"},
    "pt-PT": {"idioma":"Português","mercado":"Portugal","ortografia":"português europeu","idade_padrao":"3–8"},
    "es-ES": {"idioma":"Español","mercado":"España","ortografia":"español de España","idade_padrao":"3–8"},
    "es-MX": {"idioma":"Español","mercado":"México","ortografia":"español de México","idade_padrao":"3–8"},
    "es-LATAM": {"idioma":"Español","mercado":"Latinoamérica","ortografia":"español latinoamericano neutral","idade_padrao":"3–8"},
    "fr-FR": {"idioma":"Français","mercado":"France","ortografia":"français de France","idade_padrao":"3–8"},
    "fr-CA": {"idioma":"Français","mercado":"Canada","ortografia":"français canadien","idade_padrao":"3–8"},
    "it-IT": {"idioma":"Italiano","mercado":"Italia","ortografia":"italiano","idade_padrao":"3–8"},
    "de-DE": {"idioma":"Deutsch","mercado":"Deutschland","ortografia":"Deutsch (Deutschland)","idade_padrao":"3–8"},
    "ja-JP": {"idioma":"日本語","mercado":"日本","ortografia":"自然な子ども向け日本語","idade_padrao":"3–8","guia":"Use child-appropriate kanji/kana balance, natural Japanese sound-symbolic language, and preserve names without inventing meanings."},
}

MODOS = {
    "fiel": "Preserve ao máximo estrutura, conteúdo e escolhas do Master; ajuste só o necessário para soar correto no locale.",
    "natural_infantil": "Priorize naturalidade para crianças do mercado-alvo, frases claras e leitura em voz alta, sem mudar fatos ou mensagem.",
    "localizacao_cultural": "Adapte apenas referências culturais que realmente prejudiquem compreensão; não caricature o país e não invente costumes.",
}

INTENSIDADE_SONS = {
    "baixa": "Use onomatopeias apenas em momentos realmente essenciais.",
    "equilibrada": "Use onomatopeias onde aumentarem humor, ritmo, ação ou leitura em voz alta, sem poluir a página.",
    "expressiva": "Aceite mais efeitos sonoros em cenas de ação/comédia, mas preserve cenas delicadas, oração e reflexão.",
}

# Biblioteca inicial de sugestões editoriais. Não é uma tabela de tradução 1:1;
# cada opção deve ser avaliada no contexto e pode ser editada pela autora.
SOUND_LIBRARY: dict[str, dict[str, list[str]]] = {
    "queda_engracada": {
        "pt-BR": ["PUF!", "PLOFT!"], "en-US": ["PLOP!", "THUMP!"], "en-GB": ["PLOP!", "THUD!"],
        "en-CA": ["PLOP!", "THUMP!"], "en-AU": ["PLOP!", "THUD!"], "en-INT": ["PLOP!"],
        "es-ES": ["¡PLOF!"], "es-MX": ["¡PUM!", "¡PLOF!"], "es-LATAM": ["¡PLOF!"],
        "fr-FR": ["POUF !", "PLOUF !"], "fr-CA": ["POUF !"], "it-IT": ["PUF!", "PATAPUM!"],
        "de-DE": ["PLUMPS!"], "ja-JP": ["どてん！", "ころん！"],
    },
    "batida_porta": {
        "pt-BR": ["TOC TOC!"], "en-US": ["KNOCK KNOCK!"], "en-GB": ["KNOCK KNOCK!"], "en-CA": ["KNOCK KNOCK!"],
        "en-AU": ["KNOCK KNOCK!"], "en-INT": ["KNOCK KNOCK!"], "es-ES": ["¡TOC, TOC!"], "es-MX": ["¡TOC, TOC!"],
        "es-LATAM": ["¡TOC, TOC!"], "fr-FR": ["TOC TOC !"], "fr-CA": ["TOC TOC !"], "it-IT": ["TOC TOC!"],
        "de-DE": ["KLOPF KLOPF!"], "ja-JP": ["コンコン！"],
    },
    "chuva": {
        "pt-BR": ["PLIC PLIC!"], "en-US": ["PITTER-PATTER!"], "en-GB": ["PITTER-PATTER!"], "en-CA": ["PITTER-PATTER!"],
        "en-AU": ["PITTER-PATTER!"], "en-INT": ["PITTER-PATTER!"], "es-ES": ["¡PLOP, PLOP!"], "es-MX": ["¡PLIP, PLIP!"],
        "es-LATAM": ["¡PLIP, PLIP!"], "fr-FR": ["PLIC PLOC !"], "fr-CA": ["PLIC PLOC !"], "it-IT": ["PLIN PLIN!"],
        "de-DE": ["PLITSCH PLATSCH!"], "ja-JP": ["ぽつぽつ", "ざあざあ"],
    },
    "risada": {
        "pt-BR": ["HA HA HA!", "HI HI HI!"], "en-US": ["HA HA!", "GIGGLE!"], "en-GB": ["HA HA!", "GIGGLE!"],
        "en-CA": ["HA HA!", "GIGGLE!"], "en-AU": ["HA HA!", "GIGGLE!"], "en-INT": ["HA HA!"],
        "es-ES": ["¡JA, JA!"], "es-MX": ["¡JA, JA!"], "es-LATAM": ["¡JA, JA!"], "fr-FR": ["HA HA !"],
        "fr-CA": ["HA HA !"], "it-IT": ["AH AH!"], "de-DE": ["HA HA!"], "ja-JP": ["あはは！", "くすくす"],
    },
    "espirro": {
        "pt-BR": ["ATCHIM!"], "en-US": ["ACHOO!"], "en-GB": ["ATISHOO!", "ACHOO!"], "en-CA": ["ACHOO!"],
        "en-AU": ["ACHOO!"], "en-INT": ["ACHOO!"], "es-ES": ["¡ACHÍS!"], "es-MX": ["¡ACHÚ!"], "es-LATAM": ["¡ACHÍS!"],
        "fr-FR": ["ATCHOUM !"], "fr-CA": ["ATCHOUM !"], "it-IT": ["ETCIÙ!"], "de-DE": ["HATSCHI!"], "ja-JP": ["はくしょん！"],
    },
}

BIBLE_STATUS = {"reference_only", "approved_text"}

@dataclass
class BibleVerseRecord:
    referencia: str
    locale: str
    status: str = "reference_only"
    versao: str = ""
    texto_aprovado: str = ""
    fonte: str = ""
    licenca_nota: str = ""
    aprovado_pela_autora: bool = False

    def validate(self) -> list[str]:
        erros=[]
        if not self.referencia.strip(): erros.append("Referência bíblica ausente.")
        if self.status not in BIBLE_STATUS: erros.append("Status bíblico inválido.")
        if self.status == "approved_text":
            if not self.texto_aprovado.strip(): erros.append("Texto aprovado do versículo ausente.")
            if not self.versao.strip(): erros.append("Informe a versão bíblica utilizada.")
            if not self.aprovado_pela_autora: erros.append("O texto do versículo ainda não foi aprovado pela autora.")
        return erros


def normalize_locale(locale: str) -> str:
    raw=(locale or "").strip()
    aliases={"en":"en-US","pt":"pt-BR","es":"es-LATAM","fr":"fr-FR","de":"de-DE","it":"it-IT","ja":"ja-JP"}
    return aliases.get(raw, raw)


def locale_info(locale: str) -> dict:
    loc=normalize_locale(locale)
    return {"locale":loc, **LOCALIZACOES.get(loc,{"idioma":loc,"mercado":"Custom","ortografia":loc,"idade_padrao":"3–8"})}


def sugerir_onomatopeias(evento: str, locale: str) -> list[str]:
    loc=normalize_locale(locale)
    opcoes=SOUND_LIBRARY.get(evento,{})
    return list(opcoes.get(loc) or opcoes.get(loc.split("-")[0]) or [])


def criar_registro_biblico(referencia: str, locale: str, *, versao: str="", texto_aprovado: str="", fonte: str="", licenca_nota: str="", aprovado: bool=False) -> dict:
    status="approved_text" if texto_aprovado.strip() else "reference_only"
    rec=BibleVerseRecord(referencia, normalize_locale(locale), status, versao, texto_aprovado, fonte, licenca_nota, bool(aprovado))
    return asdict(rec)


def validar_registro_biblico(registro: dict | None) -> list[str]:
    if not registro: return ["Registro bíblico ausente."]
    campos={k:registro.get(k, getattr(BibleVerseRecord('', ''), k)) for k in BibleVerseRecord.__dataclass_fields__}
    return BibleVerseRecord(**campos).validate()


def texto_biblico_para_exportacao(registro: dict | None) -> dict:
    """Nunca gera/traduz Bíblia. Retorna texto somente se previamente aprovado."""
    if not registro:
        return {"referencia":"", "texto":"", "pode_exportar_texto":False, "motivo":"Sem registro bíblico."}
    erros=validar_registro_biblico(registro)
    if registro.get("status") == "approved_text" and not erros:
        return {"referencia":registro.get("referencia",""),"texto":registro.get("texto_aprovado",""),"versao":registro.get("versao",""),"pode_exportar_texto":True,"motivo":"Texto fornecido/selecionado e aprovado pela autora."}
    return {"referencia":registro.get("referencia",""),"texto":"","versao":registro.get("versao",""),"pode_exportar_texto":False,"motivo":"Somente a referência será usada; FaithBloom não traduz versículos livremente."}


def detectar_nomes_protegidos(state: dict) -> list[str]:
    nomes=set((state.get("personagens") or {}).keys())
    for item in state.get("lista_dedicatoria",[]) or []:
        if isinstance(item,dict) and item.get("pessoa"): nomes.add(str(item["pessoa"]))
    return sorted(x for x in nomes if x)


def _proteger_texto_biblico(texto: str, state: dict) -> str:
    """Remove do payload qualquer texto bíblico explicitamente cadastrado.

    Se um projeto legado guardou o texto do versículo em `versiculo_texto`,
    `versiculo_texto_original` ou `bible_verse_text`, ele é substituído por um
    placeholder antes de chamar o tradutor. Projetos novos devem usar
    `bible_records` e manter esse conteúdo fora das cenas narrativas.
    """
    out=str(texto or "")
    for key in ("versiculo_texto","versiculo_texto_original","bible_verse_text"):
        trecho=str(state.get(key,"") or "").strip()
        if trecho and trecho in out:
            out=out.replace(trecho,f"[BIBLE_VERSE_PROTECTED:{state.get('versiculo_referencia','')}]" )
    return out


def _conteudo_master_sem_versiculo(state: dict) -> dict:
    """Monta conteúdo traduzível mantendo Bíblia fora da geração livre."""
    cenas=copy.deepcopy(state.get("cenas_texto",[]))
    for cena in cenas:
        if not isinstance(cena,dict):
            continue
        # Campos explicitamente bíblicos nunca seguem para o tradutor.
        for key in list(cena):
            if key.lower() in {"versiculo","versiculo_texto","bible_verse","scripture_text"}:
                cena.pop(key,None)
        if "texto" in cena:
            cena["texto"]=_proteger_texto_biblico(cena.get("texto",""),state)
    return {
        "titulo":_proteger_texto_biblico(state.get("titulo",""),state),
        "subtitulo":_proteger_texto_biblico(state.get("subtitulo",""),state),
        "sinopse_poetica":_proteger_texto_biblico(state.get("sinopse_poetica",""),state),
        "cenas_texto":cenas,
        "dedicatoria":_proteger_texto_biblico(state.get("dedicatoria_texto",""),state),
        "licao_final":_proteger_texto_biblico(state.get("licao_final",""),state),
        "sinopse_vendas_curta":_proteger_texto_biblico(state.get("sinopse_vendas_curta",""),state),
        "sinopse_contracapa":_proteger_texto_biblico(state.get("sinopse_contracapa",""),state),
    }


def construir_prompt_localizacao(state: dict, locale: str, *, modo: str="natural_infantil", faixa_etaria: str="3–8", intensidade_sons: str="equilibrada", glossario: dict | None=None, instrucoes: str="") -> tuple[str,dict]:
    loc=locale_info(locale)
    modo=modo if modo in MODOS else "natural_infantil"
    intensidade_sons=intensidade_sons if intensidade_sons in INTENSIDADE_SONS else "equilibrada"
    nomes=detectar_nomes_protegidos(state)
    glossario=glossario or {}
    bible_ref=state.get("versiculo_referencia","")
    sistema=f"""Você é o Translation & Localization Studio do FaithBloom, especializado em literatura infantil.
Destino: {loc['locale']} — {loc['idioma']} / {loc['mercado']} ({loc['ortografia']}).
Guia regional: {loc.get('guia','Use as convenções naturais deste locale sem regionalismos forçados.')}
Faixa etária: {faixa_etaria}. Modo: {modo} — {MODOS[modo]}
Onomatopeias: {intensidade_sons} — {INTENSIDADE_SONS[intensidade_sons]}

REGRAS RÍGIDAS:
1. Preserve fatos, arco emocional, moral cristã, personalidade e intenção de cada cena.
2. Nomes protegidos nunca mudam: {', '.join(nomes) if nomes else '(nenhum cadastrado)'}.
3. Use linguagem realmente natural para crianças do mercado-alvo; não faça caricatura cultural e evite gírias datadas.
4. Localize onomatopeias quando isso melhorar humor, ritmo, ação ou leitura em voz alta. Não sobrecarregue cenas de oração/reflexão. Se houver efeito sonoro, retorne também sound_event e sound_rendering para aprovação.
5. BÍBLIA É CONTEÚDO PROTEGIDO. Referência: {bible_ref or '(não informada)'}. NÃO traduza, parafraseie, complete, invente ou cite o texto do versículo. O texto bíblico será inserido por outra camada somente a partir de uma versão aprovada pela autora. Se aparecer um campo de versículo, devolva apenas a referência, nunca o texto.
6. Não altere Character DNA, nomes de coleção ou termos marcados no glossário.
7. Para japonês, ajuste leitura infantil de forma natural; use kanji/kana de acordo com a faixa etária e não force traduções fonéticas de nomes próprios.
8. Responda JSON com as mesmas chaves estruturais do conteúdo recebido. Para cenas, preserve numero e demais metadados e traduza apenas campos linguísticos apropriados.
"""
    payload={
        "locale":loc["locale"], "modo":modo, "faixa_etaria":faixa_etaria,
        "intensidade_onomatopeias":intensidade_sons,
        "glossario_protegido":glossario,
        "conteudo":_conteudo_master_sem_versiculo(state),
        "versiculo_protegido":{"referencia":bible_ref,"instrucao":"NAO TRADUZIR TEXTO; apenas preservar referencia"},
        "instrucoes_da_autora":instrucoes,
    }
    return sistema,payload


def _remover_campos_biblicos_gerados(value: Any) -> Any:
    """Descarta campos bíblicos textuais que o modelo tente inventar."""
    if isinstance(value,dict):
        out={}
        for k,v in value.items():
            lk=str(k).lower()
            if lk in {"versiculo_texto","bible_verse_text","scripture_text","texto_versiculo"}:
                continue
            out[k]=_remover_campos_biblicos_gerados(v)
        return out
    if isinstance(value,list): return [_remover_campos_biblicos_gerados(x) for x in value]
    return value


def normalizar_resultado_localizacao(resposta: Any, locale: str, bible_record: dict | None=None) -> dict:
    if isinstance(resposta,list): resposta={"cenas_texto":resposta}
    if not isinstance(resposta,dict): resposta={"conteudo":resposta}
    # Alguns modelos repetem o envelope {conteudo:{...}}; normalizamos.
    base=resposta.get("conteudo") if isinstance(resposta.get("conteudo"),dict) else resposta
    out=_remover_campos_biblicos_gerados(copy.deepcopy(base))
    out["locale"]=normalize_locale(locale)
    out["versiculo_biblico"]=texto_biblico_para_exportacao(bible_record)
    out["bible_ai_translation_allowed"]=False
    out.setdefault("status","rascunho")
    out.setdefault("versao_id",uuid.uuid4().hex)
    out.setdefault("criado_em",int(time.time()))
    return out


def localizar_livro(state: dict, chamar_llm, locale: str, *, modo: str="natural_infantil", faixa_etaria: str="3–8", intensidade_sons: str="equilibrada", glossario: dict | None=None, bible_record: dict | None=None, instrucoes: str="") -> dict:
    sistema,payload=construir_prompt_localizacao(state,locale,modo=modo,faixa_etaria=faixa_etaria,intensidade_sons=intensidade_sons,glossario=glossario,instrucoes=instrucoes)
    resposta=chamar_llm(sistema=sistema,instrucao="Localize o objeto editorial fornecido preservando a estrutura JSON.\n"+json.dumps(payload,ensure_ascii=False))
    return normalizar_resultado_localizacao(resposta,locale,bible_record)


def revisar_localizacao_estrutural(master: dict, traducao: dict, *, bible_record: dict | None=None, glossario: dict | None=None) -> dict:
    alertas=[]
    mc=master.get("cenas_texto",[]) or []
    tc=traducao.get("cenas_texto",[]) or []
    if len(mc)!=len(tc): alertas.append({"nivel":"bloqueante","codigo":"scene_count","mensagem":f"Master possui {len(mc)} cenas e tradução possui {len(tc)}."})
    for i,cena in enumerate(tc):
        texto=(cena.get("texto","") if isinstance(cena,dict) else str(cena)).strip()
        if not texto: alertas.append({"nivel":"bloqueante","codigo":"empty_scene","mensagem":f"Cena {i+1} sem texto traduzido."})
    # nomes do Character Universe/dedicatória devem permanecer literais
    for nome in detectar_nomes_protegidos(master):
        master_text=repr(_conteudo_master_sem_versiculo(master))
        trans_text=repr(traducao)
        if nome in master_text and nome not in trans_text:
            alertas.append({"nivel":"atencao","codigo":"protected_name_missing","mensagem":f"Nome protegido possivelmente omitido/alterado: {nome}."})
    for termo,valor in (glossario or {}).items():
        if isinstance(valor,str) and valor and valor not in repr(traducao):
            alertas.append({"nivel":"sugestao","codigo":"glossary_review","mensagem":f"Revisar termo de glossário: {termo} → {valor}."})
    b=texto_biblico_para_exportacao(bible_record)
    if traducao.get("bible_ai_translation_allowed") is not False:
        alertas.append({"nivel":"bloqueante","codigo":"bible_guard","mensagem":"Proteção bíblica não está marcada como ativa."})
    if bible_record and bible_record.get("status")=="approved_text" and not b["pode_exportar_texto"]:
        alertas.append({"nivel":"bloqueante","codigo":"bible_approval","mensagem":"Há texto bíblico informado, mas ele não está validado/aprovado para exportação."})
    bloqueantes=sum(1 for a in alertas if a["nivel"]=="bloqueante")
    return {"ok":bloqueantes==0,"alertas":alertas,"bloqueantes":bloqueantes,"requer_revisao_humana":True}


def construir_prompt_revisor_linguistico(master: dict, traducao: dict, locale: str, faixa_etaria: str="3–8") -> str:
    loc=locale_info(locale)
    return f"""Você é um Revisor Linguístico Independente do FaithBloom. Compare MASTER e LOCALIZAÇÃO para {loc['locale']} ({loc['mercado']}) e faixa {faixa_etaria}.
Avalie: omissões, invenções, mudança de significado, naturalidade infantil, voz dos personagens, emoção, onomatopeias, adequação cultural e consistência de nomes.
REGRA ABSOLUTA: não traduza nem proponha texto de versículos bíblicos. Para Bíblia, apenas sinalize se a referência estiver ausente ou se houver texto sem origem/versão aprovada.
Retorne JSON: {{"veredito":"aprovado|revisar|bloqueado","alertas":[{{"nivel":"bloqueante|recomendado|atencao|sugestao","onde":"...","problema":"...","motivo":"...","sugestao":"..."}}]}}.
MASTER={repr(_conteudo_master_sem_versiculo(master))}
LOCALIZACAO={repr(traducao)}"""


def revisar_localizacao_com_llm(master: dict, traducao: dict, chamar_llm, locale: str, faixa_etaria: str="3–8") -> dict:
    prompt=construir_prompt_revisor_linguistico(master,traducao,locale,faixa_etaria)
    resp=chamar_llm(sistema=prompt,instrucao="Faça a revisão independente. Não reescreva o livro inteiro.")
    return resp if isinstance(resp,dict) else {"veredito":"revisar","alertas":[],"resposta":resp}



def extrair_texto_pdf_localizacao(caminho_pdf: str) -> dict:
    """Extrai somente a camada de texto de uma edição existente para auditoria.

    Não usa OCR. Se o PDF for escaneado/achatado sem texto selecionável, o
    relatório informa isso em vez de inventar conteúdo.
    """
    from pypdf import PdfReader
    reader=PdfReader(caminho_pdf)
    paginas=[]
    for i,page in enumerate(reader.pages,1):
        try:
            texto=(page.extract_text() or "").strip()
        except Exception:
            texto=""
        paginas.append({"pagina":i,"texto":texto})
    chars=sum(len(p["texto"]) for p in paginas)
    return {"paginas_total":len(paginas),"paginas":paginas,"caracteres_extraidos":chars,"texto_disponivel":chars>0,"nota":"Texto extraído da camada textual do PDF; PDFs achatados/escaneados podem exigir outro fluxo de importação."}

def _idx() -> list[dict]:
    x=_json(TRANSLATION_INDEX,[])
    return x if isinstance(x,list) else []


def criar_projeto_traducao(titulo: str, colecao: str, idioma_master: str="pt-BR", source_ref: str="") -> dict:
    pid=uuid.uuid4().hex
    p={"id":pid,"titulo":titulo,"colecao":colecao,"idioma_master":idioma_master,"source_ref":source_ref,"glossario":{},"bible_records":{},"edicoes":{},"sound_library":{},"historico":[],"criado_em":int(time.time())}
    _save_json(f"translation_studio/{pid}.json",p)
    idx=_idx(); idx.append({"id":pid,"titulo":titulo,"colecao":colecao,"idioma_master":idioma_master}); _save_json(TRANSLATION_INDEX,idx)
    return p


def listar_projetos_traducao() -> list[dict]: return list(reversed(_idx()))
def carregar_projeto_traducao(pid: str) -> dict: return _json(f"translation_studio/{pid}.json",{}) or {}

def salvar_projeto_traducao(p: dict) -> dict:
    p=copy.deepcopy(p); p["atualizado_em"]=int(time.time()); _save_json(f"translation_studio/{p['id']}.json",p); return p


def adicionar_versao_localizada(p: dict, locale: str, traducao: dict, label: str="A") -> dict:
    p=copy.deepcopy(p); loc=normalize_locale(locale); ed=p.setdefault("edicoes",{}).setdefault(loc,{"versoes":[],"aprovada_id":""})
    item=copy.deepcopy(traducao); item.setdefault("versao_id",uuid.uuid4().hex); item["label"]=label; item["salva_em"]=int(time.time()); ed["versoes"].append(item)
    p.setdefault("historico",[]).append({"evento":"localizacao_salva","locale":loc,"versao_id":item["versao_id"],"em":int(time.time())})
    return salvar_projeto_traducao(p)


def aprovar_versao_localizada(p: dict, locale: str, versao_id: str) -> dict:
    p=copy.deepcopy(p); loc=normalize_locale(locale); ed=p.setdefault("edicoes",{}).setdefault(loc,{"versoes":[],"aprovada_id":""})
    if not any(v.get("versao_id")==versao_id for v in ed.get("versoes",[])): raise ValueError("Versão não encontrada para este locale.")
    ed["aprovada_id"]=versao_id; p.setdefault("historico",[]).append({"evento":"localizacao_aprovada","locale":loc,"versao_id":versao_id,"em":int(time.time())}); return salvar_projeto_traducao(p)
