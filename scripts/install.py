"""Instalador determinístico do minimal-squad.

Lê .claude/minimal-squad.json do projeto, renderiza os templates do plugin e
grava no projeto. Regras:
- arquivo novo → grava;
- arquivo igual ao renderizado → nada;
- arquivo que o próprio minimal-squad gravou e ninguém mudou (hash no lock)
  → atualiza;
- arquivo existente com conteúdo de outra origem ou editado à mão → NÃO
  sobrescreve: grava a versão nova em .claude/.minimal-squad-pending/ e avisa.
Nunca faz commit, push ou qualquer operação de rede.

Uso:
  python install.py --project . --steps all
  python install.py --project . --steps agents,commands --check   (só mostra)
Etapas: skills, agents, commands, settings, layout, githooks, claude-md, progress, bin
"""
from __future__ import annotations

import argparse
import json
import stat
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (  # noqa: E402
    AGENTS,
    BASE_SKILLS,
    BASE_TOOLS,
    COMMANDS,
    CONFIG_REL,
    LOCK_REL,
    MAX_SKILLS,
    PENDING_REL,
    SKILLS,
    TEMPLATES,
    WRITE_ALLOWED,
    WRITE_TOOLS,
    TemplateError,
    dump_json,
    load_json,
    plugin_version,
    render,
    resolve_integrations,
    resolve_params,
    sha256_text,
)

ALL_STEPS = ["skills", "agents", "commands", "settings", "layout", "githooks", "claude-md", "progress", "bin"]
BLOCK_START = "<!-- minimal-squad:start"
BLOCK_END = "<!-- minimal-squad:end -->"


