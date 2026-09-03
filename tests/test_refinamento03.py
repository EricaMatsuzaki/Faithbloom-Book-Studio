from emotional_color_director import direcao_emocional, sugerir_arco, construir_mapa_emocional
from character_universe import normalizar_dna, personagem_para_prompt
from character_consistency import auditar_caracteristicas
from style_dna import style_para_prompt


def test_emotional_director_preserva_character_dna():
    d = direcao_emocional('tristeza')
    assert d['cor_principal'] == 'azul-claro'
    assert 'Nunca recolorir' in d['regra_character_dna']


def test_arco_tem_tamanho_pedido():
    arco = sugerir_arco('impaciencia', 24)
    assert len(arco) == 24
    assert arco[0]
    assert arco[-1] == 'gratidao'


def test_mapa_emocional_por_cena():
    mapa = construir_mapa_emocional([{'numero':1,'texto':'x','emocao':'alegria'},{'numero':2,'texto':'y','emocao':'medo'}])
    assert [x['numero'] for x in mapa] == [1,2]
    assert mapa[1]['direcao']['emocao_cromatica_base'] == 'medo'


def test_character_prompt_separa_bloqueado_de_variavel():
    p = {'nome':'Mel','dna':{'descricao_master':'gatinha creme','campos_bloqueados':{'olhos':'verdes','pelagem':'creme'},'variaveis_permitidas':['figurino','cenario','expressao']},'metadata':{'usos_permitidos':['story','coloring','activity','cover']}}
    prompt = personagem_para_prompt(p, 'color', {'figurino':'cachecol vermelho','cenario':'neve','pelagem':'azul'}, 'story')
    assert 'cachecol vermelho' in prompt
    assert 'neve' in prompt
    assert 'pelagem' in prompt and 'Ignorar alterações não autorizadas' in prompt
    assert 'olhos' in prompt


def test_consistency_score_so_com_evidencia():
    p = {'dna':{'campos_bloqueados':{'olhos':'verdes','pelagem':'creme','laco':'rosa'}}}
    r = auditar_caracteristicas(p, {'olhos':'verdes','pelagem':'bege'})
    assert r['avaliadas'] == 2
    assert r['score_evidenciado'] == 50.0
    assert 'laco' in r['nao_avaliadas']


def test_consistency_texto_livre_nao_inventa_score():
    p = {'dna':{'caracteristicas_bloqueadas':'gatinha creme, olhos verdes'}}
    r = auditar_caracteristicas(p, {})
    assert r['score_evidenciado'] is None


def test_style_prompt_contexto():
    s = {'nome':'Cute Friends','modo':'line_art','regras':{'contorno':'preto uniforme'},'usos_permitidos':['coloring','activity']}
    assert 'preto uniforme' in style_para_prompt(s,'coloring')
    assert style_para_prompt(s,'story') == ''
