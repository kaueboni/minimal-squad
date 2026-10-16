"""Detecta parâmetros e integrações para o minimal-squad. Só lê; não altera nada.

Uso: python detect.py [--project .]
Imprime um JSON com o que encontrou, as evidências e uma sugestão de configuração.
"""
from __future__ import annotations

import argparse
import configparser
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (  # noqa: E402
    AGENTS,
    COMMANDS,
    CONFIG_REL,
    DEFAULT_PARAMS,
    LOCK_REL,
    env_home_settings,
    find_transcript_dir,
    load_json,
    plugin_version,
    read_settings,
)

SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", ".tox", ".mypy_cache", "dist", "build"}
SPEC_RE = re.compile(r"^(\d{3})-SPEC-.+\.md$", re.IGNORECASE)
DOCS_BY_DEP = {
    "streamlit": "docs.streamlit.io", "fastapi": "fastapi.tiangolo.com",
    "django": "docs.djangoproject.com", "flask": "flask.palletsprojects.com",
    "pandas": "pandas.pydata.org", "polars": "docs.pola.rs", "sqlalchemy": "docs.sqlalchemy.org",
    "pydantic": "docs.pydantic.dev", "pytest": "docs.pytest.org", "requests": "requests.readthedocs.io",
    "httpx": "www.python-httpx.org", "databricks": "docs.databricks.com", "pyspark": "spark.apache.org/docs",
    "boto3": "boto3.amazonaws.com", "celery": "docs.celeryq.dev",
}


def git(root, *args):
    try:
        out = subprocess.run(["git", *args], check=False, cwd=root, capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def walk(root: Path, max_depth=4):
    for dirpath, dirnames, filenames in os.walk(root):
        rel_depth = len(Path(dirpath).relative_to(root).parts)
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and rel_depth < max_depth]
        for name in filenames:
            yield Path(dirpath) / name


def detect_python():
    if os.name == "nt":
        order = ["py", "python", "python3"]
    else:
        order = ["python3", "python"]
    for cmd in order:
        if shutil.which(cmd):
            return cmd
    return "python"


def deps_text(root: Path) -> str:
    parts = [read(root / "pyproject.toml"), read(root / "setup.cfg"), read(root / "setup.py")]
    parts += [read(p) for p in root.glob("requirements*.txt")]
    parts += [read(p) for p in (root / "requirements").glob("*.txt")] if (root / "requirements").is_dir() else []
    return "\n".join(parts).lower()


def detect_runner(root: Path):
    if (root / "uv.lock").is_file():
        return "uv run ", "uv.lock"
    if (root / "poetry.lock").is_file():
        return "poetry run ", "poetry.lock"
    if (root / "pdm.lock").is_file():
        return "pdm run ", "pdm.lock"
    if (root / "Pipfile.lock").is_file():
        return "pipenv run ", "Pipfile.lock"
    return "", None


def detect_tests(root: Path, deps: str):
    runner, runner_ev = detect_runner(root)
    evidence = []
    if runner_ev:
        evidence.append(runner_ev)
    has_pytest = "pytest" in deps or (root / "pytest.ini").is_file() or (root / "conftest.py").is_file()
    if has_pytest:
        evidence.append("pytest nas dependências/config")
    mentions = []
    for doc in ["SPEC.md", "CLAUDE.md", "README.md", "Makefile", "PROGRESS.md"]:
        for line in read(root / doc).splitlines():
            if "pytest" in line and len(line) < 200:
                mentions.append(f"{doc}: {line.strip()}")
    test_cmd = f"{runner}pytest -q"
    lint_cmd = ""
    if "ruff" in deps or (root / "ruff.toml").is_file() or (root / ".ruff.toml").is_file():
        lint_cmd = f"{runner}ruff check ."
        evidence.append("ruff configurado")
    elif "flake8" in deps or (root / ".flake8").is_file():
        lint_cmd = f"{runner}flake8"
        evidence.append("flake8 configurado")
    return {"test_cmd": test_cmd, "lint_cmd": lint_cmd, "has_pytest": has_pytest,
            "evidence": evidence, "mentions": mentions[:10]}


