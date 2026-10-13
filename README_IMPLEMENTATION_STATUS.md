# Status de implementação do README — FaithBloom

**Auditoria de 14/10/2026.** Branch examinada: `feature/refinamento-24-prompt-mestre-compliance`, commit `9b0e6a8df0b69d972db205cc8f8bfcd44687637c`. README: blob `35a48bdf1f86d244d002418f8de09d7f0a33f85d`.

O README mistura recursos existentes, integrações incompletas e planos futuros. Esta matriz identifica o status de cada item e a implementação que sustenta a conclusão. Cadastro, skill ou prompt não equivalem a um produto completo. **Os status referem-se à base examinada; correções desta auditoria ainda são uma proposta de PR, sem deploy.**

## Como ler

| Status | Significado |
| --- | --- |
| Implementado | Código e entrada, contrato ou controle do escopo indicado existem. Não significa certificação de produção ou de qualidade de toda saída da IA. |
| Parcial | Há código relevante, mas falta executor, ligação entre módulos, etapa do produto ou correção de uma falha reproduzida. |
| Não implementado | Falta a capacidade específica; pode existir apenas nome, registro ou planejamento. |
| Validação pendente | Conector ou infraestrutura existe, mas operação real, configuração ou resultados não foram confirmados. |

O relatório não calcula uma porcentagem global: um registro de tipo de livro e um gerador completo não têm o mesmo peso. Há itens detalhados e requisitos repetidos no roadmap; eles não são contados como produtos independentes.

## O que mudou em relação às marcações do README

- **Já existe:** Home conversacional, inbox editorial, voz/microfone, clima/notícias, conector real do Google Calendar, registro dos 16 tipos e separação das origens. Algumas caixas continuam marcadas como futuras.
- **Existe parcialmente:** vários tipos têm cadastro/roteamento, mas não geração própria; há três candidatas de personagem e Diretor A/B/C em telas específicas, sem integração completa ao Orquestrador.
- **Falta implementar:** DNAs/fluxos especializados para conselhos, adolescentes, devocionais, estudos, workbook/guia/flashcards; Gmail, WhatsApp, fechamento do dia, lembretes e modos Copiloto/Gerente executáveis.
- **Ainda não integrado:** World visual A/B/C, execução central de cenas/ilustrações e Element Lock com editor/máscaras. A geração final de música/vídeo também não tem provedor conectado.
- **Há falhas na base examinada:** geração/recuperação de histórias, PDF e salvamento de colorir, tradução, áudio, identidade de projeto e locale de publicação. Foram reproduzidas e corrigidas na proposta descrita no [relatório funcional](ENGINEERING_FUNCTIONAL_AUDIT.md).

## Verificação funcional realizada

O diagnóstico local do agente SaaS/Full-Stack foi executado. O registro dos **27 papéis** passou; a auditoria estática final registrou **0 bloqueios e 46 avisos**. Os avisos incluem exceções silenciosas, ciclos/imports e colisões de prefixo; não são prova de que cada fluxo funciona.

O executor realizou os ensaios: **787 testes e 2 subtestes antes**, **894 testes e 2 subtestes após as correções propostas**, com **107 novos casos**. Todas as **59 aberturas de app/páginas** passaram no ensaio final. Também foram exercitadas **19 telas principais com livro/perfil sintéticos** e ações reais de Activity Book, Audiobook e Quality Guardian.

Não foram usadas APIs pagas, credenciais ou dados de produção. Gemini/OpenRouter/TTS, Supabase de produção, OAuth, microfone no navegador, fidelidade gráfica/literária real e aceite das lojas ainda requerem testes próprios. Não se infere que as credenciais estejam ausentes no Streamlit só porque não estavam disponíveis neste ambiente.

## Prioridades para concluir o produto

1. Revisar/integrar as correções propostas e validar um Story Book e um Coloring Book reais, com reabertura no Supabase, tradução e áudio.
2. Ligar o executor central aos Studios e aplicar seus gates em cada operação: história, personagens, cenários, orçamento e lote.
3. Implementar os DNAs e geradores dos produtos que hoje têm somente registro; completar produção/exportação de HQ.
4. Completar edição com Element Lock, World A/B/C e seleção efetiva dos quatro modos de geração visual.
5. Configurar/testar Calendar e definir o escopo de Gmail, WhatsApp, lembretes e rotinas pessoais; construir políticas executáveis de autonomia.

## Matriz detalhada — seções 1 a 10

### 1. Orquestrador e pré-voo visual

| Item | Status na base | Evidência | O que falta / correção proposta |
| --- | --- | --- | --- |
| Orquestrador central completo: intenção → execução de especialistas → QA → publicação | Parcial | jarvis_assistant.py::interpret_request; orchestrator_editorial.py::build_editorial_route; pages/0_🤖_Orquestrador_FaithBloom.py | O roteamento cria um plano/lista de capacidades e atalhos; falta dispatcher persistente que execute a rota genérica e sincronize estados de todos os Studios. |
| Aprovação explícita da história no pré-voo | Implementado | orchestrator_visual.py::approve_story; pages/0_🤖_Orquestrador_FaithBloom.py checkpoint 2 | Integrar o checkpoint ao executor de cenas quando conectado; hoje existe como estado persistido. |
| Aprovação de personagens principais antes de cenas | Implementado | orchestrator_visual.py::approve_character_candidate/visual_preflight_status; pages/0_🤖_Orquestrador_FaithBloom.py checkpoint 3 | A aprovação central usa Master existente ou URI digitada; conectar candidatas geradas no fluxo profissional. |
| Reutilização de Character Masters existentes | Implementado | pages/0_🤖_Orquestrador_FaithBloom.py::listar_personagens_oficiais/carregar_personagem_oficial/approve_character_candidate | Ensaio com o catálogo e referências reais; nenhuma promoção automática adicionada. |
| Candidata aprovada não vira Master automaticamente | Implementado | orchestrator_visual.py::approve_character_candidate/mark_character_master_promoted; visual_master_manager.py::promote_master | A marcação do plano não promove assets; a promoção real mantém confirmação humana no Character Universe. |
| Style Master aprovado no plano | Implementado | orchestrator_visual.py::approve_style; pages/0_🤖_Orquestrador_FaithBloom.py checkpoint 5 | O pré-voo grava descrição/dicionário; conectar Style DNA oficial completo e referências ao futuro executor. |
| Gate do Diretor de Cena bloqueado até universo aprovado | Parcial | orchestrator_visual.py::visual_preflight_status/require_scene_generation_ready; pages/0_🤖_Orquestrador_FaithBloom.py checkpoint 6 | Decisão e bloqueio de função testados; require_scene_generation_ready não é chamado pelos geradores de produção, apenas testes. Aplicar no dispatcher e nos caminhos reais de geração. |
| Persistência/histórico do plano visual | Implementado | orchestrator_visual.py::create_visual_plan/save_visual_plan/load_visual_plan | Validar backend real e recuperação em sessão nova. A UI atual mantém id do plano em session_state, sem seletor de planos anteriores. |
| Conectar candidatas reais de personagem ao Orquestrador | Parcial | pages/14_👥_Character_Universe.py geração de candidata(s); character_guide.py::generate_character_variations; pages/0_🤖_Orquestrador_FaithBloom.py ID/URI manual | Gerador existe fora do Orquestrador; falta seleção/vínculo automático das candidatas, comparação e aprovação no mesmo plano. |
| World Master A/B/C visual | Não implementado | orchestrator_visual.py::create_world_master; pages/0_🤖_Orquestrador_FaithBloom.py checkpoint 4 | Criar três imagens de cenário distintas, preservar versões, comparar/aprovar e vincular referências. Hoje é descrição aprovada, não lote visual A/B/C. |
| Geração de lote de ilustrações pelo Orquestrador central | Parcial | agents/ilustrador.py::ilustrador_node; fila_producao.py::executor_ilustracao_story; pages/0_🤖_Orquestrador_FaithBloom.py | Há gerador e fila nas telas específicas, mas a tela0 não despacha lote usando plano+World+Style+checkpoints. **Proposta, sem deploy:** Correções locais propostas: reaproveitar ilustrações existentes, resolver protagonista/DNA, salvar cada geração e preservar histórico. Ainda não publicadas. |

### 2. Tipos oficiais e projetos híbridos

