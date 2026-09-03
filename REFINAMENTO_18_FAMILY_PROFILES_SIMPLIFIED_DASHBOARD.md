# Refinamento 18 — Family Profiles & Simplified Dashboard

## Objetivo
Simplificar a entrada do FaithBloom e permitir que várias pessoas organizem o próprio workspace sem confundir **usuário da aplicação**, **perfil pessoal** e **autoria editorial**.

## Entregas
- Perfis pessoais/familiares reutilizáveis com preferências de idioma, faixa etária, estilo, mercados e modo do dashboard.
- Vínculo opcional entre perfil pessoal e perfil editorial de autoria, sem autoria automática.
- Organização externa dos projetos por responsável e compartilhamento, sem modificar o Book Master ou fingerprint editorial.
- Thumbnail/capa opcional por projeto no dashboard.
- Projeto ativo preservado em `session_state` para navegação entre Studios.
- Dashboard simplificado por objetivo: criar, revisar, colorir, atividades, tradução, audiobook, biblioteca, Quality Guardian e publicação.
- Modo avançado preservado em um catálogo recolhível de ferramentas.
- Continuação por projetos recentes do perfil.
- Aviso explícito: perfil de workspace **não é** autenticação/ACL. Segurança multiusuário real continua dependendo de OIDC/backend.

## Regra de segurança
Trocar o responsável de um projeto no workspace não muda autoria, conteúdo, Quality Gate, pacote de publicação ou fingerprint editorial.
