# FaithBloom Book Studio 2.0 — Refinamento 10

## FaithBloom Quality Guardian
- revisor final independente, separado dos agentes de criação;
- 12 domínios: editorial, legibilidade, Bible Guard/contexto, personagens, emoção/cores, tradução, atividades, audiobook, capa, impressão, plataformas e consistência multimodal;
- severidades 🔴 bloqueante, 🟠 recomendado, 🟡 atenção e 🔵 sugestão;
- cada alerta traz local, achado, motivo, sugestão e evidência;
- nenhuma correção silenciosa e nenhum percentual de qualidade inventado;
- correções marcadas como resolvidas exigem rerun para desaparecer do gate;
- bloqueios não podem ser ignorados por justificativa;
- Activity QA inválido é bloqueante; audiobook exige aprovação por escuta;
- Bible Guard preservado e revisão teológica trabalha com contexto/referência, sem traduzir versículo;
- proxy de legibilidade explicitamente não é teste com crianças reais;
- segunda opinião independente opcional por IA, sem editar a obra;
- fingerprint evita reutilizar revisão especializada em conteúdo alterado;
- certificado INTERNO só após decisões e aprovação final da autora;
- certificado não substitui Previewer, EPUBCheck, prova física ou validação externa.

---

# FaithBloom Book Studio 2.0 — Refinamento 08

## Activity Book Studio — Kids, Teens & Adults
- públicos 3–4, 5–6, 7–8, 9–12, Teen, Adulto, 60+ e custom;
- dificuldade Relaxante, Moderado, Desafiador e Expert independente da idade;
- catálogo amplo de atividades infantis e adultas;
- QA objetivo com validadores de solução/gabarito;
- aprovação obrigatória da autora folha por folha;
- versões A/B/C e "Modificar somente isto" com campos preservados;
- integração com Character Universe em contexto Activity;
- Story → Activities com Bible Guard preservado.
- Preview vetorial SVG para revisar a folha antes da montagem final.
- Activity Designer opcional por IA gera apenas rascunho estrutural, nunca aprovação automática.

---

# FaithBloom Book Studio 2.0 — Refinamento 07

## Publishing Platform Engine
- Platform Registry expansível e versionado;
- perfis técnicos principais + perfis de canal;
- cadastro de novas plataformas;
- overrides de especificações com histórico;
- Book Master → planos de edições derivadas;
- política `never_resize_silently`;
- preflight por destino e proteção KDP Select;
- geometria KDP/Lulu e template-required quando a lombada não pode ser inferida com segurança;
- exportador EPUB 3 fixed-layout/reflowable;
- Apple EPUBCheck permanece bloqueio explícito;
- pacote multicanal com manifesto por plataforma.

---

# FaithBloom Book Studio 2.0.0-rc1

## Fase 16 — QA Final e Estabilização

Esta entrega consolida as Fases 1–15 e prepara o projeto para o primeiro smoke test completo no Streamlit Cloud.

### Quality gate concluído

- 69 arquivos Python analisados sintaticamente.
- 13 rotas internas do Streamlit verificadas.
- Requirements essenciais verificados.
- Varredura offline de padrões comuns de chaves/segredos: sem chave real detectada.
- Projeto piloto `historia_natal.py`: 22 cenas e 3 personagens carregados pelo diagnóstico.
- 20 testes automatizados aprovados.
- Caches Python e logs de execução removidos do pacote de release.
- `.gitignore` reforçado para Secrets, caches e outputs temporários.

### O que ainda precisa ser validado no ambiente real

A release é uma **RC (Release Candidate)**, não a versão estável final. Antes de marcar `v2.0.0`, faça no Streamlit Cloud:

1. abrir todas as páginas do dashboard;
2. confirmar Secrets e storage persistente;
3. testar uma chamada mínima da OpenRouter;
4. gerar uma referência de personagem;
5. gerar e aprovar uma única cena piloto;
6. testar variação/restauração da cena;
7. salvar e reabrir o projeto;
8. gerar PDF de prova e capa de prova;
9. testar a retomada do `historia_natal.py` sem regenerar conteúdo aprovado;
10. revisar os outputs no KDP Previewer antes de publicação real.

### Política da release

Nenhum conteúdo é publicado automaticamente. A autora continua aprovando história, personagens, ilustrações, arquivos finais e publicação.

---

## Refinamento 04 — Restoration Studio + Book Doctor Integration

- Book Doctor ampliado para Story, Coloring/Line Art, Activity e outros projetos.
- Upload de capa em imagem ou PDF/wrap.
- Manifest SHA-256 dos originais.
- Novo Restoration Studio com Original × Remastered.
- Melhoria técnica determinística sem sobrescrever o original.
- Limpeza de line art com preto/branco puro, redução de ruído e ajuste de espessura.
- Line Art QA objetivo.
- Integração com Character Master e Style DNA.
- Character Master visual pode ser enviado como referência adicional na restauração por IA.
- Histórico de decisões e versões derivadas com aprovação humana.
- 36 testes automatizados aprovados nesta entrega incremental.


---

## Refinamento 06 — Translation & Localization Studio

- Localização por locale/mercado: en-US, en-CA, en-GB, en-AU, en-INT e demais mercados suportados.
- Modos Fiel, Natural Infantil e Localização Cultural.
- Glossário protegido da coleção e nomes oficiais preservados.
- Onomatopoeia & Sound Localization com intensidade baixa/equilibrada/expressiva.
- Bible Guard: versículos nunca são traduzidos livremente pela IA; texto bíblico exige versão/fonte e aprovação da autora.
- Sanitização de campos bíblicos eventualmente gerados pelo modelo.
- Histórico A/B/C por locale.
- Revisor Linguístico Independente e QA estrutural Master × localização.
- Auditoria de traduções existentes por camada de texto do PDF, sem OCR automático.
- Nova rota no dashboard: Translation & Localization Studio.
- QA do Refinamento 06: 57 testes pytest aprovados; suíte unittest/release com 37 testes aprovados; 94 arquivos Python e 21 rotas verificados.

