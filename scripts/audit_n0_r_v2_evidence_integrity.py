"""Phase A evidence-integrity audit for the closed N0-R v2 attempt."""

from __future__ import annotations

import argparse
import json
import platform
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import torch
import yaml

from pinnpcm.pinn.full_pinn_1d import FullPINN1D
from pinnpcm.pinn.full_pinn_1d_split import DualDomainFullPINN1D
from pinnpcm.pinn.n0_cv_evidence import (
    canonical_lf_sha256,
    common_cv_score,
    gate_coverage_table,
    git_tracked,
    load_frozen_gt,
    model_trajectory,
    query_remote_ci,
    radau_replay_interval,
    raw_sha256,
    semantic_sha256,
    stable_file_hash,
    tamper_detection,
    trajectory_ledgers,
    v2_gate_coverage_audit,
)


ROOT = Path(__file__).resolve().parents[1]


def _load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, text=True, capture_output=True, check=True
    ).stdout.strip()


def _load_global_baseline(
    params: dict[str, Any], duration_s: float, checkpoint: Path
) -> FullPINN1D:
    config = _load_yaml(ROOT / "configs/full_pinn_architecture_v1.yaml")
    architecture = config["architecture"]
    model = FullPINN1D(
        params=params,
        t_max_s=duration_s,
        hidden_dim=int(architecture["hidden_dim"]),
        hidden_layers=int(architecture["hidden_layers"]),
        fourier_scales=architecture["fourier_scales"],
        voltage_scale_v=float(architecture["voltage_scale_V"]),
        temperature_scale_k=float(architecture["temperature_scale_K"]),
        seed=20260715,
    )
    model.load_state_dict(torch.load(checkpoint, map_location="cpu", weights_only=False)["model_state_dict"])
    return model


def _load_split_repair(
    params: dict[str, Any], duration_s: float, checkpoint: Path, config: dict[str, Any]
) -> DualDomainFullPINN1D:
    architecture = config["architecture"]
    model = DualDomainFullPINN1D(
        params=params,
        t_max_s=duration_s,
        hidden_dim_per_domain=int(architecture["hidden_dim_per_domain"]),
        hidden_layers=int(architecture["hidden_layers"]),
        fourier_scales=architecture["fourier_scales"],
        voltage_scale_v=float(architecture["voltage_scale_V"]),
        temperature_scale_k=float(architecture["temperature_scale_K"]),
        seed=20260715,
    )
    model.load_state_dict(torch.load(checkpoint, map_location="cpu", weights_only=False)["model_state_dict"])
    return model


def _pytest_evidence() -> dict[str, Any]:
    report_path = ROOT / "docs/codex_reports/n0_full_pinn_bounded_repair_v2_report.md"
    report_text = report_path.read_text(encoding="utf-8") if report_path.exists() else ""
    match = re.search(r"(\d+) passed in ([0-9.]+)s", report_text)
    machine_candidates = [
        ROOT / "outputs/tables/n0_r_v2_pytest_evidence.json",
        ROOT / "outputs/logs/n0_r_v2_pytest.txt",
    ]
    existing = [path for path in machine_candidates if path.exists()]
    return {
        "report_path": str(report_path.relative_to(ROOT)).replace("\\", "/"),
        "textual_summary_present": match is not None,
        "textual_summary": match.group(0) if match else None,
        "machine_log_present": bool(existing),
        "machine_log_paths": [str(path.relative_to(ROOT)).replace("\\", "/") for path in existing],
        "classification": "textual_report_only" if match and not existing else "machine_evidence_present" if existing else "missing",
    }


