# Estado da integração do FaithBloom

Atualizado em 19/10/2026 (Japão). Este documento descreve o código desta revisão. A existência de um módulo, uma tela ou um teste simulado não comprova que o respectivo serviço já esteja ativo no site. O [relatório por agente](docs/AGENT_CONNECTIONS_STATUS.md) detalha competências e conexões; o [relatório operacional](docs/OPERATIONAL_READINESS.md) lista as correções adicionais e o que ainda falta.

## Entrega para o piloto

| Área | Implementação nesta revisão | Validação e limite |
| --- | --- | --- |
| Livros infantis e continuação | Checkpoints por etapa, recuperação de gerações interrompidas, persistência e vínculo exato do projeto | Testes locais com provedores simulados; geração paga e qualidade editorial exigem validação real |
| Livros de colorir | Desenhos no PDF, verso em branco opcional, salvamento de miolo/capas/variações e referências aprovadas | Contratos e exportações locais; não certifica impressão ou aprovação KDP |
| Masters e ilustrações | Resolução de DNA/referências, histórico preservado, cenas e aplicação com identidade/hash da origem | Não promove candidato a Master automaticamente |
| Orquestrador e studios | Encaminhamento da origem salva, faixa etária e consentimento; HQ recebe história-base exata | Fontes adultas/adolescentes não entram silenciosamente no pipeline infantil |
| Produtos editoriais especializados | Conselhos infantis/adolescentes, devocionais, desenvolvimento pessoal, estudo, preparação para provas, atividades, guias, flashcards e formato livre; revisão, versões, PDF e EPUB | Saídas textuais reais; revisão humana de conteúdo, referências bíblicas, gabaritos e fontes continua necessária. Flashcards não têm imposição duplex certificada |
| Produção visual | Opções de mundo e cena, escolha humana, estimativa/reserva de custo, imagens e aplicação na cena aprovada | Falha ambígua não autoriza repetição paga automática. Edição por máscara ElementLock continua indisponível |
| HQ | Roteiro, painéis, falas, revisão, opções visuais, seleção de imagens, PDF com balões e EPUB | Origem e plano exatos; relatos pessoais exigem consentimento novo por ação. Não certifica impressão nem EPUBCheck |
| Governança de IA, dados, TI e cibersegurança | Quatro verificadores reais por ação coberta, incluindo geração especializada, visual, roteiro HQ, mídia, mensageria e callbacks conectados de tradução, atividades, direção de voz e revisão; evidências gravadas e relidas antes do provedor | Qualquer veto aplicável ou evidência desconhecida bloqueia. Não substitui auditoria externa nem cobre automaticamente todo novo chamador de provedor |
| Gmail e WhatsApp | Adaptadores, confirmação, escopo da conta, rascunhos com expiração, governança e recibos antes do envio; falha anterior ao envio não vira resultado incerto | Sem envio externo nesta revisão. WhatsApp exige estimativa explícita em `WHATSAPP_ESTIMATED_COST_USD`, incluída na revisão do rascunho; tarifa real não é inventada. OAuth/contas reais e receptor HTTPS de webhook continuam pendentes |
| Assistente pessoal | Prioridades, lembretes, briefing e fechamento diário persistidos por perfil | Sem agendador em segundo plano nem cofre OAuth por cliente |
| Mídia e ideias | Animatic MP4 local a partir das imagens originais aprovadas, áudio opcional, biblioteca de ideias e adaptador Replicate configurável | Animatic não equivale a animação corporal de personagens; modelo pago precisa de configuração e teste real |
| Tradução, narração e publicação | Guardas de idioma, identidade da origem, traduções aprovadas e consistência dos arquivos | Credenciais, voz e saída real precisam de teste; nenhuma publicação automática em loja |
| Interface e Jarvis | Banner original preservado, animações e aceno por interação verificados pelos contratos existentes | Microfone depende da permissão e do navegador; não foi validado ao vivo nesta revisão |
| Persistência | Leitura estrita, paginação completa e API opcional de atualização atômica/CAS; perfis, vínculos e transições da fila migrados | Piloto Supabase legado serializa esses consumidores somente no mesmo host, por opt-in explícito. SQL não executado; demais consumidores e gastos compartilhados ainda precisam migrar |
| Fila e recuperação | Tentativa exclusiva por job, pausa/cancelamento preservados e reconciliação explícita de resultados incertos; abrir uma página não interrompe outro executor | Não constitui worker distribuído; resultado recebido pode precisar de recuperação no provedor se armazenamento e sessão falharem juntos |
| Limites de conta | Cache/ativação de projetos, Book Doctor, registros locais, biblioteca e exportadores corrigidos revalidam conta e caminhos | Outros caminhos legados ainda precisam de migração. Interface comercial permanece bloqueada |