| Item | Status na base | Evidência | O que falta / correção proposta |
| --- | --- | --- | --- |
| História Infantil | Parcial | agents/roteirista.py::roteirista_node; pages/1_📖_Criar_do_Zero.py; pages/39_✍️_Historia_4_Estilos.py | Geração/UI reais existem; corrigir perdas em falha, validação de conteúdo e preservação de referência/história escolhida; ligar rota genérica. **Proposta, sem deploy:** Correções locais propostas nos handoffs, validação de resposta, checkpoints e ilustrações; precisam ser integradas/deployadas. |
| História Inspirada na Vida Real | Implementado | real_experience_story.py::build_real_experience_brief/apply_real_experience_to_state; pages/42_🌿_Historias_Inspiradas_na_Vida_Real.py | Origem baseada em relato/consentimento/fidelidade funciona e reutiliza Storyteller; geração final herda pendências do Story Book. |
| Conselhos para Crianças | Parcial | orchestrator_editorial.py::PROJECT_TYPES/TYPE_ROUTES; pages/0_🤖_Orquestrador_FaithBloom.py | Só seleção/roteamento; criar Children Advice DNA, estrutura de conselho/reflexão/atividade, gerador/editor/QA/exportação. |
| Conselhos para Adolescentes | Parcial | orchestrator_editorial.py::PROJECT_TYPES/TYPE_ROUTES | Só seleção/roteamento; criar Teen Editorial DNA e fluxo de conselhos adequados à adolescência. |
| Devocional Infantil | Parcial | orchestrator_editorial.py::PROJECT_TYPES/TYPE_ROUTES | Só seleção/Bible Guard na lista; criar Devotional DNA, texto/reflexão/aplicação/oração/desafio e execução. |
| Devocional para Adolescentes | Parcial | orchestrator_editorial.py::PROJECT_TYPES/TYPE_ROUTES | Só seleção/rota; falta estrutura devocional própria e Teen DNA integrado. |
| Desenvolvimento Pessoal / Educativo | Parcial | orchestrator_editorial.py::PROJECT_TYPES/TYPE_ROUTES | Só registro; implementar outlines, fonte verificável, conteúdo/prática, QA específico e layout. |
| Livro de Estudos / Apostila | Parcial | orchestrator_editorial.py::PROJECT_TYPES/TYPE_ROUTES; jarvis_assistant.py::PROJECT_HINTS | Jarvis reconhece e apresenta rota; falta Study/Educational DNA, gerador de unidades, exercícios/gabarito, revisão de precisão e exportação. |
| Preparatório para Provas / Certificações | Parcial | orchestrator_editorial.py::PROJECT_TYPES/TYPE_ROUTES; jarvis_assistant.py::PROJECT_HINTS | Só classificação; faltam syllabus/fonte oficial, teoria, simulados, respostas comentadas e avaliação. |
| Workbook / Caderno de Exercícios | Parcial | orchestrator_editorial.py::PROJECT_TYPES/TYPE_ROUTES | Só registro/rota; gerar exercícios, campos de resposta, gabaritos e renderer próprio. |
| Guia de Estudos | Parcial | orchestrator_editorial.py::PROJECT_TYPES/TYPE_ROUTES | Só registro; implementar resumo/plano/revisão/exercícios e validação curricular. |
| Flashcards / Memorização | Parcial | orchestrator_editorial.py::PROJECT_TYPES/TYPE_ROUTES | Só registro; gerar frente/verso, texto/imagem/tradução/áudio, revisão e exportação próprios. |
| Livro de Atividades | Implementado | activity_studio.py; pages/23_🧩_Activity_Book_Studio.py; orchestrator_editorial.py::TYPE_ROUTES | Studio específico existe; ligar execução no Orquestrador e certificar saídas reais. Auditoria detalhada é seção12/serviços do relatório. |
| Livro de Colorir / Line Art | Parcial | coloring_studio.py; agents/line_art_colorir.py; pages/3_🖍️_Livros_de_Colorir.py | Fluxo existe; renderer publicado não reconhece layout colorir e há pendências de salvamento/capa/retomada; integrar correções e ensaiar com provedor/storage reais. **Proposta, sem deploy:** Correções locais propostas: PDF com imagens/versos, capa persistida, drafts/variações duráveis e referência oficial/DNA; não publicadas. |
| HQ / Quadrinhos | Parcial | agents/formato_quadrinhos.py::gerar_roteiro_quadrinhos; pages/40_➕_Explorar_outros_estilos.py | Roteiro de páginas/painéis/diálogos/SFX e formato ativo existem; faltam geração por painel, balões/composição e exportação de HQ. |
| Outro tipo de projeto | Parcial | orchestrator_editorial.py::PROJECT_TYPES/TYPE_ROUTES | Há fallback/registro aberto; não existe fábrica de fluxo especializado arbitrário. |
| 16 tipos oficiais registrados / ampliar roteamento do Orquestrador | Implementado | orchestrator_editorial.py::PROJECT_TYPES/build_editorial_route; tests/test_orchestrator_editorial.py::test_all_official_project_types_are_registered | README está atrasado ao tratar todo o registro como próxima implantação; registro não equivale à execução dos 16 produtos. |
| Projetos híbridos com várias famílias editoriais | Parcial | orchestrator_editorial.py::build_editorial_route/DERIVED_OUTPUTS | Combina um tipo com saídas derivadas áudio/animação/música e uma linha editorial; não combina vários tipos de projeto/DNAs (devocional+workbook etc.). |

### 3. Origem e inspiração

| Item | Status na base | Evidência | O que falta / correção proposta |
| --- | --- | --- | --- |
| Bíblia / versículo / passagem | Implementado | biblical_reference_validator.py; agents/curador_tema.py; pages/1_📖_Criar_do_Zero.py | Validar a fonte aprovada e a aplicação literária no livro real; universalizar handoff do seletor central. |
| Ideia própria | Implementado | pages/1_📖_Criar_do_Zero.py entrada; pages/39_✍️_Historia_4_Estilos.py origem_ideia | Ligar origem do registro central ao mesmo estado de criação em todos os tipos. |
| Experiência real | Implementado | real_experience_story.py::build_real_experience_brief/apply_real_experience_to_state; pages/42_🌿_Historias_Inspiradas_na_Vida_Real.py | Controles de consentimento/anonimização/fidelidade existem; avaliar relato e resultado reais com autora. |
| Filme, livro ou obra inspiradora | Parcial | orchestrator_editorial.py::ORIGINS; jarvis_assistant.py::infer_origin; originality_guard.py::creation_originality_contract/evaluate_originality | Só rótulo/rota e contrato de princípios; falta intake/análise/extração abstrata que alimente o gerador e registre referência validada. |
| Imagem como origem da obra | Parcial | orchestrator_editorial.py::ORIGINS; jarvis_assistant.py::infer_origin; jarvis_multimodal.py | Uploads/análise multimodal existem; falta fluxo padronizado independente imagem→brief→DNA por tipo, com rastreio e ligação do plano central. |
| PDF/documento/material próprio como origem | Parcial | orchestrator_editorial.py::ORIGINS; jarvis_multimodal.py; book_doctor.py | Anexos/extrator e Book Doctor existem; falta intake editorial genérico PDF→novo tipo de projeto e conexão com rota. |
| Tema / lição | Implementado | agents/curador_tema.py::curador_tema_node; pages/1_📖_Criar_do_Zero.py | Operacional no livro infantil; estender gerador/estrutura para outros tipos. |
| Emoção como origem independente | Parcial | orchestrator_editorial.py::ORIGINS; emotion_colors.py; emotional_experience_engine.py | Emoção é briefing/campo real infantil, mas escolher emotion no registro central não executa um fluxo emoção→obra independente. |
| Sugestão da IA | Implementado | agents/gerador_ideias.py::gerador_ideias_node; pages/1_📖_Criar_do_Zero.py; pages/39_✍️_Historia_4_Estilos.py | Validar sugestões reais e ampliar para os tipos que só possuem registro. |
| Origem / Inspiração independente de tipo, público e linha editorial | Parcial | orchestrator_editorial.py::ORIGINS/build_editorial_route; pages/0_🤖_Orquestrador_FaithBloom.py seletores separados | Separação está implementada no schema/UI (README atrasado), mas não há executor que transforme cada origem em intake/brief e o entregue a cada tipo. |
| Originality & Ineditism Guard | Implementado | originality_guard.py::creation_originality_contract/evaluate_originality; agents/diagramador.py::diagramador_node; external_ai_bridge.py | Analisa referências declaradas e riscos locais; não é pesquisa universal/jurídica nem certificado externo de ineditismo. Revisão humana da obra real continua necessária. |

### 4. Núcleo editorial e perfis de idade

