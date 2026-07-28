from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent


def main() -> int:
    prefix = Path(sys.prefix).resolve()
    active_prefix = os.environ.get("CONDA_PREFIX")
    conda_exe = (
        prefix.parents[1] / "Scripts" / "conda.exe"
        if len(prefix.parents) > 1
        else Path("")
    )
    if os.name == "nt" and (
        not active_prefix or Path(active_prefix).resolve() != prefix
    ) and conda_exe.exists():
        command = [
            str(conda_exe),
            "run",
            "--no-capture-output",
            "-p",
            str(prefix),
            "python",
            str(HERE / "gui.py"),
            *sys.argv[1:],
        ]
    else:
        command = [sys.executable, str(HERE / "gui.py"), *sys.argv[1:]]
    return subprocess.call(command)


if __name__ == "__main__":
    raise SystemExit(main())
