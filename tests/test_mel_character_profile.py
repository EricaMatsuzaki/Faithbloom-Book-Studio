from character_universe import personagem_para_prompt
from mel_character_profile import (
    MEL_CHARACTER_DNA,
    MEL_EYE_SIGNATURE,
    MEL_HEART_CHEEK_BLUSH,
    MEL_VISUAL_PROMPT_MASTER,
    mel_character_dna,
    mel_visual_prompt,
)
from scene_color_controls import build_restoration_prompt


def test_mel_eye_signature_keeps_star_heart_and_green_gradient():
    text = MEL_EYE_SIGNATURE.lower()
    assert "estrela branca de cinco pontas" in text
    assert "pequeno coração vermelho" in text
    assert "gradiente" in text
    assert "verde" in text
    assert "vítreo" in text


def test_mel_blush_is_two_layer_not_flat_heart():
    text = MEL_HEART_CHEEK_BLUSH.lower()
    assert "duas camadas" in text
    assert "esfumado" in text
    assert "coração" in text
    assert "nunca adesivo" in text
    assert "coração chapado" in text


def test_mel_bow_color_is_contextual_but_shape_is_locked():
    dna = mel_character_dna()
    assert "cor_acessorio_identitario" in dna["variaveis_permitidas"]
    locked = dna["campos_bloqueados"]["laco_forma_posicao"].lower()
    assert "formato" in locked
    assert "posição" in locked
    rule = dna["regras_variaveis"]["cor_acessorio_identitario"].lower()
    assert "natal" in rule
    assert "vermelho" in rule
    assert "rosa" in rule


def test_visual_prompt_can_authorize_red_christmas_bow_without_unlocking_identity():
    prompt = mel_visual_prompt(
        bow_color="vermelho para o Natal",
        scene_direction="Mel perto de uma árvore de Natal",
    )
    assert "COR CONTEXTUAL DO LAÇO AUTORIZADA" in prompt
    assert "vermelho para o Natal" in prompt
    assert "Mude apenas a cor" in prompt
    assert "MEL EYE SIGNATURE" in prompt
    assert "HEART CHEEK BLUSH" in prompt


def test_character_universe_injects_mel_visual_prompt_master():
    character = {
        "nome": "Mel",
        "dna": MEL_CHARACTER_DNA,
        "metadata": {"usos_permitidos": ["story"]},
    }
    prompt = personagem_para_prompt(
        character,
        modo="color",
        contexto="story",
        variaveis={"cor_acessorio_identitario": "vermelho"},
    )
    assert "PROMPT MESTRE VISUAL OFICIAL" in prompt
    assert MEL_VISUAL_PROMPT_MASTER in prompt
    assert "cor_acessorio_identitario" in prompt
    assert "presença, forma e posição canônicas permanecem bloqueadas" in prompt


def test_restoration_prompt_also_inherits_mel_visual_master():
    prompt = build_restoration_prompt(
        "controlled_remaster",
        dna=MEL_CHARACTER_DNA,
        request="deixe o laço vermelho para o Natal",
    )
    assert "PROMPT MESTRE VISUAL OFICIAL DO PERSONAGEM" in prompt
    assert MEL_VISUAL_PROMPT_MASTER in prompt
    assert "cor_acessorio_identitario" in prompt
