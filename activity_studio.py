"""FaithBloom Activity Book Studio — Kids, Teens & Adults.

Refinamento 08.

Princípios:
- a faixa/público altera de verdade a complexidade e o layout;
- cada folha nasce como rascunho e exige QA + aprovação da autora;
- revisões A/B/C preservam o histórico;
- "modificar somente isto" registra o escopo e os campos preservados;
- validators objetivos nunca inventam uma nota estética;
- personagens oficiais podem ser usados no contexto ``activity`` sem alterar DNA.
"""
from __future__ import annotations

from collections import deque
from copy import deepcopy
from dataclasses import dataclass, asdict
import json
import math
import re
import time
import uuid
from typing import Any

from armazenamento import _json, _save_json, _slug


AUDIENCE_PRESETS: dict[str, dict[str, Any]] = {
    "3-4": {
        "label": "3–4 anos",
        "group": "kids",
        "reading": "pré-leitor / instrução muito curta com apoio visual",
        "max_instruction_words": 9,
        "min_font_pt": 22,
        "visual_density": "muito_baixa",
        "recommended": ["trace", "match_pairs", "find_same", "count", "maze", "shapes", "coloring", "simple_patterns"],
    },
    "5-6": {
        "label": "5–6 anos",
        "group": "kids",
        "reading": "início de alfabetização; frases simples",
        "max_instruction_words": 14,
        "min_font_pt": 18,
        "visual_density": "baixa",
        "recommended": ["trace", "connect_dots", "spot_difference", "count", "maze", "matching", "simple_math", "patterns", "find_object", "coloring"],
    },
    "7-8": {
        "label": "7–8 anos",
        "group": "kids",
        "reading": "leitura infantil independente curta",
        "max_instruction_words": 22,
        "min_font_pt": 15,
        "visual_density": "media_baixa",
        "recommended": ["word_search", "maze", "spot_difference", "math", "logic", "patterns", "matching", "complete_drawing", "reading_qa", "bible_activity"],
    },
    "9-12": {
        "label": "9–12 anos",
        "group": "kids",
        "reading": "instruções em múltiplas etapas curtas",
        "max_instruction_words": 35,
        "min_font_pt": 13,
        "visual_density": "media",
        "recommended": ["word_search", "crossword", "sudoku", "logic", "cryptogram", "math", "reading_qa", "trivia", "bible_activity", "observation"],
    },
    "teen": {
        "label": "Teen / Adolescente",
        "group": "teen",
        "reading": "linguagem juvenil natural",
        "max_instruction_words": 50,
        "min_font_pt": 12,
        "visual_density": "media_alta",
        "recommended": ["crossword", "word_search", "sudoku", "logic", "cryptogram", "trivia", "journaling", "bible_study", "observation"],
    },
    "adult": {
        "label": "Adulto",
        "group": "adult",
        "reading": "adulto geral",
        "max_instruction_words": 70,
        "min_font_pt": 11,
        "visual_density": "alta_controlada",
        "recommended": ["crossword", "word_search", "sudoku", "logic", "cryptogram", "trivia", "journaling", "bible_study", "observation", "memory"],
    },
    "senior": {
        "label": "Adulto 60+ / Terceira idade",
        "group": "adult",
        "reading": "clareza alta, tipografia ampliada e carga cognitiva configurável",
        "max_instruction_words": 55,
        "min_font_pt": 16,
        "visual_density": "media",
        "recommended": ["word_search", "crossword", "memory", "matching", "observation", "simple_math", "trivia", "journaling"],
    },
    "custom": {
        "label": "Personalizado",
        "group": "custom",
        "reading": "definido pela autora",
        "max_instruction_words": 80,
        "min_font_pt": 11,
        "visual_density": "custom",
        "recommended": [],
    },
}

DIFFICULTY_PROFILES = {
    "relaxing": {"label": "Relaxante / Fácil", "factor": 0.75},
    "moderate": {"label": "Moderado", "factor": 1.0},
    "challenging": {"label": "Desafiador", "factor": 1.25},
    "expert": {"label": "Expert", "factor": 1.6},
}

CONTENT_THEMES = [
    "Cristão / Bíblico", "Educacional", "Alfabetização", "Matemática", "Lógica",
    "Animais", "Natureza", "Viagem", "Datas comemorativas", "Observação",
    "Memória & atenção", "Journaling", "Customizado",
]