| Item | Status na base | Evidência | O que falta / correção proposta |
| --- | --- | --- | --- |
| Literary Excellence Charter: Encantar antes de ensinar | Implementado | agent_skills.py::FAITHBLOOM_EDITORIAL_DNA/shared_literary_contract/skill_contract; agents/roteirista.py::montar_prompt; agents/revisor.py | Contrato injetado nos prompts e revisão; verificar cumprimento em saídas reais (qualidade literária não é garantida pelo prompt). |
| Literary Excellence Charter: História funciona sem sermão | Implementado | agent_skills.py::FAITHBLOOM_EDITORIAL_DNA/shared_literary_contract/skill_contract; agents/roteirista.py::montar_prompt; agents/revisor.py | Contrato injetado nos prompts e revisão; verificar cumprimento em saídas reais (qualidade literária não é garantida pelo prompt). |
| Literary Excellence Charter: Emoções concretas adequadas à idade | Implementado | agent_skills.py::FAITHBLOOM_EDITORIAL_DNA/shared_literary_contract/skill_contract; agents/roteirista.py::montar_prompt; agents/revisor.py | Contrato injetado nos prompts e revisão; verificar cumprimento em saídas reais (qualidade literária não é garantida pelo prompt). |
| Literary Excellence Charter: Transformação por escolhas/tentativas/consequências/relações | Implementado | agent_skills.py::FAITHBLOOM_EDITORIAL_DNA/shared_literary_contract/skill_contract; agents/roteirista.py::montar_prompt; agents/revisor.py | Contrato injetado nos prompts e revisão; verificar cumprimento em saídas reais (qualidade literária não é garantida pelo prompt). |
| Literary Excellence Charter: Fé natural, amorosa e não coercitiva | Implementado | agent_skills.py::FAITHBLOOM_EDITORIAL_DNA/shared_literary_contract/skill_contract; agents/roteirista.py::montar_prompt; agents/revisor.py | Contrato injetado nos prompts e revisão; verificar cumprimento em saídas reais (qualidade literária não é garantida pelo prompt). |
| Literary Excellence Charter: Prazer de leitura/identificação/participação/releitura | Implementado | agent_skills.py::FAITHBLOOM_EDITORIAL_DNA/shared_literary_contract/skill_contract; agents/roteirista.py::montar_prompt; agents/revisor.py | Contrato injetado nos prompts e revisão; verificar cumprimento em saídas reais (qualidade literária não é garantida pelo prompt). |
| Literary Excellence Charter: Originalidade editorial | Implementado | agent_skills.py::FAITHBLOOM_EDITORIAL_DNA/shared_literary_contract/skill_contract; agents/roteirista.py::montar_prompt; agents/revisor.py | Contrato injetado nos prompts e revisão; verificar cumprimento em saídas reais (qualidade literária não é garantida pelo prompt). |
| Literary Excellence Charter: Continuidade de personagem/coleção/universo | Implementado | agent_skills.py::FAITHBLOOM_EDITORIAL_DNA/shared_literary_contract/skill_contract; agents/roteirista.py::montar_prompt; agents/revisor.py | Contrato injetado nos prompts e revisão; verificar cumprimento em saídas reais (qualidade literária não é garantida pelo prompt). |
| Heart Arc: encantamento→emoção→experiência→descoberta→transformação→fé | Implementado | agent_skills.py::FAITHBLOOM_HEART_ARC/HEART_ARC_PRINCIPLES; story_experience_biblical_harmony.py::deterministic_story_experience_gate/review_story_experience_harmony | Há contrato e gates de mapa/semântica (no Remaster); auditar a história gerada e ampliar cobertura obrigatória a todos os caminhos de novos livros. |
| Emotional Experience Engine causal | Implementado | emotional_experience_engine.py::instrucao_experiencia_emocional/perfil_emocional_etario; age_profiles.py::instrucao_faixa_etaria | Acontecimento→reação→escolha→consequência é diretriz real nos prompts; resultado emocional/cumprimento exigem revisão editorial. |
| Age Profile infantil 3-5 | Implementado | age_profiles.py::AGE_PROFILES/perfil_etario/instrucao_faixa_etaria; emotional_experience_engine.py | Há regras específicas por idade; validar linguagem real e ensaios de leitura. Adolescente/adulto não possuem o mesmo DNA especializado. |
| Age Profile infantil 3-8 | Implementado | age_profiles.py::AGE_PROFILES/perfil_etario/instrucao_faixa_etaria; emotional_experience_engine.py | Há regras específicas por idade; validar linguagem real e ensaios de leitura. Adolescente/adulto não possuem o mesmo DNA especializado. |
| Age Profile infantil 6-8 | Implementado | age_profiles.py::AGE_PROFILES/perfil_etario/instrucao_faixa_etaria; emotional_experience_engine.py | Há regras específicas por idade; validar linguagem real e ensaios de leitura. Adolescente/adulto não possuem o mesmo DNA especializado. |
| Age Profile infantil 9-12 | Implementado | age_profiles.py::AGE_PROFILES/perfil_etario/instrucao_faixa_etaria; emotional_experience_engine.py | Há regras específicas por idade; validar linguagem real e ensaios de leitura. Adolescente/adulto não possuem o mesmo DNA especializado. |

### 5. Roteirista, estilos e formato HQ

| Item | Status na base | Evidência | O que falta / correção proposta |
| --- | --- | --- | --- |
| Estilo narrativo Aventura | Implementado | agents/estilos_narrativos.py::ESTILOS_NARRATIVOS/_gerar_um_estilo/gerar_comparativo_estilos; agents/roteirista.py::montar_prompt | Roteiro/comparativo existem; robustez e salvamento parcial publicados têm falhas, corrigidas só na proposta local. **Proposta, sem deploy:** Checkpoints por versão, rejeição de conteúdo vazio e preservação de versão escolhida propostos; ainda não publicados. |
| Estilo narrativo Poético / Rimado | Implementado | agents/estilos_narrativos.py::ESTILOS_NARRATIVOS/_gerar_um_estilo/gerar_comparativo_estilos; agents/roteirista.py::montar_prompt | Roteiro/comparativo existem; robustez e salvamento parcial publicados têm falhas, corrigidas só na proposta local. **Proposta, sem deploy:** Checkpoints por versão, rejeição de conteúdo vazio e preservação de versão escolhida propostos; ainda não publicados. |
| Estilo narrativo Fábula Cristã | Implementado | agents/estilos_narrativos.py::ESTILOS_NARRATIVOS/_gerar_um_estilo/gerar_comparativo_estilos; agents/roteirista.py::montar_prompt | Roteiro/comparativo existem; robustez e salvamento parcial publicados têm falhas, corrigidas só na proposta local. **Proposta, sem deploy:** Checkpoints por versão, rejeição de conteúdo vazio e preservação de versão escolhida propostos; ainda não publicados. |
| Estilo narrativo Misto | Implementado | agents/estilos_narrativos.py::ESTILOS_NARRATIVOS/_gerar_um_estilo/gerar_comparativo_estilos; agents/roteirista.py::montar_prompt | Roteiro/comparativo existem; robustez e salvamento parcial publicados têm falhas, corrigidas só na proposta local. **Proposta, sem deploy:** Checkpoints por versão, rejeição de conteúdo vazio e preservação de versão escolhida propostos; ainda não publicados. |
| Escolha do Roteirista / proposta autoral | Implementado | agents/roteirista_autoral.py::gerar_proposta_roteirista/gerar_versao_autoral_roteirista; pages/39_✍️_Historia_4_Estilos.py | Geração e aplicação existem; revisar versão real, integrar validação de saída/continuidade aprimorada. **Proposta, sem deploy:** Validação de conteúdo utilizável e continuidade reforçadas só na proposta local. |
| Estilo adicional Cumulativo / Lengalenga | Parcial | agents/estilos_narrativos.py::ESTILOS_ADICIONAIS/gerar_estilo_adicional; pages/40_➕_Explorar_outros_estilos.py; agents/roteirista.py::roteirista_node | Gerador especializado/UI existem, mas handoff para Roteirista publicado consulta registro dos 4 antigos e pode gerar KeyError; integrar conserto de TODOS_ESTILOS. **Proposta, sem deploy:** Handoff dos 6 estilos corrigido e testado localmente; não publicado. |
| Estilo adicional Cotidiano Cômico / Diário Visual | Parcial | agents/estilos_narrativos.py::ESTILOS_ADICIONAIS/gerar_estilo_adicional; pages/40_➕_Explorar_outros_estilos.py; agents/roteirista.py::roteirista_node | Gerador especializado/UI existem, mas handoff para Roteirista publicado consulta registro dos 4 antigos e pode gerar KeyError; integrar conserto de TODOS_ESTILOS. **Proposta, sem deploy:** Handoff dos 6 estilos corrigido e testado localmente; não publicado. |
| Storyteller compartilhado em estilos e formato HQ | Implementado | agents/estilos_narrativos.py::_gerar_um_estilo; agents/roteirista_autoral.py::_base_sistema; agents/formato_quadrinhos.py::gerar_roteiro_quadrinhos; agent_skills.py::skill_contract | Contrato compartilhado é real; não equivale a garantir qualidade de todo texto retornado. |
| Estilo narrativo ≠ formato visual / combinar Aventura ou Misto com HQ | Parcial | agents/formato_quadrinhos.py::gerar_roteiro_quadrinhos; pages/40_➕_Explorar_outros_estilos.py formato_narrativo_ativo | Separação e adaptação para roteiro HQ existem; formato ativo ainda não conduz renderer/generador de painéis e balões. |

### 6. Character Universe, Mel e melhoria genérica

| Item | Status na base | Evidência | O que falta / correção proposta |
| --- | --- | --- | --- |
| Character DNA normalizado e reutilizável | Implementado | character_universe.py::normalizar_dna/personagem_para_prompt; character_guide.py::_identity_block | Validar catálogo/assets/storage reais e retomada; consistência visual produzida por IA exige inspeção da autora. |
| Color Master e Line Art Master | Implementado | character_universe.py::definir_master_visual; visual_master_manager.py::promote_master/promote_reference_color_master | Validar catálogo/assets/storage reais e retomada; consistência visual produzida por IA exige inspeção da autora. |
| Reference Pack persistido e categorizado | Implementado | character_universe.py::normalizar_reference_pack/adicionar_referencia; character_guide.py::character_reference_paths | Validar catálogo/assets/storage reais e retomada; consistência visual produzida por IA exige inspeção da autora. |
| Prompt Mestre Visual | Implementado | character_universe.py::personagem_para_prompt; character_guide.py::_identity_block | Validar catálogo/assets/storage reais e retomada; consistência visual produzida por IA exige inspeção da autora. |
| Mesmo nome distinguido por coleção/id | Implementado | character_universe.py::detectar_personagens_mesmo_nome/listar_personagens_oficiais/mover_personagem_para_colecao | Validar catálogo/assets/storage reais e retomada; consistência visual produzida por IA exige inspeção da autora. |
| Status oficial e coleção preservados | Implementado | character_universe.py::_sync_index_record/atualizar_personagem_oficial | Validar catálogo/assets/storage reais e retomada; consistência visual produzida por IA exige inspeção da autora. |
| Arquivamento não destrutivo e restauração | Implementado | character_universe.py::arquivar_personagem/restaurar_personagem; pages/14_👥_Character_Universe.py | Validar catálogo/assets/storage reais e retomada; consistência visual produzida por IA exige inspeção da autora. |
| Proteção de exclusão permanente com histórico | Implementado | character_universe.py::validar_exclusao_permanente (gate para eventual exclusão física) | Validar catálogo/assets/storage reais e retomada; consistência visual produzida por IA exige inspeção da autora. |
| Promoção de candidata só com aprovação humana | Implementado | visual_master_manager.py::create_candidate/promote_master; pages/14_👥_Character_Universe.py confirmed checkbox | Validar catálogo/assets/storage reais e retomada; consistência visual produzida por IA exige inspeção da autora. |
| Mel Eye Signature: verde/gradiente/estrela/coração/microbrilhos | Implementado | mel_character_profile.py::MEL_CHARACTER_DNA/MEL_VISUAL_PROMPT_MASTER/mel_visual_prompt; pages/43_🌸_Mel_DNA_e_Prompt_Visual.py; character_universe.py::personagem_para_prompt | Código protege atributos e consulta Master quando disponível; existência e fidelidade dos assets reais/novas gerações não foram certificadas nesta auditoria. |
| Heart Cheek Blush: duas camadas | Implementado | mel_character_profile.py::MEL_CHARACTER_DNA/MEL_VISUAL_PROMPT_MASTER/mel_visual_prompt; pages/43_🌸_Mel_DNA_e_Prompt_Visual.py; character_universe.py::personagem_para_prompt | Código protege atributos e consulta Master quando disponível; existência e fidelidade dos assets reais/novas gerações não foram certificadas nesta auditoria. |
| Bow Signature: forma/posição fixas, cor contextual | Implementado | mel_character_profile.py::MEL_CHARACTER_DNA/MEL_VISUAL_PROMPT_MASTER/mel_visual_prompt; pages/43_🌸_Mel_DNA_e_Prompt_Visual.py; character_universe.py::personagem_para_prompt | Código protege atributos e consulta Master quando disponível; existência e fidelidade dos assets reais/novas gerações não foram certificadas nesta auditoria. |
| Mel DNA + Prompt Mestre + Color Master + Reference Pack | Implementado | mel_character_profile.py::MEL_CHARACTER_DNA/MEL_VISUAL_PROMPT_MASTER/mel_visual_prompt; pages/43_🌸_Mel_DNA_e_Prompt_Visual.py; character_universe.py::personagem_para_prompt | Código protege atributos e consulta Master quando disponível; existência e fidelidade dos assets reais/novas gerações não foram certificadas nesta auditoria. |
| Melhoria profissional para qualquer personagem: referência→análise→ 3 candidatas→comparação→Master | Parcial | pages/14_👥_Character_Universe.py gerar 1/3 candidatas + comparação/promover; character_guide.py::generate_character_variations; jarvis_character_auto_setup.py | Restauro/variações/3 candidatas/manuais já genéricos; faltam estratégias diferenciadas Conservadora/Refinada/Premium e um fluxo contínuo análise→atualização de DNA/pack/prompt e Orquestrador. README subestima implementação existente. |