---

# FaithBloom Book Studio 2.0 — Refinamento 09

## Audiobook Studio Professional
- nova rota `🎧 Audiobook Studio Professional`;
- narrador único ou narrador + personagens;
- Voice Profiles reutilizáveis, favoritos e casting por speaker;
- modos Automático e Studio;
- AI Voice Director sem permissão para reescrever o texto aprovado;
- fingerprint e validação de integridade do roteiro de performance;
- dicionário de pronúncia provider-neutral;
- preview por cena e fila TTS com pause/resume/cancel;
- limite próprio para lotes de áudio e estimativa de custo;
- versões A/B/C, favoritos e aprovação por segmento;
- QA objetivo de áudio + escuta humana obrigatória;
- mix final com FFmpeg quando disponível;
- pacote de estúdio com clips, roteiro, pronúncia, QA e Master final;
- Bible Guard preservado: somente referência ou texto bíblico previamente aprovado.


---

## Refinamento 12 — Production Release & Project Hub

- painel único por Book Master;
- pipeline consolidado sem score fictício;
- detecção de Quality Gate/plano de distribuição obsoletos por fingerprint;
- matriz de edições por locale;
- próxima ação recomendada e links diretos aos Studios;
- snapshot JSON de release/acompanhamento;
- Hub read-only por padrão: não aprova nem altera o Book Master silenciosamente.

## Refinamento 14 — Production Deployment & Real E2E
- preparação explícita para Streamlit Cloud/produção;
- suporte de identidade via Streamlit OIDC (`st.user`) quando configurado;
- snapshot sanitizado de configuração;
- inventário local com SHA-256 e migração segura de storage com verificação de hash;
- health check e probe write/read/delete acionado manualmente;
- checklist de evidências Real E2E;
- novo gate que não confunde readiness de produção com tag Stable.

---

## Refinamento 15 — Stable Candidate & Cloud Launch Checklist

- versão interna avançada para `2.0.0-rc2`;
- manifest SHA-256 do código/configuração da candidata;
- evidências cloud obrigatórias com nota/referência, não apenas checkbox;
- Candidate Gate separado do Stable Promotion Gate;
- candidatas registradas e invalidadas quando o source fingerprint muda;
- plano de rollback não destrutivo;
- sign-off humano final obrigatório;
- Evidence Bundle auditável em ZIP;
- nenhuma tag, deploy ou publicação automática.

---

## Refinamento 16 — Asset Library & Media Manager

- nova rota visual `🖼️ Asset Library & Media Manager`;
- schema de asset v2 compatível com a Galeria existente;
- busca rica e filtros por tipo, mídia, personagem, coleção, livro, emoção, estação, aprovação, Master e coleção virtual;
- grade grande/compacta/lista com paginação e thumbnails persistentes;
- favoritos, aprovação, Character/Color/Line Art/Cover Master e Style Reference;
- versões relacionadas sem apagar original;
- coleções virtuais sem duplicar arquivos;
- seleção múltipla e ações em lote;
- rastreio sob demanda “onde este asset é usado?”;
- proteção contra exclusão de Masters/originais/vínculos;
- detecção de possíveis duplicatas por fingerprint;
- Storage Manager e metadados técnicos sob demanda;
- handoff para Coloring Studio, Restoration Studio e Character Universe;
- 165 testes Pytest aprovados na suíte consolidada desta entrega.


## Refinamento 17 — Integration & UX Hardening + Author & Contributor Profiles
- perfis de autores/colaboradores reutilizáveis;
- autoria e coautoria por projeto com ordem explícita;
- snapshots de crédito e pseudônimos;
- metadata/capa/PDF/EPUB usam autoria estruturada;
- Project Hub registra projeto ativo;
- Integration & UX Center padroniza handoff de projeto/asset;
- schema de projeto v4;
- remoção de defaults funcionais que atribuíam todos os livros a uma única autora.

## Refinamento 18 — Family Profiles & Simplified Dashboard
- Perfis pessoais/familiares de workspace separados de autenticação e autoria editorial.
- Preferências por perfil: idioma, faixa etária, estilo visual, mercados e modo simplificado/avançado.
- Organização de projetos por responsável e compartilhamento sem alterar Book Master/fingerprint.
- Thumbnail opcional por projeto e projeto ativo persistido na sessão.
- Dashboard inicial refeito por objetivo, com continuação de projetos recentes e catálogo avançado recolhível.
- Novos Story Books, Coloring Books e versões retomadas podem ser vinculados automaticamente ao perfil ativo após o salvamento.
- Segurança explícita: perfis do workspace não substituem OIDC/ACL real de produção.


## Refinamento 19 — Real Pilot & Bug Fix
- auditoria rápida para PDFs reais sem decodificar todas as imagens;
- três perfis oficiais de piloto: Mel Master, Mel Natal e Bolufinhas/Cute Friends;
- detecção de forte sobreposição textual e repetição de referência bíblica na camada textual;
- Bug Registry com reteste obrigatório antes de `verified`;
- gate para próxima candidata a Stable.

## 2.0.0-rc4-prelaunch — Refinamento 20
- Gate final RC4 exige QA, pilotos reais, readiness de produção e Cloud E2E com evidências registráveis.
- Novo plano de validação cloud exportável e painel RC4 Final Pre-Launch.
- Stable continua bloqueado até sign-off humano e fingerprint vigente.
