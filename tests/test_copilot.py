"""Alvo GitHub Copilot. Só biblioteca padrão: python -m unittest discover -s tests"""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTALL = ROOT / "scripts" / "install.py"
sys.path.insert(0, str(ROOT / "scripts"))

from common import AGENTS, COMMANDS, copilot_tools  # noqa: E402


def git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def run_install(proj, *args):
    out = subprocess.run([sys.executable, str(INSTALL), "--project", str(proj), *args],
                         capture_output=True, text=True, encoding="utf-8")
    return out.returncode, json.loads(out.stdout)


def header(text):
    """Cabeçalho YAML simples (chave: valor por linha), sem PyYAML."""
    assert text.startswith("---\n"), text[:40]
    head = text.split("---\n", 2)[1]
    return dict(line.split(":", 1) for line in head.splitlines() if ":" in line)


class Copilot(unittest.TestCase):
    def setUp(self):
        base = tempfile.mkdtemp(prefix="squad copilot ")
        self.addCleanup(shutil.rmtree, base, ignore_errors=True)
        self.proj = Path(base) / "projeto"
        (self.proj / "tests").mkdir(parents=True)
        (self.proj / "pyproject.toml").write_text('[project]\nname="x"\ndependencies=["pytest"]\n', encoding="utf-8")
        git(self.proj, "init", "-q")

    def install_copilot(self):
        code, out = run_install(self.proj, "--init-config", "--target", "copilot")
        self.assertEqual(code, 0, out)
        self.assertEqual(out["created"], ".github/minimal-squad.json")
        cfg = json.loads((self.proj / ".github" / "minimal-squad.json").read_text(encoding="utf-8"))
        self.assertEqual(cfg["target"], "copilot")
        self.assertFalse(any(cfg["integrations"].values()))
        code, out = run_install(self.proj, "--steps", "all")
        self.assertEqual(code, 0, out)
        self.assertEqual(out["target"], "copilot")
        return out

    def test_gera_arquivos_do_copilot_e_nada_do_claude(self):
        self.install_copilot()
        gh = self.proj / ".github"
        for agent in AGENTS:
            self.assertTrue((gh / "agents" / f"{agent}.agent.md").is_file(), agent)
        for cmd in COMMANDS + ["base-spec"]:
            self.assertTrue((gh / "prompts" / f"{cmd}.prompt.md").is_file(), cmd)
        self.assertTrue((gh / "skills" / "spec-driven-development" / "SKILL.md").is_file())
        self.assertTrue((gh / "references" / "security-checklist.md").is_file())
        self.assertTrue((gh / "minimal-squad.lock.json").is_file())
        self.assertIn("minimal-squad:start", (gh / "copilot-instructions.md").read_text(encoding="utf-8"))
        self.assertFalse((self.proj / ".claude").exists())
        self.assertFalse((self.proj / "CLAUDE.md").exists())
        self.assertIn(".github/.minimal-squad-pending/", (self.proj / ".gitignore").read_text(encoding="utf-8"))

    def test_agentes_e_prompts_sem_sintaxe_do_claude(self):
        self.install_copilot()
        gh = self.proj / ".github"
        for agent in AGENTS:
            text = (gh / "agents" / f"{agent}.agent.md").read_text(encoding="utf-8")
            fm = header(text)
            self.assertEqual(fm["name"].strip(), agent)
            for key in ("skills", "maxTurns", "effort", "model"):
                self.assertNotIn(key, fm, f"{agent}: {key}")
            self.assertNotIn("CLAUDE.md", text)
            self.assertIn(".github/skills/", text)
        for p in (gh / "prompts").glob("*.prompt.md"):
            text = p.read_text(encoding="utf-8")
            fm = header(text)
            self.assertEqual(fm["agent"].strip(), "'agent'")
            self.assertNotIn('(agent)"', text, p.name)
            self.assertNotIn("$ARGUMENTS", text, p.name)
        self.assertIn("'agent'", header((gh / "prompts" / "build.prompt.md").read_text(encoding="utf-8"))["tools"])
        dev = header((gh / "agents" / "developer.agent.md").read_text(encoding="utf-8"))
        self.assertEqual(dev["tools"].strip(), "['read', 'search', 'edit', 'execute']")
        aud = header((gh / "agents" / "auditor.agent.md").read_text(encoding="utf-8"))
        self.assertNotIn("edit", aud["tools"])

    def test_auto_aprovacao_do_terminal(self):
        self.install_copilot()
        rules = json.loads((self.proj / ".vscode" / "settings.json").read_text(encoding="utf-8"))
        rules = rules["chat.tools.terminal.autoApprove"]
        self.assertIs(rules["pytest"], True)
        self.assertIs(rules["git push"], False)
        self.assertIs(rules["rm -rf"], False)

    def test_settings_com_comentario_nao_e_tocado(self):
        (self.proj / ".vscode").mkdir()
        original = '{\n  // meu comentário\n  "editor.tabSize": 4\n}\n'
        (self.proj / ".vscode" / "settings.json").write_text(original, encoding="utf-8")
        out = self.install_copilot()
        self.assertEqual((self.proj / ".vscode" / "settings.json").read_text(encoding="utf-8"), original)
        self.assertTrue(any("autoApprove" in w for w in out["warnings"]))

    def test_arquivo_editado_vai_para_pending_em_github(self):
        self.install_copilot()
        dev = self.proj / ".github" / "agents" / "developer.agent.md"
        dev.write_text(dev.read_text(encoding="utf-8") + "\nregra local\n", encoding="utf-8")
        cfg_path = self.proj / ".github" / "minimal-squad.json"
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        cfg["params"]["copilot_model_work"] = "Claude Sonnet 4.5"
        cfg_path.write_text(json.dumps(cfg), encoding="utf-8")
        code, out = run_install(self.proj, "--steps", "agents")
        self.assertEqual(code, 0, out)
        pend = [p["file"] for p in out["pending"]]
        self.assertEqual(pend, [".github/agents/developer.agent.md"])
        self.assertIn("regra local", dev.read_text(encoding="utf-8"))
        new = self.proj / ".github" / ".minimal-squad-pending" / ".github" / "agents" / "developer.agent.md"
        self.assertIn("model: 'Claude Sonnet 4.5'", new.read_text(encoding="utf-8"))
        self.assertIn(".github/agents/auditor.agent.md", out["updated"])

    def test_integracoes_do_claude_sao_ignoradas(self):
        self.install_copilot()
        cfg_path = self.proj / ".github" / "minimal-squad.json"
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        cfg["integrations"]["cortex_lite"] = True
        cfg_path.write_text(json.dumps(cfg), encoding="utf-8")
        code, out = run_install(self.proj, "--steps", "agents")
        self.assertEqual(code, 0, out)
        self.assertTrue(any("cortex_lite" in w for w in out["warnings"]))
        text = (self.proj / ".github" / "agents" / "tech-lead.agent.md").read_text(encoding="utf-8")
        self.assertNotIn("memory_", text)
        self.assertNotIn("recall", text)

    def test_alvo_claude_continua_igual(self):
        code, out = run_install(self.proj, "--init-config")
        self.assertEqual(code, 0, out)
        self.assertEqual(out["created"], ".claude/minimal-squad.json")
        code, out = run_install(self.proj, "--steps", "agents,commands,claude-md")
        self.assertEqual(code, 0, out)
        self.assertTrue((self.proj / ".claude" / "agents" / "developer.md").is_file())
        self.assertTrue((self.proj / ".claude" / "commands" / "build.md").is_file())
        self.assertIn('@"developer (agent)"',
                      (self.proj / ".claude" / "commands" / "build.md").read_text(encoding="utf-8"))
        self.assertTrue((self.proj / "CLAUDE.md").is_file())
        self.assertFalse((self.proj / ".github").exists())

    def test_check_nao_grava_e_avisa(self):
        code, out = run_install(self.proj, "--init-config", "--target", "copilot")
        self.assertEqual(code, 0, out)
        code, out = run_install(self.proj, "--steps", "all", "--check")
        self.assertEqual(code, 0, out)
        self.assertEqual(next(iter(out)), "SIMULACAO")
        self.assertNotIn("created", out)
        self.assertIn(".github/agents/developer.agent.md", out["would_create"])
        self.assertFalse((self.proj / ".github" / "agents").exists())

    def test_init_config_nao_sobrescreve(self):
        self.install_copilot()
        code, out = run_install(self.proj, "--init-config", "--target", "copilot")
        self.assertEqual(code, 2)
        self.assertIn("já existe", out["errors"][0])


class Ferramentas(unittest.TestCase):
    def test_aliases(self):
        self.assertEqual(copilot_tools(["Read", "Grep", "Glob", "Edit", "Write", "Bash"]),
                         ["read", "search", "edit", "execute"])
        self.assertEqual(copilot_tools(["WebSearch", "WebFetch"]), ["web"])
        self.assertEqual(copilot_tools(["mcp__github__get_issue"]), ["github/get_issue"])


if __name__ == "__main__":
    unittest.main()