### 7. World / Location Master

| Item | Status na base | Evidência | O que falta / correção proposta |
| --- | --- | --- | --- |
| World/Location Master: descrição→draft→aprovação→vínculo→histórico | Implementado | orchestrator_visual.py::create_world_master/approve_world_master/link_location_approval; pages/0_🤖_Orquestrador_FaithBloom.py checkpoint 4 | Cadastro e aprovação explícita existem; falta criação visual A/B/C e enviar os Masters ao lote central. A UI cria/aprova em um clique autoral. |
| Cenário não aprovado não entra no lote principal | Parcial | orchestrator_visual.py::link_location_approval/visual_preflight_status/require_scene_generation_ready | Vínculo no plano é bloqueado; geradores atuais não consomem automaticamente esse gate. Aplicar em todos os caminhos do lote principal. |

### 8. Diretor de Cena A/B/C

| Item | Status na base | Evidência | O que falta / correção proposta |
| --- | --- | --- | --- |
| Diretor de Cena: três propostas A/B/C distintas e escolha humana | Implementado | character_guide.py::suggest_scene_concepts/validate_scene_concepts; pages/6_👤_Personagens.py Scene Director | UI de Personagens já faz chamada textual e escolha A/B/C; conectar ao plano/gates do Orquestrador. README está atrasado sobre a capacidade fora do Orquestrador. |
| Diretor de Cena: ilustração da direção escolhida | Implementado | character_guide.py::compose_scene_prompt/generate_scene_assets; pages/6_👤_Personagens.py Gerar imagem da direção escolhida | Referências e DNA chegam ao gerador; validar qualidade real e fidelidade com autora. |
| Conectar Diretor de Cena A/B/C ao Orquestrador | Parcial | pages/0_🤖_Orquestrador_FaithBloom.py readiness; character_guide.py::suggest_scene_concepts/generate_scene_assets | Falta dispatcher que chame estas funções após gate e persista seleção em approvals.scene_options antes do lote; estrutura já contém campo. |

### 9. Element Lock

| Item | Status na base | Evidência | O que falta / correção proposta |
| --- | --- | --- | --- |
| Element Lock: contrato de bloqueio de Personagens | Implementado | orchestrator_visual.py::DEFAULT_LOCKS/build_element_lock_instruction; pages/0_🤖_Orquestrador_FaithBloom.py checkpoint 8 | Contrato textual controlável existe; não afirma preservação de pixels. Envio do contrato/máscara/referência a editor real continua pendente. |
| Element Lock: contrato de bloqueio de Pose/composição | Implementado | orchestrator_visual.py::DEFAULT_LOCKS/build_element_lock_instruction; pages/0_🤖_Orquestrador_FaithBloom.py checkpoint 8 | Contrato textual controlável existe; não afirma preservação de pixels. Envio do contrato/máscara/referência a editor real continua pendente. |
| Element Lock: contrato de bloqueio de Expressões | Implementado | orchestrator_visual.py::DEFAULT_LOCKS/build_element_lock_instruction; pages/0_🤖_Orquestrador_FaithBloom.py checkpoint 8 | Contrato textual controlável existe; não afirma preservação de pixels. Envio do contrato/máscara/referência a editor real continua pendente. |
| Element Lock: contrato de bloqueio de Figurino | Implementado | orchestrator_visual.py::DEFAULT_LOCKS/build_element_lock_instruction; pages/0_🤖_Orquestrador_FaithBloom.py checkpoint 8 | Contrato textual controlável existe; não afirma preservação de pixels. Envio do contrato/máscara/referência a editor real continua pendente. |
| Element Lock: contrato de bloqueio de Estilo | Implementado | orchestrator_visual.py::DEFAULT_LOCKS/build_element_lock_instruction; pages/0_🤖_Orquestrador_FaithBloom.py checkpoint 8 | Contrato textual controlável existe; não afirma preservação de pixels. Envio do contrato/máscara/referência a editor real continua pendente. |
| Element Lock: contrato de bloqueio de Cenário | Implementado | orchestrator_visual.py::DEFAULT_LOCKS/build_element_lock_instruction; pages/0_🤖_Orquestrador_FaithBloom.py checkpoint 8 | Contrato textual controlável existe; não afirma preservação de pixels. Envio do contrato/máscara/referência a editor real continua pendente. |
| Element Lock: contrato de bloqueio de Iluminação | Implementado | orchestrator_visual.py::DEFAULT_LOCKS/build_element_lock_instruction; pages/0_🤖_Orquestrador_FaithBloom.py checkpoint 8 | Contrato textual controlável existe; não afirma preservação de pixels. Envio do contrato/máscara/referência a editor real continua pendente. |
| Element Lock: contrato de bloqueio de Texto | Implementado | orchestrator_visual.py::DEFAULT_LOCKS/build_element_lock_instruction; pages/0_🤖_Orquestrador_FaithBloom.py checkpoint 8 | Contrato textual controlável existe; não afirma preservação de pixels. Envio do contrato/máscara/referência a editor real continua pendente. |
| Element Lock integrado ao editor real, máscaras/referências | Parcial | orchestrator_visual.py::build_element_lock_instruction/scenario_only_instruction; agents/ilustrador.py::gerar_cena_unica/criar_variacao_cena; openrouter_client.py::gerar_imagem | Editor/variação por referência existem, mas não recebem o contrato estruturado do Orquestrador nem API de máscaras; preservação exata depende do provedor. Conectar adapter de edição e QA de regiões bloqueadas. |

### 10. Custos, modos de geração e fila

