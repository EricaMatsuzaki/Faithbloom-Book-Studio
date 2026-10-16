# Revisão funcional do FaithBloom

Revisão solicitada pela autora em outubro de 2026. Base verificada: `9b0e6a8df0b69d972db205cc8f8bfcd44687637c`, branch `feature/refinamento-24-prompt-mestre-compliance`.

## Conclusão

Não é possível afirmar que todos os produtos estão em pleno funcionamento em produção. A revisão encontrou falhas reproduzíveis nos fluxos de histórias, colorir, tradução, áudio, publicação e salvamento. As correções deste PR passaram nos testes locais; geração com provedores reais e armazenamento de produção permanecem pendentes de validação. Música e animação/vídeo ainda não possuem integração de geração final.

## Evidência

- Antes das correções: 787 testes e 2 subtestes passaram, apesar dos problemas de integração identificados pela revisão.
- Depois das correções: **894 testes e 2 subtestes passaram**, incluindo **107 novos casos de regressão**.
- Navegação real a partir de `app.py`: **59/59 aberturas** aprovadas, sem chamadas externas e sem mudanças no código durante o ensaio final.
- **19/19 telas principais** abriram com livro e perfil sintéticos salvos. Criação de Activity Book, criação de Audiobook e execução/salvamento de Quality Guardian também passaram pelas interfaces reais.
- PDFs de colorir reais foram inspecionados: 24 páginas, 11 desenhos incorporados, versos em branco e opções de sangria. Arquivos ausentes, resolução inadequada ou inspeção de PDF inválida bloqueiam o resultado final.
- O diagnóstico local do Engenheiro do projeto foi executado por `agents.engenheiro_saas_automacao.run_diagnostic`. O registro dos 27 papéis está consistente. Auditoria estática e revisão semântica são verificações distintas; um diagnóstico gerado não é apresentado como teste ou deploy realizado.

## Produtos e serviços revisados

| Produto ou serviço | Verificação e resultado |
| --- | --- |
| Novos Story Books e estilos narrativos | Handoffs dos seis estilos, histórias escolhidas, comparativo, resposta inválida, complementos editoriais e recuperação de falhas validados com provedores simulados. |
| Coloring Books | Geração/conversão com referência, variações, rascunhos, Masters, miolo, capa e recuperação do armazenamento validados em interfaces reais e armazenamento isolado. |
| Activity Books | Criação e composição testadas pela interface; regras e exportação cobertas pela suíte. |
| Personagens, DNA, Masters e biblioteca | Contratos, seleção e persistência testados. O Coloring Studio recebe os bytes originais e o DNA do Master aprovado sem promoção ou alteração automática. Fidelidade de uma imagem realmente gerada exige avaliação visual. |
| Imagens, ilustrações e restauração | Referências, histórico, aprovação e recuperação testados; resultados visuais de provedores reais não foram produzidos nesta auditoria. |
| Revisão, Remaster e Book Doctor | Testes de contratos, roteamento, versões, aprovações e handoffs aprovados. Pareceres/editoriais gerados por IA ainda exigem revisão humana. |
| Tradução e localização, incluindo japonês | Widgets, fonte exata, rascunhos, versões, fingerprints, Bible Guard e leitura infantil cobertos. Qualidade linguística real depende de geração e revisão de resultados. |
| Audiobook, TTS e Voice Lab | Interfaces, locale, edição aprovada, direção, fila, arquivos e mix cobertos; TTS real, custos, disponibilidade e qualidade da voz não certificados. |
| PDF, EPUB e distribuição | Exportadores e regras testados. Edições não podem ser rotuladas com outro idioma sem uma fonte localizada. Aceitação por KDP/lojas é externa; envio permanece manual. |
| Projetos, coleções, perfis e salvamento | Testes de retomada, identidade, versões, nomes repetidos, arquivos, vínculo de perfil e falhas de armazenamento aprovados. Supabase de produção não foi exercitado. |
| Jarvis, navegação, fila e automações | Testes locais existentes e ensaio de abertura aprovados. Login, sessão, microfone e integrações externas ao vivo não fazem parte do ensaio offline. |
| Idea Vault | Fundação/contratos e planejamento cobertos; não equivale a um gerador de mídia final. |
| Música e animação/vídeo | `provider_integration_pending` em `creative_studios.py`; **geração final ainda indisponível**. |

## Falhas corrigidas

### Histórias e preservação de gerações

