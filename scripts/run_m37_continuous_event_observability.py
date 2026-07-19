"""Run the preregistered M37 continuous-event observability gate."""

from __future__ import annotations

import argparse
import csv
import json
import math
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import matplotlib.pyplot as plt
import numpy as np
import scipy
import yaml

from pinnpcm.external_data.vo2_cross_regime_observability import (
    run_cross_regime_observability,
)
from pinnpcm.external_data.vo2_multivoltage import preprocess_experiment
from pinnpcm.external_data.vo2_zhang import compute_sha256
from pinnpcm.physics.vo2_thermal_neuristor import VO2ThermalNeuristorParameters


ROOT = Path(__file__).resolve().parents[1]


def _resolve(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def _relative(path: Path) -> str:
    return str(path.resolve().relative_to(ROOT.resolve())).replace("\\", "/")


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, text=True, capture_output=True, check=True
    ).stdout.strip()


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, np.ndarray):
        return _jsonable(value.tolist())
    if isinstance(value, (float, np.floating)):
        result = float(value)
        return result if math.isfinite(result) else None
    if isinstance(value, (int, np.integer)) and not isinstance(value, bool):
        return int(value)
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    return value


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_jsonable(dict(payload)), indent=2, sort_keys=True, allow_nan=False)
        + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    output_rows = list(rows)
    if not output_rows:
        output_rows = [
            {
                "method": "not_reached",
                "coordinate_system": "raw_log_C_th_log_S_e",
                "observation_group": "not_reached",
                "relative_step": None,
                "singular_index": None,
                "singular_value": None,
                "threshold_rank": None,
                "effective_rank": None,
                "retained_condition_number": None,
                "top_right_log_C_th": None,
                "top_right_log_S_e": None,
            }
        ]
    fields: list[str] = []
    for row in output_rows:
        for key in row:
            if key not in fields:
                fields.append(str(key))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in output_rows:
            writer.writerow({key: _jsonable(row.get(key)) for key in fields})


def _verify_preregistration(config: Mapping[str, Any]) -> dict[str, Any]:
    path = _resolve(config["outputs"]["preregistration"])
    if not path.exists():
        raise RuntimeError("M37 cannot run before preregistration exists.")
    prereg = json.loads(path.read_text(encoding="utf-8"))
    if prereg.get("solver_authorized_after_preregistration_commit") is not True:
        raise RuntimeError("M37 preregistration did not authorize the solver.")
    if prereg.get("sealed_13v_access") is not False:
        raise RuntimeError("M37 preregistration violated the 13 V seal.")
    if _git("rev-parse", "HEAD") == str(config["base_snapshot"]):
        raise RuntimeError("M37 solver must run after the preregistration commit.")
    mismatches = {
        name: {"expected": expected, "actual": compute_sha256(_resolve(name))}
        for name, expected in prereg["locked_files"].items()
        if not _resolve(name).exists() or compute_sha256(_resolve(name)) != expected
    }
    if mismatches:
        raise RuntimeError(f"M37 locked-file mismatch: {mismatches}")
    return prereg


def _load_observations(
    config: Mapping[str, Any], prereg: Mapping[str, Any]
) -> tuple[dict[float, dict[str, Any]], dict[float, str], dict[float, str]]:
    expected_hashes = {
        float(row["voltage_V"]): str(row["sha256"])
        for row in prereg["open_public_curve_records"]
    }
    observations: dict[float, dict[str, Any]] = {}
    regimes: dict[float, str] = {}
    activity: dict[float, str] = {}
    for item in config["data"]["open_voltage_curves"]:
        path = _resolve(item["path"])
        normalized = path.name.casefold().replace("_", "").replace(" ", "")
        if "13v" in normalized:
            raise PermissionError("M37 attempted sealed 13 V numeric access.")
        voltage = float(item["voltage_V"])
        if compute_sha256(path) != expected_hashes[voltage]:
            raise RuntimeError(f"Open {voltage:g} V curve changed after preregistration.")
        observations[voltage] = preprocess_experiment(
            path,
            voltage_V=voltage,
            current_sense_ohm=float(config["data"]["current_sense_ohm"]),
        )
        regimes[voltage] = str(item["regime"])
        activity[voltage] = str(item["expected_activity_class"])
    if sorted(observations) != [9.0, 11.0, 15.0, 17.0]:
        raise RuntimeError("M37 open observations are not exactly 9/11/15/17 V.")
    return observations, regimes, activity