ACTIVITY_CATALOG: dict[str, dict[str, Any]] = {
    "maze": {"label": "Labirinto", "qa": "maze", "groups": ["kids", "teen", "adult", "custom"]},
    "spot_difference": {"label": "Encontre as diferenças", "qa": "spot_difference", "groups": ["kids", "teen", "adult", "custom"]},
    "connect_dots": {"label": "Ligue os pontos", "qa": "connect_dots", "groups": ["kids", "custom"]},
    "trace": {"label": "Trace letras/números/formas", "qa": "trace", "groups": ["kids", "custom"]},
    "count": {"label": "Conte e marque", "qa": "count", "groups": ["kids", "custom"]},
    "find_object": {"label": "Encontre o objeto", "qa": "find_object", "groups": ["kids", "teen", "adult", "custom"]},
    "matching": {"label": "Faça as associações", "qa": "matching", "groups": ["kids", "teen", "adult", "custom"]},
    "match_pairs": {"label": "Ligue os pares", "qa": "matching", "groups": ["kids", "custom"]},
    "find_same": {"label": "Encontre o igual", "qa": "find_object", "groups": ["kids", "custom"]},
    "shapes": {"label": "Formas e reconhecimento", "qa": "generic", "groups": ["kids", "custom"]},
    "patterns": {"label": "Padrões e sequências", "qa": "sequence", "groups": ["kids", "teen", "adult", "custom"]},
    "simple_patterns": {"label": "Sequências simples", "qa": "sequence", "groups": ["kids", "custom"]},
    "complete_drawing": {"label": "Complete o desenho", "qa": "generic", "groups": ["kids", "custom"]},
    "coloring": {"label": "Colorir", "qa": "generic", "groups": ["kids", "teen", "adult", "custom"]},
    "word_search": {"label": "Caça-palavras", "qa": "word_search", "groups": ["kids", "teen", "adult", "custom"]},
    "crossword": {"label": "Palavras cruzadas", "qa": "crossword", "groups": ["kids", "teen", "adult", "custom"]},
    "sudoku": {"label": "Sudoku", "qa": "sudoku", "groups": ["kids", "teen", "adult", "custom"]},
    "logic": {"label": "Desafio de lógica", "qa": "generic_answer", "groups": ["kids", "teen", "adult", "custom"]},
    "cryptogram": {"label": "Criptograma", "qa": "cryptogram", "groups": ["kids", "teen", "adult", "custom"]},
    "trivia": {"label": "Quiz / Trivia", "qa": "quiz", "groups": ["kids", "teen", "adult", "custom"]},
    "math": {"label": "Matemática", "qa": "math", "groups": ["kids", "teen", "adult", "custom"]},
    "simple_math": {"label": "Matemática simples", "qa": "math", "groups": ["kids", "adult", "custom"]},
    "reading_qa": {"label": "Leitura & interpretação", "qa": "quiz", "groups": ["kids", "teen", "adult", "custom"]},
    "observation": {"label": "Observação", "qa": "generic_answer", "groups": ["kids", "teen", "adult", "custom"]},
    "memory": {"label": "Memória & atenção", "qa": "generic_answer", "groups": ["teen", "adult", "custom"]},
    "journaling": {"label": "Journaling guiado", "qa": "open_ended", "groups": ["teen", "adult", "custom"]},
    "bible_activity": {"label": "Atividade bíblica infantil", "qa": "generic_answer", "groups": ["kids", "custom"]},
    "bible_study": {"label": "Estudo bíblico / reflexão", "qa": "open_ended", "groups": ["teen", "adult", "custom"]},
}


def available_activity_types(audience_id: str) -> list[str]:
    preset = AUDIENCE_PRESETS.get(audience_id, AUDIENCE_PRESETS["custom"])
    group = preset["group"]
    if audience_id != "custom" and preset.get("recommended"):
        recommended = [x for x in preset["recommended"] if x in ACTIVITY_CATALOG]
        rest = [k for k, v in ACTIVITY_CATALOG.items() if group in v["groups"] and k not in recommended]
        return recommended + rest
    return [k for k, v in ACTIVITY_CATALOG.items() if group in v["groups"] or "custom" in v["groups"]]


def _version_label(n: int) -> str:
    # A..Z, then V27 etc.
    return chr(64 + n) if 1 <= n <= 26 else f"V{n}"


def create_activity_page(activity_type: str, audience_id: str, difficulty: str = "moderate", *,
                         title: str = "", instruction: str = "", objective: str = "",
                         theme: str = "", content: dict | None = None, answer_key: Any = None,
                         character_ids: list[str] | None = None, style_id: str = "",
                         layout: dict | None = None, source_story: dict | None = None) -> dict:
    if activity_type not in ACTIVITY_CATALOG:
        raise ValueError("Tipo de atividade não reconhecido")
    if audience_id not in AUDIENCE_PRESETS:
        raise ValueError("Faixa/público não reconhecido")
    if difficulty not in DIFFICULTY_PROFILES:
        raise ValueError("Dificuldade não reconhecida")
    return {
        "id": uuid.uuid4().hex,
        "version": 1,
        "version_label": "A",
        "status": "draft",
        "activity_type": activity_type,
        "audience_id": audience_id,
        "difficulty": difficulty,
        "title": title or ACTIVITY_CATALOG[activity_type]["label"],
        "instruction": instruction,
        "objective": objective,
        "theme": theme,
        "content": deepcopy(content or {}),
        "answer_key": deepcopy(answer_key),
        "character_ids": list(character_ids or []),
        "style_id": style_id,
        "layout": {"font_pt": AUDIENCE_PRESETS[audience_id]["min_font_pt"], "visual_density": AUDIENCE_PRESETS[audience_id]["visual_density"], **(layout or {})},
        "source_story": deepcopy(source_story or {}),
        "qa": None,
        "author_approval": None,
        "revisions": [],
        "created_at": int(time.time()),
        "updated_at": int(time.time()),
    }


def revise_activity_page(page: dict, *, change_request: str, patch: dict | None = None,
                         preserve_fields: list[str] | None = None) -> dict:
    """Cria nova versão sem apagar a anterior.

    ``preserve_fields`` torna explícita a intenção de "modificar somente isto".
    O patch nunca pode trocar id nem apagar o histórico.
    """
    out = deepcopy(page)
    snapshot = {k: deepcopy(v) for k, v in page.items() if k != "revisions"}
    out.setdefault("revisions", []).append({
        "version": page.get("version", 1),
        "version_label": page.get("version_label", "A"),
        "change_request": change_request,
        "snapshot": snapshot,
        "saved_at": int(time.time()),
    })
    protected = {"id", "revisions", "created_at"}
    for k, v in (patch or {}).items():
        if k not in protected:
            out[k] = deepcopy(v)
    for field in preserve_fields or []:
        if field in page:
            out[field] = deepcopy(page[field])
    out["version"] = int(page.get("version", 1)) + 1
    out["version_label"] = _version_label(out["version"])
    out["status"] = "draft"
    out["qa"] = None
    out["author_approval"] = None
    out["last_change_request"] = change_request
    out["preserve_fields"] = list(preserve_fields or [])
    out["updated_at"] = int(time.time())
    return out