| Item | Status na base | Evidência | O que falta / correção proposta |
| --- | --- | --- | --- |
| Modo de geração Gratuito primeiro | Parcial | orchestrator_visual.py::GENERATION_MODES/create_visual_plan; pages/0_🤖_Orquestrador_FaithBloom.py | Modo é opção/metadata; não escolhe automaticamente provedor/modelo visual gratuito/econômico/premium. faithbloom_cost_mode.py regula modelos de diálogo/visão em outro contrato, não estes 4 modos visuais. |
| Modo de geração Econômico visual | Parcial | orchestrator_visual.py::GENERATION_MODES/create_visual_plan; pages/0_🤖_Orquestrador_FaithBloom.py | Modo é opção/metadata; não escolhe automaticamente provedor/modelo visual gratuito/econômico/premium. faithbloom_cost_mode.py regula modelos de diálogo/visão em outro contrato, não estes 4 modos visuais. |
| Modo de geração Premium visual | Parcial | orchestrator_visual.py::GENERATION_MODES/create_visual_plan; pages/0_🤖_Orquestrador_FaithBloom.py | Modo é opção/metadata; não escolhe automaticamente provedor/modelo visual gratuito/econômico/premium. faithbloom_cost_mode.py regula modelos de diálogo/visão em outro contrato, não estes 4 modos visuais. |
| Modo de geração Automático visual | Parcial | orchestrator_visual.py::GENERATION_MODES/create_visual_plan; pages/0_🤖_Orquestrador_FaithBloom.py | Modo é opção/metadata; não escolhe automaticamente provedor/modelo visual gratuito/econômico/premium. faithbloom_cost_mode.py regula modelos de diálogo/visão em outro contrato, não estes 4 modos visuais. |
| Limite de orçamento por projeto / impedir estouro silencioso | Parcial | orchestrator_visual.py::create_visual_plan/cost_gate; pages/0_🤖_Orquestrador_FaithBloom.py demonstração de estimativa | cost_gate retorna decisão; budget_spent_usd começa0 e não recebe custo de geradores. Implementar reserva+registro de custo por projeto e bloquear dispatcher antes de enviar. |
| Confirmação antes de toda operação paga | Parcial | orchestrator_visual.py::cost_gate; pages/1_📖_Criar_do_Zero.py botões autorais; openrouter_client.py::chamar_llm/gerar_imagem | Botões/gates e avisos existem, mas cliente não exige token de autorização de custo e pipeline agrega chamadas. Unificar estimativa e autorização explícita no executor; não tratar um aviso como bloqueio universal. |
| Orçamento diário operacional | Implementado | controle_geracao.py::validar_orcamento/iniciar_requisicao/custo_hoje_usd; openrouter_client.py; gemini_client.py | Proteção compartilhada é real. É diária/global e estimada, com log local, não orçamento transacional por projeto/multiusuário. |
| Limite de imagens por lote | Parcial | controle_geracao.py::validar_lote_imagens; fila_producao.py::processar_lote; retomar_fluxo.py | Aplicado na fila/retomada; ilustrador_node legacy e loop de criação não usam validar_lote_imagens. Uniformizar limites em todos os caminhos. |
| Cooldown e bloqueio de clique duplicado | Implementado | controle_geracao.py::assinatura_requisicao/iniciar_requisicao/liberar_requisicao; openrouter_client.py | Bloqueio é por processo e assinatura; testar simultaneidade/restart em serviço real. Não substitui idempotência transacional multiworker. |
| Retry apenas transitório e backoff | Implementado | openrouter_client.py::_post_com_retry; gemini_client.py::_post_com_retry | Texto/áudio repetem429/5xx/erros transitórios; endpoint imagens usa 1 tentativa para evitar cobrança duplicada. Confirmar rate limits e erro real do provedor. |
| Log sanitizado de geração | Implementado | controle_geracao.py::_gravar/finalizar_requisicao/sanitizar_texto; pages/11_🛡️_Custos_e_Seguranca.py | Não grava prompts completos/segredos; armazenamento é arquivo local configurável. Centralizar logs/reservas para produção multiusuário se aplicável. |
| Fila persistente: pause/continue/cancel/recuperação | Implementado | fila_producao.py::criar_job/processar_proximo/pausar_job/continuar_job/cancelar_job/recuperar_jobs_interrompidos; pages/12_🏭_Fila_de_Producao.py | Fila cooperativa por execução de UI, não worker 24h; testar storage real/recuperação. Cancelamento não interrompe chamada de provedor já enviada. |
| Imagens geradas não aprovadas automaticamente | Implementado | agents/ilustrador.py::definir_imagem_cena/ilustrador_node; character_guide.py::generate_scene_assets; visual_master_manager.py::create_candidate | Gerações entram como não aprovadas/candidatas; upload da autora é explicitamente aprovado por ela. Auditoria visual continua humana. |

### Especializações editoriais ainda faltantes

| Item | Status na base | Evidência | O que falta / correção proposta |
| --- | --- | --- | --- |
| Children Advice DNA | Não implementado | orchestrator_editorial.py::PROJECT_TYPES/TYPE_ROUTES (registro somente); busca de referências em fontes .py | Não há módulo/gerador/QA específico; apenas children_advice no registry. |
| Teen Editorial DNA | Não implementado | orchestrator_editorial.py::PROJECT_TYPES/TYPE_ROUTES (registro somente); busca de referências em fontes .py | Não há regras editoriais adolescentes comparáveis aos4 Age Profiles infantis; teen é rótulo/rota. |
| Devotional DNA | Não implementado | orchestrator_editorial.py::PROJECT_TYPES/TYPE_ROUTES (registro somente); busca de referências em fontes .py | Não há fluxo estruturado Bíblia/reflexão/aplicação/oração/desafio; apenas registro/timbre de áudio devocional. |
| Study / Educational DNA | Não implementado | orchestrator_editorial.py::PROJECT_TYPES/TYPE_ROUTES (registro somente); busca de referências em fontes .py | Faltam conteúdo didático, objetivos, fontes, unidades, gabarito e QA de precisão. |
| Workbook / Guide / Flashcard flows | Não implementado | orchestrator_editorial.py::PROJECT_TYPES/TYPE_ROUTES (registro somente); busca de referências em fontes .py | Os3tipos estão registrados, mas geradores, formatos de dados, revisão e exportação especializados não existem. |

### Validação real de produção

| Item | Status na base | Evidência | O que falta / correção proposta |
| --- | --- | --- | --- |
| Pleno funcionamento de geração visual/literária com provedores e storage reais | Validação pendente | ENGINEERING_FUNCTIONAL_AUDIT.md:894 testes + 2 subtestes; 59/59 aberturas offline; testes com provedores simulados | Integrar/deployar correções, gerar Story/Coloring controlados nos provedores reais, reabrir em Supabase, avaliar texto, olhos/DNA/fidelidade, custo e falhas reais. Auditoria offline não certifica operação real. |

## Matriz detalhada — serviços

### 11. Book Doctor / Restoration Studio

| Item do README | Status na base | Evidência no código | O que falta / limite concreto |
| --- | --- | --- | --- |
| Importar livro e gerar diagnóstico de PDF, imagens e capa | Implementado | `book_doctor.py`: `criar_projeto`, `auditar_pdf`, `auditar_pdf_rapido`, `auditar_imagem`, `auditar_capa_pdf`, `gerar_relatorio`; página 16 | Diagnóstico é triagem técnica; parecer editorial humano continua necessário. Auditoria rápida não extrai todos os assets. |
| Preservar original e comparar antes/depois | Implementado | `preservar_original` registra SHA256 e cópia; `restoration_studio._registrar_versao`; página 19 | Ensaio com originais reais e persistência de produção pendente. |
| Melhoria técnica de imagens / limpeza de line art | Implementado | `melhorar_imagem_tecnicamente`, `limpar_line_art`, `auditar_line_art`; testes Refinamento 04 | Upscale Lanczos não recupera detalhes semânticos perdidos; QA de complexidade é heurístico. |
| Corrigir personagem, reilustrar ou gerar variação por IA | Implementado | `montar_prompt_restauracao`, `gerar_variacao_ia` recebe `imagem_base` e referências; página 19 usa provedor real | Falta ensaio com provedor configurado e avaliação visual da preservação de pose, olhos, identidade e itens bloqueados. Prompt não garante edição pixel a pixel. |
| Character Master / Style DNA como referência | Implementado | `vincular_character`, `vincular_style`, `personagem_para_prompt`, `style_para_prompt`; referências enviadas na geração | Fidelidade visual de saída real pendente. Não confundir presença de referência com garantia de preservação. |
| Derivados versionados sem promoção automática a Master | Implementado | `_registrar_versao` começa `aprovada=False`; `aprovar_versao` é ação explícita | Nenhuma generalização automática de Master deve ser inferida desse fluxo. |

### 12. Coloring Book Studio / Doctor

| Item do README | Status na base | Evidência | O que falta / correção proposta |
| --- | --- | --- | --- |
| Criar line art por IA | Implementado | `coloring_studio._gerar_uma_pagina`; `agents/line_art_colorir.py`; página 3 | Gerar/avaliar resultado real com custos e provedor de produção. |
| Upload de line art pronta e conversão de foto/ilustração | Parcial | `ORIGENS`, `_pagina_from_form`, `_gerar_uma_pagina` | PROPOSTO: bloquear conversão sem referência disponível e encaminhar corretamente a referência. Falta teste visual de conversão real. |
| Reutilizar assets e personagens oficiais | Parcial | Galeria/biblioteca em `_pagina_from_form`; `character_asset_selector.py` | PROPOSTO: usar Masters oficiais aprovados e permitidos para colorir, incluir DNA/bytes originais e impedir promoção de candidatos/arquivados. |
| Presets de estilo, público e idade | Implementado | `coloring_presets.py`; `_render_presets`, presets globais e por página | Consistência visual real entre páginas exige avaliação. |
| Variações, histórico, aprovação | Parcial | `_registrar_variacao_inicial`, `_render_pagina_card`, `gerar_variacao_line_art` | PROPOSTO: salvar rascunhos/variações antes da diagramação, manter resultados diante de interrupção e retry sem outra geração. |
| Versos em branco e diagramação | Parcial | `agents/diagramador_colorir.py`; renderer compartilhado | Falha real da base: layout `colorir` não era reconhecido no renderer/preflight. PROPOSTO: incorporar desenhos e versos corretamente. PDFs locais de 24 páginas/11 desenhos inspecionados após correção. |
| Line Art QA / Coloring Book Doctor | Implementado | `coloring_book_doctor.py`: `analisar_line_art_avancada`, `auditar_lote_colorir`, `gerar_plano_recuperacao`; página 20 | Métricas de espessura/complexidade são heurísticas; aprovação gráfica humana e impressão física pendentes. |
| Preflight + capa + PDF Print Ready | Parcial | `qualidade_impressao.py`, `renderizador_editorial.py`, `capa_profissional.py`, `coloring_studio` | PROPOSTO: ações completas de exportação/salvamento do miolo/capa PDF, bloqueio de imagens ausentes/baixa resolução/PDF inválido; limpar preview do projeto anterior. Aceitação KDP continua externa. |

### 13. Tradução / Localization Excellence

