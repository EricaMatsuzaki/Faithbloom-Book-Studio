# Refinamento 26 — Localization Excellence

## Objetivo
Transformar o Tradutor do FaithBloom em um sistema de localização literária infantil por locale/mercado, preservando o Master e produzindo uma edição que soe natural para crianças do destino.

## Princípios
- tradução não é equivalência palavra por palavra;
- preservar fatos, personagens, Character DNA, moral, referência bíblica e intenção;
- preservar o FaithBloom Heart Arc™: encantamento → emoção → experiência → descoberta → transformação → fé;
- preservar humor, musicalidade, refrões, participação, page-turn e recompensa emocional quando presentes;
- transcriação é permitida apenas para recuperar efeito narrativo perdido, sem alterar fatos centrais;
- adaptação cultural nunca deve caricaturar ou transplantar automaticamente a história para outro país;
- Bible Guard continua absoluto: texto bíblico não é traduzido livremente pela IA;
- revisão humana competente no locale continua recomendada para edição final importante.

## Especialização japonesa — 日本の児童文学・絵本
`ja-JP` recebe uma camada específica de linguagem infantil japonesa:
- orientação de kanji/kana por faixa etária;
- ritmo e legibilidade apropriados a 絵本 e leitura infantil;
- registro natural entre irmãos, amigos, professores e adultos;
- prevenção de japonês gramaticalmente correto porém com aparência de tradução mecânica;
- uso contextual de 擬音語 (giongo), 擬声語 (giseigo) e 擬態語 (gitaigo);
- onomatopeias/miméticos escolhidos por evento, emoção, intensidade e idade, nunca por tabela literal 1:1.

## Faixas japonesas
- 3–5: hiragana predominante, frases curtas, repetição, leitura em voz alta e linguagem sonora forte;
- 3–8: leitura clara, kanji básico com cautela e musicalidade;
- 6–8: leitor iniciante, mais diálogo/causa-consequência, kanji-kana natural e sem infantilização excessiva;
- 9–12: vocabulário e kanji mais ricos, nuance emocional e uso menos infantilizado de miméticos.

## Arquitetura
`agents/tradutor.py` continua sendo o agente formal `translator_localizer`, herda o FaithBloom Literary Excellence Charter e agora também injeta `localization_excellence_contract()` por locale.

Cada edição salva `localization_excellence_profile`, e o estado mantém `localization_quality_profiles` por locale para auditoria.

## Originalidade
A camada aprende princípios gerais de literatura infantil/localização. É proibido imitar voz, bordões, personagens, refrões, layout distintivo ou identidade de obra/editora existente.

## Mercado
A localização busca naturalidade e adequação ao leitor local. Ela não promete vendas, ranking ou aceitação por plataforma. Bestseller Readiness continua tratando apenas fatores controláveis e evidência real de mercado quando houver alegações comerciais.
