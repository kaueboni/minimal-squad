<!-- minimal-squad:start (gerado pelo plugin minimal-squad; edite fora deste bloco) -->
## Squad SDD (minimal-squad)
- Fluxo: `/spec <feature>` → `/build auto NNN` → `/review`. Onboarding: `/onboard`.
- `{{BASE_SPEC}}` é a spec de base e é FIXA: agentes nunca escrevem nele.
- Specs de feature: `{{SPECS_DIR}}/NNN-SPEC-<feature>.md`. Plano e tarefas: `tasks/plan.md`, `tasks/todo.md`.
- Estado do projeto, histórico e setup: `PROGRESS.md`.{{#cortex}} Decisões e lições: memória do cortex-lite (export em `docs/MEMORIA.md`).{{/cortex}}
- Testes: `{{TEST_SUITE_CMD}}`. Integração (só humanos): `{{TEST_INTEGRATION_CMD}}`.
- As convenções deste projeto prevalecem sobre os padrões das skills.
- Nunca: push, deploy, ler `.env`, dados reais em fixtures, testes ou commits.
<!-- minimal-squad:end -->