| Item | Status na base | Evidência | O que falta / correção proposta |
| --- | --- | --- | --- |
| Tradução por locale, versões e aprovação | Parcial | `translation_localization.localizar_livro`, `adicionar_versao_localizada`, `aprovar_versao_localizada`; página 21 | Base tinha `AgeOption` incompatível com cópia/pickle de widget, bloqueando abertura. PROPOSTO: corrigir abertura, preservar rascunho por fonte/mercado e não misturar títulos iguais. |
| Preservar Heart Arc, humor, musicalidade, refrões, onomatopeias, DNA e moral | Implementado | `construir_prompt_localizacao`, `localization_excellence_contract`, revisão estrutural e revisão LLM | São contratos e guardas de revisão, não prova de equivalência literária; gerar/revisar com leitor nativo em cada mercado. |
| Japonês infantil / 絵本 | Implementado | `japanese_reading_level.py`, `japanese_localization_bridge.py`; página 21 chama Reading Guard | Testes de idade/kanji/leitura cobertos; qualidade editorial japonesa real pendente. |
| Bible Guard com fonte/versão aprovada | Implementado | `_proteger_texto_biblico`, `_remover_campos_biblicos_gerados`, `texto_biblico_para_exportacao`, registros aprovados | Conferir versão/fonte/licença na obra final; guardas não concedem licença de reprodução. |

### 14. Audiobook Studio

| Item | Status na base | Evidência | O que falta / correção proposta |
| --- | --- | --- | --- |
| Derivado de Story/Translation Master | Parcial | `audiobook_studio.build_audio_source`, `create_audiobook_project`; página 24 | PROPOSTO: bloquear locale sem fonte localizada válida, usar edição aprovada da mesma fonte, evitar lição original em idioma divergente. |
| Adaptação de performance sem reescrever obra | Implementado | `script_integrity`, `revise_script_scene`, `normalize_voice_director_result`, `approve_script_scene` | Aprovar direção e divisão de falas humanas antes do lote. |
| Pausas, emoção, ritmo e Voice Profiles | Implementado | `create_voice_profile`, `assign_voice`, `build_generation_units`, `apply_automatic_direction_project` | Direção automática conservadora não equivale a performance final certificada. |
| Dicionário de pronúncia | Implementado | `add_pronunciation`, `apply_pronunciations` | Escutar pronúncia real do provedor; substituição não altera texto editorial. |
| Previews A/B/C e histórico | Implementado | Fila só de uma cena, `add_audio_version`, `approve_audio_version`, `favorite_audio_version`; página 24 | A/B/C são versões comparáveis, não geração automática garantida das três. |
| TTS e seleção de provedor | Parcial | `executor_audiobook(gerar_audio)` e clientes Gemini/OpenRouter/Google Cloud | PROPOSTO: compatibilidade do provedor Gemini nos controles e constante do Voice Lab; base também tinha erro de magic em pendências. Disponibilidade, preço e voz reais não verificados. |
| QA técnico, mix e pacote de áudio | Implementado | `inspect_audio`, `qa_audio_clip`, `merge_approved_audio`, `export_audiobook_package`; testes WAV/FFmpeg | Exige FFmpeg/FFprobe; não há QA semântico automático de fala. Escuta humana continua obrigatória. |
| Master de áudio com aprovação humana | Implementado | `approve_final_mix`, `distribution_readiness`; aprovação explícita após segmentos aprovados | Aprovação de conteúdo não significa aceite ACX/Spotify/loja. |

### 15. Publicação / distribuição

| Item | Status na base | Evidência | O que falta / correção proposta |
| --- | --- | --- | --- |
| Preflight KDP / compatibilidade de plataforma | Implementado | `platform_format_engine.compatibility`, `preflight_target`; `qualidade_impressao.py` | Regras internas não equivalem ao Print Previewer oficial. Conferir specs/fontes atuais e prova de impressão. |
| PDF Print Ready e capa matemática | Parcial | `renderizador_editorial.py`, `capa_profissional.py`, `calculate_print_geometry` | PROPOSTO: correções do layout colorir e bloqueios de preflight/PDF. Plataformas sem fórmula verificada requerem template oficial; o código não inventa lombada. |
| EPUB | Implementado | `epub_exporter.export_epub`, `inspect_epub` | EPUBCheck externo não foi executado nesta auditoria; Apple bloqueia sem marca de verificação. |
| Metadados e pacote comercial | Implementado | `pacote_publicacao.py`, `metadata_readiness`, `build_channel_package` | PROPOSTO: não rotular/exportar obra em locale diferente da fonte. Arquivos precisam de validação externa no canal. |
| Quality Guardian e gate/certificado | Implementado | `run_quality_guardian`, `register_author_final_approval`, `issue_internal_certificate`, `guardian_gate` | Certificado é interno; heurísticas/prompt não comprovam bestseller nem qualidade de todos os resultados reais. |
| Platform Registry expansível/versionado | Implementado | `register_custom_platform`, `update_platform_spec`, `verification_state` | Cadastro/spec estática não cria conector de loja. Fontes/data são registros; atualização oficial precisa ser conferida. |
| Publishing & Distribution Center / estados draft→submitted→processing→live | Parcial | `create_distribution_plan`, `update_submission`, `save_distribution_plan`; página 26 | Estados são registros manuais confirmados pela autora, não respostas de uma API. PROPOSTO: impedir locale falso inclusive em planos antigos/mudanças de status. |
| Publicação automática / submissão direta a lojas | NAO_Implementado | Página 26 declara envio manual; `policy.no_auto_publish=True` | Integrar APIs oficiais onde existirem, autorização, confirmação e reconciliação real. Isso não é requisito já cumprido pelo “Center”. |

### 16. Persistência / biblioteca / versões

| Item | Status na base | Evidência | O que falta / correção proposta |
| --- | --- | --- | --- |
| Backend local | Implementado | `storage_backend.LocalStorageBackend`, `get_backend` | Adequado para desenvolvimento; disco Streamlit temporário não substitui nuvem persistente. |
| Backend Supabase configurável | Validação pendente | `SupabaseStorageBackend`: bytes/JSON/list/delete; `backend_status` | Código/conector existem. Reabrir um projeto real após restart e testar upload/read/list com credenciais do Streamlit; elas não estavam disponíveis na auditoria, sem inferir ausência em produção. |
| Salvar/retomar projetos e manter identidade | Parcial | `armazenamento.salvar_livro`, `salvar_livro_colorir`, `carregar_livro`; `storage_backend` | PROPOSTO: nomes únicos evitam overwrite no mesmo segundo; `storage_path`/`source_ref` JSON não são convertidos em caminho temporário de cache. |
| Biblioteca de Versões Narrativas | Parcial | Estados/histórico de `agents/estilos_narrativos.py`; salvamento e arquivos de projetos | PROPOSTO: checkpoint após cada estilo, preservar sucessos ao falhar geração/salvamento e não reutilizar caminho de outro livro. Ver seção narrativa do relatório principal. |
| AutoSave | Parcial | `generation_autosave.persist_generation_snapshot` + chamadas de agentes | PROPOSTO: não escolher arbitrariamente um livro com título/coleção repetido; checkpoints de histórias/imagens/colorir e retry de salvamento. Não é autosave universal de toda ação. |
| Asset Library / Media Manager | Implementado | `asset_library.list_assets`, filtros, coleções, favoritos, miniaturas, uso/duplicatas; página 31 | Testar materialização e navegação com grande biblioteca/latência de storage real. |
| Personagens, referências e presets persistidos | Implementado | `character_universe.py`, `coloring_presets.py`, `asset_library.py` | Masters oficiais exigem aprovação humana; uso no Coloring Studio tem correção PROPOSTA. |
| PDFs, imagens e áudio persistidos/materializados | Parcial | `persistir_arquivo`, `persistir_assets_em_objeto`, `materializar_assets_em_objeto` | PROPOSTO: separar identidade de JSON de materialização de mídia e salvar saídas/rascunhos de geração. Roundtrip Supabase e downloads após reinício pendentes. |
| Arquivamento seguro / exclusão protegida | Implementado | `asset_library.set_archived`, `permanent_delete_allowed`, `permanent_delete(confirmed)`; Character Universe | Arquivar não apaga; exclusão permanente exige confirmação e verificação de uso. Perfis pessoais não substituem auth/isolamento de tenant. |
| Recovery points e restauração em cópia | Implementado | `stable_hardening.create_recovery_point`, `prepare_restore_working_copy`; página 28 | Há snapshot/restore manual; não pressupor backup remoto agendado de todos os projetos. Validar recuperação real no storage de produção. |
| Audit log sanitizado | Implementado | `record_audit_event`, `sanitize_for_log`, controle de geração | Nem todo fluxo tem trilha auditável integral; base mantém último lote de eventos, não log imutável externo. |

### 17. Assistente pessoal / itens de roadmap ainda marcados [ ]

