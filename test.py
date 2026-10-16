"""Run isolated regression checks without touching local saves or live services."""

from pathlib import Path
import subprocess
import sys
import os

if __name__ == "__main__":
    root = Path(__file__).resolve().parent
    raise SystemExit(
        subprocess.call(
            [
                sys.executable,
                "-m",
                "pytest",
                "tests/test_regressions.py",
                "-q",
                *sys.argv[1:],
            ],
            cwd=root,
            env=dict(
                os.environ, PYTEST_DISABLE_PLUGIN_AUTOLOAD="1", PYTHONIOENCODING="utf-8"
            ),
        )
    )