def detect_pytest_config(root: Path):
    pyproject = read(root / "pyproject.toml")
    if "[tool.pytest.ini_options]" in pyproject:
        section = pyproject.split("[tool.pytest.ini_options]", 1)[1].split("\n[", 1)[0]
        return {"file": "pyproject.toml", "section": "[tool.pytest.ini_options]",
                "has_integration_marker": bool(re.search(r"[\"']integration\b", section))}
    for name, section in [("pytest.ini", "pytest"), ("tox.ini", "pytest"), ("setup.cfg", "tool:pytest")]:
        path = root / name
        if path.is_file():
            cp = configparser.ConfigParser()
            try:
                cp.read(path, encoding="utf-8")
            except configparser.Error:
                continue
            if cp.has_section(section):
                markers = cp.get(section, "markers", fallback="")
                return {"file": name, "section": f"[{section}]",
                        "has_integration_marker": bool(re.search(r"^\s*integration\b", markers, re.MULTILINE))}
    return {"file": None, "section": None, "has_integration_marker": False}


def detect_specs(root: Path):
    found = []
    for path in walk(root, max_depth=3):
        m = SPEC_RE.match(path.name)
        if m:
            found.append({"path": str(path.relative_to(root)).replace("\\", "/"), "number": int(m.group(1))})
    found.sort(key=lambda x: x["number"])
    dirs = sorted({str(Path(f["path"]).parent).replace("\\", "/") for f in found})
    next_number = (max(f["number"] for f in found) + 1) if found else 1
    base = None
    for candidate in ["SPEC.md", "specs/SPEC.md", "docs/SPEC.md"]:
        if (root / candidate).is_file():
            base = candidate
            break
    return {"base_spec": base, "feature_specs": found[-15:], "feature_spec_count": len(found),
            "feature_spec_dirs": dirs, "next_number": f"{next_number:03d}"}


def detect_tasks(root: Path):
    out = {}
    for name in ["tasks/plan.md", "tasks/todo.md"]:
        text = read(root / name)
        out[name] = {"exists": (root / name).is_file(),
                     "unchecked": len(re.findall(r"^\s*-\s*\[ \]", text, re.MULTILINE))}
    return out


def detect_claude_dir(root: Path):
    claude = root / ".claude"
    agents = sorted(p.stem for p in (claude / "agents").rglob("*.md")) if (claude / "agents").is_dir() else []
    commands = sorted(p.stem for p in (claude / "commands").rglob("*.md")) if (claude / "commands").is_dir() else []
    skills = sorted(p.parent.name for p in (claude / "skills").glob("*/SKILL.md")) if (claude / "skills").is_dir() else []
    settings, err = read_settings(claude / "settings.json")
    deny = ((settings or {}).get("permissions") or {}).get("deny", []) if settings else []
    return {
        "agents": agents, "commands": commands, "skills": skills,
        "conflicting_agents": [a for a in agents if a in AGENTS],
        "conflicting_commands": [c for c in commands if c in COMMANDS],
        "settings_exists": (claude / "settings.json").is_file(), "settings_error": err,
        "agent_tool_denied": [d for d in deny if d == "Agent" or d.startswith("Agent(")],
    }


def detect_hooks(root: Path):
    hooks_path = git(root, "config", "--get", "core.hooksPath")
    git_dir = git(root, "rev-parse", "--git-dir")
    custom = False
    if git_dir:
        pc = (root / git_dir / "hooks" / "pre-commit")
        custom = pc.is_file()
    others = [n for n in [".pre-commit-config.yaml", ".husky", "lefthook.yml", ".lefthook.yml"] if (root / n).exists()]
    ours = (root / ".githooks" / "pre-commit").is_file() and "minimal-squad" in read(root / ".githooks" / "pre-commit")
    conflict = bool(others) or custom or (hooks_path not in (None, "", ".githooks"))
    return {"core_hooksPath": hooks_path, "custom_git_hook": custom, "other_frameworks": others,
            "minimal_squad_hook_present": ours, "conflict": conflict and not ours}


def enabled_plugins():
    sources = [env_home_settings(), Path(".claude/settings.json"), Path(".claude/settings.local.json")]
    keys = {}
    for src in sources:
        data, _ = read_settings(src)
        for key, val in ((data or {}).get("enabledPlugins") or {}).items():
            keys[key] = {"enabled": bool(val), "source": str(src)}
    return keys