def _region_fixed_set_audit(path: Path) -> dict[str, Any]:
    with np.load(path, allow_pickle=False) as archive:
        rows = {}
        for region in ("near_interface", "near_transition", "ordinary"):
            keys = [key for key in archive.files if key.startswith(region)]
            rows[region] = {
                "keys": keys,
                "point_count": int(sum(np.asarray(archive[key]).shape[0] for key in keys)),
                "nonempty": bool(keys) and all(np.asarray(archive[key]).shape[0] > 0 for key in keys),
            }
    return {"regions": rows, "all_nonempty": all(row["nonempty"] for row in rows.values())}


def run(config_path: Path) -> dict[str, Any]:
    config = _load_yaml(config_path)
    frozen = config["frozen_inputs"]
    gt_path = ROOT / frozen["gt_path"]
    gt_config_path = ROOT / frozen["gt_config"]
    gt, params = load_frozen_gt(gt_path)
    gt_config = _load_yaml(gt_config_path)
    duration_s = float(np.asarray(gt["t"])[-1])

    v2_config_path = ROOT / frozen["v2_config"]
    v2_lock_path = ROOT / frozen["v2_preregistration"]
    v2_result_path = ROOT / frozen["v2_result"]
    v2_config = _load_yaml(v2_config_path)
    v2_lock = _load_json(v2_lock_path)
    v2_result = _load_json(v2_result_path)
    v2_checkpoint = ROOT / frozen["v2_checkpoint"]

    declared_checkpoint_sha = v2_result.get("result", {}).get("checkpoint_sha256")
    checkpoint_record = {
        "declared_path": frozen["v2_checkpoint"],
        "exists_in_active_workspace": v2_checkpoint.exists(),
        "tracked_by_git": git_tracked(v2_checkpoint, ROOT) if v2_checkpoint.exists() else False,
        "raw_sha256": raw_sha256(v2_checkpoint) if v2_checkpoint.exists() else None,
        "declared_result_sha256": declared_checkpoint_sha,
        "local_hash_matches_result": bool(
            v2_checkpoint.exists() and raw_sha256(v2_checkpoint) == declared_checkpoint_sha
        ),
        "classification": "missing_from_versioned_evidence",
        "remote_retrieval_documented": False,
    }

    ledger = trajectory_ledgers(gt, params)
    tamper = tamper_detection(gt, params)
    replay = radau_replay_interval(
        gt,
        params,
        rtol=float(gt_config["run"]["rtol"]),
        atol=float(gt_config["run"]["atol"]),
    )

    registry = config["dimensionless_registry"]
    global_checkpoint = ROOT / frozen["global_baseline_checkpoint"]
    global_model = _load_global_baseline(params, duration_s, global_checkpoint)
    global_trajectory = model_trajectory(global_model, gt)
    unified_scores: dict[str, Any] = {
        "normalization_registry": registry,
        "strongest_global_baseline": {
            "checkpoint_sha256": raw_sha256(global_checkpoint),
            "checkpoint_tracked": git_tracked(global_checkpoint, ROOT),
            "metrics": common_cv_score(global_trajectory, gt, params, registry),
        },
    }
    if v2_checkpoint.exists():
        split_model = _load_split_repair(params, duration_s, v2_checkpoint, v2_config)
        split_trajectory = model_trajectory(split_model, gt)
        unified_scores["e3f5765_split_repair"] = {
            "checkpoint_sha256": raw_sha256(v2_checkpoint),
            "checkpoint_tracked": False,
            "reproducibility_boundary": "local_untracked_checkpoint",
            "metrics": common_cv_score(split_trajectory, gt, params, registry),
        }
    else:
        unified_scores["e3f5765_split_repair"] = {
            "available": False,
            "metrics": None,
            "reproducibility_boundary": "checkpoint_missing",
        }

    current_commit = _git("rev-parse", "HEAD")
    remote_ci = query_remote_ci(current_commit)
    old_points_path = ROOT / frozen["old_fixed_points"]
    v3_mapping = gate_coverage_table(config)
    v2_coverage = v2_gate_coverage_audit(v2_config, v2_result)

    frozen_hashes = {
        frozen["gt_path"]: raw_sha256(gt_path),
        frozen["gt_config"]: raw_sha256(gt_config_path),
        frozen["gt_manifest"]: raw_sha256(ROOT / frozen["gt_manifest"]),
        frozen["old_fixed_points"]: raw_sha256(old_points_path),
    }
    frozen_checks = {
        "gt_matches_v2_lock": frozen_hashes[frozen["gt_path"]]
        == v2_lock["locked_file_sha256"][frozen["gt_path"]],
        "gt_config_matches_v2_lock": frozen_hashes[frozen["gt_config"]]
        == v2_lock["locked_file_sha256"][frozen["gt_config"]],
        "old_fixed_points_raw_hash_matches_config": frozen_hashes[frozen["old_fixed_points"]]
        == frozen["old_fixed_points_raw_sha256"],
    }

    phase_a_checks = {
        "v3_gate_mapping_complete": bool(v3_mapping["mapping_complete"]),
        "frozen_hashes_unchanged": all(frozen_checks.values()),
        "old_fixed_regions_nonempty": _region_fixed_set_audit(old_points_path)["all_nonempty"],
        "independent_defect_ledger": ledger["defect"]["gate_value"]
        <= float(config["preflight_gates"]["frozen_trajectory_defect_ledger_max"]),
        "independent_energy_ledger": ledger["energy"]["gate_value"]
        <= float(config["preflight_gates"]["frozen_trajectory_energy_ledger_max"]),
        "radau_replay": bool(replay.get("success"))
        and replay.get("maximum_relative_rms", float("inf"))
        <= float(config["preflight_gates"]["radau_replay_relative_rms_max"]),
        "tamper_detection": bool(tamper["defect_tamper_detected"] and tamper["energy_tamper_detected"]),
        "unified_rescore_executed": unified_scores["strongest_global_baseline"]["metrics"] is not None
        and unified_scores["e3f5765_split_repair"]["metrics"] is not None,
    }

    payload = {
        "schema_version": "n0_r_v2_evidence_integrity_audit_v1",
        "stage_id": "N0-CV-E-v3-Phase-A",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "base_commit": config["base_commit"],
        "git_commit": current_commit,
        "git_dirty": bool(_git("status", "--short")),
        "machine": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "torch": torch.__version__,
            "cuda_available": torch.cuda.is_available(),
            "device": "cpu",
        },
        "phase_a_checks": phase_a_checks,
        "phase_a_completed": all(phase_a_checks.values()),
        "status": "completed_with_documented_v2_evidence_gaps" if all(phase_a_checks.values()) else "failed",
        "v2_gate_coverage": v2_coverage,
        "v3_gate_mapping": v3_mapping,
        "stable_hash_policy": {
            "config_semantic_sha256": semantic_sha256(config_path),
            "config_raw_sha256_preserved_separately": raw_sha256(config_path),
            "audit_script_canonical_lf_sha256": canonical_lf_sha256(Path(__file__)),
            "binary_gt_raw_sha256": raw_sha256(gt_path),
            "v2_recorded_hashes_rewritten": False,
        },
        "frozen_hashes": frozen_hashes,
        "frozen_checks": frozen_checks,
        "v2_checkpoint": checkpoint_record,
        "remote_ci": remote_ci,
        "pytest_evidence": _pytest_evidence(),
        "historical_conservation_audit_disposition": {
            "path": "outputs/tables/n0_global_conservation_audit_v1.json",
            "new_role": "algebraic_bookkeeping_smoke_test",
            "independent_trajectory_evidence": False,
        },
        "independent_trajectory_ledger": ledger,
        "radau_replay": replay,
        "tamper_detection": tamper,
        "old_fixed_region_usage": _region_fixed_set_audit(old_points_path),
        "unified_cv_rescore": unified_scores,
        "claim_status": {
            "teacher_operator_audit": "supported",
            "v2_trained_forward": "failed_but_informative",
            "v2_reproducibility_completeness": "failed_but_informative",
            "v3_forward": "forbidden_until_preflight_and_training",
        },
    }
    return payload


