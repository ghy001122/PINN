"""Run the post-hoc M34-A gradient-semantics amendment without training."""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from pinnpcm.external_data.vo2_zhang import compute_sha256
from pinnpcm.pinn.m34a_gradient_semantics import gradient_semantics_amendment


ROOT = Path(__file__).resolve().parents[1]


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, text=True, capture_output=True, check=True
    ).stdout.strip()


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0])
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def run(config_path: Path) -> dict[str, Any]:
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    m34a = config["m34a"]
    output = ROOT / config["outputs"]["m34a_summary"]
    if output.exists():
        raise RuntimeError("M34-A amendment already exists; do not rerun it.")
    if _git("status", "--short"):
        raise RuntimeError("M34-A requires a clean committed preregistration worktree.")
    original_summary = ROOT / m34a["original_summary"]
    actual_hash = compute_sha256(original_summary)
    if actual_hash != str(m34a["original_summary_sha256"]).upper():
        raise RuntimeError("Locked M34 summary changed; amendment fails closed.")
    original = json.loads(original_summary.read_text(encoding="utf-8"))
    if original["corrected_training_authorized"] is not False:
        raise RuntimeError("M34-A cannot amend a training authorization.")
    m33_config = yaml.safe_load(
        (ROOT / m34a["m33_config"]).read_text(encoding="utf-8")
    )
    history = json.loads((ROOT / m34a["m33_history"]).read_text(encoding="utf-8"))
    with np.load(ROOT / m34a["diagnostic_dataset"], allow_pickle=False) as archive:
        arrays = {key: np.asarray(archive[key]) for key in archive.files}
    rows, summary = gradient_semantics_amendment(
        m33_config,
        m34a,
        ROOT / m34a["m33_checkpoint"],
        arrays,
        history,
    )
    _write_csv(ROOT / config["outputs"]["m34a_directions"], rows)
    payload = {
        "schema_version": "m34a_gradient_semantics_amendment_v1",
        "stage_id": "M34_A_POSTHOC_GRADIENT_SEMANTICS",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": _git("rev-parse", "HEAD"),
        "original_m34_summary": m34a["original_summary"],
        "original_m34_summary_sha256": actual_hash,
        "original_m34_status_preserved": original["status"],
        "original_preregistered_authorization_gate_preserved": True,
        "post_hoc_diagnostic_amendment": True,
        "dtype": m34a["dtype"],
        "relative_steps": m34a["relative_steps"],
        "direction_seeds": m34a["direction_seeds"],
        "summary": summary,
        "three_class_decision": {
            "autograd_implementation_error": summary[
                "autograd_implementation_error_supported"
            ],
            "total_loss_scale_finite_difference_cancellation": summary[
                "total_loss_scale_fd_cancellation_supported"
            ],
            "no_stable_step_interval_uncertain": bool(
                summary["uncertain_direction_count"]
            ),
        },
        "training_authorized": False,
        "sealed_13v_access": False,
        "evidence_type": "diagnostic_evidence",
        "claim_status": "failed_but_informative",
        "manuscript_rule": "The preregistered M34 authorization gate failed; do not claim a gradient implementation error unless this amendment directly supports it.",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config", type=Path, default=Path("configs/m35_public_multivoltage_fit.yaml")
    )
    args = parser.parse_args()
    path = args.config if args.config.is_absolute() else ROOT / args.config
    result = run(path)
    print(
        json.dumps(
            {
                "global_classification": result["summary"]["global_classification"],
                "training_authorized": False,
            },
            allow_nan=False,
        )
    )


if __name__ == "__main__":
    main()