def _make_figure(path: Path, rows: Sequence[Mapping[str, Any]], summary: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    figure, axes = plt.subplots(1, 2, figsize=(10.5, 4.2))
    groups = ("static_only", "oscillatory_only", "joint")
    colors = {"static_only": "#3B82F6", "oscillatory_only": "#EF4444", "joint": "#111827"}
    fine = 0.0025
    for group in groups:
        values = [
            float(row["singular_value"])
            for row in rows
            if row["method"] == "DOP853"
            and row["coordinate_system"] == "raw_log_C_th_log_S_e"
            and row["observation_group"] == group
            and float(row["relative_step"]) == fine
        ]
        if values:
            axes[0].plot(
                np.arange(1, len(values) + 1),
                values,
                marker="o",
                label=group,
                color=colors[group],
            )
    axes[0].set_yscale("log")
    axes[0].set_xlabel("Singular index")
    axes[0].set_ylabel("Whitened singular value")
    axes[0].set_title("M37 cross-regime spectra")
    axes[0].grid(alpha=0.25)
    if axes[0].lines:
        axes[0].legend(frameon=False)

    group_results = summary.get("groups", {})
    for group in groups:
        record = group_results.get(group)
        if not record:
            continue
        direction = np.asarray(record["top_right_singular_vector"], dtype=float)
        axes[1].arrow(
            0.0,
            0.0,
            direction[0],
            direction[1],
            width=0.012,
            length_includes_head=True,
            color=colors[group],
            label=group,
        )
        axes[1].text(direction[0] * 1.07, direction[1] * 1.07, group, color=colors[group])
    axes[1].axhline(0.0, color="0.8", linewidth=0.8)
    axes[1].axvline(0.0, color="0.8", linewidth=0.8)
    axes[1].set_xlim(-1.25, 1.25)
    axes[1].set_ylim(-1.25, 1.25)
    axes[1].set_aspect("equal")
    axes[1].set_xlabel("log(C_th) direction")
    axes[1].set_ylabel("log(S_e) direction")
    angle = summary.get("static_oscillatory_top_direction_angle_deg")
    angle_text = "not reached" if angle is None else f"{float(angle):.2f} deg"
    axes[1].set_title(f"Top directions; static/osc angle={angle_text}")
    axes[1].grid(alpha=0.25)
    figure.tight_layout()
    figure.savefig(path, dpi=180)
    plt.close(figure)


def _write_report(path: Path, summary: Mapping[str, Any], config: Mapping[str, Any]) -> None:
    groups = summary.get("groups", {})
    lines = [
        "# M37 continuous-event cross-regime observability results",
        "",
        "## Outcome",
        "",
        f"- Status: `{summary['status']}`.",
        f"- Claim status: `{summary['claim_status']}`.",
        f"- M38 authorized: `{str(summary['m38_authorized']).lower()}`.",
        f"- Forward evaluations: `{summary['forward_evaluations']}`.",
        f"- Solver wall time: `{summary['elapsed_seconds']:.3f} s`.",
        "- No fit, fit lock, PINN training, or 13 V numeric access occurred.",
        "",
        "M37 is a local continuous-equation observability preflight at the source",
        "parameter anchor. It is not source-compatible finite-step reproduction,",
        "parameter recovery, experimental validation, or a trained-PINN result.",
        "",
        "## M36 superseding semantic audit",
        "",
        "M36's historical JSON/CSV and failed vote remain unchanged. The new audit",
        "replaces the overly broad wording `true_numerical_nonconvergence` for",
        "11/15/17 V with finite-step accuracy-gate failure wording that records the",
        "observed error-versus-step trend. This is not a gate relaxation or a pass.",
        "",
        "## Preregistered observability geometry",
        "",
        "| Group | Rank | Singular values | Condition number | Step Jacobian change | Left-subspace angle |",
        "| --- | ---: | --- | ---: | ---: | ---: |",
    ]
    for group in ("static_only", "oscillatory_only", "joint"):
        record = groups.get(group)
        if record is None:
            lines.append(f"| {group} | not reached | not reached | not reached | not reached | not reached |")
        else:
            singular = ", ".join(f"{value:.6g}" for value in record["singular_values"])
            lines.append(
                f"| {group} | {record['threshold_rank']} | {singular} | "
                f"{record['retained_condition_number']:.6g} | "
                f"{record['two_finest_white_jacobian_relative_change']:.6g} | "
                f"{record['two_finest_retained_left_subspace_angle_deg']:.6g} |"
            )
    lines.extend(
        [
            "",
            "The static/oscillatory top-direction angle is "
            f"`{summary.get('static_oscillatory_top_direction_angle_deg')}` degrees.",
            "The DOP853/Radau comparison and analytic quotient transform are recorded",
            "in the machine-readable JSON. The quotient Jacobian is obtained only by",
            "the registered analytic chain rule; no quotient simulation was run and",
            "no Fisher-rank increase is claimed.",
            "",
            "## Claim boundary and next action",
            "",
        ]
    )
    if summary["m38_authorized"]:
        lines.extend(
            [
                "All registered gates pass. M37 therefore authorizes a separately",
                "preregistered M38 open-voltage LOVO fit, but performs no fit itself.",
            ]
        )
    else:
        lines.extend(
            [
                "At least one registered geometry, event, or cross-solver gate fails.",
                "The continuous-model public inverse route is closed and the project",
                "returns to `Q2_MANUSCRIPT_EVIDENCE_COMPRESSION` without extra scales,",
                "threshold changes, parameter search, or solver rescue.",
            ]
        )
    lines.extend(
        [
            "",
            "Forbidden claims remain: unique parameter recovery, independent external",
            "validation, gamma_sub/S_e equivalence, 13 V evaluation, trained-PINN",
            "success, and novelty for SVD/Fisher/event sensitivity or reversible",
            "reparameterization.",
            "",
            f"Base SHA: `{config['base_snapshot']}`. The final result SHA is supplied",
            "in the execution handoff because it cannot self-reference its own commit.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def run(config_path: Path) -> dict[str, Any]:
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    prereg = _verify_preregistration(config)
    result_paths = [
        _resolve(config["outputs"]["jacobian_summary"]),
        _resolve(config["outputs"]["jacobian_spectra"]),
        _resolve(config["outputs"]["figure"]),
        _resolve(config["outputs"]["report"]),
    ]
    if any(path.exists() for path in result_paths):
        raise FileExistsError("M37 refuses to overwrite an existing result artifact.")
    started_at = datetime.now(timezone.utc).isoformat()
    observations, regimes, expected_activity = _load_observations(config, prereg)
    m36_config = yaml.safe_load(
        _resolve(config["historical_inputs"]["m36_config"]).read_text(encoding="utf-8")
    )
    m36_summary = json.loads(
        _resolve(config["historical_inputs"]["m36_summary"]).read_text(encoding="utf-8")
    )
    source_config = yaml.safe_load(
        _resolve(config["historical_inputs"]["source_parameter_config"]).read_text(
            encoding="utf-8"
        )
    )
    base = VO2ThermalNeuristorParameters.from_config(source_config)
    expected_event_counts = {
        voltage: int(
            m36_summary["voltage_results"][f"{voltage:g}"]["reference_parity_metrics"]
            ["reference_reversal_event_count"]
        )
        for voltage in (9.0, 11.0, 15.0, 17.0)
    }
    rows, result = run_cross_regime_observability(
        base,
        observations,
        regimes,
        expected_activity,
        config,
        m36_config,
        prereg["locked_whitening"],
        expected_event_counts,
    )
    result.update(
        {
            "schema_version": "m37_continuous_event_observability_evidence_v1",
            "stage_id": config["stage_id"],
            "started_at_utc": started_at,
            "ended_at_utc": datetime.now(timezone.utc).isoformat(),
            "git_commit": _git("rev-parse", "HEAD"),
            "machine_summary": {
                "device": "cpu",
                "python": platform.python_version(),
                "platform": platform.platform(),
                "numpy": np.__version__,
                "scipy": scipy.__version__,
            },
            "claim_status": "qualified_supported"
            if result["m37_all_gates_pass"]
            else "failed_but_informative",
            "groups": result.get("groups", {}),
            "dop853_radau_crosscheck": result.get("dop853_radau_crosscheck", {}),
            "analytic_quotient_transform": result.get(
                "analytic_quotient_transform",
                {
                    "resimulation_performed": False,
                    "rank_increase_claim": "forbidden",
                },
            ),
            "m36_outputs_modified": False,
            "m36_failure_vote_unchanged": True,
            "m35_or_m36_full_workflow_rerun": False,
            "fit_executed": False,
            "fit_lock_created": False,
            "sealed_13v_access": False,
            "pinn_training_performed": False,
            "evidence_type": "solver_generated_local_observability_under_public_protocol",
            "next_single_action": "M38_OPEN_VOLTAGE_LOVO_PREREGISTRATION"
            if result["m38_authorized"]
            else "Q2_MANUSCRIPT_EVIDENCE_COMPRESSION",
        }
    )
    _write_csv(_resolve(config["outputs"]["jacobian_spectra"]), rows)
    _write_json(_resolve(config["outputs"]["jacobian_summary"]), result)
    _make_figure(_resolve(config["outputs"]["figure"]), rows, result)
    _write_report(_resolve(config["outputs"]["report"]), result, config)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/m37_continuous_event_observability.yaml"),
    )
    args = parser.parse_args()
    result = run(_resolve(args.config))
    print(
        json.dumps(
            {
                "status": result["status"],
                "m37_all_gates_pass": result["m37_all_gates_pass"],
                "m38_authorized": result["m38_authorized"],
                "forward_evaluations": result["forward_evaluations"],
                "elapsed_seconds": result["elapsed_seconds"],
                "sealed_13v_access": result["sealed_13v_access"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
