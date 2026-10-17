# minimal-squad

Plugin do Claude Code que **instala no seu projeto** uma squad mínima de
spec-driven development (SDD): seis subagentes, cinco comandos, skills de
engenharia e guardrails. Depois de instalada, a squad vive no repositório
(`.claude/`), vai para o git e o time inteiro herda. O plugin só é
necessário para instalar, religar integrações e atualizar.

Python primeiro (pytest; ruff ou flake8 se o projeto usar).

## O que é instalado no projeto

| Onde | O quê |
|---|---|
| `.claude/agents/` | `discovery`, `researcher`, `tech-lead`, `contract-tester`, `developer`, `auditor` |
| `.claude/commands/` | `/spec`, `/build` (e `/build auto`), `/review`, `/test`, `/onboard` |
| `.claude/skills/` | 10 skills de [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) (MIT), cópia fixa |
| `.claude/references/` | checklists usados pelas skills |
| `.claude/settings.json` | permissões (merge; nada é removido) |
| `.githooks/` | pre-commit: spec de base fixa, busca de segredos, lint, testes |
| `CLAUDE.md` | um bloco curto delimitado (`minimal-squad:start/end`) |
| `PROGRESS.md` | estado do projeto, histórico, testes e setup (só se não existir) |
| `specs/`, `tasks/`, `tests/contract/`, `tests/fixtures/` | estrutura do fluxo |
| `.claude/minimal-squad.json` | parâmetros confirmados por você |
| `.claude/minimal-squad.lock.json` | hashes do que o plugin gravou (permite atualizar sem pisar em edições suas) |

### A squad

| Agente | Papel | Ferramentas | Modelo padrão |
|---|---|---|---|
| discovery | mapeia o projeto como ele é; só leitura | Read, Grep, Glob | haiku |
| researcher | confere documentação oficial | WebSearch, WebFetch | haiku |
| tech-lead | escreve a spec e o plano | Read, Grep, Glob, Write, Edit | sonnet |
| contract-tester | testes de contrato de integrações, antes do código | Read, Grep, Glob, Write, Bash | sonnet |
| developer | implementa uma tarefa com TDD | Read, Grep, Glob, Edit, Write, Bash | sonnet |
| auditor | audita; não edita | Read, Grep, Glob, Bash | sonnet |

### O fluxo

```
/spec <feature>        discovery → researcher → tech-lead escreve specs/NNN-SPEC-<feature>.md
                       ⏸ você aprova a spec
/build auto NNN        tech-lead gera tasks/plan.md e tasks/todo.md
                       ⏸ você aprova o plano
                       por tarefa: contract-tester (se "Integração: sim") → developer → auditor → commit
/review                auditor revisa a branch inteira
                       você roda os testes de integração, faz push e deploy
```

Convenções: `SPEC.md` é a spec de base e é **fixa** para os agentes;
testes de integração (`@pytest.mark.integration`) **nunca** são rodados por
agentes; fixtures são sempre fictícias.

## Instalação

### Ordem recomendada com os plugins parceiros

1. [agentmeter](https://github.com/kaueboni/agentmeter) (opcional): mede tokens por subagente desde o início.
2. [cortex-lite](https://github.com/kaueboni/cortex-lite) (opcional): memória entre sessões e agentes.
3. **minimal-squad**: o `/minimal-squad:init` detecta os dois e liga a squad a eles.

A ordem não é obrigatória: se instalar um parceiro depois, rode
`/minimal-squad:init --integracoes`.

### Instalar o plugin

```
/plugin marketplace add kaueboni/minimal-squad
/plugin install minimal-squad@minimal-squad
```

Requisitos: Claude Code com suporte a plugins, git, Python 3.9+ no PATH
(`python3`, `python` ou `py`).

**Windows:** instale o [Git for Windows](https://git-scm.com/download/win) (Git Bash). O Claude Code e o hook de pre-commit rodam nele. Se o projeto usa `.venv`, o `init` grava `test_cmd` e `lint_cmd` com o Python do venv (`.venv/Scripts/python -m pytest -q`), então não precisa ativar o ambiente para commitar.

### Instalar a squad num projeto

Na raiz do projeto (repositório git, sem mudanças pendentes):

```
/minimal-squad:init
```

O comando detecta os parâmetros (comando de testes, lint, specs existentes,
hooks, integrações), mostra tudo e **espera sua confirmação**. Depois cria a
branch `chore/minimal-squad` e aplica em etapas, com um commit por etapa.
Nada é publicado: você revisa e abre o PR.

Se um arquivo do projeto conflitar (por exemplo, um `/spec` seu), o plugin
**não sobrescreve**: grava a versão nova em `.claude/.minimal-squad-pending/`
e lista no relatório para você decidir.

Depois: reinicie o Claude Code.

## Integrações (opcionais e desacopladas)

O minimal-squad é o único que conhece os outros plugins. Eles não sabem da
squad.

- **cortex-lite**: cada agente recebe as ferramentas de memória do perfil
  dele (mapeamento em `templates/integrations/cortex-lite.json`):
  discovery e contract-tester → leitor; researcher → pesquisador;
  tech-lead → decisor; developer → executor; auditor → revisor. Ninguém
  recebe `memory_delete`. O `/build auto` exporta a memória para
  `docs/MEMORIA.md` no fim de cada feature.
- **agentmeter**: só observa; o `/build auto` sugere `/agentmeter:tokens --sessao`.
- **Ponytail** e **rtk**: detectados; o rtk ganha regras de permissão com
  prefixo `rtk`, e o Ponytail fica restrito ao diff de cada tarefa.

Sem eles, a squad funciona igual, só sem memória e sem medição.

## Comandos do plugin

| Comando | O que faz |
|---|---|
| `/minimal-squad:init` | instalação completa, com confirmação |
| `/minimal-squad:init --integracoes` | religa cortex-lite, agentmeter, Ponytail e rtk |
| `/minimal-squad:init --atualizar` | aplica uma versão nova do plugin (mostra antes o que muda) |

Os scripts também rodam direto, sem o Claude:

```
python scripts/detect.py --project <projeto>          # só lê
python scripts/inventory.py --project <projeto>       # uso real do Claude Code no projeto
python scripts/install.py --project <projeto> --steps all --check
```

## Segurança

- O instalador é determinístico e não usa rede.
- As permissões instaladas bloqueiam `git push`, `git reset --hard`,
  `git clean`, `rm -rf`, leitura de `.env`, escrita na spec de base, no
  `.claude/settings.json` e em `.githooks/`.
- O pre-commit bloqueia alteração na spec de base, padrões comuns de
  segredos, lint e testes falhando.
- Nada disso substitui revisão humana no PR.

## Licença

MIT. As skills em `templates/skills/` são de Addy Osmani, também MIT; veja
`THIRD_PARTY_NOTICES.md`.
