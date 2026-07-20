"""Run the single preregistered M37R repaired observability vote."""

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

from pinnpcm.external_data.vo2_cross_regime_observability_repair import (
    build_m36_reference_window_audit,
    run_cross_regime_observability_repair,
    validate_evidence_contract,
)
from pinnpcm.external_data.vo2_multivoltage import preprocess_experiment
from pinnpcm.external_data.vo2_zhang import compute_sha256
from pinnpcm.physics.vo2_thermal_neuristor import VO2ThermalNeuristorParameters


ROOT = Path(__file__).resolve().parents[1]


def _resolve(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


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
        output_rows = [{"status": "not_reached"}]
    fields: list[str] = []
    for row in output_rows:
        for key in row:
            if str(key) not in fields:
                fields.append(str(key))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in output_rows:
            writer.writerow({key: _jsonable(row.get(key)) for key in fields})


def _verify_preregistration(config: Mapping[str, Any]) -> dict[str, Any]:
    prereg_path = _resolve(config["outputs"]["preregistration"])
    if not prereg_path.exists():
        raise RuntimeError("M37R cannot run before preregistration exists.")
    prereg = json.loads(prereg_path.read_text(encoding="utf-8"))
    if prereg.get("solver_authorized_after_preregistration_commit") is not True:
        raise RuntimeError("M37R preregistration does not authorize the solver.")
    if prereg.get("formal_execution_limit") != 1:
        raise RuntimeError("M37R formal execution limit is not exactly one.")
    if prereg.get("sealed_13v_access") is not False:
        raise RuntimeError("M37R preregistration violated the 13 V seal.")
    head = _git("rev-parse", "HEAD")
    if head == str(config["base_snapshot"]):
        raise RuntimeError("M37R must run after the separate preregistration commit.")
    if _git("status", "--short"):
        raise RuntimeError("M37R formal run requires a clean preregistration commit.")
    mismatches = {
        name: {"expected": expected, "actual": compute_sha256(_resolve(name))}
        for name, expected in prereg["locked_files"].items()
        if not _resolve(name).exists() or compute_sha256(_resolve(name)) != expected
    }
    if mismatches:
        raise RuntimeError(f"M37R locked-file mismatch: {mismatches}")
    historical_mismatches = {
        name: {"expected": expected, "actual": compute_sha256(_resolve(name))}
        for name, expected in prereg["historical_read_only_files"].items()
        if not _resolve(name).exists() or compute_sha256(_resolve(name)) != expected
    }
    if historical_mismatches:
        raise RuntimeError(
            f"M35/M36/M37 read-only artifact mismatch: {historical_mismatches}"
        )
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
    activities: dict[float, str] = {}
    for item in config["data"]["open_voltage_curves"]:
        path = _resolve(item["path"])
        normalized = path.name.casefold().replace("_", "").replace(" ", "")
        if "13v" in normalized:
            raise PermissionError("M37R attempted sealed 13 V numeric access.")
        voltage = float(item["voltage_V"])
        if compute_sha256(path) != expected_hashes[voltage]:
            raise RuntimeError(f"Open {voltage:g} V curve changed after lock.")
        observations[voltage] = preprocess_experiment(
            path,
            voltage_V=voltage,
            current_sense_ohm=float(config["data"]["current_sense_ohm"]),
        )
        regimes[voltage] = str(item["regime"])
        activities[voltage] = str(item["expected_activity_class"])
    if sorted(observations) != [9.0, 11.0, 15.0, 17.0]:
        raise RuntimeError("M37R open observations are not exactly 9/11/15/17 V.")
    return observations, regimes, activities


def _decision_route(result: Mapping[str, Any]) -> str:
    if result["m37r_all_gates_pass"]:
        return "D_all_gates_pass_qualified_local_observability"
    if result["status"] == "stopped_at_nominal_post_transient_event_gate":
        return "A_nominal_window_contract_still_not_closed"
    gates = result["gate_results"]
    numerical_keys = (
        "all_states_finite",
        "all_activity_classes_exact",
        "all_post_transient_event_topologies_compatible",
        "two_finest_white_jacobian_stability",
        "two_finest_retained_left_subspace_stability",
        "dop853_radau_column_direction_consistency",
        "dop853_radau_retained_singular_value_consistency",
        "dop853_radau_rank_consistency",
    )
    if not all(bool(gates.get(key, False)) for key in numerical_keys):
        return "B_local_continuous_jacobian_geometry_not_numerically_reliable"
    return "C_stable_geometry_without_required_rank_condition_or_complementarity"


def _make_figure(
    path: Path, rows: Sequence[Mapping[str, Any]], summary: Mapping[str, Any]
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    figure, axes = plt.subplots(1, 2, figsize=(10.5, 4.2))
    groups = ("static_only", "oscillatory_only", "joint")
    colors = {"static_only": "#3B82F6", "oscillatory_only": "#EF4444", "joint": "#111827"}
    fine = 0.0025
    for group in groups:
        values = [
            float(row["singular_value"])
            for row in rows
            if row.get("method") == "DOP853"
            and row.get("coordinate_system") == "raw_log_C_th_log_S_e"
            and row.get("observation_group") == group
            and float(row.get("relative_step", -1.0)) == fine
        ]
        if values:
            axes[0].plot(
                np.arange(1, len(values) + 1),
                values,
                marker="o",
                label=group,
                color=colors[group],
            )
    if axes[0].lines:
        axes[0].set_yscale("log")
        axes[0].legend(frameon=False)
    else:
        axes[0].text(0.5, 0.5, "SVD not reached", ha="center", va="center")
    axes[0].set_xlabel("Singular index")
    axes[0].set_ylabel("Whitened singular value")
    axes[0].set_title("M37R cross-regime spectra")
    axes[0].grid(alpha=0.25)

    for group in groups:
        record = summary.get("groups", {}).get(group)
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
    axes[1].set_title(f"Top directions; static/osc={angle_text}")
    axes[1].grid(alpha=0.25)
    figure.tight_layout()
    figure.savefig(path, dpi=180)
    plt.close(figure)


def _format_value(value: Any, digits: int = 6) -> str:
    if value is None:
        return "not reached"
    if isinstance(value, (list, tuple)):
        return ", ".join(_format_value(item, digits) for item in value)
    if isinstance(value, float):
        return f"{value:.{digits}g}"
    return str(value)


def _write_report(
    path: Path, summary: Mapping[str, Any], config: Mapping[str, Any]
) -> None:
    lines = [
        "# M37R repaired continuous-event observability results",
        "",
        "## Outcome",
        "",
        f"- Status: `{summary['status']}`.",
        f"- Claim status: `{summary['claim_status']}`.",
        f"- Decision route: `{summary['decision_route']}`.",
        f"- Forward evaluations: `{summary['forward_evaluations']}`.",
        f"- Cache hits: `{summary['cache_hits']}`.",
        f"- Solver wall time: `{summary['elapsed_seconds']:.3f} s`.",
        "- GPU use: `0`; fit, optimization, bootstrap, PINN training, M38, and 13 V access: `not executed`.",
        "",
        "M37R is solver-generated local continuous-model observability evidence at",
        "the declared published-source parameter anchor. It is not a public-data fit,",
        "parameter recovery result, trained-PINN result, or experimental validation.",
        "",
        "## Repaired event-window contract",
        "",
        "All M36 reference rows, nominal runs, perturbations, and both solvers use",
        "the exact interval $[t_0+0.1(T-t_0),T]$. Both endpoints are inclusive and",
        "no floating tolerance is applied. Full-horizon counts are diagnostics only;",
        "post-transient counts and signatures alone vote on reproduction/topology.",
        "",
        "| Voltage | DOP853 full | DOP853 post | Radau full | Radau post | M36 post | Nominal gate |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for voltage in (9.0, 11.0, 15.0, 17.0):
        key = f"{voltage:g}"
        dop = summary.get("nominal_checks", {}).get("DOP853", {}).get(key, {})
        rad = summary.get("nominal_checks", {}).get("Radau", {}).get(key, {})
        nominal_pass = bool(
            dop.get("m36_post_transient_event_count_reproduced", False)
            and rad.get("m36_post_transient_event_count_reproduced", False)
            and dop.get("radau_post_transient_signature_exact", False)
        )
        lines.append(
            f"| {voltage:g} | {_format_value(dop.get('full_horizon_event_count'))} | "
            f"{_format_value(dop.get('post_transient_event_count'))} | "
            f"{_format_value(rad.get('full_horizon_event_count'))} | "
            f"{_format_value(rad.get('post_transient_event_count'))} | "
            f"{_format_value(dop.get('expected_m36_post_transient_event_count'))} | "
            f"{'pass' if nominal_pass else 'fail'} |"
        )
    lines.extend(
        [
            "",
            "## Jacobian and SVD geometry",
            "",
            "| Group | Rank | Singular values | Effective rank | Condition | Jacobian change | Left angle |",
            "| --- | ---: | --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for group in ("static_only", "oscillatory_only", "joint"):
        record = summary.get("groups", {}).get(group)
        if not record:
            lines.append(
                f"| {group} | not reached | not reached | not reached | not reached | not reached | not reached |"
            )
        else:
            lines.append(
                f"| {group} | {record['threshold_rank']} | "
                f"{_format_value(record['singular_values'])} | "
                f"{_format_value(record['effective_rank'])} | "
                f"{_format_value(record['retained_condition_number'])} | "
                f"{_format_value(record['two_finest_white_jacobian_relative_change'])} | "
                f"{_format_value(record['two_finest_retained_left_subspace_angle_deg'])} |"
            )
    lines.extend(
        [
            "",
            f"Static/oscillatory acute top-direction angle: `{_format_value(summary.get('static_oscillatory_top_direction_angle_deg'))}` degrees.",
            "The complete whitened Jacobians for every registered step and solver are",
            "stored in the machine JSON; singular spectra are stored in CSV.",
            "",
            "## Independent-solver crosscheck",
            "",
            "| Group | Min column cosine | DOP853 rank | Radau rank | Retained singular difference | Gate |",
            "| --- | ---: | ---: | ---: | ---: | --- |",
        ]
    )
    for group in ("static_only", "oscillatory_only", "joint"):
        record = summary.get("dop853_radau_crosscheck", {}).get(group)
        if not record:
            lines.append(f"| {group} | not reached | not reached | not reached | not reached | not reached |")
        else:
            lines.append(
                f"| {group} | {_format_value(record['minimum_column_direction_cosine'])} | "
                f"{record['dop853_rank']} | {record['radau_rank']} | "
                f"{_format_value(record['retained_singular_value_relative_difference'])} | "
                f"{'pass' if record['all_crosscheck_gates_pass'] else 'fail'} |"
            )
    lines.extend(["", "## Preregistered gate vote", "", "| Gate | Pass |", "| --- | --- |"])
    for name, passed in summary["gate_results"].items():
        lines.append(f"| `{name}` | `{str(bool(passed)).lower()}` |")
    lines.extend(["", "## Claim and manuscript routing", ""])
    if summary["m37r_all_gates_pass"]:
        lines.extend(
            [
                "Allowed wording (and no stronger wording):",
                "",
                f"> {config['claim_boundary']['allowed_if_all_gates_pass']}",
                "",
                "This is `qualified_supported` local source-anchor continuous-model",
                "evidence. It only makes a separately preregistered M38 robustness",
                "audit eligible for human review; M38 was not executed or auto-authorized.",
            ]
        )
    else:
        lines.extend(
            [
                "The positive local complementarity claim is `failed_but_informative`.",
                "The route returns to `Q2_MANUSCRIPT_EVIDENCE_COMPRESSION`; no rescue",
                "step, smoothing, saltation variant, extra feature, extra step, or fit is allowed.",
            ]
        )
    lines.extend(
        [
            "",
            "The analytic quotient transform is reversible and is reported only as an",
            "audit; it does not create rank or constitute a novelty claim.",
            "",
            "Forbidden wording remains: public fit, unique recovery, experimental or",
            "independent external validation, gamma_sub/S_e equivalence, trained-PINN",
            "success, 13 V evaluation, world-first, or standalone SVD/Fisher/event novelty.",
            "",
            "## Validation",
            "",
            "Focused preregistration and result tests run before the final one-time full",
            "suite. Exact final counts are recorded in the execution handoff and compact",
            "project state after that suite; no scientific solve is repeated.",
            "",
            f"Base SHA: `{config['base_snapshot']}`. Formal-run SHA: `{summary['git_commit']}`.",
            "The final evidence commit is supplied in the execution handoff because it",
            "cannot self-reference its own commit.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def run(config_path: Path) -> dict[str, Any]:
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    prereg = _verify_preregistration(config)
    result_paths = [
        _resolve(config["outputs"][key])
        for key in (
            "jacobian_summary",
            "jacobian_spectra",
            "event_window_audit",
            "figure",
            "report",
        )
    ]
    if any(path.exists() for path in result_paths):
        raise FileExistsError("M37R refuses to overwrite any formal result artifact.")
    started_at = datetime.now(timezone.utc).isoformat()
    observations, regimes, expected_activity = _load_observations(config, prereg)
    m36_config = yaml.safe_load(
        _resolve(config["historical_inputs"]["m36_config"]).read_text(
            encoding="utf-8"
        )
    )
    m36_summary = json.loads(
        _resolve(config["historical_inputs"]["m36_summary"]).read_text(
            encoding="utf-8"
        )
    )
    with _resolve(config["historical_inputs"]["m36_event_times"]).open(
        encoding="utf-8", newline=""
    ) as handle:
        m36_event_rows = list(csv.DictReader(handle))
    source_config = yaml.safe_load(
        _resolve(config["historical_inputs"]["source_parameter_config"]).read_text(
            encoding="utf-8"
        )
    )
    expected_counts = {
        voltage: int(
            m36_summary["voltage_results"][f"{voltage:g}"][
                "reference_parity_metrics"
            ]["reference_reversal_event_count"]
        )
        for voltage in (9.0, 11.0, 15.0, 17.0)
    }
    m36_window_audit = build_m36_reference_window_audit(
        m36_event_rows,
        observations,
        expected_counts,
        transient_fraction=float(config["event_window"]["transient_fraction"]),
    )
    if m36_window_audit != prereg["m36_reference_window_audit"]:
        raise RuntimeError("M36 reference-window audit changed after preregistration.")
    base = VO2ThermalNeuristorParameters.from_config(source_config)
    spectra_rows, event_rows, result = run_cross_regime_observability_repair(
        base,
        observations,
        regimes,
        expected_activity,
        config,
        m36_config,
        prereg["locked_whitening"],
        expected_counts,
        m36_window_audit,
    )
    result.update(
        {
            "started_at_utc": started_at,
            "ended_at_utc": datetime.now(timezone.utc).isoformat(),
            "git_commit": _git("rev-parse", "HEAD"),
            "git_dirty_at_formal_start": False,
            "formal_execution_attempt": 1,
            "machine_summary": {
                "device": "cpu",
                "python": platform.python_version(),
                "platform": platform.platform(),
                "numpy": np.__version__,
                "scipy": scipy.__version__,
            },
            "decision_route": _decision_route(result),
            "m35_or_m36_full_workflow_rerun": False,
            "m35_m36_m37_artifacts_modified": False,
            "original_m37_status_preserved": prereg[
                "original_m37_result_status"
            ],
            "evidence_type": "solver_generated_local_continuous_model_observability",
            "public_data_fit_evidence": False,
            "trained_pinn_evidence": False,
            "experimental_validation_evidence": False,
        }
    )
    validation = validate_evidence_contract(result)
    result["schema_validation"] = validation
    if not validation["all_pass"]:
        raise RuntimeError(f"M37R result schema contract failed: {validation}")
    _write_csv(_resolve(config["outputs"]["jacobian_spectra"]), spectra_rows)
    _write_csv(_resolve(config["outputs"]["event_window_audit"]), event_rows)
    _write_json(_resolve(config["outputs"]["jacobian_summary"]), result)
    _make_figure(_resolve(config["outputs"]["figure"]), spectra_rows, result)
    _write_report(_resolve(config["outputs"]["report"]), result, config)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/m37r_continuous_event_observability_repair.yaml"),
    )
    args = parser.parse_args()
    result = run(_resolve(args.config))
    print(
        json.dumps(
            {
                "status": result["status"],
                "claim_status": result["claim_status"],
                "decision_route": result["decision_route"],
                "m37r_all_gates_pass": result["m37r_all_gates_pass"],
                "forward_evaluations": result["forward_evaluations"],
                "cache_hits": result["cache_hits"],
                "elapsed_seconds": result["elapsed_seconds"],
                "sealed_13v_access": result["sealed_13v_access"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