def approve_activity_page(page: dict, approved_by: str = "autora") -> dict:
    out = deepcopy(page)
    qa = out.get("qa") or qa_activity(out)
    if not qa.get("valid"):
        raise ValueError("A página possui bloqueios de QA e não pode ser aprovada ainda.")
    out["qa"] = qa
    out["status"] = "approved"
    out["author_approval"] = {"approved": True, "by": approved_by, "at": int(time.time())}
    out["updated_at"] = int(time.time())
    return out


def reject_activity_page(page: dict, reason: str) -> dict:
    out = deepcopy(page)
    out["status"] = "needs_revision"
    out["author_approval"] = {"approved": False, "reason": reason, "at": int(time.time())}
    out["updated_at"] = int(time.time())
    return out


def _alert(severity: str, code: str, message: str) -> dict:
    return {"severity": severity, "code": code, "message": message}


def _common_qa(page: dict) -> list[dict]:
    alerts: list[dict] = []
    audience = AUDIENCE_PRESETS.get(page.get("audience_id"), AUDIENCE_PRESETS["custom"])
    words = len(re.findall(r"\w+", page.get("instruction", ""), re.UNICODE))
    max_words = int(audience.get("max_instruction_words", 80))
    if not page.get("instruction", "").strip():
        alerts.append(_alert("blocker", "missing_instruction", "A folha precisa de uma instrução clara."))
    elif words > max_words:
        alerts.append(_alert("warning", "instruction_too_long", f"A instrução tem {words} palavras; o perfil {audience['label']} recomenda até {max_words}."))
    font = float((page.get("layout") or {}).get("font_pt", audience.get("min_font_pt", 11)))
    if font < float(audience.get("min_font_pt", 11)):
        alerts.append(_alert("warning", "font_small", f"Fonte de {font:g} pt está abaixo do mínimo de referência deste perfil ({audience['min_font_pt']} pt)."))
    if page.get("activity_type") not in available_activity_types(page.get("audience_id", "custom")):
        alerts.append(_alert("warning", "audience_mismatch", "Este tipo de atividade não é recomendado para o público selecionado."))
    return alerts


def _grid_rect(grid: list[list[Any]]) -> bool:
    return bool(grid) and all(isinstance(r, list) and len(r) == len(grid[0]) for r in grid)


def _validate_maze(page: dict) -> tuple[list[dict], Any]:
    c = page.get("content") or {}; grid = c.get("grid") or []
    if not _grid_rect(grid):
        return [_alert("blocker", "maze_grid_invalid", "O labirinto precisa de uma grade retangular estruturada para validação automática.")], None
    start = tuple(c.get("start", (0, 0))); end = tuple(c.get("end", (len(grid)-1, len(grid[0])-1)))
    h, w = len(grid), len(grid[0])
    def open_(p):
        r, col = p
        return 0 <= r < h and 0 <= col < w and grid[r][col] in (0, ".", "S", "E", False)
    if not open_(start) or not open_(end):
        return [_alert("blocker", "maze_endpoints", "Entrada ou saída está bloqueada/fora da grade.")], None
    q=deque([start]); prev={start: None}
    while q:
        p=q.popleft()
        if p==end: break
        r,col=p
        for n in ((r-1,col),(r+1,col),(r,col-1),(r,col+1)):
            if open_(n) and n not in prev:
                prev[n]=p; q.append(n)
    if end not in prev:
        return [_alert("blocker", "maze_unsolvable", "O labirinto não possui caminho válido até a saída.")], None
    path=[]; cur=end
    while cur is not None:
        path.append(list(cur)); cur=prev[cur]
    path.reverse()
    return [], {"path": path, "steps": max(0, len(path)-1)}


def _directions():
    return [(-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1)]


def _word_exists(grid: list[list[str]], word: str) -> bool:
    word = re.sub(r"\s+", "", word.upper())
    if not word or not _grid_rect(grid): return False
    G=[[str(x).upper() for x in row] for row in grid]; h,w=len(G),len(G[0])
    for r in range(h):
        for c in range(w):
            for dr,dc in _directions():
                ok=True
                for i,ch in enumerate(word):
                    rr,cc=r+dr*i,c+dc*i
                    if not (0<=rr<h and 0<=cc<w and G[rr][cc]==ch): ok=False; break
                if ok: return True
    return False


def _validate_word_search(page: dict) -> tuple[list[dict], Any]:
    c=page.get("content") or {}; grid=c.get("grid") or []; words=c.get("words") or []
    alerts=[]
    if not _grid_rect(grid): alerts.append(_alert("blocker","word_search_grid_invalid","A grade do caça-palavras precisa ser retangular.")); return alerts,None
    if not words: alerts.append(_alert("blocker","word_search_no_words","Cadastre as palavras que a criança/adulto deve encontrar.")); return alerts,None
    missing=[w for w in words if not _word_exists(grid,str(w))]
    if missing: alerts.append(_alert("blocker","word_search_missing_words","Palavras ausentes da grade: "+", ".join(map(str,missing))))
    return alerts, {"words": words} if not missing else None


def _validate_spot_difference(page: dict) -> tuple[list[dict], Any]:
    diffs=(page.get("content") or {}).get("differences") or []
    declared=(page.get("content") or {}).get("declared_count")
    alerts=[]
    if not diffs: alerts.append(_alert("blocker","differences_missing","Registre as diferenças reais para gerar e validar o gabarito."))
    if declared is not None and int(declared)!=len(diffs): alerts.append(_alert("blocker","differences_count_mismatch",f"A página anuncia {declared} diferenças, mas o gabarito possui {len(diffs)}."))
    ids=[json.dumps(d,sort_keys=True,ensure_ascii=False) for d in diffs]
    if len(ids)!=len(set(ids)): alerts.append(_alert("blocker","differences_duplicate","Há diferenças duplicadas no gabarito."))
    return alerts, {"differences": diffs, "count": len(diffs)} if not alerts else None


