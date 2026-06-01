#!/usr/bin/env python3
"""PostToolUse hook: ruff-check a Python file right after Claude edits it.

Reads the hook payload from stdin, and if the edited path is a ``.py`` file,
runs ``ruff check`` on it. A lint failure is reported back to Claude (exit 2 so
the output is surfaced). The hook stays quiet and non-blocking when ruff is not
installed or the edited file is not Python, so it never gets in the way on a
fresh clone without the dev extras.
"""

from __future__ import annotations

import json
import subprocess
import sys


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    file_path = (payload.get("tool_input") or {}).get("file_path") or ""
    if not file_path.endswith(".py"):
        return 0

    try:
        result = subprocess.run(
            [sys.executable, "-m", "ruff", "check", file_path],
            capture_output=True,
            text=True,
        )
    except OSError:
        return 0

    output = f"{result.stdout}{result.stderr}"
    if "No module named ruff" in output:
        # Dev extras not installed; do not nag.
        return 0
    if result.returncode != 0:
        sys.stderr.write(output)
        return 2  # Surface the lint findings to Claude.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