## Bloqueios antes de disponibilizar o SaaS comercialmente

A autora confirmou em 17/10/2026 que os provedores de IA e o armazenamento estão configurados nos Secrets do Streamlit. Essa configuração pertence ao ambiente publicado e não foi copiada para esta sessão de desenvolvimento. A confirmação de configuração é distinta da execução de uma geração real e da observação da versão implantada.

O modo comercial continua bloqueado intencionalmente. O piloto mantém o namespace de autoria existente; não inventa autenticação de cliente. Identidade OIDC verificada e controles de namespace não resolvem, por si sós, os itens abaixo.

1. Isolar arquivos, exportações e estado de runtime legados por cliente.
2. Migrar as atualizações de índices dos consumidores para a API atômica. Revisar, aplicar e validar a migração Supabase em ambiente apropriado antes de ativar `rpc_cas`; veja [STORAGE_CONCURRENCY.md](docs/STORAGE_CONCURRENCY.md).
3. Configurar e testar identidade, permissões, provedores de IA/imagem/voz, armazenamento e integrações reais sem registrar credenciais ou manuscritos nos relatórios.
4. Implementar receptor público de webhook, agendamento e proteção de credenciais por cliente quando esses serviços forem oferecidos.
5. Validar cobrança, planos e cotas, backup/restauração, observabilidade, limites de custo e operação com múltiplos workers.
6. Fazer uma aceitação ponta a ponta no ambiente implantado: novo livro, colorir, tradução, narração, HQ, exportação e recuperação após interrupção, com aprovação humana para gastos e envios.

## Como interpretar os testes

A revisão de 17/10 acrescenta contratos de execução por cargo e casos comportamentais explícitos para os 31 papéis. Cada caso chama uma função real, verifica entrada/saída e substitui o provedor externo quando necessário. A configuração das skills não é uma medição de excelência profissional; qualidade editorial, fidelidade visual, voz e resultados de serviços reais precisam de revisão própria.

O mapa emocional agora possui aprovação vinculada à obra, às cenas, ao DNA e ao estilo. Alterações invalidam a aprovação antes de novas imagens. O fluxo central/HQ carrega direção canônica e vínculo painel–cena; o ilustrador legado também exige mapa e referência aprovados, aplica o Style DNA e verifica a fonte persistida antes do provedor e do salvamento do lote. No caminho legado, o callback de cena usa uma referência principal; referências simultâneas de múltiplos World/Style Masters pertencem ao fluxo visual central. Capas e contracapas narrativas aplicam o Style DNA da obra, recebem o DNA dos personagens e todas as referências nos adaptadores compatíveis. O DNA do Master prevalece sobre presets genéricos nas páginas e capas de colorir.

O AutoSave atualiza somente o destino explícito em `storage_path`. Um rascunho sem referência cria uma obra nova, mesmo que já exista apenas um livro com o mesmo título; os checkpoints seguintes conservam o novo destino. Esta proteção não equivale a controle transacional entre vários editores.

No CLI de exemplo, uma revisão reprovada tem limite de tentativas; aprovação editorial sem mapa emocional encerra a execução com rascunho preservado. A retomada explícita após a revisão emocional não reescreve a história. Nenhum registro de cargo dispara sozinho todos os demais agentes.

Os testes desta revisão exercitam código, persistência local, arquivos exportados e contratos com provedores simulados. A revisão independente também verifica consentimento de relatos reais, identidade de origem, governança e abertura inicial das páginas. A contagem final e o commit efetivamente verificado ficam registrados no pull request e no GitHub Actions. Nenhuma migração remota, envio de mensagem, compra de geração ou publicação em loja é executada pelos testes.

O relatório anterior, [README_IMPLEMENTATION_STATUS.md](README_IMPLEMENTATION_STATUS.md), permanece como fotografia histórica da auditoria inicial. Este documento prevalece para o escopo adicional desta integração; pendências de serviços reais não devem ser marcadas como concluídas apenas porque a suíte local passou.
