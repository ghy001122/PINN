from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import sys
import time

import yaml

from scripts import run_m43_finite_width_thermal_spreading as runner


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def test_main_terminalizes_post_receipt_exception_and_forbids_rerun(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    source_config = Path(__file__).resolve().parents[1] / "configs" / "m43_finite_width_thermal_spreading.yaml"
    config = yaml.safe_load(source_config.read_text(encoding="utf-8"))
    config_path = tmp_path / "configs" / source_config.name
    config_path.parent.mkdir(parents=True)
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8", newline="\n")

    protected_path = tmp_path / "protected.bin"
    protected_path.write_bytes(b"locked-evidence")
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    monkeypatch.setattr(runner, "_protected_paths", lambda: [protected_path])
    monkeypatch.setattr(
        runner,
        "_verify_protected_baseline",
        lambda paths: {"verified": True, "record_count": len(paths), "failures": []},
    )

    real_sha = runner._sha256

    def safe_sha(path: str | Path) -> str:
        candidate = Path(path)
        resolved = candidate if candidate.is_absolute() else tmp_path / candidate
        return real_sha(resolved) if resolved.is_file() else "A" * 64

    monkeypatch.setattr(runner, "_sha256", safe_sha)

    def injected_failure(path: Path) -> dict:
        outputs = config["outputs"]
        before = runner._snapshot([protected_path])
        receipt_path = tmp_path / outputs["execution_receipt"]
        summary_path = tmp_path / outputs["summary"]
        receipt = runner._create_execution_receipt(
            receipt_path,
            summary_path,
            "prereg-sha",
            safe_sha(path),
            {"configs/m43_finite_width_thermal_spreading.yaml": safe_sha(path)},
            before,
            wall_started=time.perf_counter(),
            cpu_started=time.process_time(),
        )
        receipt["forward_invocations_attempted"] = 1
        receipt["forward_invocations_completed"] = 1
        receipt["cases"] = [
            {
                "case_id": "tiny_completed_case",
                "canonical_case_sha256": "B" * 64,
                "status": "completed",
                "cell_count": 8,
            }
        ]
        runner._update_execution_receipt(receipt_path, receipt)
        raise RuntimeError("injected post-receipt failure")

    monkeypatch.setattr(runner, "run", injected_failure)
    monkeypatch.setattr(
        sys,
        "argv",
        ["run_m43_finite_width_thermal_spreading.py", "--config", str(config_path)],
    )

    assert runner.main() == 1
    captured = capsys.readouterr()
    assert "injected post-receipt failure" in captured.err

    receipt_path = tmp_path / config["outputs"]["execution_receipt"]
    summary_path = tmp_path / config["outputs"]["summary"]
    cases_path = tmp_path / config["outputs"]["cases"]
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    with cases_path.open("r", encoding="utf-8", newline="") as handle:
        case_rows = list(csv.DictReader(handle))

    assert receipt["status"] == "terminal_failed"
    assert receipt["terminal_rerun_forbidden"] is True
    assert receipt["formal_runner_invocations"] == 1
    assert summary["decision"] == "M43_STOP_C_FREEZE_1D"
    assert summary["status"] == "failed_but_informative"
    assert summary["gate_total_count"] == 21 == len(runner.EXPECTED_GATE_NAMES)
    assert set(summary["gates"]) == runner.EXPECTED_GATE_NAMES
    assert all(record["value"] is None and record["passed"] is False for record in summary["gates"].values())
    assert summary["forward_accounting"]["unique_thermal_pde_forwards"] == 1
    assert summary["forward_accounting"]["attempted_thermal_pde_forwards"] == 1
    assert summary["protected_evidence_unchanged"] is True
    assert summary["protected_evidence_mtime_unchanged"] is True
    assert len(case_rows) == 1
    assert case_rows[0]["case_id"] == "tiny_completed_case"

    receipt_digest = _digest(receipt_path)
    summary_digest = _digest(summary_path)
    assert runner.main() == 1
    capsys.readouterr()
    assert _digest(receipt_path) == receipt_digest
    assert _digest(summary_path) == summary_digest
