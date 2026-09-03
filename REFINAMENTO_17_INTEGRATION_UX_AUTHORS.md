# Refinamento 17 — Integration & UX Hardening + Author & Contributor Profiles

## Objetivos
- separar usuário autenticado de autor/crédito editorial;
- permitir autor principal, coautores, pseudônimo e colaboradores por projeto;
- preservar snapshots de crédito para não reescrever edições antigas silenciosamente;
- remover defaults funcionais que forçavam `Erica Matsuzaki` como autora de qualquer livro;
- propagar autoria estruturada para metadata, capa, PDF e EPUB;
- invalidar fingerprint editorial quando autoria mudar;
- padronizar contexto de projeto/asset e handoff entre Studios;
- manter Project Hub e Integration Center como navegação, nunca como edição silenciosa.

## Compatibilidade
O campo legado `autora` continua existindo para módulos antigos, mas passa a ser derivado da autoria estruturada quando houver perfis associados.

## Regra central
**Usuário do SaaS != autor do livro.** O mesmo usuário pode produzir projetos assinados por pessoas diferentes, e uma pessoa pode aparecer com papéis distintos em obras diferentes.