class Installer:
    def __init__(self, root: Path, config: dict, check: bool):
        self.root = root
        self.config = config
        self.check = check
        self.params = resolve_params(config)
        self.integ = resolve_integrations(config)
        self.lock_path = root / LOCK_REL
        lock = load_json(self.lock_path, {}) or {}
        self.lock = lock.get("files", {})
        self.report = {"created": [], "updated": [], "unchanged": [], "pending": [],
                       "skipped": [], "warnings": [], "errors": []}
        self.cortex = load_json(TEMPLATES / "integrations" / "cortex-lite.json", {})

    def validate(self):
        """Valida configuração e overrides antes de gravar qualquer coisa."""
        saved = (list(self.report["errors"]), list(self.report["warnings"]))
        for agent in AGENTS:
            self.agent_tools_skills(agent)
        problems = self.report["errors"][len(saved[0]):]
        self.report["errors"], self.report["warnings"] = saved
        p = self.params
        if not p["test_cmd"].strip():
            problems.append("params.test_cmd vazio")
        if Path(p["specs_dir"]).is_absolute() or ".." in Path(p["specs_dir"]).parts:
            problems.append("params.specs_dir precisa ser um caminho relativo dentro do projeto")
        if Path(p["base_spec"]).is_absolute() or ".." in Path(p["base_spec"]).parts:
            problems.append("params.base_spec precisa ser um caminho relativo dentro do projeto")
        for key in ("model_read", "model_work", "effort", "python"):
            if not str(p.get(key, "")).strip():
                problems.append(f"params.{key} vazio")
        try:
            for agent in AGENTS:
                render((TEMPLATES / "agents" / f"{agent}.md").read_text(encoding="utf-8"),
                       self.variables({"TOOLS": "x", "SKILLS": "x"}), self.flags)
        except TemplateError as exc:
            problems.append(f"template: {exc}")
        return problems

    # ------------------------------------------------------------ helpers
    @property
    def flags(self):
        p, i = self.params, self.integ
        return {
            "cortex": i["cortex_lite"], "agentmeter": i["agentmeter"], "ponytail": i["ponytail"],
            "rtk": i["rtk"], "researcher": bool(p["researcher"]), "lint": bool(p["lint_cmd"].strip()),
            "refs": bool(p.get("integration_refs")),
        }

    def variables(self, extra=None):
        p = self.params
        v = {
            "MODEL_READ": p["model_read"], "MODEL_WORK": p["model_work"], "EFFORT": p["effort"],
            "TEST_SUITE_CMD": p["test_suite_cmd"], "TEST_INTEGRATION_CMD": p["test_integration_cmd"],
            "LINT_CMD": p["lint_cmd"].strip(), "SPECS_DIR": p["specs_dir"], "BASE_SPEC": p["base_spec"],
            "DOCS": ", ".join(p.get("docs") or ["docs.python.org"]),
            "INTEGRATION_REFS": ", ".join(p.get("integration_refs") or []),
            "PYTHON": p["python"], "NEXT_SPEC": self.config.get("next_spec", "NNN"),
            "PLUGIN_VERSION": plugin_version(),
        }
        if extra:
            v.update(extra)
        return v

    def rel(self, path: Path) -> str:
        return str(path.relative_to(self.root)).replace("\\", "/")

    def put(self, rel: str, content: str, mode_exec=False, managed=True):
        """Grava respeitando o lock. Retorna o estado."""
        target = self.root / rel
        new_hash = sha256_text(content)
        if target.is_file():
            current = target.read_text(encoding="utf-8", errors="replace")
            cur_hash = sha256_text(current)
            if cur_hash == new_hash:
                self.report["unchanged"].append(rel)
                if managed:
                    self.lock[rel] = new_hash
                return "unchanged"
            if managed and self.lock.get(rel) == cur_hash:
                self._write(target, content, mode_exec)
                self.lock[rel] = new_hash
                self.report["updated"].append(rel)
                return "updated"
            pending = self.root / PENDING_REL / rel
            self._write(pending, content, mode_exec)
            self.report["pending"].append({"file": rel, "new_version": self.rel(pending)})
            return "pending"
        self._write(target, content, mode_exec)
        if managed:
            self.lock[rel] = new_hash
        self.report["created"].append(rel)
        return "created"

    def remove_if_managed(self, rel: str, reason: str):
        """Remove um arquivo só se foi gravado pelo minimal-squad e não foi editado."""
        target = self.root / rel
        if not target.is_file():
            self.report["skipped"].append(f"{rel} ({reason})")
            return
        if self.lock.get(rel) == sha256_text(target.read_text(encoding="utf-8", errors="replace")):
            if not self.check:
                target.unlink()
            self.lock.pop(rel, None)
            self.report.setdefault("removed", []).append(f"{rel} ({reason})")
        else:
            self.report["warnings"].append(f"{rel}: {reason}, mas o arquivo foi editado; não removi")

    def _write(self, path: Path, content: str, mode_exec=False):
        if self.check:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="\n") as fh:
            fh.write(content)
        if mode_exec:
            path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    def tpl(self, rel: str, extra=None) -> str:
        text = (TEMPLATES / rel).read_text(encoding="utf-8")
        return render(text, self.variables(extra), self.flags)

    # ------------------------------------------------------------ steps
    def step_skills(self):
        for skill in SKILLS:
            src_dir = TEMPLATES / "skills" / skill
            for src in sorted(src_dir.rglob("*")):
                if src.is_file():
                    rel = ".claude/skills/" + str(src.relative_to(TEMPLATES / "skills")).replace("\\", "/")
                    self.put(rel, src.read_text(encoding="utf-8"))
        self.put(".claude/skills/LICENSE-addyosmani-agent-skills",
                 (TEMPLATES / "skills" / "LICENSE-addyosmani-agent-skills").read_text(encoding="utf-8"))
        for ref in sorted((TEMPLATES / "references").glob("*.md")):
            self.put(f".claude/references/{ref.name}", ref.read_text(encoding="utf-8"))

    def agent_tools_skills(self, agent):
        tools = list(BASE_TOOLS[agent])
        skills = list(BASE_SKILLS[agent])
        if self.integ["cortex_lite"]:
            profile = self.cortex["agents"][agent]
            tools += [self.cortex["tool_prefix"] + t for t in self.cortex["profiles"][profile]]
            skills.append(self.cortex["skill"])
        ov = ((self.config.get("overrides") or {}).get("agents") or {}).get(agent) or {}
        for t in ov.get("tools_extra", []):
            if t == "Agent" or t.startswith("Agent("):
                self.report["errors"].append(f"{agent}: a ferramenta Agent não pode ser dada a subagentes")
                continue
            if t in WRITE_TOOLS and agent not in WRITE_ALLOWED:
                self.report["errors"].append(f"{agent}: ferramenta de escrita {t} não permitida neste papel")
                continue
            if t.endswith("memory_delete"):
                self.report["errors"].append(f"{agent}: memory_delete é reservado a humanos")
                continue
            if t not in tools:
                tools.append(t)
        for s in ov.get("skills_extra", []):
            if s not in skills:
                skills.append(s)
        if len(skills) > MAX_SKILLS:
            self.report["warnings"].append(
                f"{agent}: {len(skills)} skills carregadas (recomendado até {MAX_SKILLS}); isso aumenta o contexto")
        return tools, skills

    def step_agents(self):
        for agent in AGENTS:
            rel = f".claude/agents/{agent}.md"
            if agent == "researcher" and not self.params["researcher"]:
                self.remove_if_managed(rel, "researcher desligado")
                continue
            tools, skills = self.agent_tools_skills(agent)
            content = self.tpl(f"agents/{agent}.md", {
                "TOOLS": ", ".join(tools),
                "SKILLS": "\n".join(f"  - {s}" for s in skills),
            })
            self.put(rel, content)

    def step_commands(self):
        for cmd in COMMANDS:
            self.put(f".claude/commands/{cmd}.md", self.tpl(f"commands/{cmd}.md"))

    def permissions(self):
        p, i = self.params, self.integ

        def prefix(cmd):
            words = cmd.replace('"', " ").split()
            if not words:
                return None
            if words[0] in ("uv", "poetry", "pdm", "pipenv") and len(words) >= 3 and words[1] == "run":
                if words[2] in ("python", "python3", "py") and len(words) >= 5 and words[3] == "-m":
                    return " ".join(words[:5])
                return " ".join(words[:3])
            if words[0] in ("python", "python3", "py") and len(words) >= 3 and words[1] == "-m":
                return " ".join(words[:3])
            return words[0]

        allow = []
        for cmd in [p["test_cmd"], p["lint_cmd"]]:
            pre = prefix(cmd) if cmd.strip() else None
            if pre:
                allow.append(f"Bash({pre}:*)")
                if i["rtk"]:
                    allow.append(f"Bash(rtk {pre}:*)")
        for g in ["status", "diff", "log", "show", "add", "commit", "hash-object", "merge-base", "branch"]:
            allow.append(f"Bash(git {g}:*)")
            if i["rtk"]:
                allow.append(f"Bash(rtk git {g}:*)")
        if p.get("autonomy_edits", True):
            allow += ["Edit", "Write"]
        if p["researcher"]:
            allow.append("WebSearch")
        if i["cortex_lite"]:
            allow.append(f"Bash({p['python']} .claude/minimal-squad/bin/export_memory.py:*)")
            used = set()
            for prof in self.cortex["profiles"].values():
                used.update(prof)
            allow += [self.cortex["tool_prefix"] + t for t in sorted(used)]
        base = p["base_spec"]
        deny = [
            "Bash(git push:*)", "Bash(git reset --hard:*)", "Bash(git clean:*)", "Bash(rm -rf:*)",
            "Read(./.env)", "Read(./.env.*)",
            f"Edit(./{base})", f"Write(./{base})",
            "Edit(./.claude/settings.json)", "Write(./.claude/settings.json)",
            "Edit(./.githooks/**)", "Write(./.githooks/**)",
        ]
        if i["rtk"]:
            deny.append("Bash(rtk git push:*)")
        ov = (self.config.get("overrides") or {}).get("permissions") or {}
        allow += ov.get("allow", [])
        deny += ov.get("deny", [])
        return allow, deny

    def step_settings(self):
        rel = ".claude/settings.json"
        path = self.root / rel
        existed = path.is_file()
        data = {}
        if existed:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                self.report["errors"].append(f"{rel} não é JSON válido ({exc}); não alterei")
                return
        perms = data.setdefault("permissions", {})
        allow, deny = self.permissions()
        cur_allow = perms.setdefault("allow", [])
        cur_deny = perms.setdefault("deny", [])
        added = []
        for item in allow:
            if item not in cur_allow and item not in cur_deny:
                cur_allow.append(item)
                added.append(("allow", item))
        for item in deny:
            if item not in cur_deny:
                cur_deny.append(item)
                added.append(("deny", item))
        blocked = [d for d in cur_deny if d == "Agent" or d.startswith("Agent(")]
        if blocked:
            self.report["warnings"].append(
                f"{rel}: {blocked} em deny impede os subagentes de rodar; não removi, decida você")
        conflicts = [a for a in allow if a in cur_deny]
        if conflicts:
            self.report["warnings"].append(f"{rel}: itens que a squad libera estão em deny e foram mantidos em deny: {conflicts}")
        if not added:
            self.report["unchanged"].append(rel)
            return
        content = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
        self._write(path, content)
        self.report["updated" if existed else "created"].append(f"{rel} (+{len(added)} regras)")

    def step_layout(self):
        specs = self.params["specs_dir"]
        for d in [specs, "tasks", "tests/contract", "tests/fixtures"]:
            if d in (".", ""):
                continue
            target = self.root / d
            if target.is_dir() and any(target.iterdir()):
                self.report["unchanged"].append(d + "/")
                continue
            self.put(f"{d}/.gitkeep", "", managed=False)
        tests_init = (self.root / "tests" / "__init__.py").is_file()
        if tests_init:
            for d in ["tests/contract", "tests/fixtures"]:
                if not (self.root / d / "__init__.py").exists():
                    self.put(f"{d}/__init__.py", "", managed=False)
        gi = self.root / ".gitignore"
        lines = gi.read_text(encoding="utf-8").splitlines() if gi.is_file() else []
        wanted = [f"{PENDING_REL}/"] + list(self.config.get("gitignore_extra", []))
        missing = [w for w in wanted if w not in lines]
        if missing:
            text = "\n".join(lines + ["", "# minimal-squad"] + missing) + "\n"
            self._write(gi, text.lstrip("\n"))
            self.report["updated" if lines else "created"].append(f".gitignore (+{len(missing)})")
        else:
            self.report["unchanged"].append(".gitignore")

    def step_githooks(self):
        if not self.params.get("precommit", True):
            self.report["skipped"].append("githooks (precommit desligado)")
            return
        hooks_path = self._git("config", "--get", "core.hooksPath")
        others = [n for n in [".pre-commit-config.yaml", ".husky", "lefthook.yml", ".lefthook.yml"]
                  if (self.root / n).exists()]
        if others or (hooks_path not in (None, "", ".githooks")):
            self.report["skipped"].append(
                f"githooks: o projeto já usa outro mecanismo ({others or hooks_path}); integre as checagens nele")
            return
        self.put(".githooks/pre-commit", self.tpl("githooks/pre-commit"), mode_exec=True)
        self.put(".githooks/secret-patterns.txt", (TEMPLATES / "githooks" / "secret-patterns.txt").read_text(encoding="utf-8"))
        if not self.check and hooks_path != ".githooks":
            if self._git("config", "core.hooksPath", ".githooks") is None:
                self.report["warnings"].append("não consegui rodar git config core.hooksPath .githooks")
            else:
                self.report["updated"].append("git config core.hooksPath = .githooks (local desta máquina)")

    def step_claude_md(self):
        path = self.root / "CLAUDE.md"
        block = self.tpl("project/CLAUDE.block.md").rstrip("\n")
        text = path.read_text(encoding="utf-8") if path.is_file() else ""
        if BLOCK_START in text and BLOCK_END in text:
            head, rest = text.split(BLOCK_START, 1)
            _, tail = rest.split(BLOCK_END, 1)
            new = head + block + tail
        else:
            new = (text.rstrip("\n") + "\n\n" if text.strip() else "") + block + "\n"
        if new == text:
            self.report["unchanged"].append("CLAUDE.md")
            return
        self._write(path, new)
        self.report["updated" if text else "created"].append("CLAUDE.md (bloco minimal-squad)")

    def step_progress(self):
        if (self.root / "PROGRESS.md").is_file():
            self.report["unchanged"].append("PROGRESS.md (já existe; não sobrescrevo)")
            return
        self.put("PROGRESS.md", self.tpl("project/PROGRESS.md"), managed=False)

    def step_bin(self):
        rel = ".claude/minimal-squad/bin/export_memory.py"
        if not self.integ["cortex_lite"]:
            self.report["skipped"].append(f"{rel} (cortex-lite não habilitado)")
            return
        self.put(rel, (TEMPLATES / "bin" / "export_memory.py").read_text(encoding="utf-8"))

    def _git(self, *args):
        try:
            out = subprocess.run(["git", *args], check=False, cwd=self.root, capture_output=True, text=True, timeout=20)
        except (OSError, subprocess.TimeoutExpired):
            return None
        return out.stdout.strip() if out.returncode == 0 else None

    def save_lock(self):
        if self.check:
            return
        dump_json(self.lock_path, {"plugin_version": plugin_version(), "files": dict(sorted(self.lock.items()))})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=".")
    ap.add_argument("--steps", default="all")
    ap.add_argument("--check", action="store_true", help="não grava; só mostra o que faria")
    args = ap.parse_args()
    root = Path(args.project).resolve()
    config = load_json(root / CONFIG_REL, None)
    if config is None:
        print(json.dumps({"errors": [f"{CONFIG_REL} não encontrado; rode /minimal-squad:init"]}, ensure_ascii=False))
        sys.exit(2)
    steps = ALL_STEPS if args.steps == "all" else [s.strip() for s in args.steps.split(",") if s.strip()]
    unknown = [s for s in steps if s not in ALL_STEPS]
    if unknown:
        print(json.dumps({"errors": [f"etapas desconhecidas: {unknown}"]}, ensure_ascii=False))
        sys.exit(2)
    inst = Installer(root, config, args.check)
    problems = inst.validate()
    if problems:
        print(json.dumps({"errors": problems, "note": "nada foi gravado"}, indent=2, ensure_ascii=False))
        sys.exit(2)
    try:
        for step in steps:
            getattr(inst, "step_" + step.replace("-", "_"))()
    except TemplateError as exc:
        inst.report["errors"].append(f"template: {exc}")
    inst.save_lock()
    inst.report["steps"] = steps
    inst.report["check"] = args.check
    print(json.dumps(inst.report, indent=2, ensure_ascii=False))
    sys.exit(1 if inst.report["errors"] else 0)


if __name__ == "__main__":
    main()