| Item | Status na base | Evidência | O que falta |
| --- | --- | --- | --- |
| Home com assistente conversacional central | Implementado | `app.py` redireciona à página 00; `jarvis_dialogue`, `jarvis_conversation`, `interpret_request` | README está desatualizado ao chamar toda a Home de futura. Conversa/roteamento não executa automaticamente todos os produtos. |
| Briefing da manhã | Parcial | `build_daily_intelligence`, `_run_daily_briefing`; botão “Gerar briefing agora” | Já retorna data, clima e agenda sob demanda. Falta incluir projetos, aprovações, mensagens importantes, pendências e prioridades da lista ideal. Não é push automático diário. |
| Fechamento do dia | NAO_Implementado | Nenhum executor encontrado; aparece no README | Criar resumo persistido de atividades, pendências e agenda seguinte; definir acionamento/agendamento. |
| Google Calendar leitura/criação/alteração | Validação pendente | `fetch_today_events`, `prepare_calendar_action`, `execute_calendar_action`, OAuth refresh; confirmação na página 00 | Conector real existe e testes simulados cobrem ações. Falta confirmar OAuth/escopos/credenciais do deploy e calendário real. Escrita exige `JARVIS_CALENDAR_WRITE_ENABLED` e confirmação. Não é OAuth de usuário self-service. |
| Aniversários/eventos especiais e contatos | Parcial | Eventos comuns/all-day vêm do Calendar; não há Contacts/People API ou domínio de aniversários | Implementar conexão autorizada aos contatos/calendário especial, recorrências, lembretes e apresentação específica. |
| Gmail / mensagens importantes | NAO_Implementado | Nenhum módulo/cliente/ação Gmail no runtime Python; somente README | OAuth Gmail, leitura segura, classificação, inbox, confirmação de envio e testes de integração. |
| Inbox do assistente para anexos e comandos | Implementado | `jarvis_multimodal.normalize_attachment`, `build_handoff_package`; `jarvis_handoff_inbox.enqueue_handoff`; UI compose/confirm | Inbox editorial interna, não caixa de e-mail Gmail. Uploads/rotas sem promoção automática a Master. |
| WhatsApp Business | NAO_Implementado | Nenhum cliente/webhook Cloud API/provedor no runtime | Conector oficial, opt-in, webhooks, templates, confirmação, entrega/erros e proteção de dados. |
| Lembretes pessoais / notificações | NAO_Implementado | Agenda mostra eventos; não há scheduler/delivery de lembrete | Persistência, fusos/recorrências, agendador e canal autorizado. |
| Prioridades pessoais + editoriais | Parcial | `jarvis_assistant.inspect_project_state`, `production_stages`, Home com próximos passos do projeto | Falta lista pessoal persistida, ranking conjunto e rotinas de planejamento. “Próxima etapa” editorial não é gestor completo de prioridades. |
| Notícias sob demanda | Implementado | `jarvis_japan_briefing.fetch_japan_foreigner_news`, `build_japan_news_reply`; `jarvis_voice` | Fontes atuais para estrangeiros no Japão, não agregador universal; conexão/atualidade de resposta ao vivo ainda não testada nesta auditoria. |
| Clima sob demanda | Implementado | `jarvis_weather.fetch_weather`, `build_weather_reply`, Open-Meteo; rota de voz/texto | Validar resposta ao vivo e localização; não gerar clima inventado quando API falha. |
| TTS / voz | Parcial | `jarvis_voice.synthesize_reply`, `openrouter_client.gerar_audio`; UI voz manual/automática | PROPOSTO: Voice Lab/seleção de provedor corrigidos. Voz real, custos e qualidade acústica pendentes. |
| STT / microfone no coração | Implementado | `jarvis_heart_mic` chama `getUserMedia`; `jarvis_voice.transcribe_audio` | Permissão do navegador/SO, suporte de codec e disponibilidade do endpoint de transcrição precisam de teste real. “Permita o microfone” é retorno de `NotAllowedError`, não confirmação de popup. |

### 18. Autonomia / controle humano

| Item | Status na base | Evidência | O que falta |
| --- | --- | --- | --- |
| Modo Assistente formal selecionável | Parcial | `jarvis_assistant.AUTONOMY_MODES` contém `assistant`; aprovações em rotas/UI | Não foi localizado seletor/persistência/executor que aplique esse modo formalmente; comportamento atual é predominantemente assistido. |
| Modo Copiloto formal | NAO_Implementado | Apenas constante `copilot` | Política executável por tarefa/risco, modo persistido, executor autorizado e trilha de decisões. |
| Modo Gerente formal / rotinas autorizadas | NAO_Implementado | Apenas constante `manager`; não há scheduler correspondente | Autorizações de escopo/duração, rotina, prioridades e execução/reconciliação segura. |
| Masters, gastos, publicação e exclusão sob aprovação | Parcial | Gates por módulo: `character_universe`, `controle_geracao`, `asset_library`, `publishing_distribution`; UI Calendar | Gates editoriais concretos existem. Não constituem motor uniforme de autonomia nem auth de todos os serviços; a auditoria não certifica a cobertura de cada caminho mutável. |

### 19. Interface / banner / navegação

| Item | Status na base | Evidência | O que falta |
| --- | --- | --- | --- |
| Visual premium acolhedor, gradientes, cards, ícones e microinterações | Implementado | `estilo.py`, `painel_visual.CSS`, cards/controle de foco/media queries | Revisão de usabilidade real e acessibilidade completa não realizada; aparência não prova execução de cada ação. |
| Desktop wide e adaptação mobile | Implementado | Breakpoints em `painel_visual.py` e página 00; container responsivo | Auditoria atual de 59 páginas é abertura offline, não ensaio browser móvel de todos os fluxos. |
| Home com busca, seis ações, projetos reais e produção | Implementado | `painel_dados.ACTIONS`, `filter_actions`, `filter_projects`, `production_stages`; `painel_projetos`, página 00 | Progresso depende do estado salvo; “pacote pronto” continua separado de “publicado”. |
| Aprovações aguardando / custos do mês / agenda na Home ideal | Parcial | Projeto mostra etapas; custos em ferramentas/controles; briefing sob demanda | Faltam widgets centrais consolidados de aprovação e custos mensais conforme mockup ideal. |
| Sidebar simplificada e técnico em Avançado | Implementado | `painel_visual.py` navegação nativa + grupos; `estilo.aplicar_estilo` | O roadmap [ ] “simplificar sidebar” está defasado; ainda há muitas páginas técnicas acessíveis. |
| PNG original inteiro, cores/brilho/detalhes dos olhos | Implementado | `painel_visual.BANNER_PATH` aponta ao original `PDF_historico/Estúdio Encantado FaithBloom.png`; `_asset` base64 bytes e `height:auto` | Código usa arquivo original sem recompressão/recorte do banner. Não confundir com logo/promo extraídos do mockup por frames separados. |
| Movimento do banner somente na moldura | Implementado | `fb-banner-frame-pulse`, toggle e reduced-motion em CSS | Brilho de moldura não anima personagens da ilustração. |
| Jarvis flutua, pisca, pulsa; acena só ao começar a falar | Implementado | `jarvis_heart_mic`: estados, `jWave 3.2s com uma execução`, classe `.greeting`, subida/retorno suaves; `motion` on/auto/off | Ensaios DOM de gesto já existem; falha de permissão/áudio real ainda depende do navegador/configuração. |
| Texto/anexos/handoffs confirmados/resposta escrita e voz | Implementado | Página 00, `jarvis_multimodal`, `jarvis_handoff_inbox`, `jarvis_voice` | Confirmar provedores/produção; handoff é encaminhamento a Studio, não conclusão automática. |
| Meus Projetos na página 53 / página 38 preservada | Implementado | `pages/53_📁_Meus_Projetos.py` / link nativo; Prompt Mestre continua página 38 | Uso real com Supabase e perfis pendente; perfil não é autenticação. |

## Princípios, execução e visão de longo prazo

| Item | Status | Evidência / pendência |
| --- | --- | --- |
| Original primeiro; versões sempre | Parcial | Book Doctor/Restoration versionam; base tem colisão de nomes e perda de checkpoint em outros fluxos. Correções de armazenamento/geração PROPOSTAS fecham casos reproduzidos, sem prova universal. |
| Master humano | Implementado | Promoções/aprovações explícitas no Character Universe, World e assets; derivados começam não aprovados. |
| Aprovar antes de gastar / custos visíveis | Parcial | Cost Gate/orçamento/UI existem, conforme auditoria core; aprovação/custo não substitui validação de fatura/cota real. |
| Fé natural e originalidade | Implementado | Contratos Storyteller/Originality Guard; são direcionamento/revisão, não garantia sobre qualquer saída real. |
| Privacidade e dignidade | Parcial | Sanitização, preservação e regras de inspiração/consentimento existem; não há auditoria de conformidade completa nem certificação multi-tenant. |
| Publicação sob controle | Implementado | Publicação externa não é automática; Center gera pacote e registra confirmação manual. |
| Praticidade sem perder controle | Parcial | Jarvis/Home/handoffs reduzem menus; fluxo completo continua multi-Studio e exige validação/aprovação. |
| Execução `streamlit run app.py` | Implementado | `app.py` encaminha à Home; smoke local com 59/59 aberturas passou após correções PROPOSTAS. |
| Secrets fora do Git / autenticação e cloud em produção | Validação pendente | Código espera config externa; não houve leitura de secrets produtivos. Matriz de papel/perfil não substitui login real. |
| PR principal Draft / release protegida | Parcial | GitHub confirmou PR #18 aberto em Draft, base release/2.0.0-rc5-skills e head da feature no commit auditado. A regra existe; configuração efetiva de proteção da branch não foi inspecionada. Nenhum merge de release foi realizado. |
| “Crie livro por versículo”, “livro de estudos teen”, “revise só imagens” | Parcial | `interpret_request` e Orquestrador constroem propostas de rota; especializações/execução nem todas completas, conforme auditoria core. |
| “Agenda e projetos precisando aprovação” integrado | Parcial | Calendar + estado editorial existem separadamente; falta briefing pessoal/editorial consolidado e validação real de conexão. |

## Resposta sobre os próprios agentes de engenharia

**Sim, os dois agentes têm contratos/skills pertinentes.** `agents/engenheiro_saas_automacao.py` registra arquitetura SaaS, Full-Stack, frontend/backend, QA, integração, operação, segurança e automação; `agents/engenheiro_code_review_profundo.py` cobre revisão semântica, rastreabilidade requisito→código, handoffs, risco e correções. `agent_skills.py` aplica seus perfis e o registro de 27 papéis está consistente.

