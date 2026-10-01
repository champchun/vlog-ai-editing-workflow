"""Stage 0B shared paths/helpers."""
from __future__ import annotations

import json
import sys
from pathlib import Path

PROCESS = Path(__file__).resolve().parents[2]
REPO = PROCESS.parent
WORKSPACE = PROCESS / "workspace"
IN0A = WORKSPACE / "project-output" / "stage0a_output"
OUT = WORKSPACE / "project-output" / "stage0b_output"
TEMP = WORKSPACE / "temp" / "stage0b"

sys.path.insert(0, str(PROCESS / "stage-0A-local-pre-analysis" / "scripts"))
from common import read_json, write_json  # noqa: E402,F401


def load_json(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))
