"""Read-only trace of declared agent entrypoints and production call sites.

AST presence proves a connection in source, not that a browser executed it.
Behavioral evidence is reported separately and never implies live quality.
This inventory executes no agent, provider, subprocess or external action.
"""
from __future__ import annotations

import ast
from pathlib import Path

from agent_skills import all_agent_profiles, INHERITED_MODULE_PROFILES, profile_module_path, role_readiness

INHERITED_ENTRYPOINTS = {
    'estilos_narrativos.py': ('gerar_comparativo_estilos', 'gerar_estilo_adicional'),
    'roteirista_autoral.py': ('gerar_proposta_roteirista', 'gerar_versao_autoral_roteirista'),
    'formato_quadrinhos.py': ('gerar_roteiro_quadrinhos',),
}

# A concrete downstream artifact, not a promise that the next job runs itself.
RESULT_CONSUMERS = {
    'idea_generator': '"pages/1_📖_Criar_do_Zero.py" and "pages/39_✍️_Historia_4_Estilos.py": author-selected premise',
    'theme_curator': 'agents/roteirista.py: tema, emotion and reference candidate; biblical_reference_validator.py: separate approval',
    'storyteller': 'agents/revisor.py and emotional_color_director.py: manuscript review and scene directions',
    'story_editor': '"pages/1_📖_Criar_do_Zero.py" and "editorial_remaster_revision.py": one scene plus explicit persistence',
    'story_reviewer': 'graph.py: bounded rewrite loop or human review; manuscript approval before paid production',
    'character_creator': 'pages/1_📖_Criar_do_Zero.py: candidate DNA and human-approved visual reference',
    'photo_to_character': 'pages/1_📖_Criar_do_Zero.py: consented derived candidate, never automatic Master',
    'character_variations': '"pages/1_📖_Criar_do_Zero.py" and "retomar_fluxo.py": gallery followed by explicit approval',
    'illustrator': 'renderizador_editorial.py: cenas_imagem; agents/ilustrador.py: history and separate approval',
    'coloring_idea_generator': 'coloring_studio.py: selected concept and editable page descriptions',
    'line_art_specialist': 'coloring_studio.py: versioned pages; rendering and Coloring Doctor require separate review',
    'coloring_activity_creator': 'renderizador_editorial.py: paginas_colorir; checkpoints preserve completed pages',
    'coloring_layout': 'coloring_studio.py and agents/line_art_colorir.py: physical PDF order and exact cover page count',
    'sales_synopsis': 'agents/capa.py and pacote_publicacao.py: backcover and metadata without automatic publication',
    'market_keywords': 'pacote_publicacao.py and bestseller_readiness.py: candidate metadata with observed/inferred provenance',
    'market_categories': 'pacote_publicacao.py and bestseller_readiness.py: candidate metadata with observed/inferred provenance',
    'marketing_launch': 'pages/7_🚀_Lançamento.py: draft materials displayed; no automatic message or posting',
    'cover_specialist': 'capa_profissional.py and pages/7_🚀_Lançamento.py: separate art, typography and print preflight',
    'diagrammer': 'renderizador_editorial.py: physical page order; qualidade_impressao.py: independent preflight',
    'dedication': 'renderizador_editorial.py: dedication; translation_localization.py: protected personal names',
    'translator_localizer': 'translation_localization.py: per-locale derivative and structural review; export requires approval',
    'audiobook_director': 'agents/audiobook.py:narracao_node: exact approved words plus performance markings',
    'narrator': 'pages/1_📖_Criar_do_Zero.py: per-scene audio; Audiobook Studio provides separate listening/QA',
    'pedagogical_editor': 'agents/complementos_editoriais.py: validated complements; renderizador_editorial.py: editorial pages',
    'scene_director': 'visual_execution.py and comic_studio.py: chosen A/B/C followed by explicit image generation',
    'saas_automation_engineer': 'pages/37_🧠_Agent_Skills_Bestseller_Readiness.py: evidence-based diagnostic, no automatic patch/deploy',
    'deep_code_review_engineer': 'agents/engenheiro_saas_automacao.py: verified code citations; independent regression/runtime proof required',
    'ai_governance': 'governance.py:run_all_diagnostics and governance_runtime.py: stored findings before guarded generation',
    'data_governance': 'governance.py:run_all_diagnostics and governance_runtime.py: consent/classification before guarded generation',
    'it_governance': 'governance.py:run_all_diagnostics and governance_runtime.py: operational evidence and release limits',
    'cybersecurity': 'governance.py:run_all_diagnostics and governance_runtime.py: sanitized security findings, no automatic attack or remediation',
}