Eles são componentes internos acionados por executor autorizado, não uma equipe externa que já testou tudo sozinha. `run_diagnostic()` retorna explicitamente `diagnosed_not_fixed`, `code_modified=False`, `tests_executed=False`, `deployed=False`; revisão profunda só ocorre com fontes selecionadas e callback LLM autorizado. `engenheiro_code_review.py` pode propor PR Draft em incidente, sem merge automático. O diagnóstico do agente foi executado na revisão anterior, mas as evidências de testes/aberturas vêm dos ensaios efetivamente rodados pelo executor, não do título do agente.

## Inconsistências principais do README

1. Marcas [x]/“implantado” escondem falhas atuais de integração em Coloring, tradução, audiobook, salvamento e pacote locale; correções estão propostas, não publicadas.
2. Marcas [ ]/“futuro” para Home conversacional, inbox, voz, clima/notícias e parte de briefing/Calendar estão defasadas: já há runtime para parte dessas funções.
3. Calendar requer validação de configuração real. Gmail, WhatsApp, fechamento do dia e modos executáveis de autonomia permanecem pendentes.
4. Platform Registry/Center organizam e exportam; não submetem/publicam via APIs. `live` é registro manual da autora.
5. Skills e prompts podem estar implantados sem prova de qualidade do resultado e operação produtiva; manter isso explícito no relatório e em futuras atualizações do README.

## Conferência de todas as 52 caixas do roadmap

A marcação original é transcrita para comparação; o status técnico resulta da revisão acima.

| Item | README | Status técnico | Seção / pendência |
| --- | --- | --- | --- |
| Storyteller compartilhado | [x] | Implementado | 5 — Contrato compartilhado nos geradores; resultados reais precisam de revisão. |
| Heart Arc™ | [x] | Implementado | 4 — Contrato/editorial e verificações existem. |
| Emotional Experience Engine™ | [x] | Implementado | 4 — Estrutura e guardas existem; qualidade real pendente. |
| Originality & Ineditism Guard | [x] | Implementado | 3 — Verificação local, sem certificado universal de originalidade. |
| histórias inspiradas na vida real como origem | [x] | Implementado | 3 — Relato/consentimento/fidelidade reutilizam Storyteller. |
| Biblioteca de Versões Narrativas | [x] | Parcial | 5/16 — Falhas de checkpoint/versão têm correções propostas. |
| Character Universe | [x] | Implementado | 6 — Cadastro/DNA/Masters/referências/histórico. |
| Mel Character DNA + Color Master + Reference Pack | [x] | Implementado | 6 — Atributos canônicos existentes; fidelidade de novos resultados exige avaliação. |
| duplicate/archive safety de personagens | [x] | Implementado | 6 — Identidade por coleção/id e arquivo não destrutivo. |
| Book Doctor | [x] | Implementado | 11 — Triagem e diagnóstico técnico. |
| Restoration Studio | [x] | Implementado | 11 — Derivados/versionamentos e geração por referência; provedor real pendente. |
| Coloring Book Studio / Doctor | [x] | Parcial | 12 — Doctor existe; exportação/rascunhos/Masters têm correções propostas. |
| Localization Excellence | [x] | Parcial | 13 — Contratos existem; abertura e isolamento de rascunhos corrigidos na proposta. |
| Audiobook Studio | [x] | Parcial | 14 — Fonte/locale/controles e Voice Lab corrigidos na proposta. |
| Quality Guardian | [x] | Implementado | 15 — Guards/certificado interno, sem garantia externa de qualidade. |
| Publishing Platform Engine | [x] | Implementado | 15 — Geometria/preflight/registry; templates e aceite oficial são externos. |
| Publishing & Distribution Center | [x] | Parcial | 15 — Pacotes/status manuais; locale corrigido na proposta; sem submissão por API. |
| Asset Library / Media Manager | [x] | Implementado | 16 — Catálogo/versões/filtros; escala e storage real pendentes. |
| Supabase / storage configurável | [x] | Validação pendente | 16 — Conector existe; roundtrip produtivo não exercitado. |
| fila de produção | [x] | Implementado | 10 — Fila persistente cooperativa; não é worker contínuo. |
| custos e segurança | [x] | Parcial | 10 — Guard diário conectado; orçamento por projeto/aprovação universal incompletos. |
| Orquestrador Visual | [x] | Parcial | 1 — Plano/checkpoints existem; executor central ainda não completo. |
| World / Location Master | [x] | Implementado | 7 — Cadastro/aprovação/vínculo; geração visual A/B/C falta. |
| Element Lock como contrato de edição | [x] | Implementado | 9 — Contrato textual existe; integração de edição real é parcial. |
| checkpoints de história/personagens/cenários/estilo | [x] | Implementado | 1 — Estados/gates existem; conectar aos geradores de ponta a ponta. |
| generalizar criação/melhoria profissional de personagens além da Mel | [ ] | Parcial | 6 — Melhoria genérica/3 candidatas já existem; estratégias e integração completa faltam. |
| conectar gerador real de candidatas de personagem | [ ] | Parcial | 1/6 — Gerador existe fora do Orquestrador; ligação central pendente. |
| gerar World Master A/B/C visualmente | [ ] | Não implementado | 7 — Existe cadastro, sem gerador visual triplo. |
| conectar Diretor de Cena A/B/C | [ ] | Parcial | 8 — Diretor existe na tela Personagens; ligação central pendente. |
| conectar geração de ilustrações ao Orquestrador | [ ] | Parcial | 1/8 — Geradores existentes fora do executor central. |
| integrar Element Lock ao editor real de imagem | [ ] | Parcial | 9 — Variação/edição por referência existe; falta contrato/máscara/QA das regiões. |
| ampliar Orquestrador para Tipos de Projeto | [ ] | Parcial | 2 — 16 registros/rotas existem; faltam executores especializados. |
| implementar Origem / Inspiração independente | [ ] | Parcial | 3 — Schema/seleção existem; intake e handoffs genéricos não completos. |
| criar DNA editorial para Conselhos infantis | [ ] | Não implementado | Especializações — Apenas children_advice registrado. |
| criar Teen Editorial DNA | [ ] | Não implementado | Especializações — Teen é rótulo/rota; falta núcleo editorial específico. |
| criar Devotional DNA | [ ] | Não implementado | Especializações — Falta estrutura/gerador/QA devocional. |
| criar Study / Educational DNA | [ ] | Não implementado | Especializações — Faltam currículo/unidades/exercícios/gabarito/precisão. |
| criar Workbook / Guide / Flashcard flows | [ ] | Não implementado | Especializações — Tipos registrados, sem geradores/renderers próprios. |
| consolidar HQ como formato visual | [ ] | Parcial | 2/5 — Roteiro/painéis/diálogos existem; produção visual/exportação faltam. |
| simplificar sidebar / navegação principal | [ ] | Implementado | 19 — Navegação agrupada e links nativos já existem. |
| Home com assistente conversacional central | [ ] | Implementado | 17/19 — Home e conversa já estão no código. |
| briefing da manhã | [ ] | Parcial | 17 — Sob demanda, com data/clima/agenda; não completo nem automático. |
| fechamento do dia | [ ] | Não implementado | 17 — Sem rotina/executor. |
| Google Calendar | [ ] | Validação pendente | 17 — Conector read/write com confirmação existe; OAuth produtivo pendente. |
| aniversários e eventos | [ ] | Parcial | 17 — Eventos comuns/all-day; contatos/aniversários especializados faltam. |
| Gmail | [ ] | Não implementado | 17 — Sem conector/runtime. |
| inbox do assistente para anexos e comandos | [ ] | Implementado | 17 — Inbox editorial interna, diferente de e-mail. |
| WhatsApp Business | [ ] | Não implementado | 17 — Sem conector/webhook/runtime. |
| voz / TTS / STT | [ ] | Parcial | 14/17 — Captura/transcrição/voz existem; bugs corrigidos na proposta e ensaio real pendente. |
| prioridades pessoais + editoriais | [ ] | Parcial | 17 — Próximas etapas editoriais; gestão pessoal consolidada falta. |
| notícias e clima sob demanda | [ ] | Implementado | 17 — HTTP/feed/Open-Meteo existentes; verificar resposta atual real. |
| modos Assistente / Copiloto / Gerente | [ ] | Parcial | 18 — Enum/assistência atual; faltam seleção/políticas/executores formais. |

## Outros componentes registrados no GitHub

| Componente | Status | Evidência / falta |
| --- | --- | --- |
| Música | Não implementado como geração final | `creative_studios.py::provider_readiness`: `provider_integration_pending`; falta provedor/render de canção/trilha. |
| Animação/vídeo | Não implementado como geração final | Mesmo registry; falta storyboard/animatic/render real integrado e QA da mídia final. |
| Idea Vault | Parcial | Contrato/fundação; falta fluxo completo de captura persistida/produção de todos os formatos. |
| Engenheiro SaaS/Full-Stack | Implementado como diagnóstico/planejamento | `run_diagnostic`, `handle_saas_request`, Agent Skills/Engenharia; não é executor autônomo de testes/deploy. |
| Engenheiro de Code Review Profundo | Implementado como revisão/proposta | `review_sources`, citações conferidas e plano de correção; revisão LLM depende do provedor autorizado. |
| Correção automática com PR Draft | Validação pendente da operação configurada | `engenheiro_code_review.investigar_e_corrigir` lê fonte e abre Draft com confiança alta; requer provedor/token GitHub no ambiente. Não faz merge. |

## Entrega e atualização futura

Os arquivos deste PR mantêm separado o inventário da base examinada e as correções testadas em proposta. Após merge/deploy, revisar os itens afetados e registrar os testes reais; não trocar todas as marcações para “implementado” apenas porque a suíte local passou.

O PR #18 foi confirmado aberto em Draft, com base `release/2.0.0-rc5-skills` e head da feature no commit auditado. A configuração efetiva de proteção da release não foi inspecionada e nenhuma mudança nela foi realizada.
