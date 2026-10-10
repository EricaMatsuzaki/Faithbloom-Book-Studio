"""Perfil canônico da Mel para o FaithBloom Character Universe.

Este módulo guarda a assinatura visual aprovada pela autora em formato
estruturado e reutilizável. A referência visual aprovada continua sendo a fonte
primária para microdetalhes; o texto abaixo funciona como Identity Lock e Prompt
Mestre Visual para reduzir deriva entre gerações.
"""
from __future__ import annotations

from copy import deepcopy

MEL_PROFILE_SCHEMA = "faithbloom.character.mel.v1"
MEL_CHARACTER_NAME = "Mel"

MEL_EYE_SIGNATURE = (
    "Olhos muito grandes, arredondados/levemente ovais e infantis, com íris verde profunda em gradiente: "
    "verde bem escuro na região superior e verde mais claro, luminoso e vivo na região inferior; pupila grande e muito escura; "
    "acabamento vítreo com profundidade. Em CADA olho, preservar a assinatura de reflexos: uma estrela branca de cinco pontas "
    "claramente visível, um pequeno coração vermelho, pequenos pontos brancos de luz e delicados microbrilhos verde-brancos. "
    "Contorno ocular escuro e cílios superiores finos, longos e delicados. A posição fina dos reflexos deve seguir a imagem Master aprovada; "
    "não transformar os olhos em olhos verdes genéricos e não remover estrela, coração, gradiente ou profundidade."
)

MEL_HEART_CHEEK_BLUSH = (
    "Em cada bochecha existe um blush canônico em DUAS CAMADAS: primeiro um esfumado/halo rosado-coral suave, difuso, "
    "airbrushed e naturalmente integrado à pelagem; por cima desse esfumado aparece um coração rosado-coral mais definido, "
    "ainda delicado e sem borda dura. O resultado deve parecer parte harmoniosa do rosto, nunca adesivo, carimbo, maquiagem pesada "
    "ou coração chapado. Manter um coração em cada bochecha, equilibrados e simétricos conforme a referência Master."
)

MEL_BOW_SIGNATURE = (
    "Laço grande e delicado de tecido na cabeça, centralizado entre as orelhas, com volume macio, nó central e dobras suaves. "
    "A PRESENÇA, o formato geral e a posição do laço fazem parte da identidade; a COR é contextual e pode mudar conforme a história. "
    "Cor-base/padrão: rosa. Em histórias de Natal, usar vermelho quando solicitado. Outras cores só quando a direção narrativa autorizar."
)

MEL_MASTER_DESCRIPTION = (
    "Mel é uma gatinha filhote creme/pêssego claro, extremamente doce e expressiva, com rosto infantil arredondado, "
    "pelagem macia e felpuda, focinho e peito mais claros, pequeno nariz rosado, orelhas triangulares felpudas, "
    "patas delicadas com almofadinhas rosadas e cauda fofa. Sua identidade facial é definida principalmente pelos olhos verdes "
    "assinados, pelo blush de coração em duas camadas e pelo laço delicado na cabeça. O acabamento visual deve ser premium, "
    "limpo, acolhedor, suave e consistente com literatura infantil ilustrada de alta qualidade."
)

