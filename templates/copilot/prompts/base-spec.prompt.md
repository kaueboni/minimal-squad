---
description: 'Escreve a spec de base ({{BASE_SPEC}}) descrevendo o projeto como ele é hoje e para para aprovação. Use uma vez, logo após instalar a squad.'
---

Você vai escrever a spec de base do projeto em `{{BASE_SPEC}}`.

Se `{{BASE_SPEC}}` já existir, não edite: diga que ela já existe e pare.

Leia e siga a skill `.github/skills/spec-driven-development/SKILL.md` em
modo BROWNFIELD: descreva o projeto COMO ELE É HOJE, sem propor nada novo.
Leia o código; não edite nada além do próprio `{{BASE_SPEC}}`.

Seções:
- Objective
- Tech Stack
- Commands (comandos completos e reais; "NÃO EXISTE" se faltar)
- Project Structure
- Code Style (UM trecho real)
- Testing Strategy (estado atual e alvo)
- Boundaries (Always / Ask first / Never)
- Success Criteria (saúde do projeto)
- Open Questions
- Débitos Técnicos (ordenados por risco; não corrija nada)

Boundaries mínimos:
- Never: push/deploy por agentes, segredos no código ou em commits,
  concatenar entrada em consultas, apagar teste falhando sem aprovação,
  dados reais em fixtures.
- Ask first: mudança de schema ou contrato de integração,
  permissão/credencial nova, dependência nova, configuração de
  infraestrutura, remover código fora do escopo.

Depois de escrever:
1. Confira se a configuração de pytest tem o marcador `integration`. Se
   não tiver, acrescente só a linha
   `integration: toca serviços reais; só humanos rodam` (em
   `[tool.pytest.ini_options]` no pyproject.toml, ou num pytest.ini se não
   houver pyproject) e rode `{{TEST_SUITE_CMD}}`.
2. Mostre um resumo, as Open Questions e os 3 débitos mais arriscados.
3. PARE e espere aprovação. Não faça commit: o usuário revisa e commita
   (`docs: spec de base`). O pre-commit bloqueia commits que alteram
   `{{BASE_SPEC}}`; este primeiro commit é feito com `--no-verify`, por um
   humano.
