# Salvamento e conexões entre os Studios

Esta entrega conecta os fluxos de criação às proteções da geração editorial. Os testes executam as telas Streamlit e o armazenamento temporário; os provedores são simulados. A aceitação autenticada com os serviços reais no Streamlit permanece necessária.

## Comportamento implementado

| Fluxo | Comportamento |
| --- | --- |
| Livro narrativo | O salvamento compara os campos editados com a versão efetivamente aberta, preserva alterações independentes e recusa sobrescrever um campo alterado em outra sessão. |
| Resultado recebido sem confirmação de salvamento | O resultado fica disponível para conferir e baixar. É possível tentar apenas o salvamento, reabrir a versão atual e confirmar a reaplicação do resultado. Não se repete a geração nessa recuperação. |
| Criar, Retomar e Roteirista | Uma pendência de salvamento pausa novas etapas de geração. O grafo conserva os resultados recebidos e os metadados salvos que não fazem parte do seu esquema tipado. |
| Livro de colorir | O estado atualizado após cada salvamento permanece na sessão, permitindo continuar da imagem aprovada à diagramação e ao PDF sem perder a referência do projeto. |
| Autoria, skills e referências bíblicas | As telas atualizam somente os campos pretendidos no projeto selecionado. Alterações conflitantes permanecem disponíveis para baixar e revisar. |
| Mapa emocional | A revisão é vinculada à história, aos personagens, ao estilo e à referência exata. A aprovação não é transferida por coincidência de título. |
| Imagem aprovada | A aplicação atualiza os campos de imagem no livro de origem e preserva o registro de geração e a imagem anterior. Não promove automaticamente uma candidata a Master oficial. |
| Produtos especializados | A opção de planejar ilustrações abre o mesmo produto salvo no Orquestrador. Público adolescente, adulto ou personalizado acompanha a direção visual, sem presumir uma faixa infantil. |
| Dados pessoais | Produtos baseados em experiências reais exigem consentimento atual também nas ações visuais. A aprovação anterior do texto não substitui essa confirmação. |
| Diagnóstico | Reconhece os provedores configurados, inclusive Gemini/Google e Groq. O teste de armazenamento só informa sucesso após confirmar também a remoção de seu arquivo temporário. |

## Recuperar um resultado

Quando aparecer o aviso de resultado aguardando salvamento, confira e baixe a cópia recebida. “Tentar salvar resultado recebido” repete somente a gravação. Se houver conflito, “Reabrir livro para conferir” apresenta a versão atual e conserva o resultado recebido separadamente. Após revisar, a confirmação permite reaplicar as alterações; uma nova edição concorrente ainda poderá interromper essa gravação.

A versão observada fica em um registro interno limitado por tamanho e quantidade. O estado da sessão contém apenas uma referência opaca, sem cópia oculta de todo o livro nos prompts. Reinício de worker ou expiração desse registro exige reabrir o livro; o salvamento não inventa uma versão observada a partir de uma leitura tardia. O download permite preservar o resultado antes de encerrar a sessão.

## Ilustrações opcionais

Em Produtos Editoriais, abra um produto salvo com conteúdo concluído e use “Planejar ilustrações no Orquestrador”. O conteúdo permanece no mesmo livro. O pré-voo exige aprovação do conteúdo, personagens, cenários, estilo e direção emocional antes das chamadas visuais. A opção não compra imagens automaticamente.

## Limites da evidência

Os testes de integração verificam geração simulada, chamadas pagas não repetidas, retomada, permissões, conflitos, exportações reais e preservação dos Masters de teste. Não comprovam qualidade de uma imagem gerada por um provedor real, duração da abertura autenticada do site, funcionamento do microfone em cada navegador ou implantação do commit pelo Streamlit.

O backend legado conserva a limitação de coordenação ao mesmo host/cache. A migração RPC e os limites financeiros distribuídos não são ativados por esta entrega. As condições para operação comercial permanecem em [OPERATIONAL_READINESS.md](OPERATIONAL_READINESS.md).
