"""Funções compartilhadas pelos scripts do minimal-squad (só biblioteca padrão)."""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = PLUGIN_ROOT / "templates"
CONFIG_REL = ".claude/minimal-squad.json"
LOCK_REL = ".claude/minimal-squad.lock.json"
PENDING_REL = ".claude/.minimal-squad-pending"

# Alvos de instalação. "claude" grava em .claude/ (Claude Code); "copilot" grava
# em .github/ (GitHub Copilot: VS Code, Copilot CLI e cloud agent).
TARGETS = ("claude", "copilot")
META_DIRS = {"claude": ".claude", "copilot": ".github"}
CONFIG_NAME = "minimal-squad.json"
LOCK_NAME = "minimal-squad.lock.json"
PENDING_NAME = ".minimal-squad-pending"
# Integrações que só existem como plugins do Claude Code.
CLAUDE_ONLY_INTEGRATIONS = ("cortex_lite", "agentmeter", "ponytail", "rtk")

# Ferramentas do Claude Code → aliases de custom agents do Copilot
# (https://docs.github.com/en/copilot/reference/custom-agents-configuration).
COPILOT_TOOL_ALIASES = {
    "Read": "read", "NotebookRead": "read",
    "Grep": "search", "Glob": "search",
    "Edit": "edit", "Write": "edit", "MultiEdit": "edit", "NotebookEdit": "edit",
    "Bash": "execute",
    "WebSearch": "web", "WebFetch": "web",
    "TodoWrite": "todo",
}
# Ferramentas dos prompt files (/spec, /build...). "agent" permite chamar subagentes.
COPILOT_PROMPT_TOOLS = {
    "spec": ["agent", "read", "search"],
    "build": ["agent", "read", "search", "edit", "execute", "todo"],
    "review": ["agent", "read", "search", "execute"],
    "test": ["read", "search", "edit", "execute"],
    "onboard": ["agent", "read", "search", "execute"],
    "base-spec": ["read", "search", "edit", "execute"],
}
COPILOT_EXTRA_PROMPTS = ["base-spec"]

AGENTS = ["discovery", "researcher", "tech-lead", "contract-tester", "developer", "auditor"]
COMMANDS = ["spec", "build", "review", "test", "onboard"]
SKILLS = [
    "spec-driven-development", "planning-and-task-breakdown", "incremental-implementation",
    "test-driven-development", "context-engineering", "debugging-and-error-recovery",
    "doubt-driven-development", "code-review-and-quality", "security-and-hardening",
    "source-driven-development",
]

BASE_TOOLS = {
    "discovery": ["Read", "Grep", "Glob"],
    "researcher": ["WebSearch", "WebFetch"],
    "tech-lead": ["Read", "Grep", "Glob", "Write", "Edit"],
    "contract-tester": ["Read", "Grep", "Glob", "Write", "Bash"],
    "developer": ["Read", "Grep", "Glob", "Edit", "Write", "Bash"],
    "auditor": ["Read", "Grep", "Glob", "Bash"],
}
BASE_SKILLS = {
    "discovery": ["context-engineering"],
    "researcher": ["source-driven-development"],
    "tech-lead": ["spec-driven-development", "planning-and-task-breakdown"],
    "contract-tester": ["test-driven-development"],
    "developer": ["incremental-implementation", "test-driven-development", "debugging-and-error-recovery"],
    "auditor": ["code-review-and-quality", "security-and-hardening"],
}
WRITE_TOOLS = {"Edit", "Write", "NotebookEdit", "MultiEdit"}
WRITE_ALLOWED = {"tech-lead", "contract-tester", "developer"}
MAX_SKILLS = 4

DEFAULT_PARAMS = {
    "python": "python",
    "test_cmd": "pytest -q",
    "test_suite_cmd": "",
    "test_integration_cmd": "",
    "lint_cmd": "",
    "model_read": "haiku",
    "model_work": "sonnet",
    "effort": "medium",
    "specs_dir": "specs",
    "base_spec": "SPEC.md",
    "researcher": True,
    "docs": ["docs.python.org"],
    "precommit": True,
    "autonomy_edits": True,
    "integration_refs": [],
    # Só para o alvo copilot. Vazio = o agente usa o modelo selecionado no Copilot.
    "copilot_model_read": "",
    "copilot_model_work": "",
}
DEFAULT_INTEGRATIONS = {"cortex_lite": False, "agentmeter": False, "ponytail": False, "rtk": False}


