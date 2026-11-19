"""Baseline invariants for the 9router follow-up project.

Cheap but real: they prove the interpreter is supported and that the local
MSF tooling stays out of version control. Extend as the tool grows.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_supported_python():
    assert sys.version_info >= (3, 9), f"needs Python 3.9+, got {sys.version.split()[0]}"


def test_msf_tooling_is_not_tracked():
    lines = [line.strip() for line in (ROOT / ".gitignore").read_text().splitlines()]
    assert ".msf/" in lines
    assert ".venv/" in lines