def plugin_on_disk(name: str):
    base = Path(os.environ.get("CLAUDE_CONFIG_DIR", Path.home() / ".claude")) / "plugins"
    if not base.is_dir():
        return []
    hits = []
    for sub in ["cache", "marketplaces"]:
        d = base / sub
        if d.is_dir():
            hits += [str(p) for p in d.glob(f"*{name}*")]
            hits += [str(p) for p in d.glob(f"*/{name}*")]
    return sorted(set(hits))[:5]


def detect_integrations():
    enabled = enabled_plugins()
    result = {}
    for key, name in [("cortex_lite", "cortex-lite"), ("agentmeter", "agentmeter"), ("ponytail", "ponytail")]:
        entries = {k: v for k, v in enabled.items() if k.split("@")[0] == name}
        on_disk = plugin_on_disk(name)
        is_enabled = any(v["enabled"] for v in entries.values())
        result[key] = {"likely": is_enabled or (bool(on_disk) and not entries),
                       "enabledPlugins": entries, "on_disk": on_disk}
    rtk = shutil.which("rtk")
    result["rtk"] = {"likely": bool(rtk), "path": rtk}
    return result


def detect_history(root: Path):
    tdir = find_transcript_dir(root)
    if not tdir:
        return {"transcript_dir": None, "sessions": 0, "auto_memory": False}
    mem = tdir / "memory" / "MEMORY.md"
    return {"transcript_dir": str(tdir), "sessions": len(list(tdir.glob("*.jsonl"))),
            "auto_memory": mem.is_file(), "auto_memory_lines": len(read(mem).splitlines()) if mem.is_file() else 0}


def suggest_docs(deps: str):
    docs = ["docs.python.org"]
    for dep, url in DOCS_BY_DEP.items():
        if re.search(rf"(^|[^a-z0-9_-]){re.escape(dep)}", deps) and url not in docs:
            docs.append(url)
    return docs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=".")
    args = ap.parse_args()
    root = Path(args.project).resolve()
    os.chdir(root)

    inside = git(root, "rev-parse", "--is-inside-work-tree") == "true"
    status = git(root, "status", "--porcelain") if inside else None
    deps = deps_text(root)
    tests = detect_tests(root, deps)
    specs = detect_specs(root)
    integrations = detect_integrations()
    previous = load_json(root / CONFIG_REL, None)

    specs_dir = "specs"
    if specs["feature_spec_dirs"]:
        specs_dir = specs["feature_spec_dirs"][-1] if specs["feature_spec_dirs"][-1] != "." else "."

    suggested = {
        "version": 1,
        "params": {
            **DEFAULT_PARAMS,
            "python": detect_python(),
            "test_cmd": tests["test_cmd"],
            "lint_cmd": tests["lint_cmd"],
            "specs_dir": specs_dir,
            "base_spec": specs["base_spec"] or "SPEC.md",
            "docs": suggest_docs(deps),
            "precommit": not detect_hooks(root)["conflict"],
        },
        "integrations": {k: v["likely"] for k, v in integrations.items()},
        "overrides": {"agents": {}, "permissions": {"allow": [], "deny": []}},
    }
    if previous:
        suggested = {**suggested, **{k: previous[k] for k in ("params", "overrides") if k in previous}}
        suggested["integrations"] = {k: v["likely"] for k, v in integrations.items()}

    report = {
        "plugin_version": plugin_version(),
        "project": str(root),
        "git": {"is_repo": inside, "clean": (status == "") if inside else None,
                "dirty_files": (status or "").splitlines()[:20] if inside else [],
                "branch": git(root, "branch", "--show-current") if inside else None},
        "tests": tests,
        "pytest_config": detect_pytest_config(root),
        "specs": specs,
        "tasks": detect_tasks(root),
        "claude_dir": detect_claude_dir(root),
        "hooks": detect_hooks(root),
        "integrations": integrations,
        "history": detect_history(root),
        "claude_md": {"exists": (root / "CLAUDE.md").is_file(),
                      "managed_block": "minimal-squad:start" in read(root / "CLAUDE.md")},
        "progress_md": (root / "PROGRESS.md").is_file(),
        "previous_install": {"config": previous is not None, "lock": (root / LOCK_REL).is_file()},
        "suggested_config": suggested,
    }
    json.dump(report, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
