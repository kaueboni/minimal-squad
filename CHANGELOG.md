# Changelog

## [0.2.0] - 2026-10-26

### Added
- Alvo **GitHub Copilot** (`--target copilot`): agentes em `.github/agents/*.agent.md`, prompts em
  `.github/prompts/*.prompt.md` (`/spec`, `/build`, `/review`, `/test`, `/onboard` e o novo `/base-spec`),
  skills e referências em `.github/`, bloco em `.github/copilot-instructions.md` e regras de
  `chat.tools.terminal.autoApprove` em `.vscode/settings.json`. Ferramentas convertidas para os aliases do
  Copilot; menções `@"x (agent)"` viram chamadas de subagente.
- `install.py --init-config [--target copilot]`: grava a configuração sugerida pelo detect, para instalar
  sem o Claude Code.
- `detect.py --target copilot`: relata conflitos em `.github/agents`, `.github/prompts` e
  `.github/copilot-instructions.md`.
- Parâmetros `copilot_model_read` e `copilot_model_work` (vazios = modelo escolhido no Copilot).
- `tests/test_copilot.py`; `check_templates.py` também valida a conversão para o Copilot.

### Changed
- A configuração é procurada em `.claude/` e depois em `.github/`; lock e pendentes ficam na mesma pasta.
- O lock registra o alvo (`target`). A etapa `claude-md` aceita o sinônimo `instructions`.

## [0.1.1] - 2026-10-16

### Fixed
- Windows: o `init` gravava `pytest -q` e `ruff check .` mesmo com `.venv` no projeto. No Git Bash essas
  ferramentas não estão no PATH, então o hook de pre-commit barrava **todo** commit. Agora, havendo
  `.venv` (ou `venv`) e nenhum runner (uv, poetry, pdm, pipenv), o comando usa o Python do venv.
- Windows: `detect.py`, `install.py`, `inventory.py` e `check_templates.py` imprimiam em cp1252 quando a
  saída ia para um pipe, corrompendo acentos (inclusive em caminhos). Agora a saída é UTF-8 com LF.
- Windows: o `chmod` não existe, e o `pre-commit` entrava no índice como `100644`; agora o instalador usa
  `git add --chmod=+x`, e o hook também funciona para quem clona no Linux ou macOS.
- A permissão derivada de um Python por caminho (`.venv/Scripts/python -m pytest`) agora é estreita
  (`Bash(.venv/Scripts/python -m pytest:*)`), não `Bash(.venv/Scripts/python:*)`.
- `settings.json` com BOM (UTF-8) deixou de ser rejeitado como JSON inválido.
- `git` é lido como UTF-8; `export_memory.py` respeita `CLAUDE_CONFIG_DIR` e grava LF.

### Added
- `tests/test_windows.py` (biblioteca padrão), `.gitattributes`, `.editorconfig` e `requirements-dev.txt`
  (PyYAML, só para `scripts/check_templates.py`).
- Requisito documentado: no Windows, Git for Windows (Git Bash).
