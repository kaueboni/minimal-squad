---
description: 'Instala a squad SDD do minimal-squad neste projeto (agentes, comandos, skills, permissões, pre-commit). Use --integracoes para religar cortex-lite/agentmeter, ou --atualizar após atualizar o plugin.'
argument-hint: '[--integracoes | --atualizar]'
---

Você vai instalar (ou atualizar) a squad do plugin minimal-squad NESTE
projeto. Os arquivos do plugin estão em: ${CLAUDE_PLUGIN_ROOT}
Argumentos: $ARGUMENTS

## Regras durante toda a execução
- Tudo que for gravado vem do instalador determinístico
  (`scripts/install.py`) ou é texto que você escreve nas etapas marcadas
  como "você escreve". Não copie templates à mão.
- Nunca sobrescreva arquivo do usuário. O instalador já protege isso: o que
  conflitar vai para `.claude/.minimal-squad-pending/` e você só reporta.
- Nunca faça push, deploy, nem rode testes marcados como integration.
- Um commit por etapa, com `git add` só dos caminhos daquela etapa
  (nunca `git add -A`).
- Nunca copie dados reais (registros, saídas de consultas, conteúdo de
  memória com dados pessoais) para arquivos, commits ou memória.
- Se o Ponytail estiver ativo, desligue-o durante esta instalação
  ("stop ponytail") e lembre o usuário de religar no fim.

## 0. Python
Descubra o comando Python desta máquina: tente `python3 --version`, depois
`python --version`, depois `py --version`. Chame de PY o primeiro que
funcionar. Se nenhum funcionar, pare e explique.

## 1. Detectar (só leitura)
Rode: `PY "${CLAUDE_PLUGIN_ROOT}/scripts/detect.py" --project .`
Leia o JSON. Se `git.is_repo` for false, pare: a squad precisa de git.

Modo pelo argumento:
- vazio → instalação completa (etapas 2 a 11);
- `--integracoes` → vá para "Modo integrações" no fim;
- `--atualizar` → vá para "Modo atualizar" no fim.

## 2. Confirmar parâmetros (PARE aqui)
Mostre ao usuário, de forma compacta:
- o bloco `suggested_config.params` e `suggested_config.integrations`, com a
  evidência de cada valor (tests.evidence, tests.mentions, specs, hooks);
- avisos, se houver:
  - `git.clean` false → precisa commitar ou guardar antes;
  - `claude_dir.conflicting_agents` / `conflicting_commands` → já existem
    arquivos com esses nomes; as versões da squad irão para pending;
  - `claude_dir.agent_tool_denied` → subagentes bloqueados no settings;
  - `hooks.conflict` → o projeto já usa outro mecanismo de hook; o
    pre-commit da squad não será instalado;
  - `specs.feature_spec_dirs` diferente de `specs_dir` → há specs antigas
    em outro lugar; pergunte se quer mantê-las onde estão (a numeração
    continua a partir da maior) ou movê-las com `git mv` para `specs_dir`;
  - `pytest_config.file` vazio → vou criar a configuração do marcador
    `integration` (em pyproject.toml se existir, senão pytest.ini);
  - integrações marcadas como prováveis: peça confirmação (a detecção é
    por melhor esforço).
Pergunte se confirma ou o que ajustar (use AskUserQuestion se disponível).
PARE e espere a resposta. Não continue sem confirmação explícita.

## 3. Branch
Exija `git status --porcelain` vazio. Crie e entre na branch
`chore/minimal-squad` (se já estiver nela, siga).

## 4. Configuração
Grave `.claude/minimal-squad.json` com o objeto confirmado (version,
params, integrations, overrides) e acrescente `"next_spec"` com
`specs.next_number`. Se o usuário escolheu mover specs antigas, faça o
`git mv` agora.
Commit: `chore(squad): configuração do minimal-squad`.

