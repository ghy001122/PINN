from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import numpy as np
import yaml

from scripts.audit_gamma_sub_simulator_backed_sequential_protocol_validation import run_simulator_backed_sequential_validation

FROZEN = [
    Path("data/processed/gt_v1_acceptance/gt_triangle.npz"),
    Path("data/processed/gt_v1_acceptance/obs_triangle_sparse.npz"),
]


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def test_simulator_backed_sequential_config_scope() -> None:
    cfg = yaml.safe_load(Path("configs/gamma_sub_simulator_backed_sequential_protocol_validation.yaml").read_text(encoding="utf-8"))
    names = {row["candidate_name"] for row in cfg["protocol_candidates"]}
    assert {"multi_pulse_to_ltp_ltd", "short_pulse_to_ltp_ltd", "ltp_ltd_only", "short_pulse_only", "best_single_protocol_only"}.issubset(names)
    assert "ODE simulator" in Path("scripts/audit_gamma_sub_simulator_backed_sequential_protocol_validation.py").read_text(encoding="utf-8")


def test_simulator_backed_sequential_smoke(tmp_path: Path) -> None:
    before = {str(path): _sha(path) for path in FROZEN}
    cfg = yaml.safe_load(Path("configs/gamma_sub_simulator_backed_sequential_protocol_validation.yaml").read_text(encoding="utf-8"))
    cfg["summary_json"] = str(tmp_path / "summary.json")
    cfg["cases_csv"] = str(tmp_path / "cases.csv")
    cfg["simulation"]["nx"] = 7
    cfg["simulation"]["nt"] = 24
    cfg["inverse"]["gamma_candidates"] = [4.25e8, 4.5e8, 5.0e8]
    cfg["protocol_candidates"] = cfg["protocol_candidates"][:2]
    cfg["scenarios"] = cfg["scenarios"][:1]
    cfg["noise_levels"] = [0.0]
    cfg["seeds"] = [2026]
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
    summary = run_simulator_backed_sequential_validation(path)
    after = {str(path): _sha(path) for path in FROZEN}
    assert before == after
    assert summary["all_finite_results"] is True
    assert summary["all_cases_simulator_backed"] is True
    assert summary["frozen_gt_unchanged"] is True
    with Path(cfg["cases_csv"]).open("r", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert rows
    assert all(row["simulator_backed"] == "True" for row in rows)
    assert all(np.isfinite(float(row["relative_error"])) for row in rows)
    saved = json.loads(Path(cfg["summary_json"]).read_text(encoding="utf-8"))
    assert "not experimental data" in saved["note"]
