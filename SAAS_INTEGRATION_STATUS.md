# Estado da integração do FaithBloom

Atualizado em 16/10/2026. Este documento descreve o código desta revisão. A existência de um módulo, uma tela ou um teste simulado não comprova que o respectivo serviço já esteja ativo no site.

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
| Governança de IA, dados, TI e cibersegurança | Quatro agentes com diagnósticos determinísticos, evidências sanitizadas e histórico; autorização antes das novas gerações especializadas, visuais e de roteiro HQ | Não substitui auditoria de segurança. A cobertura não é universal: chamadas legadas e mensageria ainda exigem extensão |
| Gmail e WhatsApp | Adaptadores, confirmação, escopo da conta, rascunhos com expiração, recibos e tratamento de envio incerto | Sem envio externo nesta revisão. OAuth/contas reais pendentes; WhatsApp ainda precisa de receptor HTTPS público para webhooks |
| Assistente pessoal | Prioridades, lembretes, briefing e fechamento diário persistidos por perfil | Sem agendador em segundo plano nem cofre OAuth por cliente |
| Mídia e ideias | Animatic MP4 local a partir das imagens originais aprovadas, áudio opcional, biblioteca de ideias e adaptador Replicate configurável | Animatic não equivale a animação corporal de personagens; modelo pago precisa de configuração e teste real |
| Tradução, narração e publicação | Guardas de idioma, identidade da origem, traduções aprovadas e consistência dos arquivos | Credenciais, voz e saída real precisam de teste; nenhuma publicação automática em loja |
| Interface e Jarvis | Banner original preservado, animações e aceno por interação verificados pelos contratos existentes | Microfone depende da permissão e do navegador; não foi validado ao vivo nesta revisão |
| Persistência | Leitura estrita, paginação completa e API opcional de atualização atômica/CAS, com testes locais entre processos | SQL Supabase fornecido, mas não executado; consumidores legados ainda precisam migrar para a API de atualização |

## Bloqueios antes de disponibilizar o SaaS comercialmente

O modo comercial continua bloqueado intencionalmente. O piloto mantém o namespace de autoria existente; não inventa autenticação de cliente. Identidade OIDC verificada e controles de namespace não resolvem, por si sós, os itens abaixo.

1. Isolar arquivos, exportações e estado de runtime legados por cliente.
2. Migrar as atualizações de índices dos consumidores para a API atômica. Revisar, aplicar e validar a migração Supabase em ambiente apropriado antes de ativar `rpc_cas`; veja [STORAGE_CONCURRENCY.md](docs/STORAGE_CONCURRENCY.md).
3. Configurar e testar identidade, permissões, provedores de IA/imagem/voz, armazenamento e integrações reais sem registrar credenciais ou manuscritos nos relatórios.
4. Implementar receptor público de webhook, agendamento e proteção de credenciais por cliente quando esses serviços forem oferecidos.
5. Validar cobrança, planos e cotas, backup/restauração, observabilidade, limites de custo e operação com múltiplos workers.
6. Fazer uma aceitação ponta a ponta no ambiente implantado: novo livro, colorir, tradução, narração, HQ, exportação e recuperação após interrupção, com aprovação humana para gastos e envios.

## Como interpretar os testes

Os testes desta revisão exercitam código, persistência local, arquivos exportados e contratos com provedores simulados. A revisão independente também verifica consentimento de relatos reais, identidade de origem, governança e abertura inicial das páginas. A contagem final e o commit efetivamente verificado ficam registrados no pull request e no GitHub Actions. Nenhuma migração remota, envio de mensagem, compra de geração ou publicação em loja é executada pelos testes.

O relatório anterior, [README_IMPLEMENTATION_STATUS.md](README_IMPLEMENTATION_STATUS.md), permanece como fotografia histórica da auditoria inicial. Este documento prevalece para o escopo adicional desta integração; pendências de serviços reais não devem ser marcadas como concluídas apenas porque a suíte local passou.