## 5. Spec de base (você escreve; só se não existir)
Se o arquivo `params.base_spec` não existir:
- Use a skill spec-driven-development em modo BROWNFIELD: descreva o
  projeto COMO ELE É HOJE, sem propor nada novo. Leia o código; não edite
  nada além do próprio arquivo da spec.
- Seções: Objective, Tech Stack, Commands (comandos completos e reais;
  "NÃO EXISTE" se faltar), Project Structure, Code Style (UM trecho real),
  Testing Strategy (estado atual e alvo), Boundaries (Always / Ask first /
  Never), Success Criteria (saúde do projeto), Open Questions e
  "Débitos Técnicos" (ordenados por risco; não corrija nada).
- Boundaries mínimos: Never → push/deploy por agentes, segredos no código
  ou em commits, concatenar entrada em consultas, apagar teste falhando sem
  aprovação, dados reais em fixtures. Ask first → mudança de schema ou
  contrato de integração, permissão/credencial nova, dependência nova,
  configuração de infraestrutura, remover código fora do escopo.
- Mostre um resumo, as Open Questions e os 3 débitos mais arriscados.
  PARE e espere aprovação. Aprovado: commit `docs: spec de base`.

## 6. Inventário e ajuste dos agentes
Rode: `PY "${CLAUDE_PLUGIN_ROOT}/scripts/inventory.py" --project .`
Se houver sessões, cruze o resultado com o que cada agente já recebe
(veja `scripts/common.py`: BASE_TOOLS e BASE_SKILLS) e monte a tabela:
| item | tipo | vezes | agente | ação (adicionar / permissão / descartar / a confirmar) | motivo |
Regras, nesta ordem:
a. Ferramentas que escrevem (Edit, Write, NotebookEdit) só para developer,
   tech-lead e contract-tester. Nenhum agente recebe Agent.
b. MCP: só ferramentas de LEITURA (get, list, read, search, describe,
   fetch) podem ir para discovery ou researcher. MCP que executa SQL,
   escreve, cria, apaga, roda job ou faz deploy: descartar. Na dúvida:
   "a confirmar", sem adicionar. As ferramentas do cortex-lite já são
   tratadas pela integração; ignore-as aqui.
c. Comandos de terminal frequentes viram permissão (`overrides.permissions.allow`)
   se forem de leitura ou teste; nunca deploy, push, rm ou escrita em
   serviços externos.
d. Skills frequentes que existem em `.claude/skills/` vão para o agente
   cuja função combina (`overrides.agents.<agente>.skills_extra`), no
   máximo 4 skills por agente.
e. Item usado 1 ou 2 vezes: descartar, salvo se essencial ao papel.
Grave as decisões em `overrides` no `.claude/minimal-squad.json` e mostre a
tabela. Commit: `chore(squad): ajustes pelo inventário`.

## 7. Instalação (determinística)
Rode cada grupo abaixo com
`PY "${CLAUDE_PLUGIN_ROOT}/scripts/install.py" --project . --steps <etapas>`
e leia o JSON de saída. Se `errors` não estiver vazio, PARE e mostre.
Depois de cada grupo, faça `git add` dos caminhos criados/atualizados e
commit:
1. `skills` → `chore(squad): skills de engenharia (Addy Osmani, MIT)`
2. `agents` → `chore(squad): subagentes`
3. `commands` → `chore(squad): comandos /spec /build /review /test /onboard`
4. `settings` → `chore(squad): permissões`
5. `layout,claude-md,progress,bin` → `chore(squad): estrutura do projeto`
   Inclua também `.claude/minimal-squad.lock.json` em todos os commits em
   que ele mudar.
6. githooks, por último: antes, rode `params.test_suite_cmd`. Se a suíte
   atual FALHAR, não instale o hook (ele bloquearia todo commit): reporte e
   siga. Se passar, rode a etapa `githooks` e faça o commit
   `chore(squad): pre-commit` (o próprio hook vai rodar; se falhar, mostre
   o motivo e pare).
Guarde a lista de `pending` de todas as rodadas para o relatório.

