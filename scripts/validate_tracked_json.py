"""Strictly parse every Git-tracked JSON artifact without writing files."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def validate_tracked_json() -> dict[str, object]:
    output = subprocess.check_output(["git", "ls-files", "*.json"], cwd=ROOT, text=True)
    paths = [Path(line.strip()) for line in output.splitlines() if line.strip()]
    failures: list[dict[str, str]] = []
    for relative in paths:
        try:
            json.loads(
                (ROOT / relative).read_text(encoding="utf-8"),
                parse_constant=lambda value: (_ for _ in ()).throw(ValueError(f"non-standard constant {value}")),
            )
        except Exception as exc:  # pragma: no cover - failure is reported to CI
            failures.append({"path": str(relative).replace("\\", "/"), "error": f"{type(exc).__name__}: {exc}"})
    summary: dict[str, object] = {
        "schema_version": "tracked_json_validation_v1",
        "tracked_json_count": len(paths),
        "failure_count": len(failures),
        "failures": failures,
        "status": "pass" if not failures else "fail",
    }
    if failures:
        raise RuntimeError(json.dumps(summary, sort_keys=True))
    return summary


if __name__ == "__main__":
    print(json.dumps(validate_tracked_json(), indent=2, sort_keys=True))
