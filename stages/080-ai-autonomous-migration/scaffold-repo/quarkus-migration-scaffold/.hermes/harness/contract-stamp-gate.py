#!/usr/bin/env python3
"""O-STAMP-GATE — verifier entrypoint (see contract-stamp.py gate subcommand)."""
import os
import runpy
import sys
from pathlib import Path

if __name__ == "__main__":
    harness = Path(__file__).resolve().parent
    argv = [str(harness / "contract-stamp.py"), "gate", *sys.argv[1:]]
    os.execv(sys.executable, [sys.executable, *argv])