def _validate_connect_dots(page: dict) -> tuple[list[dict], Any]:
    pts=(page.get("content") or {}).get("points") or []
    nums=[]
    for p in pts:
        try: nums.append(int(p.get("n") if isinstance(p,dict) else p[0]))
        except Exception: pass
    alerts=[]
    if len(nums)<2: alerts.append(_alert("blocker","dots_insufficient","São necessários ao menos dois pontos numerados."))
    elif nums!=list(range(min(nums),max(nums)+1)): alerts.append(_alert("blocker","dots_sequence_invalid","A numeração dos pontos contém lacunas ou está fora de sequência."))
    return alerts, {"sequence": nums} if not alerts else None


def _validate_matching(page: dict) -> tuple[list[dict], Any]:
    pairs=(page.get("content") or {}).get("pairs") or []
    alerts=[]
    if not pairs: alerts.append(_alert("blocker","pairs_missing","Cadastre os pares corretos."))
    left=[]; right=[]
    for p in pairs:
        if isinstance(p,dict): left.append(str(p.get("left",""))); right.append(str(p.get("right","")))
        elif isinstance(p,(list,tuple)) and len(p)>=2: left.append(str(p[0])); right.append(str(p[1]))
    if any(not x for x in left+right): alerts.append(_alert("blocker","pair_blank","Há item vazio nos pares."))
    if len(left)!=len(set(left)): alerts.append(_alert("warning","left_duplicates","Existem itens repetidos na coluna esquerda; confirme se isso é intencional."))
    return alerts, {"pairs": pairs} if not any(a["severity"]=="blocker" for a in alerts) else None


def _validate_sequence(page: dict) -> tuple[list[dict], Any]:
    c=page.get("content") or {}; seq=c.get("sequence") or []; answer=c.get("answer")
    alerts=[]
    if len(seq)<2: alerts.append(_alert("blocker","sequence_short","A sequência precisa de exemplos suficientes para indicar um padrão."))
    if answer in (None,""): alerts.append(_alert("blocker","sequence_no_answer","Informe a resposta correta da sequência."))
    return alerts, {"answer": answer} if not alerts else None


def _validate_math(page: dict) -> tuple[list[dict], Any]:
    items=(page.get("content") or {}).get("items") or []
    alerts=[]; key=[]
    if not items: return [_alert("blocker","math_items_missing","Inclua ao menos uma questão matemática estruturada.")], None
    allowed=re.compile(r"^[0-9+\-*/(). %]+$")
    for i,item in enumerate(items,1):
        expr=str(item.get("expression","")).strip() if isinstance(item,dict) else ""
        expected=item.get("answer") if isinstance(item,dict) else None
        if not expr or not allowed.match(expr): alerts.append(_alert("blocker","math_expression_invalid",f"Questão {i}: expressão ausente ou não suportada.")); continue
        try:
            calc=eval(expr,{"__builtins__":{}},{})
        except Exception:
            alerts.append(_alert("blocker","math_expression_error",f"Questão {i}: não foi possível calcular a expressão.")); continue
        if expected is None or (isinstance(calc,float) and isinstance(expected,(int,float)) and not math.isclose(calc,float(expected),rel_tol=1e-9,abs_tol=1e-9)) or (not isinstance(calc,float) and calc!=expected):
            alerts.append(_alert("blocker","math_answer_wrong",f"Questão {i}: gabarito não corresponde ao cálculo ({calc})."))
        key.append({"expression":expr,"answer":calc})
    return alerts, key if not any(a["severity"]=="blocker" for a in alerts) else None


def _validate_quiz(page: dict) -> tuple[list[dict], Any]:
    qs=(page.get("content") or {}).get("questions") or []; alerts=[]; key=[]
    if not qs: return [_alert("blocker","questions_missing","Inclua perguntas e respostas estruturadas.")],None
    for i,q in enumerate(qs,1):
        if not isinstance(q,dict) or not str(q.get("question","")).strip(): alerts.append(_alert("blocker","question_blank",f"Pergunta {i} está vazia.")); continue
        ans=q.get("answer")
        if ans in (None,""): alerts.append(_alert("blocker","answer_blank",f"Pergunta {i} não possui resposta no gabarito."))
        key.append({"question":q.get("question"),"answer":ans})
    return alerts,key if not any(a["severity"]=="blocker" for a in alerts) else None


def _validate_cryptogram(page: dict) -> tuple[list[dict], Any]:
    c=page.get("content") or {}; encoded=str(c.get("encoded","")).strip(); decoded=str(c.get("decoded","")).strip(); mapping=c.get("mapping") or {}
    alerts=[]
    if not encoded or not decoded: alerts.append(_alert("blocker","cryptogram_text_missing","Criptograma precisa do texto codificado e da solução."))
    if not mapping: alerts.append(_alert("warning","cryptogram_mapping_missing","Sem mapa de substituição, o FaithBloom não consegue conferir a decodificação automaticamente."))
    elif encoded:
        generated="".join(str(mapping.get(ch,ch)) for ch in encoded)
        if generated!=decoded: alerts.append(_alert("blocker","cryptogram_solution_mismatch","A solução não corresponde ao mapa de substituição informado."))
    return alerts,{"decoded":decoded,"mapping":mapping} if not any(a["severity"]=="blocker" for a in alerts) else None


