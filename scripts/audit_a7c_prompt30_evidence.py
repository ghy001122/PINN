"""Build a read-only, machine-readable audit of the a7c prompt-29 evidence."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = Path("outputs/tables/prompt30_a7c_audit_summary.json")
BASE_COMMIT = "a7c108e3980953ced24d2de86ce7afc340e65a88"
INPUTS = [
    Path("docs/codex_reports/n0_optimizer_forensics_sid_discovery_final.md"),
    Path("outputs/tables/n0_cv_e_v3r_post_adam_score.json"),
    Path("outputs/tables/n0_cv_e_v3r_forensic_resolution.json"),
    Path("outputs/tables/n0_cv_e_v3r_summary.json"),
    Path("outputs/tables/sid_ec_oq_summary.json"),
    Path("outputs/tables/n0_sid_prompt29_validation.json"),
    Path("configs/n0_cv_e_v3r_optimizer_forensics.yaml"),
    Path("configs/sid_ec_oq_event_geometry.yaml"),
    Path(".github/workflows/read_only_validation.yml"),
]


def _resolve(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _base_blob_sha256(path: Path) -> str:
    git_path = str(path).replace("\\", "/")
    payload = subprocess.check_output(["git", "show", f"{BASE_COMMIT}:{git_path}"], cwd=ROOT)
    return hashlib.sha256(payload).hexdigest()


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n"
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(encoded, encoding="utf-8")
    tmp.replace(path)


def _load_json(path: str) -> dict[str, Any]:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def _csv_count(path: str) -> int:
    with (ROOT / path).open("r", newline="", encoding="utf-8") as handle:
        return sum(1 for _ in csv.DictReader(handle))


def build_audit(output: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    missing = [str(path).replace("\\", "/") for path in INPUTS if not _resolve(path).exists()]
    if missing:
        raise FileNotFoundError(f"Missing a7c audit inputs: {missing}")
    report = (ROOT / "docs/codex_reports/n0_optimizer_forensics_sid_discovery_final.md").read_text(encoding="utf-8")
    post = _load_json("outputs/tables/n0_cv_e_v3r_post_adam_score.json")
    forensic = _load_json("outputs/tables/n0_cv_e_v3r_forensic_resolution.json")
    sid = _load_json("outputs/tables/sid_ec_oq_summary.json")
    validation = _load_json("outputs/tables/n0_sid_prompt29_validation.json")
    sid_case_rows = _csv_count("outputs/tables/sid_ec_oq_cases.csv")
    sid_bootstrap_rows = _csv_count("outputs/tables/sid_ec_oq_bootstrap.csv")
    derivative = sid["derivative_audit"]
    sid_decision = sid["decision"]
    metrics_over_20x = post["metrics_exceeding_20x_gate"]

    consistency = {
        "report_mentions_1200_adam_steps": "1200" in report and int(post["adam_steps"]) == 1200,
        "report_matches_port_gate": "port" in report.lower() and "passes" in report.lower() and math.isclose(float(post["score"]["metrics"]["port_full_trace_nrmse95"]), 0.09554748319724289) and float(post["score"]["metrics"]["port_full_trace_nrmse95"]) <= 0.10,
        "report_matches_five_over_20x_metrics": "Five metrics exceed" in report and len(metrics_over_20x) == 5,
        "report_matches_sid_forward_budget": "189" in report and int(sid["solver_forward_evaluations"]) == 189,
        "report_matches_sid_derivative_vote": "3/9" in report and int(derivative["passing_cases"]) == 3 and int(derivative["total_cases"]) == 9,
        "report_matches_sid_max_discrepancy": "0.648429" in report and math.isclose(float(derivative["maximum_relative_difference"]), 0.6484293492573403),
        "sid_case_count_matches_validation": sid_case_rows == 36,
        "sid_bootstrap_count_matches_validation": sid_bootstrap_rows == 600,
        "prompt29_frozen_gt_unchanged": validation["frozen_gt_modified"] is False,
    }
    if not all(consistency.values()):
        raise RuntimeError(f"a7c report/JSON consistency check failed: {consistency}")

    working_hashes = {str(path).replace("\\", "/"): _sha256(_resolve(path)) for path in INPUTS}
    base_hashes = {str(path).replace("\\", "/"): _base_blob_sha256(path) for path in INPUTS}
    matches_base = {path: working_hashes[path] == base_hashes[path] for path in working_hashes}
    scientific_paths = [path for path in matches_base if not path.startswith(".github/workflows/")]
    if not all(matches_base[path] for path in scientific_paths):
        raise RuntimeError(f"Scientific a7c artifact drift detected: {matches_base}")

    payload = {
        "schema_version": "prompt30_a7c_audit_summary_v1",
        "audited_commit": BASE_COMMIT,
        "audit_semantics": "hash, row-count, gate-logic, and report-to-JSON consistency only; no historical experiment was rerun",
        "audited_base_blob_hashes": base_hashes,
        "working_tree_hashes": working_hashes,
        "working_tree_matches_a7c": matches_base,
        "workflow_scope_note": "The a7c workflow blob is hash-audited from Git; the working workflow is the prompt-30 preregistered CI split and is not a scientific-result change.",
        "row_counts": {"sid_cases": sid_case_rows, "sid_bootstrap": sid_bootstrap_rows},
        "report_json_consistency": consistency,
        "actually_executed": [
            {
                "id": "n0_v3r_adam_replay",
                "evidence": "1200 Adam steps completed; a scoreable PINN-predicted post-Adam trajectory exists",
                "metrics": {"initial_loss": post["initial_total_loss"], "post_loss": post["post_total_loss"]},
            },
            {
                "id": "n0_v3r_lbfgs_diagnostic",
                "evidence": "serializer-safe same-checkpoint replay reproduced the strong-Wolfe non-finite parameter at closure 3",
                "metrics": forensic["authorized_replay"]["serializer_safe_diagnostic_replay"],
            },
            {
                "id": "sid_ec_oq_current_preregistered_audit",
                "evidence": "solver-first event-window geometry audit completed within its locked budget",
                "metrics": {"solver_forward_evaluations": sid["solver_forward_evaluations"], "budget_cap": sid["budget_cap"], "case_rows": sid_case_rows},
            },
        ],
        "gates_passed": [
            {"id": "n0_v3r_port", "value": post["score"]["metrics"]["port_full_trace_nrmse95"], "threshold": 0.10, "scope": "port-only; not forward fidelity"},
            {"id": "n0_v3r_finite_and_bounds", "scope": "finite output/state-bound implementation checks only"},
            {"id": "sid_isolated_rank_vote", "scope": "non-voting after the numerical derivative prerequisite failed"},
            {"id": "sid_switch_information_vote", "value": sid["gate_metrics"]["switch_information_ratio"], "scope": "non-voting after the derivative/window prerequisite failed"},
        ],
        "failed_but_informative": [
            {
                "id": "n0_v3r_trained_forward",
                "reason": "port passes but residual, field, interface-flux, energy, and defect-ledger gates fail",
                "metrics_over_20x_gate": metrics_over_20x,
            },
            {
                "id": "sid_ec_oq_current_preregistered_implementation",
                "reason": "derivative agreement, event-window, stability, and dual-geometry prerequisites fail",
                "metrics": {"derivative": derivative, "gate_metrics": sid["gate_metrics"]},
            },
        ],
        "current_implementation_rejected": [
            {
                "id": "n0_v3r_optimizer_route",
                "disposition": forensic["recovery_decision"]["decision"],
                "scope": "the locked N0 optimizer route; not deletion of the complete multidomain PINN architecture",
            },
            {
                "id": "sid_ec_oq_prompt29_contract",
                "disposition": sid_decision["disposition"],
                "scope": "the prompt-29 preregistered numerical derivative/event-window implementation",
            },
        ],
        "still_unvalidated": [
            "reliable complete-PINN forward fidelity",
            "PINN sensitivity/Fisher geometry fidelity",
            "PINN inverse readiness",
            "protocol-dependent quotient identifiability",
            "the broader SID scientific hypothesis under a new numerical/event-window contract",
            "D0b-D0d, any 13 V evaluation, and independent external validation",
        ],
        "sid_scope_correction": {
            "current_preregistered_implementation_rejected": True,
            "broad_scientific_hypothesis_permanently_falsified": False,
            "active_now": False,
            "revisit_requires": "new user-authorized phase plus a new numerical derivative and event-window contract",
            "allowed_wording": "The current preregistered SID implementation failed its numerical and stability gates and is inactive.",
            "forbidden_wording": "The SID scientific hypothesis has been permanently falsified.",
        },
        "claim_status": "supported",
        "claim_scope": "machine audit of existing a7c artifacts only",
        "frozen_gt_modified": False,
        "historical_expensive_results_recomputed": False,
    }
    _atomic_json(_resolve(output), payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    print(json.dumps(build_audit(args.output), indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