def _qualified(node, aliases):
    if isinstance(node, ast.Name):
        return aliases.get(node.id, node.id)
    if isinstance(node, ast.Attribute):
        return _qualified(node.value, aliases) + '.' + node.attr
    return ''


def _source_calls(path, root):
    tree = ast.parse(path.read_text(encoding='utf-8'))
    aliases = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            for name in node.names:
                aliases[name.asname or name.name] = node.module + '.' + name.name
        elif isinstance(node, ast.Import):
            for name in node.names:
                aliases[name.asname or name.name.split('.')[0]] = name.name if name.asname else name.name.split('.')[0]
    return [(_qualified(node.func, aliases), {'path': path.relative_to(root).as_posix(), 'line': node.lineno})
            for node in ast.walk(tree) if isinstance(node, ast.Call)]


def build_execution_inventory(root: str | Path | None = None) -> dict:
    """Trace first-party source only; never inspect customer data or credentials."""
    folder = Path(root or Path(__file__).resolve().parent)
    calls = []
    for directory in (folder, folder / 'agents', folder / 'pages'):
        for path in sorted(directory.glob('*.py')):
            if path.is_symlink():
                continue
            calls.extend(_source_calls(path, folder))
    rows = []
    for profile in all_agent_profiles():
        role = profile['role_id']
        module_path = profile_module_path(profile, folder)
        module = module_path.relative_to(folder).with_suffix('').as_posix().replace('/', '.')
        entrypoints = [module + '.' + name for name in profile['runtime_contract']['entrypoints']]
        inherited = []
        for filename, roles in INHERITED_MODULE_PROFILES.items():
            if role in roles:
                inherited.extend('agents.' + filename[:-3] + '.' + fn for fn in INHERITED_ENTRYPOINTS[filename])
        callers = [{'callee': name, **source} for name, source in calls if name in entrypoints + inherited]
        # Dynamic dispatch is explicit and separate from a statically resolved call.
        dynamic = []
        if role in {'ai_governance', 'data_governance', 'it_governance', 'cybersecurity'}:
            dynamic = ['governance.py:run_all_diagnostics imports each approved governance module then calls run_diagnostic']
        readiness = role_readiness(role, root=folder)
        rows.append({
            'role_id': role, 'name': profile['name'], 'execution_kind': profile['execution'],
            'entrypoints': entrypoints, 'inherited_entrypoints': inherited,
            'static_call_sites': callers, 'explicit_dynamic_dispatch': dynamic,
            'result_consumer': RESULT_CONSUMERS.get(role, 'Not traced; requires independent review.'),
            'configuration_status': readiness['status'], 'configuration_errors': readiness['errors'],
            'source_connection_found': bool(callers or dynamic),
            'behavioral_test': f'tests/test_agent_execution_alignment.py::test_each_job_executes_its_real_entrypoint_and_returns_reviewable_output[{role}]',
            'test_result': 'not_executed_by_inventory', 'output_quality_validated': False,
            'live_provider_validated': False,
        })
    return {
        'schema': 'faithbloom.agent-execution-trace.v1', 'role_count': len(rows),
        'evidence_scope': 'source trace; separate behavioral test references; no provider calls or deployed execution',
        'fully_functional_certified': False, 'rows': rows,
        'limits': [
            'Source call sites and valid skills are necessary configuration, not proof of content excellence.',
            'Test doubles prove context transfer and output contracts, not the quality of commercial provider responses.',
            'Reading/listening/visual review and live credentials must be checked independently for each product.',
            'Engineering agents produce diagnostics and verified review hypotheses; repository changes, tests and deploy require an authorized executor.',
            'A declared required_handoff is not an automatic dispatcher and never authorizes a paid or publishing action.',
        ],
    }