def _write_report(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ledger = payload["independent_trajectory_ledger"]
    comparison = payload["unified_cv_rescore"]
    baseline = comparison["strongest_global_baseline"]["metrics"]
    repair = comparison["e3f5765_split_repair"]["metrics"]
    lines = [
        "# N0-R v2 Evidence-Integrity Audit",
        "",
        f"Base commit: `{payload['base_commit']}`",
        "",
        f"Audit commit/worktree HEAD: `{payload['git_commit']}` (pre-commit working tree).",
        "",
        f"Status: `{payload['status']}`. This is a no-training audit.",
        "",
        "## Findings",
        "",
        f"- v2 gate coverage complete: `{payload['v2_gate_coverage']['coverage_complete']}`; fail-closed gaps: `{', '.join(payload['v2_gate_coverage']['documented_gaps'])}`.",
        f"- v2 checkpoint is locally present but Git-tracked: `{payload['v2_checkpoint']['tracked_by_git']}`; classification: `{payload['v2_checkpoint']['classification']}`.",
        f"- Remote CI: `{payload['remote_ci']['status']}`; the audit does not infer CI success from an empty run list.",
        f"- Historical pytest evidence: `{payload['pytest_evidence']['classification']}`.",
        "- `n0_global_conservation_audit_v1.json` is now explicitly treated as an algebraic bookkeeping smoke test, not independent trajectory validation.",
        "",
        "## Independent adjacent-state ledger",
        "",
        f"- Defect gate value: `{ledger['defect']['gate_value']:.9g}` (gate `0.01`).",
        f"- Energy gate value: `{ledger['energy']['gate_value']:.9g}` (gate `0.05`).",
        f"- Radau replay maximum relative RMS: `{payload['radau_replay']['maximum_relative_rms']:.9g}`.",
        f"- Tamper detection: defect `{payload['tamper_detection']['defect_tamper_detected']}`, energy `{payload['tamper_detection']['energy_tamper_detected']}`.",
        "",
        "## Unified frozen-scale rescore",
        "",
        "| Model | Port NRMSE95 | max CV residual | defect ledger | energy ledger |",
        "| --- | ---: | ---: | ---: | ---: |",
        f"| global baseline | {baseline['port_full_trace_nrmse95']:.6g} | {max(baseline['cv_residual_rms'].values()):.6g} | {baseline['defect_mass_ledger']['gate_value']:.6g} | {baseline['global_energy_ledger']['gate_value']:.6g} |",
        f"| e3f5765 split repair | {repair['port_full_trace_nrmse95']:.6g} | {max(repair['cv_residual_rms'].values()):.6g} | {repair['defect_mass_ledger']['gate_value']:.6g} | {repair['global_energy_ledger']['gate_value']:.6g} |",
        "",
        "Both rows use the same analytic series-electrical reconstruction, frozen CV RHS, full 31-cell time grid, and dimensionless registry. The comparison does not reuse the incompatible v2 interface scales.",
        "",
        "## Claim boundary",
        "",
        "Phase A repairs evidence routing but does not upgrade trained full-PINN evidence. N0-CV-E v3 remains forbidden until its independent preflight and conditional training gates pass.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("configs/full_pinn_n0_cv_e_v3.yaml"))
    args = parser.parse_args()
    config_path = args.config if args.config.is_absolute() else ROOT / args.config
    payload = run(config_path)
    config = _load_yaml(config_path)
    output_path = ROOT / config["outputs"]["phase_a_json"]
    report_path = ROOT / config["outputs"]["phase_a_report"]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    _write_report(payload, report_path)
    print(json.dumps({"status": payload["status"], "phase_a_completed": payload["phase_a_completed"]}))
    if not payload["phase_a_completed"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