## 8. Marcador de integração do pytest (você escreve)
Se `pytest_config.has_integration_marker` for false, acrescente o marcador
`integration: toca serviços reais; só humanos rodam` na configuração de
pytest existente (só a linha do marcador, nada mais). Sem configuração:
crie `[tool.pytest.ini_options]` com `markers` no pyproject.toml, ou um
pytest.ini se não houver pyproject. Rode `params.test_suite_cmd` para
confirmar. Commit: `chore(squad): marcador integration do pytest`.

## 9. PROGRESS.md (você escreve)
Se o PROGRESS.md foi criado agora pelo instalador, preencha:
- "Estado atual": última feature concluída e se há tarefas abertas
  (tasks/todo.md);
- "Histórico de features": uma linha por spec NNN-SPEC existente (título,
  status pelo git log e tasks, integrações lidas/escritas).
Marque A CONFIRMAR o que não tiver certeza. Se o PROGRESS.md já existia,
não edite: liste no relatório o que falta nele.
Commit: `docs: PROGRESS.md`.

## 10. Memória (você escreve)
Se `history.auto_memory` for true, leia o MEMORY.md e os arquivos da pasta
de memória automática (só leitura) e classifique cada item em:
CONHECIMENTO DO PROJETO, PREFERÊNCIA PESSOAL ou DESATUALIZADO.
- Com cortex-lite: grave cada CONHECIMENTO DO PROJETO com memory_save
  (kind decisao, licao ou fato; título curto; motivo). Preferências
  pessoais podem ir como kind preferencia com escopo global, se o usuário
  quiser. Nunca grave segredos ou dados pessoais.
- Sem cortex-lite: acrescente os itens de CONHECIMENTO DO PROJETO às
  seções Decisões e Aprendizados do PROGRESS.md e faça commit.
Não apague nada da memória automática. No relatório, recomende desligá-la
em /memory depois de conferir a migração.

## 11. Verificação e relatório
- Rode `params.test_suite_cmd`.
- Abra cada `.claude/agents/*.md` e confira que o cabeçalho YAML está
  válido (name, description, tools, skills).
- Relatório final, curto:
  - commits feitos;
  - arquivos em pending (`.claude/.minimal-squad-pending/`), cada um com
    a sugestão: comparar com `diff` e decidir manualmente;
  - itens "a confirmar" do inventário;
  - skills instaladas que nunca apareceram no inventário (candidatas a
    remover depois);
  - o que não foi instalado e por quê (hook, researcher etc.).
- Próximos passos para o usuário:
  1. reiniciar o Claude Code (agentes e comandos carregam no início);
  2. testar um agente: `@"discovery (agent)" mapeie o projeto`;
  3. resolver os pending, se houver;
  4. abrir PR da branch `chore/minimal-squad`;
  5. primeira feature pequena: `/spec ...` e depois `/build auto NNN`.
Não faça push.

## Modo integrações (`--integracoes`)
1. Leia `.claude/minimal-squad.json` (se não existir, diga para rodar
   /minimal-squad:init sem argumentos e pare).
2. Compare `integrations` do arquivo com `suggested_config.integrations`
   do detect. Mostre as diferenças e PARE para confirmação.
3. Confirmado: atualize `integrations` no arquivo, exija git limpo, e rode
   o install com `--steps agents,commands,settings,claude-md,bin`.
4. Commit: `chore(squad): integrações atualizadas`. Relate pending.
5. Se o cortex-lite acabou de ser ligado e houver memória automática, ofereça
   rodar a etapa 10.

## Modo atualizar (`--atualizar`)
1. Leia `.claude/minimal-squad.json` (se não existir, pare como acima).
2. Rode o install com `--steps all --check` e mostre o que mudaria
   (created, updated, pending). PARE para confirmação.
3. Confirmado: exija git limpo, crie a branch `chore/minimal-squad-update`,
   rode `--steps all` sem `--check` e faça um commit
   `chore(squad): atualiza para a versão <plugin_version>`. Relate pending.
