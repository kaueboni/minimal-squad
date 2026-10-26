"""Verificação dos templates para quem mantém o plugin (requer PyYAML).

Renderiza agentes e comandos em todas as combinações de flags e confere:
- nenhum marcador {{...}} sobra;
- o cabeçalho YAML é válido, com name/description e os campos esperados;
- com a flag copilot, a conversão para .agent.md / .prompt.md também gera YAML válido.

Uso: python scripts/check_templates.py
"""
from __future__ import annotations

import itertools
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import AGENTS, COMMANDS, COPILOT_EXTRA_PROMPTS, TEMPLATES, render, utf8_stdio  # noqa: E402
from install import Installer  # noqa: E402

FLAGS = ["cortex", "agentmeter", "ponytail", "rtk", "researcher", "lint", "refs", "copilot"]
VARS = {
    "MODEL_READ": "haiku", "MODEL_WORK": "sonnet", "EFFORT": "medium",
    "TEST_SUITE_CMD": 'pytest -q -m "not integration"', "TEST_INTEGRATION_CMD": "pytest -q -m integration",
    "LINT_CMD": "ruff check .", "SPECS_DIR": "specs", "BASE_SPEC": "SPEC.md", "DOCS": "docs.python.org",
    "INTEGRATION_REFS": "docs/ref.md", "PYTHON": "python3", "NEXT_SPEC": "014", "PLUGIN_VERSION": "0",
    "TOOLS": "Read, Grep", "SKILLS": "  - a\n  - b", "INSTRUCTIONS_FILE": "CLAUDE.md",
}
COPILOT = Installer(Path("/nonexistent-minimal-squad"), {}, check=True, target="copilot")


def frontmatter(text: str) -> dict:
    assert text.startswith("---\n"), "sem cabeçalho"
    return yaml.safe_load(text.split("---\n", 2)[1])


def main():
    utf8_stdio()
    failures = []
    files = [f"agents/{a}.md" for a in AGENTS] + [f"commands/{c}.md" for c in COMMANDS] + \
            [f"copilot/prompts/{p}.prompt.md" for p in COPILOT_EXTRA_PROMPTS] + \
            ["project/CLAUDE.block.md", "project/PROGRESS.md", "githooks/pre-commit"]
    for combo in itertools.product([False, True], repeat=len(FLAGS)):
        flags = dict(zip(FLAGS, combo))
        for rel in files:
            try:
                out = render((TEMPLATES / rel).read_text(encoding="utf-8"), VARS, flags)
                if rel.endswith(".md") and rel.split("/")[0] in ("agents", "commands"):
                    fm = frontmatter(out)
                    assert isinstance(fm.get("description"), str) and fm["description"], "description"
                    if rel.startswith("agents/"):
                        for key in ("name", "tools", "model", "skills"):
                            assert key in fm, key
                        assert isinstance(fm["skills"], list), "skills deve ser lista"
                if flags["copilot"] and rel.split("/")[0] in ("agents", "commands", "copilot"):
                    name = Path(rel).name.split(".")[0]
                    if rel.startswith("agents/"):
                        conv = COPILOT.copilot_agent(name, out, ["Read", "Grep", "Bash"], ["a", "b"])
                    else:
                        conv = COPILOT.copilot_prompt(name, out)
                    fm = frontmatter(conv)
                    assert isinstance(fm.get("description"), str) and fm["description"], "copilot description"
                    assert isinstance(fm.get("tools"), list), "copilot tools deve ser lista"
                    assert '(agent)"' not in conv and "$ARGUMENTS" not in conv, "sobrou sintaxe do Claude Code"
                    if rel.startswith("agents/"):
                        assert fm.get("name") == name, "copilot name"
                        for key in ("skills", "maxTurns", "effort"):
                            assert key not in fm, f"campo do Claude Code no .agent.md: {key}"
            except Exception as exc:  # noqa: BLE001
                failures.append(f"{rel} {flags}: {exc}")
    plugin_cmd = (TEMPLATES.parent / "commands" / "init.md").read_text(encoding="utf-8")
    try:
        frontmatter(plugin_cmd)
    except Exception as exc:  # noqa: BLE001
        failures.append(f"commands/init.md: {exc}")
    if failures:
        print("\n".join(sorted(set(failures))[:40]))
        sys.exit(1)
    print(f"ok: {len(files)} templates x {2 ** len(FLAGS)} combinações")


if __name__ == "__main__":
    main()
