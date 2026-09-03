# Refinamento 02 — Book Doctor

Implementa a primeira camada do Book Doctor para livros existentes:
- upload de PDF do miolo e capa;
- preservação imutável do original em cópia;
- hash SHA-256 do original;
- inspeção de tamanho/contagem das páginas;
- extração de imagens incorporadas por página;
- medição de pixels e estimativa conservadora de PPI;
- medição de PPI efetivo da capa quando o tamanho final é informado;
- relatório JSON com alertas mensuráveis;
- lista explícita do que ainda exige revisão visual/editorial;
- base separada `remastered/` para futuras correções sem sobrescrever a edição publicada.

Importante: a versão atual não inventa pontuações de consistência visual. Character DNA, texto×imagem e comparação Antes×Depois serão ligados ao fluxo de revisão visual na evolução seguinte do Book Doctor.
