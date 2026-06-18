"""Path and serialization helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def ensure_dir(path: str | Path) -> Path:
    """Create a directory if needed and return it as a Path."""

    out = Path(path)
    out.mkdir(parents=True, exist_ok=True)
    return out


def write_json(path: str | Path, payload: dict[str, Any]) -> Path:
    """Write JSON with stable formatting."""

    target = Path(path)
    ensure_dir(target.parent)
    target.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return target


def read_json(path: str | Path) -> dict[str, Any]:
    """Read a JSON object from disk."""

    return json.loads(Path(path).read_text(encoding="utf-8"))
