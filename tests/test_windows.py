"""Regressões do Windows. Só biblioteca padrão: python -m unittest discover -s tests"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import install  # noqa: E402
from common import is_python_word, venv_python  # noqa: E402


def utf8_free_env():
    """Ambiente sem nenhuma pista de UTF-8: é o que o Claude Code encontra no Windows."""
    env = dict(os.environ, PYTHONUTF8="0")
    env.pop("PYTHONIOENCODING", None)
    return env


def git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


class ProjetoTemporario(unittest.TestCase):
    def setUp(self):
        base = tempfile.mkdtemp(prefix="pasta com espaço e ação ")
        self.addCleanup(shutil.rmtree, base, ignore_errors=True)
        self.proj = Path(base) / "projeto"
        self.proj.mkdir()
        (self.proj / "pyproject.toml").write_text(
            '[project]\nname="x"\ndependencies=["pytest","ruff"]\n[tool.ruff]\nline-length=100\n', encoding="utf-8")
        git(self.proj, "init", "-q")
        # venv falso: o detector só olha a existência do executável
        (self.proj / ".venv" / "Scripts").mkdir(parents=True)
        (self.proj / ".venv" / "Scripts" / "python.exe").write_bytes(b"")

    def detect(self):
        r = subprocess.run([sys.executable, str(SCRIPTS / "detect.py"), "--project", str(self.proj)],
                           env=utf8_free_env(), capture_output=True, check=True)
        return json.loads(r.stdout.decode("utf-8"))  # falha se a saída não for UTF-8

    def test_detect_saida_utf8_com_caminho_acentuado(self):
        self.assertIn("ação", self.detect()["project"])

    def test_detect_usa_python_do_venv(self):
        params = self.detect()["suggested_config"]["params"]
        self.assertEqual(params["test_cmd"], ".venv/Scripts/python -m pytest -q")
        self.assertEqual(params["lint_cmd"], ".venv/Scripts/python -m ruff check .")

    def test_detect_sem_venv_mantem_comando_simples(self):
        shutil.rmtree(self.proj / ".venv")
        params = self.detect()["suggested_config"]["params"]
        self.assertEqual(params["test_cmd"], "pytest -q")

    def test_install_saida_utf8(self):
        cfg = self.proj / ".claude"
        cfg.mkdir()
        config = {"version": 1, "params": {"test_cmd": "pytest -q", "docs": ["docs.python.org"]}}
        (cfg / "minimal-squad.json").write_text(json.dumps(config), encoding="utf-8")
        r = subprocess.run([sys.executable, str(SCRIPTS / "install.py"), "--project", str(self.proj),
                            "--steps", "agents", "--check"], env=utf8_free_env(), capture_output=True)
        json.loads(r.stdout.decode("utf-8"))

    def test_settings_com_bom_e_aceito(self):
        cfg = self.proj / ".claude"
        cfg.mkdir()
        (cfg / "settings.json").write_bytes(b"\xef\xbb\xbf" + '{"nota": "ação"}'.encode("utf-8"))
        inst = install.Installer(self.proj, {"params": {"test_cmd": "pytest -q"}}, False)
        inst.step_settings()
        self.assertEqual(inst.report["errors"], [])


class Permissoes(unittest.TestCase):
    def allow(self, test_cmd):
        inst = install.Installer(Path(tempfile.gettempdir()), {"params": {"test_cmd": test_cmd}}, True)
        return inst.permissions()[0]

    def test_python_do_venv_vira_permissao_estreita(self):
        allow = self.allow(".venv/Scripts/python -m pytest -q")
        self.assertIn("Bash(.venv/Scripts/python -m pytest:*)", allow)
        self.assertNotIn("Bash(.venv/Scripts/python:*)", allow)

    def test_palavras_python(self):
        for w in ("python", "python3", "py", ".venv/Scripts/python", ".venv\\Scripts\\python.exe", ".venv/bin/python"):
            self.assertTrue(is_python_word(w), w)
        self.assertFalse(is_python_word("pytest"))

    def test_venv_python(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(venv_python(Path(d)))
            (Path(d) / ".venv" / "bin").mkdir(parents=True)
            (Path(d) / ".venv" / "bin" / "python").write_bytes(b"")
            self.assertEqual(venv_python(Path(d)), ".venv/bin/python")


@unittest.skipUnless(sys.platform == "win32", "o chmod só falha no Windows")
class BitDeExecucao(unittest.TestCase):
    def test_hook_entra_no_indice_como_executavel(self):
        with tempfile.TemporaryDirectory(prefix="hook ação ") as d:
            proj = Path(d)
            git(proj, "init", "-q")
            cfg = proj / ".claude"
            cfg.mkdir()
            (cfg / "minimal-squad.json").write_text(
                json.dumps({"version": 1, "params": {"test_cmd": "pytest -q"}}), encoding="utf-8")
            r = subprocess.run([sys.executable, str(SCRIPTS / "install.py"), "--project", str(proj),
                                "--steps", "githooks"], capture_output=True, env=utf8_free_env())
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            out = subprocess.run(["git", "ls-files", "-s", ".githooks/pre-commit"], cwd=proj,
                                 capture_output=True, text=True).stdout
            self.assertTrue(out.startswith("100755"), out)


class ExportMemory(unittest.TestCase):
    def test_usa_config_dir_e_grava_lf(self):
        with tempfile.TemporaryDirectory(prefix="cfg ação ") as d:
            plug = Path(d) / "plugins" / "x"
            (plug / "cortexlite").mkdir(parents=True)
            (plug / "run.py").write_text(
                'import sys\nsys.stdout.buffer.write("# Memória\\r\\nação\\r\\n".encode("utf-8"))\n', encoding="utf-8")
            out = Path(d) / "saida" / "MEMORIA.md"
            env = dict(os.environ, CLAUDE_CONFIG_DIR=d)
            env.pop("CORTEXLITE_RUN", None)
            r = subprocess.run([sys.executable, str(ROOT / "templates" / "bin" / "export_memory.py"), str(out)],
                               env=env, capture_output=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            data = out.read_bytes()
            self.assertNotIn(b"\r\n", data)
            self.assertIn("ação".encode("utf-8"), data)


if __name__ == "__main__":
    unittest.main()
