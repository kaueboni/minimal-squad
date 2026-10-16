"""Inventário do uso real do Claude Code neste projeto, lido das transcrições locais.

Só lê e conta: ferramentas, MCP, comandos de terminal, skills, subagentes e
comandos "/". Não imprime conteúdo de mensagens.

Uso: python inventory.py [--project .] [--dir <pasta de transcrições>] [--json]
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import find_transcript_dir, utf8_stdio  # noqa: E402

RUNNERS = {"git", "uv", "poetry", "pdm", "pipenv", "python", "python3", "py", "npx", "pip", "docker", "make"}
SKIP = {"cd", "echo", "export", "set", "true", "false"}


def bash_key(command: str):
    keys = []
    for part in re.split(r"&&|\|\||;|\|", command or ""):
        words = part.strip().split()
        while words and "=" in words[0] and not words[0].startswith("-"):
            words = words[1:]
        if not words or words[0] in SKIP:
            continue
        if words[0] == "rtk" and len(words) > 1:
            words = words[1:]
        head = Path(words[0]).name
        if head in RUNNERS and len(words) > 1:
            sub = words[1]
            if head in ("uv", "poetry", "pdm", "pipenv") and sub == "run" and len(words) > 2:
                keys.append(f"{head} run {Path(words[2]).name}")
            elif head in ("python", "python3", "py") and sub == "-m" and len(words) > 2:
                keys.append(f"{head} -m {words[2]}")
            else:
                keys.append(f"{head} {sub}")
        else:
            keys.append(head)
    return keys


def scan(tdir: Path):
    c = {k: collections.Counter() for k in ("tools", "mcp", "bash", "skills", "subagents", "commands")}
    files = sorted(tdir.glob("*.jsonl")) + sorted(tdir.glob("*/subagents/*.jsonl"))
    first = last = None
    for f in files:
        mtime = datetime.fromtimestamp(f.stat().st_mtime)
        first = mtime if first is None or mtime < first else first
        last = mtime if last is None or mtime > last else last
        with f.open(encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                for cmd in re.findall(r"<command-name>(/[\w:.-]+)</command-name>", line):
                    c["commands"][cmd] += 1
                try:
                    msg = json.loads(line).get("message") or {}
                except (json.JSONDecodeError, AttributeError):
                    continue
                content = msg.get("content") if isinstance(msg, dict) else None
                if not isinstance(content, list):
                    continue
                for block in content:
                    if not isinstance(block, dict) or block.get("type") != "tool_use":
                        continue
                    name = block.get("name") or "?"
                    inp = block.get("input") or {}
                    c["tools"][name] += 1
                    if name.startswith("mcp__"):
                        c["mcp"][name] += 1
                    elif name == "Bash":
                        for key in bash_key(inp.get("command", "")):
                            c["bash"][key] += 1
                    elif name == "Skill":
                        c["skills"][inp.get("skill") or "?"] += 1
                    elif name in ("Agent", "Task"):
                        c["subagents"][inp.get("subagent_type") or "general-purpose"] += 1
    return {
        "transcript_dir": str(tdir),
        "sessions": len([f for f in files if f.parent == tdir]),
        "period": [first.date().isoformat() if first else None, last.date().isoformat() if last else None],
        **{k: v.most_common(50) for k, v in c.items()},
    }


def main():
    utf8_stdio()
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=".")
    ap.add_argument("--dir")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    tdir = Path(args.dir) if args.dir else find_transcript_dir(Path(args.project).resolve())
    if not tdir or not tdir.is_dir():
        result = {"transcript_dir": None, "sessions": 0,
                  "note": "transcrições não encontradas (talvez apagadas pela retenção)"}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    result = scan(tdir)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    print(f"{result['sessions']} sessões em {result['transcript_dir']} ({result['period'][0]} a {result['period'][1]})")
    for title, key, limit in [("FERRAMENTAS", "tools", 30), ("MCP", "mcp", 40), ("TERMINAL", "bash", 30),
                              ("SKILLS", "skills", 30), ("SUBAGENTES", "subagents", 20), ("COMANDOS /", "commands", 20)]:
        print(f"\n== {title}")
        for name, n in result[key][:limit]:
            print(f"{n:6} {name}")


if __name__ == "__main__":
    main()
