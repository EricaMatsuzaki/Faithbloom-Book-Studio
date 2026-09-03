# Refinamento 07 — Publishing Platform Engine

## Objetivo
Transformar o FaithBloom de um fluxo orientado principalmente ao KDP em um motor editorial multicanal baseado em **Book Master → edições derivadas**, sem redimensionar, cortar ou reutilizar arquivos de outra plataforma silenciosamente.

## O que entrou

### Platform Registry expansível
Perfis pré-configurados para Amazon KDP, IngramSpark, Lulu, Kobo Writing Life, Apple Books, Google Play Books, Draft2Digital, Barnes & Noble Press e perfis de canal para StreetLib, PublishDrive, BookBaby, Blurb, Etsy, Hotmart, Kiwify, Gumroad e Payhip.

O Registry distingue:
- **verified**: requisitos carregados a partir de documentação oficial disponível na data registrada;
- **profile_only**: canal conhecido, mas sem preflight numérico completo carregado;
- **custom**: plataforma cadastrada pela usuária.

Cada perfil guarda `spec_version`, `last_verified`, `source_urls`, capacidades e formatos aceitos.

### Adicionar nova plataforma
O dashboard permite cadastrar uma plataforma personalizada, seus produtos, formatos, documentação e data de verificação. Ela passa a aparecer imediatamente entre os destinos possíveis.

### Atualização versionada de especificações
Plataformas oficiais podem receber **overrides versionados** sem apagar o baseline do código. Antes de cada atualização, o Registry guarda um snapshot no histórico. Isso permite atualizar regras quando uma plataforma muda sem reescrever projetos antigos.

### Book Master e plano de derivados
O usuário informa o Master (trim, páginas, interior, binding, bleed, idioma, ISBN, KDP Select) e escolhe destinos. O motor retorna:
- compatível;
- revisar;
- bloqueado;
- trim mais próximo quando há presets carregados;
- necessidade de novo layout;
- formato de saída esperado.

**Política obrigatória:** `never_resize_silently`.

### Cálculo de impressão
- KDP: reaproveita o motor de capa já existente e mantém recomendação de conferência na calculadora oficial.
- Lulu paperback: usa a fórmula de lombada publicada pela Lulu, com recomendação de confirmar no template oficial.
- IngramSpark e outros perfis dependentes de template: **não inventa largura de lombada**; retorna `official_template_required`.

### EPUB 3
Novo `epub_exporter.py` gera:
- `fixed` (pre-paginated) para picture books;
- `reflowable` para leitura fluida.

O exportador cria container EPUB 3, OPF, NAV, CSS e assets. Ele não marca EPUBCheck como aprovado automaticamente. Para Apple Books, o preflight mantém EPUBCheck como bloqueio.

O exportador também preserva a regra do Refinamento 06: texto bíblico separado não é injetado automaticamente; por padrão é usada apenas a referência aprovada no `state`.

### Preflight por destino
O motor valida o que realmente consegue observar, por exemplo:
- produto suportado;
- versão da especificação;
- arquivo PDF do miolo;
- capa física;
- EPUB;
- EPUBCheck quando exigido pelo perfil;
- contagem de páginas;
- target PPI;
- ISBN próprio ausente;
- KDP Select bloqueando distribuição digital concorrente.

### Pacote multicanal
`gerar_pacote_multiplataforma()` cria um ZIP de controle com Master, metadados, manifestos e preflight por destino. Um arquivo ausente nunca é substituído por outro incompatível apenas para “completar” o pacote.

## Fontes oficiais carregadas no Registry (verificação: 2026-09-03)
- Amazon KDP: cover calculator / submission guidelines.
- IngramSpark: file requirements / title processing.
- Lulu: Create, Full Bleed e Book Creation Guide.
- Kobo Writing Life: file types/sizes e EPUB.
- Apple Books for Authors: publishing portal e preparation.
- Google Play Books Partner Center: file formats/guidelines.
- Draft2Digital: FAQ / Knowledge Base.
- Barnes & Noble Press: cover template generator / policy updates.

Perfis `profile_only` devem ser revalidados/importados antes de serem usados para um preflight técnico completo.
