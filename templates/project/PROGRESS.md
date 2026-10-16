# PROGRESS

> Estado do projeto para humanos e agentes. Atualizado ao fim de cada feature
> pelo `/build auto`. Mantenha curto: detalhes ficam nas specs{{#cortex}} e
> decisões ficam na memória do cortex-lite{{/cortex}}.

## Estado atual
- Última feature concluída: A CONFIRMAR
- Em andamento: nenhuma
- Próxima spec: {{SPECS_DIR}}/{{NEXT_SPEC}}-SPEC-<feature>.md

## Histórico de features
| Nº | Feature | Status | Integrações lidas/escritas | Observação |
|---|---|---|---|---|

{{^cortex}}
## Decisões
<!-- Decisões que valem para todo o projeto, uma linha cada, com a spec de origem. -->

## Aprendizados
<!-- Lições que vão se repetir. Só fatos do projeto; nada de preferência pessoal. -->

{{/cortex}}
## Testes
- Unitários (developer) e contrato com mock (contract-tester, em `tests/contract/`):
  `{{TEST_SUITE_CMD}}`
- Integração com serviços reais (`@pytest.mark.integration`): **nunca** rodados por
  agentes. Rodar manualmente contra o ambiente de desenvolvimento antes do deploy:
  `{{TEST_INTEGRATION_CMD}}`
- Fixtures em `tests/fixtures/` são sempre fictícias.

## Setup para um novo dev
- Clonar o repositório e instalar as dependências do projeto.
- `git config core.hooksPath .githooks` (ativa o pre-commit da squad).
{{#rtk}}
- Instalar o rtk e rodar `rtk init`.
{{/rtk}}
{{#ponytail}}
- Instalar o plugin Ponytail.
{{/ponytail}}
{{#cortex}}
- Instalar o plugin cortex-lite (memória) e ler `docs/MEMORIA.md`.
{{/cortex}}
{{#agentmeter}}
- Instalar o plugin agentmeter e rodar `/agentmeter:setup`.
{{/agentmeter}}
- Abrir o Claude Code e rodar `/onboard`.

## Como trabalhar
`/spec <feature>` → aprovar a spec → `/clear` → `/build auto NNN` → aprovar o plano → `/review` → testes de integração → push/deploy.