MEL_VISUAL_PROMPT_MASTER = f"""PROMPT MESTRE VISUAL OFICIAL — MEL

FONTE PRIMÁRIA DE IDENTIDADE
Use sempre a imagem Color Master aprovada da Mel como referência visual principal quando ela estiver disponível. O texto abaixo é um Identity Lock complementar: preserve microgeometria do rosto, proporções e assinatura visual da referência; não redesenhe a personagem do zero quando houver Master.

IDENTIDADE CANÔNICA
{MEL_MASTER_DESCRIPTION}

MEL EYE SIGNATURE™ — BLOQUEIO FORTE
{MEL_EYE_SIGNATURE}

HEART CHEEK BLUSH™ — BLOQUEIO FORTE
{MEL_HEART_CHEEK_BLUSH}

BOW SIGNATURE™ — FORMA FIXA, COR CONTEXTUAL
{MEL_BOW_SIGNATURE}

REGRAS DE CONSISTÊNCIA
- Preserve espécie, idade visual de filhote, formato do rosto, pelagem creme/pêssego, focinho claro, nariz rosado e proporções fundamentais.
- Preserve rigorosamente a assinatura dos olhos e das bochechas; esses detalhes têm prioridade alta na identidade da Mel.
- O laço deve permanecer na cabeça, salvo decisão autoral explícita; sua cor pode variar quando a cena/história autorizar.
- Emoção, expressão, pose, ação, figurino, cenário, estação, festividade e iluminação podem variar sem alterar o Character DNA.
- Psicologia das cores atua no cenário, iluminação, atmosfera e acessórios variáveis; não recolora olhos, pelagem, nariz ou marcas canônicas.
- Não adicionar texto, letras, logotipos, marcas d'água ou símbolos aleatórios à arte.
- Não transformar o coração da bochecha em círculo, sardas, adesivo ou ícone plano.
- Não simplificar a assinatura ocular para um único brilho genérico.
- Não adultizar a Mel, não alterar sua espécie e não substituir seu rosto por uma gatinha visualmente diferente.

QUALIDADE VISUAL
Ilustração infantil premium, acabamento polido, formas suaves, pelagem delicadamente detalhada, leitura facial clara, olhos luminosos sem aparência plástica excessiva, anatomia limpa e pose natural. A imagem deve continuar reconhecível como a MESMA Mel em diferentes cenas.
""".strip()

MEL_CHARACTER_DNA = {
    "schema": MEL_PROFILE_SCHEMA,
    "descricao_master": MEL_MASTER_DESCRIPTION,
    "caracteristicas_bloqueadas": (
        f"{MEL_MASTER_DESCRIPTION} MEL EYE SIGNATURE: {MEL_EYE_SIGNATURE} "
        f"HEART CHEEK BLUSH: {MEL_HEART_CHEEK_BLUSH} BOW SIGNATURE: {MEL_BOW_SIGNATURE}"
    ),
    "campos_bloqueados": {
        "especie": "gatinha filhote",
        "pelagem_paleta_base": "creme/pêssego claro, com focinho, peito e áreas internas mais claras; nariz e almofadinhas rosados",
        "rosto": "arredondado, infantil, doce e delicado",
        "olhos": MEL_EYE_SIGNATURE,
        "bochechas": MEL_HEART_CHEEK_BLUSH,
        "laco_forma_posicao": "laço grande e delicado de tecido, centralizado entre as orelhas; presença, formato geral e posição canônicos",
        "nariz": "pequeno, delicado e rosado",
        "identidade_visual": "premium, suave, acolhedora, infantil e emocionalmente expressiva",
    },
    "assinaturas_visuais": {
        "mel_eye_signature": MEL_EYE_SIGNATURE,
        "heart_cheek_blush": MEL_HEART_CHEEK_BLUSH,
        "bow_signature": MEL_BOW_SIGNATURE,
    },
    "visual_prompt_master": MEL_VISUAL_PROMPT_MASTER,
    "variaveis_permitidas": [
        "pose",
        "acao",
        "expressao",
        "emocao",
        "figurino",
        "acessorios_temporarios",
        "cor_acessorio_identitario",
        "cenario",
        "estacao",
        "festividade",
    ],
    "regras_variaveis": {
        "cor_acessorio_identitario": (
            "Refere-se principalmente à cor do laço da Mel. A cor pode mudar conforme história/tema; "
            "presença, formato e posição do laço permanecem canônicos. Rosa é a cor-base; Natal pode usar vermelho."
        )
    },
}


def mel_character_dna() -> dict:
    """Retorna cópia independente do DNA canônico da Mel."""
    return deepcopy(MEL_CHARACTER_DNA)


def mel_visual_prompt(*, bow_color: str = "", scene_direction: str = "") -> str:
    """Monta o Prompt Mestre da Mel com variáveis contextuais opcionais."""
    extras = []
    if str(bow_color or "").strip():
        extras.append(
            "COR CONTEXTUAL DO LAÇO AUTORIZADA NESTA GERAÇÃO: "
            + str(bow_color).strip()
            + ". Mude apenas a cor; preserve formato, tecido, volume e posição do laço."
        )
    if str(scene_direction or "").strip():
        extras.append("DIREÇÃO DA CENA: " + str(scene_direction).strip())
    if not extras:
        return MEL_VISUAL_PROMPT_MASTER
    return MEL_VISUAL_PROMPT_MASTER + "\n\n" + "\n".join(extras)
