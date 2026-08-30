"""
Exemplo de como rodar o pipeline usando a assinatura da OpenRouter para
texto E imagem (ver openrouter_client.py).

Antes de rodar:
    export OPENROUTER_API_KEY="sua-chave-aqui"
    pip install langgraph requests --break-system-packages
"""

from graph import construir_grafo
from state import LivroState, PersonagemDNA
from openrouter_client import chamar_llm, gerar_imagem, gerar_audio


def estado_inicial() -> LivroState:
    return LivroState(
        titulo="A Coragem de Léo",
        emocao_central="medo",
        aprendizado_cristao="confiar em Deus mesmo com medo",
        versiculo_referencia="Isaías 41:10",
        idioma_original="pt-BR",
        idiomas_alvo=["en", "es", "de", "ja"],
        paginas_minimas=24,
        personagens={
            "Leo": PersonagemDNA(
                nome="Léo",
                descricao_fixa=(
                    "filhote de leão, olhos grandes castanho-mel, "
                    "juba cor de mel curta e fofa, proporção cabeça "
                    "grande / corpo pequeno"
                ),
                imagem_referencia="",
                papel="protagonista",
            ),
        },
        lista_dedicatoria=[
            # Preencher com a lista fixa de pessoas da Erica.
        ],
    )


if __name__ == "__main__":
    grafo = construir_grafo(chamar_llm, gerar_imagem, gerar_audio)
    resultado = grafo.invoke(estado_inicial())
    print("Pacote pronto para publicação manual na KDP:", resultado["pacote_pronto"])
    print("Checklist:", resultado["checklist_kdp"])