def utf8_stdio() -> None:
    """No Windows o stdout em pipe usa cp1252 e o texto vira CRLF; o Claude Code lê UTF-8."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", newline="\n")
        except (AttributeError, ValueError):
            pass


def venv_python(root: Path):
    """Python do venv do projeto, em caminho relativo com barras (funciona no Git Bash), ou None."""
    for rel in (".venv/Scripts/python.exe", ".venv/bin/python", "venv/Scripts/python.exe", "venv/bin/python"):
        if (root / rel).is_file():
            return rel[:-4] if rel.endswith(".exe") else rel
    return None


def is_python_word(word: str) -> bool:
    """python, python3, py ou um caminho para eles (por exemplo .venv/Scripts/python)."""
    name = word.replace("\\", "/").rsplit("/", 1)[-1].lower()
    return name in ("python", "python3", "py", "python.exe")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path, default=None):
    if not path.is_file():
        return default
    with path.open(encoding="utf-8-sig") as fh:
        return json.load(fh)


def dump_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def plugin_version() -> str:
    data = load_json(PLUGIN_ROOT / ".claude-plugin" / "plugin.json", {}) or {}
    return data.get("version", "0.0.0")


def resolve_params(config: dict) -> dict:
    params = dict(DEFAULT_PARAMS)
    params.update(config.get("params", {}))
    test = params["test_cmd"].strip()
    if not params.get("test_suite_cmd"):
        params["test_suite_cmd"] = f'{test} -m "not integration"'
    if not params.get("test_integration_cmd"):
        params["test_integration_cmd"] = f"{test} -m integration"
    params["specs_dir"] = params["specs_dir"].strip().strip("/") or "specs"
    return params


def resolve_integrations(config: dict, target: str = "claude") -> dict:
    integ = dict(DEFAULT_INTEGRATIONS)
    integ.update(config.get("integrations", {}))
    integ = {k: bool(v) for k, v in integ.items()}
    if target == "copilot":
        integ.update({k: False for k in CLAUDE_ONLY_INTEGRATIONS})
    return integ


def find_config(root: Path):
    """Procura a configuração em .claude/ e depois em .github/.

    Retorna (pasta_meta_relativa, config) ou (None, None). A pasta onde a
    configuração está é também a pasta do lock e dos arquivos pendentes.
    """
    for meta in (META_DIRS["claude"], META_DIRS["copilot"]):
        data = load_json(root / meta / CONFIG_NAME, None)
        if data is not None:
            return meta, data
    return None, None


def copilot_tools(tools: list) -> list:
    """Converte nomes de ferramentas do Claude Code para os aliases do Copilot, sem repetir.

    MCP no formato do Claude (mcp__servidor__ferramenta) vira servidor/ferramenta.
    """
    out = []
    for t in tools:
        if t in COPILOT_TOOL_ALIASES:
            name = COPILOT_TOOL_ALIASES[t]
        elif t.startswith("mcp__") and t.count("__") >= 2:
            _, server, tool = t.split("__", 2)
            name = f"{server}/{tool}"
        else:
            name = t
        if name not in out:
            out.append(name)
    return out


# ---------------------------------------------------------------- templating
_STANDALONE = re.compile(r"^[ \t]*(\{\{[#^/][\w-]+\}\})[ \t]*\r?\n", re.MULTILINE)
_BLOCK = re.compile(r"\{\{([#^])([\w-]+)\}\}(.*?)\{\{/\2\}\}", re.DOTALL)
_VAR = re.compile(r"\{\{([A-Z][A-Z0-9_]*)\}\}")


class TemplateError(Exception):
    pass


def render(text: str, variables: dict, flags: dict) -> str:
    text = _STANDALONE.sub(r"\1", text)
    for _ in range(20):
        new = _BLOCK.sub(lambda m: _block(m, flags), text)
        if new == text:
            break
        text = new
    text = _VAR.sub(lambda m: _var(m, variables), text)
    leftover = re.findall(r"\{\{[^}]*\}\}", text)
    if leftover:
        raise TemplateError(f"marcadores não resolvidos: {sorted(set(leftover))}")
    return text


def _block(match, flags):
    kind, name, body = match.groups()
    if name not in flags:
        raise TemplateError(f"flag desconhecida no template: {name}")
    keep = bool(flags[name]) if kind == "#" else not bool(flags[name])
    return body if keep else ""


def _var(match, variables):
    key = match.group(1)
    if key not in variables:
        raise TemplateError(f"variável desconhecida no template: {key}")
    return str(variables[key])


def encode_project_dir(root: Path) -> str:
    """Nome da pasta que o Claude Code usa em ~/.claude/projects para um projeto."""
    return re.sub(r"[^A-Za-z0-9]", "-", str(root))


def find_transcript_dir(root: Path):
    base = Path.home() / ".claude" / "projects"
    if not base.is_dir():
        return None
    target = encode_project_dir(root).lower()
    candidates = [d for d in base.iterdir() if d.is_dir()]
    for d in candidates:
        if d.name.lower() == target:
            return d
    tail = re.sub(r"[^A-Za-z0-9]", "-", root.name).lower()
    matches = [d for d in candidates if d.name.lower().endswith("-" + tail)]
    return matches[0] if len(matches) == 1 else None


def read_settings(path: Path):
    try:
        return load_json(path, None), None
    except (json.JSONDecodeError, OSError) as exc:
        return None, str(exc)


def env_home_settings():
    return Path(os.environ.get("CLAUDE_CONFIG_DIR", Path.home() / ".claude")) / "settings.json"
