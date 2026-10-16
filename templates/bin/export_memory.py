"""Exporta a memória do cortex-lite para um arquivo versionável.

Gerado pelo plugin minimal-squad. Procura o run.py do cortex-lite nas
pastas de plugins do Claude Code e roda `run.py export`.

Uso: python .claude/minimal-squad/bin/export_memory.py docs/MEMORIA.md
"""
import os
import subprocess
import sys
from pathlib import Path


def find_run_py():
    env = os.environ.get("CORTEXLITE_RUN")
    if env and Path(env).is_file():
        return Path(env)
    config = os.environ.get("CLAUDE_CONFIG_DIR") or str(Path.home() / ".claude")
    roots = [Path(config) / "plugins"]
    found = []
    for root in roots:
        if not root.is_dir():
            continue
        for run in root.rglob("run.py"):
            if (run.parent / "cortexlite").is_dir():
                found.append(run)
    if not found:
        return None
    return max(found, key=lambda p: p.stat().st_mtime)


def main():
    if len(sys.argv) != 2:
        print("uso: export_memory.py <arquivo de saída>", file=sys.stderr)
        return 2
    out = Path(sys.argv[1])
    run = find_run_py()
    if run is None:
        print("cortex-lite não encontrado em ~/.claude/plugins. "
              "Defina CORTEXLITE_RUN com o caminho do run.py.", file=sys.stderr)
        return 1
    result = subprocess.run([sys.executable, str(run), "export"],
                            check=False, capture_output=True, text=True, encoding="utf-8")
    if result.returncode != 0:
        print(result.stderr or "export falhou", file=sys.stderr)
        return result.returncode
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(result.stdout)
    print(f"memória exportada para {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
