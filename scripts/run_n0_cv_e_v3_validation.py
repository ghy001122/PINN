"""Run and record the final N0-CV-E v3 validation commands."""

from __future__ import annotations

import argparse
import json
import platform
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import torch


ROOT = Path(__file__).resolve().parents[1]
PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
OUTPUT = ROOT / "outputs" / "tables" / "n0_cv_e_v3_validation.json"


def _run(label: str, arguments: list[str], display: str) -> dict[str, Any]:
    started = time.perf_counter()
    completed = subprocess.run(
        arguments,
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    combined = "\n".join(part for part in (completed.stdout, completed.stderr) if part).strip()
    counts = {
        "passed": 0,
        "failed": 0,
        "skipped": 0,
        "xfailed": 0,
        "xpassed": 0,
        "errors": 0,
        "warnings": 0,
    }
    for value, key in re.findall(
        r"(\d+)\s+(passed|failed|skipped|xfailed|xpassed|errors?|warnings?)",
        combined,
    ):
        normalized = "errors" if key.startswith("error") else "warnings" if key.startswith("warning") else key
        counts[normalized] = int(value)
    return {
        "label": label,
        "command": display,
        "returncode": completed.returncode,
        "result": "pass" if completed.returncode == 0 else "fail",
        "wall_clock_s": time.perf_counter() - started,
        "counts": counts,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-full", action="store_true")
    args = parser.parse_args()
    focused_tests = [
        "tests/test_electrostatics.py",
        "tests/test_gt_solver_smoke.py",
        "tests/test_full_pinn_contract.py",
        "tests/test_full_pinn_manufactured.py",
        "tests/test_full_pinn_n0_split.py",
        "tests/test_n0_fixed_diagnostics.py",
        "tests/test_n0_repair_evidence.py",
        "tests/test_n0_teacher_equation_compatibility.py",
        "tests/test_train_full_pinn_n0_repair.py",
        "tests/test_n0_r_v2_evidence_integrity.py",
        "tests/test_n0_cv_e_v3_operator.py",
        "tests/test_n0_cv_e_v3_gate_safety.py",
    ]
    commands = [
        _run(
            "focused_physics_and_n0_tests",
            [str(PYTHON), "-m", "pytest", *focused_tests, "-q"],
            ".\\.venv\\Scripts\\python.exe -m pytest "
            + " ".join(path.replace("/", "\\") for path in focused_tests)
            + " -q",
        ),
        _run(
            "governance_audit",
            [str(PYTHON), "scripts/audit_project_governance.py"],
            ".\\.venv\\Scripts\\python.exe scripts\\audit_project_governance.py",
        ),
    ]
    if not args.skip_full:
        commands.append(
            _run(
                "full_pytest",
                [str(PYTHON), "-m", "pytest", "-q"],
                ".\\.venv\\Scripts\\python.exe -m pytest -q",
            )
        )
    commands.append(
        _run("git_diff_check", ["git", "diff", "--check"], "git diff --check")
    )
    payload = {
        "schema_version": "n0_cv_e_v3_validation_v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "machine": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "torch": torch.__version__,
            "cuda_available": torch.cuda.is_available(),
            "device": "cpu",
        },
        "commands": commands,
        "all_pass": all(command["returncode"] == 0 for command in commands),
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps({"all_pass": payload["all_pass"], "commands": len(commands)}))
    if not payload["all_pass"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