def _sudoku_candidates(board, r, c, n):
    nums=set(range(1,n+1)); nums-=set(board[r]); nums-={board[i][c] for i in range(n)}
    box=int(math.isqrt(n))
    if box*box==n:
        br=(r//box)*box; bc=(c//box)*box
        nums-={board[i][j] for i in range(br,br+box) for j in range(bc,bc+box)}
    return nums


def _solve_sudoku_count(board, limit=2):
    n=len(board); solutions=0; first=None
    def rec():
        nonlocal solutions,first
        if solutions>=limit: return
        pos=None; cand=None
        for r in range(n):
            for c in range(n):
                if board[r][c]==0:
                    cs=_sudoku_candidates(board,r,c,n)
                    if not cs: return
                    if cand is None or len(cs)<len(cand): pos=(r,c); cand=cs
        if pos is None:
            solutions+=1
            if first is None: first=deepcopy(board)
            return
        r,c=pos
        for v in sorted(cand):
            board[r][c]=v; rec(); board[r][c]=0
            if solutions>=limit: return
    rec(); return solutions,first


def _validate_sudoku(page: dict) -> tuple[list[dict], Any]:
    board=deepcopy((page.get("content") or {}).get("board") or []); alerts=[]
    if not _grid_rect(board) or len(board)!=len(board[0]) or len(board) not in (4,9):
        return [_alert("blocker","sudoku_shape","Sudoku deve ser 4×4 ou 9×9 para o validador atual.")],None
    n=len(board); box=int(math.isqrt(n))
    def valid_vals(vals):
        vals=[x for x in vals if x]
        return len(vals)==len(set(vals)) and all(isinstance(x,int) and 1<=x<=n for x in vals)
    for r in range(n):
        if not valid_vals(board[r]): alerts.append(_alert("blocker","sudoku_row_conflict",f"Conflito na linha {r+1}."))
    for c in range(n):
        if not valid_vals([board[r][c] for r in range(n)]): alerts.append(_alert("blocker","sudoku_col_conflict",f"Conflito na coluna {c+1}."))
    for br in range(0,n,box):
        for bc in range(0,n,box):
            if not valid_vals([board[r][c] for r in range(br,br+box) for c in range(bc,bc+box)]): alerts.append(_alert("blocker","sudoku_box_conflict","Conflito em um bloco do Sudoku."))
    if any(a["severity"]=="blocker" for a in alerts): return alerts,None
    count,solution=_solve_sudoku_count(board)
    if count==0: alerts.append(_alert("blocker","sudoku_no_solution","Sudoku sem solução."))
    elif count>1: alerts.append(_alert("blocker","sudoku_multiple_solutions","Sudoku possui mais de uma solução; para publicação o gabarito deve ser inequívoco."))
    return alerts,solution if count==1 else None


def _validate_crossword(page: dict) -> tuple[list[dict], Any]:
    entries=(page.get("content") or {}).get("entries") or []; alerts=[]; occupied={}; key=[]
    if not entries: return [_alert("blocker","crossword_entries_missing","Inclua as palavras, pistas e posições da cruzadinha.")],None
    for idx,e in enumerate(entries,1):
        try:
            answer=re.sub(r"\s+","",str(e["answer"]).upper()); r=int(e["row"]); c=int(e["col"]); direction=e["direction"]
        except Exception:
            alerts.append(_alert("blocker","crossword_entry_invalid",f"Entrada {idx} incompleta.")); continue
        if direction not in ("across","down") or not answer: alerts.append(_alert("blocker","crossword_entry_invalid",f"Entrada {idx} inválida.")); continue
        if not str(e.get("clue","")).strip(): alerts.append(_alert("warning","crossword_clue_blank",f"Entrada {idx} sem pista."))
        cells=[]
        for i,ch in enumerate(answer):
            pos=(r, c+i) if direction=="across" else (r+i,c); cells.append(pos)
            if pos in occupied and occupied[pos]!=ch: alerts.append(_alert("blocker","crossword_conflict",f"Conflito de letras em {pos}."))
            occupied[pos]=ch
        key.append({"answer":answer,"clue":e.get("clue"),"cells":[list(x) for x in cells]})
    # ao menos um cruzamento quando há mais de uma palavra
    if len(entries)>1:
        total=sum(len(re.sub(r"\s+","",str(e.get("answer","")))) for e in entries if isinstance(e,dict))
        if total==len(occupied): alerts.append(_alert("warning","crossword_no_intersection","As palavras não se cruzam; revise o layout da cruzadinha."))
    return alerts,key if not any(a["severity"]=="blocker" for a in alerts) else None


def _validate_count(page: dict) -> tuple[list[dict], Any]:
    c=page.get("content") or {}; items=c.get("items") or []; expected=c.get("answer")
    if expected is None: expected=len(items)
    alerts=[]
    if not items: alerts.append(_alert("blocker","count_items_missing","Não há objetos estruturados para contar."))
    if int(expected)!=len(items): alerts.append(_alert("blocker","count_answer_wrong",f"O gabarito diz {expected}, mas há {len(items)} itens."))
    return alerts,{"answer":len(items)} if not alerts else None


def _validate_generic_answer(page: dict) -> tuple[list[dict], Any]:
    ans=page.get("answer_key")
    if ans in (None,"",[],{}): return [_alert("blocker","answer_key_missing","Esta atividade precisa de gabarito estruturado antes de ser aprovada.")],None
    return [],deepcopy(ans)


def _validate_open_ended(page: dict) -> tuple[list[dict], Any]:
    prompts=(page.get("content") or {}).get("prompts") or []
    if not prompts: return [_alert("blocker","prompts_missing","Inclua ao menos uma pergunta/reflexão aberta.")],None
    return [],{"type":"open_ended","note":"Sem resposta única; revisar adequação editorial e espaço de escrita."}


def _validate_generic(page: dict) -> tuple[list[dict], Any]:
    return [], deepcopy(page.get("answer_key"))


VALIDATORS = {
    "maze": _validate_maze,
    "word_search": _validate_word_search,
    "spot_difference": _validate_spot_difference,
    "connect_dots": _validate_connect_dots,
    "matching": _validate_matching,
    "sequence": _validate_sequence,
    "math": _validate_math,
    "quiz": _validate_quiz,
    "cryptogram": _validate_cryptogram,
    "sudoku": _validate_sudoku,
    "crossword": _validate_crossword,
    "count": _validate_count,
    "generic_answer": _validate_generic_answer,
    "open_ended": _validate_open_ended,
    "trace": _validate_generic,
    "find_object": _validate_generic_answer,
    "generic": _validate_generic,
}


def qa_activity(page: dict) -> dict:
    alerts=_common_qa(page)
    qa_kind=ACTIVITY_CATALOG.get(page.get("activity_type"),{}).get("qa","generic")
    fn=VALIDATORS.get(qa_kind,_validate_generic)
    more,key=fn(page); alerts.extend(more)
    blockers=[a for a in alerts if a["severity"]=="blocker"]
    warnings=[a for a in alerts if a["severity"]=="warning"]
    return {
        "valid": not blockers,
        "ready_for_author_review": not blockers,
        "blockers": len(blockers),
        "warnings": len(warnings),
        "alerts": alerts,
        "answer_key": key,
        "checked_at": int(time.time()),
        "validator": qa_kind,
        "note": "QA objetivo/estrutural. Não é uma nota estética e não substitui a aprovação da autora.",
    }


def attach_qa(page: dict) -> dict:
    out=deepcopy(page); out["qa"]=qa_activity(out)
    if out["qa"]["valid"] and out.get("status")!="approved": out["status"]="ready_for_author_review"
    elif not out["qa"]["valid"]: out["status"]="needs_revision"
    out["updated_at"]=int(time.time()); return out


def build_activity_prompt(page: dict, character_prompts: list[str] | None = None, extra_instruction: str = "") -> str:
    audience=AUDIENCE_PRESETS[page["audience_id"]]; diff=DIFFICULTY_PROFILES[page["difficulty"]]
    char_block="\n".join(character_prompts or []) or "Sem personagem oficial obrigatório."
    return f"""FAITHBLOOM ACTIVITY SHEET — preserve a estrutura solucionável da atividade.
Público: {audience['label']} ({audience['reading']}). Dificuldade: {diff['label']}.
Tipo: {ACTIVITY_CATALOG[page['activity_type']]['label']}. Objetivo: {page.get('objective','')}.
Tema: {page.get('theme','')}. Instrução aprovada/rascunho: {page.get('instruction','')}.
Layout: fonte mínima {audience['min_font_pt']} pt; densidade visual {audience['visual_density']}.
PERSONAGENS OFICIAIS (não alterar DNA):
{char_block}
A personagem pode decorar ou participar da atividade, mas NÃO pode cobrir grade, pistas, números, campos de resposta ou caminho solucionável.
Não gere gabarito visível na folha do aluno. Preserve áreas seguras e espaço de resposta.
{extra_instruction}
""".strip()


def story_to_activity_suggestions(story_state: dict, audience_id: str, count: int = 6) -> list[dict]:
    """Sugestões determinísticas a partir de metadados da história; sem inventar versículos."""
    candidates=available_activity_types(audience_id)
    title=story_state.get("titulo",""); lesson=story_state.get("licao_final") or story_state.get("aprendizado_cristao","")
    ref=story_state.get("versiculo_referencia","")
    out=[]
    for idx,t in enumerate(candidates[:max(1,count)],1):
        objective="atenção, compreensão e vínculo com a história"
        if t in {"math","simple_math","count"}: objective="raciocínio matemático contextualizado"
        elif t in {"word_search","crossword"}: objective="vocabulário e memória da história"
        elif t in {"maze","logic","patterns","simple_patterns"}: objective="raciocínio lógico e persistência"
        item={"activity_type":t,"title":ACTIVITY_CATALOG[t]["label"],"objective":objective,"source_title":title,"lesson_context":lesson}
        if "bible" in t and ref: item["bible_reference_only"]=ref
        out.append(item)
    return out


# ---------------- persistence ----------------
INDEX_PATH="activity_studio/index.json"

def _index():
    x=_json(INDEX_PATH,[]); return x if isinstance(x,list) else []


def create_activity_project(title: str, audience_id: str, difficulty: str="moderate", theme: str="", collection: str="", source_book: dict | None=None) -> dict:
    pid=uuid.uuid4().hex
    obj={"id":pid,"title":title,"audience_id":audience_id,"difficulty":difficulty,"theme":theme,"collection":collection,"source_book":deepcopy(source_book or {}),"pages":[],"status":"draft","created_at":int(time.time()),"updated_at":int(time.time())}
    save_activity_project(obj, snapshot=False)
    return obj


def save_activity_project(project: dict, snapshot: bool=True) -> str:
    obj=deepcopy(project); pid=obj.get("id") or uuid.uuid4().hex; obj["id"]=pid
    path=f"activity_studio/projects/{pid}.json"
    if snapshot:
        current=_json(path,{}) or {}
        if current:
            hist=_json(f"activity_studio/history/{pid}.json",[]) or []
            hist.append({"saved_at":int(time.time()),"snapshot":current}); _save_json(f"activity_studio/history/{pid}.json",hist[-30:])
    obj["updated_at"]=int(time.time()); _save_json(path,obj)
    idx=[x for x in _index() if x.get("id")!=pid]
    idx.append({"id":pid,"title":obj.get("title",""),"audience_id":obj.get("audience_id"),"theme":obj.get("theme",""),"status":obj.get("status","draft")})
    _save_json(INDEX_PATH,idx)
    return path


def load_activity_project(pid: str) -> dict:
    return _json(f"activity_studio/projects/{pid}.json",{}) or {}


def list_activity_projects() -> list[dict]:
    return sorted(_index(),key=lambda x:x.get("title","").lower())


def add_page_to_project(project: dict, page: dict) -> dict:
    out=deepcopy(project); out.setdefault("pages",[]).append(deepcopy(page)); out["updated_at"]=int(time.time()); return out


def replace_page_in_project(project: dict, page: dict) -> dict:
    out=deepcopy(project); found=False
    for i,p in enumerate(out.get("pages",[])):
        if p.get("id")==page.get("id"): out["pages"][i]=deepcopy(page); found=True; break
    if not found: out.setdefault("pages",[]).append(deepcopy(page))
    out["updated_at"]=int(time.time()); return out


def project_readiness(project: dict) -> dict:
    pages=project.get("pages",[]) or []; total=len(pages)
    approved=sum(1 for p in pages if p.get("status")=="approved")
    blockers=sum(1 for p in pages if (p.get("qa") or {}).get("blockers",0)>0)
    return {"total_pages":total,"approved_pages":approved,"qa_blocked_pages":blockers,"ready": bool(total) and approved==total and blockers==0,
            "policy":"every_activity_page_requires_author_approval"}

# ---------------- AI planner + printable SVG preview ----------------
def generation_prompt(activity_type: str, audience_id: str, difficulty: str, theme: str, objective: str, source_story: dict | None = None) -> tuple[str, str]:
    """Prompt para gerar apenas a ESTRUTURA solucionável; a autora revisa antes da arte.

    Bible Guard: nunca inclui texto de versículo original, somente referência.
    """
    if activity_type not in ACTIVITY_CATALOG:
        raise ValueError("Tipo de atividade não reconhecido")
    audience=AUDIENCE_PRESETS[audience_id]; diff=DIFFICULTY_PROFILES[difficulty]
    story=source_story or {}
    safe_story={
        "titulo":story.get("titulo",""),
        "tema":story.get("tema") or story.get("aprendizado_cristao") or "",
        "licao":story.get("licao_final") or "",
        "referencia_biblica":story.get("versiculo_referencia") or "",
        "personagens":list((story.get("personagens") or {}).keys()),
    }
    system=f"""Você é o Activity Designer do FaithBloom. Crie UMA atividade estruturalmente verificável.
Público: {audience['label']}. Perfil: {audience['reading']}.
Dificuldade: {diff['label']}. Tipo: {ACTIVITY_CATALOG[activity_type]['label']}.
Tema: {theme}. Objetivo: {objective}.
Regras: instrução adequada ao público (máx. aproximado {audience['max_instruction_words']} palavras); solução inequívoca quando houver gabarito; não inserir resposta visível na folha do aluno.
BIBLE GUARD: se houver referência bíblica, use SOMENTE a referência. Nunca escreva, traduza, complete ou parafraseie o texto de um versículo.
Responda somente JSON com: instruction, content, answer_key, designer_notes.
"""
    user="Contexto seguro do Story Book: "+json.dumps(safe_story,ensure_ascii=False)+". Gere a estrutura da atividade."
    return system,user


def normalize_llm_activity_result(result: Any) -> dict:
    if isinstance(result,list):
        result=result[0] if result and isinstance(result[0],dict) else {}
    if not isinstance(result,dict): return {"instruction":"","content":{},"answer_key":None,"designer_notes":""}
    # descarte defensivo de qualquer campo que tente carregar texto bíblico
    forbidden={"verse_text","scripture_text","versiculo_texto","bible_text","texto_biblico"}
    clean={k:v for k,v in result.items() if k not in forbidden}
    return {
        "instruction":str(clean.get("instruction","")).strip(),
        "content":clean.get("content") if isinstance(clean.get("content"),dict) else {},
        "answer_key":clean.get("answer_key"),
        "designer_notes":str(clean.get("designer_notes","")).strip(),
    }


def _xml(s: Any) -> str:
    import html
    return html.escape(str(s),quote=True)


def render_activity_svg(page: dict, width: int=1700, height: int=2200) -> str:
    """Preview vetorial determinístico da folha.

    Não é o PDF final de publicação. Serve para a autora revisar hierarquia,
    instrução e estrutura antes da montagem editorial final.
    """
    margin=110; title=_xml(page.get("title") or ACTIVITY_CATALOG.get(page.get("activity_type"),{}).get("label","Atividade"))
    instruction=_xml(page.get("instruction", "")); typ=page.get("activity_type"); c=page.get("content") or {}
    pieces=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
            '<rect width="100%" height="100%" fill="white"/>',
            f'<rect x="55" y="55" width="{width-110}" height="{height-110}" rx="36" fill="none" stroke="#222" stroke-width="4"/>',
            f'<text x="{margin}" y="165" font-family="Arial, sans-serif" font-size="62" font-weight="700" fill="#111">{title}</text>',
            f'<text x="{margin}" y="235" font-family="Arial, sans-serif" font-size="32" fill="#333">{instruction}</text>',
            f'<text x="{width-margin}" y="165" text-anchor="end" font-family="Arial, sans-serif" font-size="23" fill="#777">{_xml(AUDIENCE_PRESETS.get(page.get("audience_id"),{}).get("label",""))} · {_xml(DIFFICULTY_PROFILES.get(page.get("difficulty"),{}).get("label",""))}</text>']
    top=330; area_w=width-2*margin; area_h=height-top-margin

    if typ=="maze" and _grid_rect(c.get("grid") or []):
        grid=c["grid"]; rows=len(grid); cols=len(grid[0]); cell=min(area_w/cols,area_h/rows)*0.9; ox=(width-cell*cols)/2; oy=top+30
        for r,row in enumerate(grid):
            for col,v in enumerate(row):
                x=ox+col*cell; y=oy+r*cell; fill="#222" if v not in (0,".","S","E",False) else "white"
                pieces.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{cell:.1f}" height="{cell:.1f}" fill="{fill}" stroke="#999" stroke-width="2"/>')
        s=c.get("start",[0,0]); e=c.get("end",[rows-1,cols-1])
        for label,pos in (("INÍCIO",s),("FIM",e)):
            rr,cc=pos; x=ox+(cc+.5)*cell; y=oy+(rr+.62)*cell
            pieces.append(f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="middle" font-family="Arial" font-size="{max(16,cell*.18):.1f}" font-weight="700">{label}</text>')
    elif typ=="word_search" and _grid_rect(c.get("grid") or []):
        grid=c["grid"]; rows=len(grid); cols=len(grid[0]); cell=min(area_w/cols,area_h*.68/rows); ox=(width-cell*cols)/2; oy=top+20
        for r,row in enumerate(grid):
            for col,v in enumerate(row):
                x=ox+col*cell; y=oy+r*cell
                pieces.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{cell:.1f}" height="{cell:.1f}" fill="white" stroke="#333" stroke-width="2"/>')
                pieces.append(f'<text x="{x+cell/2:.1f}" y="{y+cell*.68:.1f}" text-anchor="middle" font-family="Arial" font-size="{cell*.46:.1f}" font-weight="700">{_xml(v)}</text>')
        words="   •   ".join(map(str,c.get("words") or [])); pieces.append(f'<text x="{margin}" y="{oy+cell*rows+75:.1f}" font-family="Arial" font-size="30">Palavras: {_xml(words)}</text>')
    elif typ=="sudoku" and _grid_rect(c.get("board") or []):
        board=c["board"]; n=len(board); cell=min(area_w/n,area_h*.8/n); ox=(width-cell*n)/2; oy=top+40; box=int(math.isqrt(n))
        for r,row in enumerate(board):
            for col,v in enumerate(row):
                x=ox+col*cell; y=oy+r*cell; sw=5 if (r%box==0 or col%box==0) else 2
                pieces.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{cell:.1f}" height="{cell:.1f}" fill="white" stroke="#222" stroke-width="{sw}"/>')
                if v: pieces.append(f'<text x="{x+cell/2:.1f}" y="{y+cell*.68:.1f}" text-anchor="middle" font-family="Arial" font-size="{cell*.5:.1f}" font-weight="700">{v}</text>')
    elif typ=="crossword" and c.get("entries"):
        cells={}; numbers={}; no=1
        for e in c["entries"]:
            ans=re.sub(r"\s+","",str(e.get("answer","")).upper()); r=int(e.get("row",0)); col=int(e.get("col",0)); direction=e.get("direction")
            numbers.setdefault((r,col),no); no+=1
            for i,ch in enumerate(ans): cells[(r,col+i) if direction=="across" else (r+i,col)]=ch
        if cells:
            minr=min(r for r,_ in cells); maxr=max(r for r,_ in cells); minc=min(c for _,c in cells); maxc=max(c for _,c in cells)
            rows=maxr-minr+1; cols=maxc-minc+1; cell=min(area_w*.62/cols,area_h*.65/rows); ox=margin; oy=top+30
            for (r,col) in cells:
                x=ox+(col-minc)*cell; y=oy+(r-minr)*cell
                pieces.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{cell:.1f}" height="{cell:.1f}" fill="white" stroke="#222" stroke-width="3"/>')
                if (r,col) in numbers: pieces.append(f'<text x="{x+7:.1f}" y="{y+18:.1f}" font-family="Arial" font-size="15">{numbers[(r,col)]}</text>')
            clue_x=ox+cell*cols+55; cy=oy+25
            for i,e in enumerate(c["entries"],1):
                pieces.append(f'<text x="{clue_x:.1f}" y="{cy:.1f}" font-family="Arial" font-size="25">{i}. {_xml(e.get("clue",""))}</text>'); cy+=42
    else:
        y=top+45
        if typ in {"math","simple_math"}:
            for i,it in enumerate(c.get("items") or [],1): pieces.append(f'<text x="{margin}" y="{y}" font-family="Arial" font-size="42">{i}. {_xml(it.get("expression",""))} = __________</text>'); y+=90
        elif typ in {"trivia","reading_qa"}:
            for i,q in enumerate(c.get("questions") or [],1):
                pieces.append(f'<text x="{margin}" y="{y}" font-family="Arial" font-size="34">{i}. {_xml(q.get("question",""))}</text>'); y+=55
                pieces.append(f'<line x1="{margin}" y1="{y}" x2="{width-margin}" y2="{y}" stroke="#777" stroke-width="2"/>'); y+=95
        elif typ in {"journaling","bible_study"}:
            for i,q in enumerate(c.get("prompts") or [],1):
                pieces.append(f'<text x="{margin}" y="{y}" font-family="Arial" font-size="32">{i}. {_xml(q)}</text>'); y+=65
                for _ in range(4): pieces.append(f'<line x1="{margin}" y1="{y}" x2="{width-margin}" y2="{y}" stroke="#aaa" stroke-width="2"/>'); y+=55
                y+=45
        else:
            pieces.append(f'<rect x="{margin}" y="{top+30}" width="{area_w}" height="{area_h*.68:.0f}" rx="28" fill="none" stroke="#999" stroke-width="3" stroke-dasharray="14 10"/>')
            pieces.append(f'<text x="{width/2}" y="{top+area_h*.34:.0f}" text-anchor="middle" font-family="Arial" font-size="34" fill="#666">Área visual da atividade / personagens</text>')
    pieces.append(f'<text x="{margin}" y="{height-85}" font-family="Arial" font-size="20" fill="#888">FaithBloom Preview · gabarito não impresso nesta folha</text>')
    pieces.append('</svg>')
    return "".join(pieces)