- Os estilos adicionais eram normalizados, mas o Roteirista buscava seus rótulos no registro dos quatro estilos antigos, causando `KeyError` antes da chamada de IA.
- O comparativo gerava quatro versões antes de salvar qualquer uma. Agora cada sucesso recebe um checkpoint; uma falha no provedor ou no salvamento interrompe as chamadas seguintes e mantém os resultados concluídos.
- Respostas sem texto utilizável não podem substituir uma história anterior nem ser apresentadas como versões completas. Esta validação não substitui a revisão de quantidade de páginas e qualidade editorial.
- A tela de quatro estilos podia reutilizar o caminho de outro livro da mesma sessão. O caminho passa a pertencer ao estado atual.
- Complementos editoriais reutilizam o gerador/validador canônico por um botão explícito que informa consumo de créditos; não são uma chamada paga oculta.
- A ilustração em lote reutiliza cenas existentes, resolve nome e DNA de forma consistente, preserva substituições no histórico e salva cada resultado. Referência recém-gerada também recebe checkpoint, sem aprovação automática.

### Coloring Books e Masters

- O layout `colorir` não era reconhecido pelo renderer/preflight compartilhado. As páginas agora incorporam os desenhos corretos e seus versos vazios.
- Miolo e capa recebem ações de exportação e salvamento durável no mesmo projeto, inclusive PDF da capa. Falhas permitem salvar novamente sem outra geração.
- Rascunhos e variações são salvos antes da diagramação; interrupções preservam as páginas concluídas e o histórico. Novo livro limpa o preview/caminho da obra anterior.
- Falha no vínculo de perfil mantém o arquivo já salvo e o perfil original para retry, sem criar outro projeto.
- Conversões exigem imagem disponível. A biblioteca consulta Masters oficiais aprovados e permitidos para colorir, além das referências legadas; candidatos, arquivados e referências inconsistentes não são promovidos.

### Tradução, áudio e publicação

- `AgeOption` não suportava cópia/pickle feita pelos widgets do Streamlit, impedindo a abertura da Tradução.
- Rascunhos são preservados por fonte, conteúdo e mercado, sem mistura entre livros, idiomas ou metadados transitórios de migração. Livros de mesmo título são diferenciados pelo caminho real.
- Audiobook bloqueia edição sem texto localizado válido, recupera apenas a edição aprovada da mesma fonte e evita misturar a lição original em outro idioma.
- Controles de áudio consideram o provedor selecionado, incluindo Gemini. Foram corrigidos o erro do magic do Streamlit ao mostrar pendências e a constante de configuração incompatível no Voice Lab.
- Distribuição e exportação bloqueiam pacote rotulado com locale divergente da fonte, inclusive planos antigos e mudanças de status. Não foi adicionado envio automático às lojas.

### Identidade e armazenamento

- A materialização recursiva convertia `storage_path`/`source_ref` JSON em caminhos locais de cache, quebrando a retomada. Referências JSON mantêm sua identidade; mídia continua materializando e a função explícita `materializar()` mantém seu contrato.
- Novos livros de mesmo título salvos no mesmo segundo podiam sobrescrever-se. Os novos nomes possuem sufixo único; arquivos existentes e caminhos explícitos de atualização permanecem válidos.
- AutoSave sem caminho explícito não escolhe arbitrariamente entre dois projetos de título/coleção iguais. O reuso de um candidato único continua compatível.

## Limites e próxima validação de produção

O ambiente desta auditoria não possui credenciais de geração nem acesso configurado ao armazenamento de produção. Isso não significa que estejam ausentes no Streamlit; significa que não foram testadas aqui. Nenhuma chamada paga, promoção de Master, alteração de dados reais ou publicação externa foi feita.

Após a integração/deploy do PR, ainda é necessário gerar um Story Book e um Coloring Book controlados usando os provedores configurados, reabrir os arquivos a partir do Supabase, testar tradução e áudio reais e avaliar fidelidade visual, narrativa e idioma. Cotas, cobrança, disponibilidade dos modelos, permissões de microfone e aceitação dos arquivos nas lojas dependem desses ensaios.

## Reproduzir os testes

```bash
FAITHBLOOM_STORAGE_MODE=local FAITHBLOOM_LOCAL_DATA_DIR=/tmp/faithbloom-audit python -m pytest -q --tb=short
```

Os cinco novos arquivos de regressão cobrem histórias, colorir, serviços, recuperação de ilustrações e identidade de projetos. Uma fixture antiga de resposta completa vazia foi substituída por uma cena válida, preservando suas verificações de prompt; nenhum teste foi desabilitado para obter aprovação.

O PR é uma proposta revisável para a feature. Resultados locais não devem ser apresentados como validação do site já publicado.
