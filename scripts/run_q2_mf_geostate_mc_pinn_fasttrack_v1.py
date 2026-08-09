"""Execute the authorized GeoState model-form, dataset, and PINN fast track."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Mapping, Sequence

for _name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ.setdefault(_name, "1")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from pinnpcm.experiments.geostate_fasttrack import (
    EVIDENCE_TYPE,
    GeoStateReferenceResult,
    build_reference_context,
    load_yaml,
    model_form_case_from_config,
    pilot_cases_from_config,
    reference_case_passes,
    select_reference_model,
    solve_reference_case,
)
from pinnpcm.experiments.geostate_training import (
    TrainingOutcome,
    aggregate_metrics,
    evaluate_case,
    train_model,
)


DEFAULT_CONFIG = Path("configs/q2_mf_geostate_mc_pinn_fasttrack_v1.yaml")


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _git_head(root: Path) -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _paths(root: Path, config: Mapping[str, Any]) -> tuple[Path, Path, Path, Path]:
    outputs = config["outputs"]
    processed = root / outputs["processed_root"]
    tables = root / outputs["table_root"]
    figures = root / outputs["figure_root"]
    report = root / outputs["report"]
    for directory in (processed, tables, figures, report.parent):
        directory.mkdir(parents=True, exist_ok=True)
    return processed, tables, figures, report


def _json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    if isinstance(value, np.bool_):
        return bool(value)
    return value


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_text(
        json.dumps(_json_ready(dict(payload)), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _save_reference_npz(path: Path, result: GeoStateReferenceResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    arrays = {name: np.asarray(value) for name, value in result.fields.items()}
    arrays.update(
        {
            "case_id": np.asarray(result.case.case_id),
            "model_form": np.asarray(result.model_form),
            "branch_label": np.asarray(result.case.branch_label),
            "device_voltage_V": np.asarray(result.case.device_voltage_V),
            "sink_amplitude": np.asarray(result.case.sink_amplitude),
            "evidence_type": np.asarray(EVIDENCE_TYPE),
        }
    )
    np.savez_compressed(path, **arrays)


def _extent_nm(result: GeoStateReferenceResult) -> list[float]:
    return [
        float(result.grid.x_edges_m[0] * 1.0e9),
        float(result.grid.x_edges_m[-1] * 1.0e9),
        float(result.grid.y_edges_m[0] * 1.0e9),
        float(result.grid.y_edges_m[-1] * 1.0e9),
    ]


def _field_image(
    axis: plt.Axes,
    field: np.ndarray,
    result: GeoStateReferenceResult,
    title: str,
    *,
    cmap: str = "viridis",
) -> None:
    image = axis.imshow(
        np.asarray(field),
        origin="lower",
        aspect="auto",
        extent=_extent_nm(result),
        cmap=cmap,
    )
    axis.set_title(title, fontsize=9)
    axis.set_xlabel("x (nm)")
    axis.set_ylabel("y (nm)")
    plt.colorbar(image, ax=axis, fraction=0.046, pad=0.04)


def _plot_model_case_fields(
    results: Mapping[tuple[str, str], GeoStateReferenceResult],
    case_id: str,
    path: Path,
) -> None:
    figure, axes = plt.subplots(3, 4, figsize=(14, 9), constrained_layout=True)
    for row, model in enumerate(("M0", "M1", "M2")):
        result = results[(model, case_id)]
        fields = result.fields
        items = (
            (fields["temperature_K"], "T (K)"),
            (fields["potential_V"], "phi (V)"),
            (fields["J_magnitude_A_m"], "|J| (A/m)"),
            (fields["joule_heat_W_m2"], "Joule (W/m2)"),
        )
        for column, (field, label) in enumerate(items):
            _field_image(axes[row, column], field, result, f"{model}: {label}")
    figure.suptitle(f"Model-form case {case_id}")
    figure.savefig(path, dpi=170)
    plt.close(figure)


def _plot_model_spread(
    results: Mapping[tuple[str, str], GeoStateReferenceResult], path: Path
) -> None:
    figure, axes = plt.subplots(2, 3, figsize=(13, 7), constrained_layout=True)
    for row, case_id in enumerate(("C0", "C1")):
        case_results = [results[(model, case_id)] for model in ("M0", "M1", "M2")]
        temperatures = np.stack([item.fields["temperature_K"] for item in case_results])
        currents = np.stack([item.fields["J_magnitude_A_m"] for item in case_results])
        reference = case_results[-1]
        _field_image(
            axes[row, 0],
            np.max(temperatures, axis=0) - np.min(temperatures, axis=0),
            reference,
            f"{case_id}: T spread (K)",
            cmap="magma",
        )
        relative_j = (np.max(currents, axis=0) - np.min(currents, axis=0)) / np.maximum(
            np.max(currents, axis=0), 1.0e-30
        )
        _field_image(
            axes[row, 1], relative_j, reference, f"{case_id}: |J| relative spread", cmap="magma"
        )
        labels = ["M0", "M1", "M2"]
        tmax = [float(item.metrics["Tmax_K"]) for item in case_results]
        current_mA = [1.0e3 * abs(float(item.metrics["source_current_A"])) for item in case_results]
        x = np.arange(3)
        axes[row, 2].bar(x - 0.18, np.asarray(tmax) - 325.0, 0.36, label="Tmax-325 K")
        axes[row, 2].bar(x + 0.18, current_mA, 0.36, label="current mA")
        axes[row, 2].set_xticks(x, labels)
        axes[row, 2].set_title(f"{case_id}: key QoI")
        axes[row, 2].legend(fontsize=8)
    figure.suptitle("M0/M1/M2 model-form spread")
    figure.savefig(path, dpi=180)
    plt.close(figure)


def _stage_model_form(
    context,
    config: Mapping[str, Any],
    tables: Path,
    figures: Path,
) -> tuple[
    str | None,
    dict[tuple[str, str], GeoStateReferenceResult],
    list[dict[str, Any]],
    dict[str, dict[str, float | bool]],
]:
    results: dict[tuple[str, str], GeoStateReferenceResult] = {}
    for model in ("M0", "M1", "M2"):
        for case_id in ("C0", "C1"):
            case = model_form_case_from_config(config, case_id)
            results[(model, case_id)] = solve_reference_case(context, model, case)
    selected, selection_audit = select_reference_model(results, config)
    gates = config["reference_solver"]["sanity_gates"]
    rows: list[dict[str, Any]] = []
    for model in ("M0", "M1", "M2"):
        for case_id in ("C0", "C1"):
            result = results[(model, case_id)]
            row = {
                "model_form": model,
                "case_id": case_id,
                **dict(result.metrics),
                "ledger_gates_pass": reference_case_passes(result, config),
                "two_dimensional_gate_pass": bool(
                    case_id != "C1"
                    or float(result.metrics["chi_2d"]) >= float(gates["chi_2d_min"])
                    or float(result.metrics["hotspot_lateral_shift_width_fraction"])
                    >= float(gates["hotspot_lateral_shift_width_fraction_min"])
                ),
                **selection_audit[model],
                "selected_reference": model == selected,
            }
            rows.append(row)
    pd.DataFrame(rows).to_csv(tables / "model_form_metrics.csv", index=False)
    _plot_model_case_fields(results, "C0", figures / "model_form_C0_fields.png")
    _plot_model_case_fields(results, "C1", figures / "model_form_C1_fields.png")
    _plot_model_spread(results, figures / "model_form_spread.png")
    return selected, results, rows, selection_audit


def _reuse_model_form_after_metric_repair(
    context,
    config: Mapping[str, Any],
    root: Path,
    tables: Path,
    figures: Path,
) -> tuple[str | None, list[dict[str, Any]], dict[str, dict[str, float | bool]]]:
    repair = config["implementation_repair"]
    source_tables = root / repair["reuse_model_form_table_root"]
    source_figures = root / repair["reuse_model_form_figure_root"]
    frame = pd.read_csv(source_tables / "model_form_metrics.csv")
    rows = frame.to_dict(orient="records")
    by_key = {
        (str(row["model_form"]), str(row["case_id"])): row for row in rows
    }
    thresholds = config["reference_solver"]["model_selection"]
    chi_gate = float(config["reference_solver"]["sanity_gates"]["chi_2d_min"])
    selection_audit: dict[str, dict[str, float | bool]] = {}
    selected: str | None = None
    for model in ("M0", "M1", "M2"):
        maximum_current = 0.0
        maximum_temperature = 0.0
        maximum_hotspot = 0.0
        ledgers_pass = True
        for case_id in ("C0", "C1"):
            candidate = by_key[(model, case_id)]
            target = by_key[("M2", case_id)]
            ledgers_pass = ledgers_pass and bool(candidate["ledger_gates_pass"])
            current_a = abs(float(candidate["source_current_A"]))
            current_b = abs(float(target["source_current_A"]))
            maximum_current = max(
                maximum_current,
                abs(current_a - current_b) / max(0.5 * (current_a + current_b), 1.0e-30),
            )
            maximum_temperature = max(
                maximum_temperature,
                abs(float(candidate["Tmax_K"]) - float(target["Tmax_K"])),
            )
            if (
                float(candidate["chi_2d"]) >= chi_gate
                or float(target["chi_2d"]) >= chi_gate
            ):
                distance = np.hypot(
                    float(candidate["hotspot_x_m"]) - float(target["hotspot_x_m"]),
                    float(candidate["hotspot_y_m"]) - float(target["hotspot_y_m"]),
                ) / context.width_m
                maximum_hotspot = max(maximum_hotspot, float(distance))
        sufficient = bool(
            ledgers_pass
            and maximum_current
            <= float(thresholds["terminal_current_relative_difference_max"])
            and maximum_temperature
            <= float(thresholds["Tmax_absolute_difference_K_max"])
            and maximum_hotspot
            <= float(thresholds["hotspot_distance_width_fraction_max"])
        )
        selection_audit[model] = {
            "ledger_gates_pass": ledgers_pass,
            "max_current_relative_difference_vs_M2": maximum_current,
            "max_Tmax_difference_K_vs_M2": maximum_temperature,
            "max_hotspot_distance_width_fraction_vs_M2": maximum_hotspot,
            "sufficient": sufficient,
        }
        if selected is None and sufficient:
            selected = model
    repaired_rows: list[dict[str, Any]] = []
    for row in rows:
        model = str(row["model_form"])
        repaired_rows.append(
            {
                **row,
                **selection_audit[model],
                "selected_reference": model == selected,
                "selection_metric_repair": "width_W_and_resolved_hotspot_only",
            }
        )
    pd.DataFrame(repaired_rows).to_csv(tables / "model_form_metrics.csv", index=False)
    for filename in (
        "model_form_spread.png",
        "model_form_C0_fields.png",
        "model_form_C1_fields.png",
    ):
        shutil.copy2(source_figures / filename, figures / filename)
    _write_json(
        source_tables / "attempt1_invalid_disposition.json",
        {
            "run_id": repair["attempt1_run_id"],
            "validity": "invalid",
            "claim_status": "forbidden",
            "disposition": repair["attempt1_disposition"],
            "failure_class": repair["classification"],
            "defect": repair["defect"],
            "historical_result_impact": "six physical solves retained; M2 selection and all downstream attempt1 data/training are non-voting",
        },
    )
    return selected, repaired_rows, selection_audit


def _split_for_case(case_id: str, config: Mapping[str, Any]) -> str:
    split = config["pilot_dataset"]["split"]
    if case_id in split["validation"]:
        return "validation"
    if case_id in split["test"]:
        return "test"
    return "train"


def _plot_pilot_fields(result: GeoStateReferenceResult, path: Path) -> None:
    figure, axes = plt.subplots(1, 5, figsize=(17, 3.5), constrained_layout=True)
    items = (
        (result.fields["potential_V"], "phi (V)"),
        (result.fields["temperature_K"], "T (K)"),
        (result.fields["J_magnitude_A_m"], "|J| (A/m)"),
        (result.fields["q_magnitude_W_m"], "|q| (W/m)"),
        (result.fields["joule_heat_W_m2"], "Joule (W/m2)"),
    )
    for axis, (field, title) in zip(axes, items, strict=True):
        _field_image(axis, field, result, title)
    figure.suptitle(f"Selected reference: {result.case.case_id}")
    figure.savefig(path, dpi=180)
    plt.close(figure)


def _generate_pilot(
    selected_model: str,
    base_context,
    config: Mapping[str, Any],
    root: Path,
    processed: Path,
    tables: Path,
    figures: Path,
) -> tuple[list[GeoStateReferenceResult], list[dict[str, Any]], list[dict[str, Any]], bool]:
    cases = pilot_cases_from_config(config)
    sentinels = set(config["pilot_dataset"]["sentinel_cases"])
    refined_context = None
    results: list[GeoStateReferenceResult] = []
    manifest: list[dict[str, Any]] = []
    ledgers: list[dict[str, Any]] = []
    all_valid = True
    for case in cases:
        result = solve_reference_case(base_context, selected_model, case)
        results.append(result)
        npz_path = processed / "cases" / f"{case.case_id}.npz"
        _save_reference_npz(npz_path, result)
        split = _split_for_case(case.case_id, config)
        anchor_count = (
            max(
                int(config["pilot_dataset"]["minimum_anchor_points_per_train_case"]),
                int(round(float(config["pilot_dataset"]["anchor_fraction"]) * result.grid.nx * result.grid.ny)),
            )
            if split == "train"
            else 0
        )
        valid = reference_case_passes(result, config)
        all_valid = all_valid and valid
        refined_path = ""
        refined_current_difference = np.nan
        refined_Tmax_difference_K = np.nan
        if case.case_id in sentinels:
            if refined_context is None:
                refined_context = build_reference_context(
                    dict(config), root, refinement=int(config["reference_solver"]["sentinel_refinement_factor"])
                )
            refined = solve_reference_case(refined_context, selected_model, case)
            refined_file = processed / "sentinel_refinement" / f"{case.case_id}_r2.npz"
            _save_reference_npz(refined_file, refined)
            refined_path = refined_file.relative_to(root).as_posix()
            refined_current_difference = abs(
                float(result.metrics["source_current_A"]) - float(refined.metrics["source_current_A"])
            ) / max(abs(float(refined.metrics["source_current_A"])), 1.0e-30)
            refined_Tmax_difference_K = abs(
                float(result.metrics["Tmax_K"]) - float(refined.metrics["Tmax_K"])
            )
            all_valid = all_valid and reference_case_passes(refined, config)
        manifest.append(
            {
                "case_id": case.case_id,
                "branch_label": case.branch_label,
                "branch_value": case.branch_value,
                "voltage_level": case.case_id.split("_")[1],
                "device_voltage_V": case.device_voltage_V,
                "state_coordinate": case.state_coordinate,
                "thermal_condition": case.thermal_condition,
                "sink_amplitude": case.sink_amplitude,
                "split": split,
                "full_field_npz": npz_path.relative_to(root).as_posix(),
                "anchor_fraction": float(config["pilot_dataset"]["anchor_fraction"]),
                "exposed_anchor_points": anchor_count,
                "reference_valid": valid,
                "sentinel_refinement_npz": refined_path,
                "sentinel_current_relative_difference": refined_current_difference,
                "sentinel_Tmax_difference_K": refined_Tmax_difference_K,
                "evidence_type": EVIDENCE_TYPE,
            }
        )
        ledgers.append(
            {
                "case_id": case.case_id,
                "source_current_A": result.metrics["source_current_A"],
                "ground_current_A": result.metrics["ground_current_A"],
                "terminal_power_W": result.metrics["terminal_power_W"],
                "field_joule_power_W": result.metrics["field_joule_power_W"],
                "sink_power_W": result.metrics["sink_power_W"],
                "terminal_current_imbalance": result.metrics["terminal_current_imbalance"],
                "terminal_field_joule_error": result.metrics["terminal_field_joule_error"],
                "joule_sink_ledger_error": result.metrics["joule_sink_ledger_error"],
                "scaled_nonlinear_residual": result.metrics["scaled_nonlinear_residual"],
            }
        )
    pd.DataFrame(manifest).to_csv(tables / "pilot_case_manifest.csv", index=False)
    pd.DataFrame(ledgers).to_csv(tables / "pilot_port_ledgers.csv", index=False)
    representative = next(
        result for result in results if result.case.case_id == "heating_near-transition_localized-sink"
    )
    _plot_pilot_fields(representative, figures / "pilot_reference_fields.png")
    return results, manifest, ledgers, all_valid


def _plot_training_history(history: pd.DataFrame, path: Path) -> None:
    models = list(dict.fromkeys(history["model"].tolist()))
    figure, axes = plt.subplots(1, len(models), figsize=(6 * len(models), 4), constrained_layout=True)
    if len(models) == 1:
        axes = [axes]
    groups = (
        "anchor_loss",
        "constitutive_loss",
        "conservation_loss",
        "interface_loss",
        "port_loss",
        "ledger_loss",
        "total_loss",
    )
    for axis, model in zip(axes, models, strict=True):
        frame = history[history["model"] == model]
        for group in groups:
            values = np.maximum(frame[group].to_numpy(dtype=float), 1.0e-14)
            axis.semilogy(frame["step"], values, label=group.replace("_loss", ""))
        axis.set_title(model)
        axis.set_xlabel("Adam step")
        axis.set_ylabel("nondimensional loss")
        axis.legend(fontsize=7, ncol=2)
    figure.suptitle("Fixed loss-group trajectories")
    figure.savefig(path, dpi=180)
    plt.close(figure)


def _plot_field_comparison(
    reference: GeoStateReferenceResult,
    predictions: Mapping[str, Mapping[str, np.ndarray]],
    path: Path,
) -> None:
    rows = ["FVM", *predictions.keys()]
    figure, axes = plt.subplots(len(rows), 4, figsize=(14, 3.1 * len(rows)), constrained_layout=True)
    target_T = np.asarray(reference.fields["temperature_K"])
    target_phi = np.asarray(reference.fields["potential_V"])
    for row_index, name in enumerate(rows):
        if name == "FVM":
            T = target_T
            phi = target_phi
        else:
            T = np.asarray(predictions[name]["T_K"])
            phi = np.asarray(predictions[name]["phi_V"])
        items = (
            (T, f"{name}: T (K)", "viridis"),
            (np.abs(T - target_T), f"{name}: |T error| (K)", "magma"),
            (phi, f"{name}: phi (V)", "viridis"),
            (np.abs(phi - target_phi), f"{name}: |phi error| (V)", "magma"),
        )
        for column, (field, title, cmap) in enumerate(items):
            _field_image(axes[row_index, column], field, reference, title, cmap=cmap)
    figure.suptitle(f"FVM and sparse-anchor model fields: {reference.case.case_id}")
    figure.savefig(path, dpi=180)
    plt.close(figure)


def _plot_ledgers(test_frame: pd.DataFrame, path: Path) -> None:
    models = list(dict.fromkeys(test_frame["model"].tolist()))
    cases = list(dict.fromkeys(test_frame["case_id"].tolist()))
    figure, axes = plt.subplots(1, 2, figsize=(12, 4), constrained_layout=True)
    x = np.arange(len(cases))
    width = 0.8 / len(models)
    for index, model in enumerate(models):
        frame = test_frame[test_frame["model"] == model].set_index("case_id").loc[cases]
        offset = (index - 0.5 * (len(models) - 1)) * width
        axes[0].bar(x + offset, frame["terminal_current_error"], width, label=model)
        axes[1].bar(x + offset, frame["energy_ledger_error"], width, label=model)
    axes[0].set_title("Terminal-current relative error")
    axes[1].set_title("Port-field-sink ledger error")
    for axis in axes:
        axis.set_xticks(x, cases, rotation=20, ha="right")
        axis.set_yscale("log")
        axis.legend()
        axis.grid(axis="y", alpha=0.25)
    figure.savefig(path, dpi=180)
    plt.close(figure)


def _screen_disposition(
    aggregate: Mapping[str, Mapping[str, Any]],
    candidate: str,
    config: Mapping[str, Any],
) -> dict[str, Any]:
    gates = config["engineering_screen"]
    b0 = aggregate["B0"]
    method = aggregate[candidate]
    field_improvement = (
        float(b0["mean_field_score"]) - float(method["mean_field_score"])
    ) / max(float(b0["mean_field_score"]), 1.0e-30)
    b0_conservation = max(
        float(b0["mean_energy_ledger_error"]),
        float(b0["mean_interface_flux_mismatch"]),
    )
    method_conservation = max(
        float(method["mean_energy_ledger_error"]),
        float(method["mean_interface_flux_mismatch"]),
    )
    conservation_factor = b0_conservation / max(method_conservation, 1.0e-30)
    catastrophic_factor = float(gates["catastrophic_field_regression_factor"])
    no_catastrophic_regression = bool(
        (
            float(method["mean_temperature_relative_l2"])
            <= catastrophic_factor * float(b0["mean_temperature_relative_l2"])
            or float(method["mean_temperature_relative_l2"])
            <= float(gates["temperature_field_relative_l2_max"])
        )
        and (
            float(method["mean_potential_relative_l2"])
            <= catastrophic_factor * float(b0["mean_potential_relative_l2"])
            or float(method["mean_potential_relative_l2"])
            <= float(gates["potential_field_relative_l2_max"])
        )
    )
    engineering_pass = bool(
        method["all_finite"]
        and int(method["passing_complete_cases"])
        >= int(gates["required_passing_complete_test_cases"])
    )
    idea_go = bool(
        engineering_pass
        and no_catastrophic_regression
        and (
            field_improvement >= float(gates["field_improvement_over_B0_min"])
            or conservation_factor
            >= float(gates["conservation_improvement_factor_over_B0_min"])
        )
    )
    if idea_go:
        disposition = "GO_GEOSTATE_PINN_IDEA_SCREEN"
    elif (
        float(method["mean_energy_ledger_error"])
        <= float(gates["energy_ledger_relative_error_max"])
        and field_improvement < float(gates["field_improvement_over_B0_min"])
    ):
        disposition = "DOWNGRADE_PHYSICS_CONSISTENT_SURROGATE"
    elif (
        float(b0["mean_field_score"]) <= float(gates["temperature_field_relative_l2_max"])
        and int(method["passing_complete_cases"]) == 0
    ):
        disposition = "NO_GO_GEOSTATE_PINN_IDEA_SCREEN_PHYSICS_OPTIMIZATION_FAILURE"
    else:
        disposition = "NO_GO_GEOSTATE_PINN_IDEA_SCREEN"
    return {
        "candidate_model": candidate,
        "engineering_gate_pass": engineering_pass,
        "field_improvement_over_B0": field_improvement,
        "conservation_improvement_factor_over_B0": conservation_factor,
        "no_catastrophic_field_regression": no_catastrophic_regression,
        "idea_level_go": idea_go,
        "disposition": disposition,
    }


def _write_report(path: Path, summary: Mapping[str, Any]) -> None:
    model_rows = summary["model_form"]["key_rows"]
    c0 = [row for row in model_rows if row["case_id"] == "C0"]
    c1 = [row for row in model_rows if row["case_id"] == "C1"]
    training = summary.get("training", {})
    lines = [
        "# Q2 MF GeoState MC-PINN Fast-Track V1",
        "",
        "## Actual execution",
        "",
        f"Executed the six fixed M0/M1/M2 x C0/C1 reference runs, selected `{summary['selected_reference_model']}`, generated twelve complete-case fields with two one-level sentinel refinements, and trained the recorded sparse-anchor baselines/PINN models at seed `20260809`. Evidence type: `{EVIDENCE_TYPE}`.",
    ]
    if "implementation_repair" in summary:
        lines.extend(
            [
                "",
                f"The first downstream attempt is immutable `invalid/{summary['implementation_repair']['attempt1_disposition']}` because the hotspot distance used device length rather than width and allowed a uniform-field argmax to vote. The six physical MVE solves were reused; Stage B was not rerun.",
            ]
        )
    lines.extend(
        [
            "",
            "## Six-run MVE",
            "",
            "| Case | Model | residual | current imbalance | port-field | field-sink | Tmax K | chi_2d |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in [*c0, *c1]:
        lines.append(
            f"| {row['case_id']} | {row['model_form']} | {float(row['scaled_nonlinear_residual']):.3e} | {float(row['terminal_current_imbalance']):.3e} | {float(row['terminal_field_joule_error']):.3e} | {float(row['joule_sink_ledger_error']):.3e} | {float(row['Tmax_K']):.3f} | {float(row['chi_2d']):.3f} |"
        )
    lines.extend(
        [
            "",
            f"Reference conclusion: `{summary['selected_reference_model']}` is the simplest model satisfying the fixed ledger and M2-spread thresholds.",
            "",
            "## Dataset and actual training",
            "",
            "The pilot contains 12 full cases split only by complete case; training exposes 1% of each train-case field (minimum three points), while continuous collocation points are generated independently. No geometry-OOD claim is made.",
            "",
        ]
    )
    if training:
        lines.extend(
            [
                "| Model | steps | T rel L2 | phi rel L2 | current error | energy error | interface mismatch | passing test cases |",
                "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
            ]
        )
        for model, values in training["aggregate_test_metrics"].items():
            outcome = training["outcomes"][model]
            lines.append(
                f"| {model} | {outcome['completed_steps']} | {float(values['mean_temperature_relative_l2']):.4f} | {float(values['mean_potential_relative_l2']):.4f} | {float(values['mean_terminal_current_error']):.4f} | {float(values['mean_energy_ledger_error']):.4f} | {float(values['mean_interface_flux_mismatch']):.4f} | {int(values['passing_complete_cases'])} |"
            )
        screen = training["screen"]
        lines.extend(
            [
                "",
                f"Gate disposition: `{screen['disposition']}`; idea-level GO = `{str(screen['idea_level_go']).lower()}`. The sole M1 homotopy rescue was {'executed' if training['rescue_executed'] else 'not eligible and not executed'}.",
                "",
            ]
        )
    lines.extend(
        [
            "## Figures",
            "",
            *[f"- `{item}`" for item in summary["figure_paths"]],
            "",
            "## Claim boundary",
            "",
            "Allowed manuscript sentence: \"On a literature-guided synthetic Qiu-inspired 2.5D benchmark, the selected reduced reference and single-seed sparse-anchor training provide a diagnostic engineering screen for state-conditioned quasi-static electrothermal fields.\"",
            "",
            "Forbidden: formal PINN superiority, experimental validation, stable-branch recovery, inverse recovery, Qiu quantitative reproduction, or geometry OOD.",
            "",
            "## Single next priority",
            "",
            summary["next_single_priority"],
            "",
            f"Base SHA: `{summary['base_sha']}`. Final task SHA is reported in the delivery handoff after the evidence commit.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(config_path: Path) -> dict[str, Any]:
    root = _repository_root()
    resolved_config = config_path if config_path.is_absolute() else root / config_path
    config = load_yaml(resolved_config)
    processed, tables, figures, report = _paths(root, config)
    base_sha = _git_head(root)
    context = build_reference_context(config, root)
    if "implementation_repair" in config:
        selected, model_rows, selection_audit = _reuse_model_form_after_metric_repair(
            context, config, root, tables, figures
        )
    else:
        selected, _, model_rows, selection_audit = _stage_model_form(
            context, config, tables, figures
        )
    figure_paths = [
        (figures / "model_form_spread.png").relative_to(root).as_posix(),
        (figures / "model_form_C0_fields.png").relative_to(root).as_posix(),
        (figures / "model_form_C1_fields.png").relative_to(root).as_posix(),
    ]
    summary: dict[str, Any] = {
        "task_id": config["task_id"],
        "run_id": config["run_id"],
        "base_sha": base_sha,
        "lifecycle_state": "executed",
        "execution_validity": "valid",
        "claim_status": "forbidden",
        "scientific_vote": False,
        "evidence_type": EVIDENCE_TYPE,
        "selected_reference_model": selected,
        "model_form": {"selection_audit": selection_audit, "key_rows": model_rows},
        "figure_paths": figure_paths,
    }
    if "implementation_repair" in config:
        summary["implementation_repair"] = dict(config["implementation_repair"])
    if selected is None:
        summary.update(
            {
                "execution_validity": "valid",
                "claim_status": "failed_but_informative",
                "disposition": "NO_GO_MODEL_FORM_REFERENCE",
                "next_single_priority": "Stop the PINN route; do not add a fourth model form.",
            }
        )
        _write_json(tables / "summary.json", summary)
        _write_report(report, summary)
        return summary

    pilot_results, manifest, ledgers, pilot_valid = _generate_pilot(
        selected, context, config, root, processed, tables, figures
    )
    summary["pilot_dataset"] = {
        "case_count": len(pilot_results),
        "complete_case_split": True,
        "sentinel_refinement_count": len(config["pilot_dataset"]["sentinel_cases"]),
        "all_reference_cases_valid": pilot_valid,
        "manifest": (tables / "pilot_case_manifest.csv").relative_to(root).as_posix(),
        "ledger": (tables / "pilot_port_ledgers.csv").relative_to(root).as_posix(),
    }
    figure_paths.append((figures / "pilot_reference_fields.png").relative_to(root).as_posix())
    if not pilot_valid:
        summary.update(
            {
                "claim_status": "failed_but_informative",
                "disposition": "NO_GO_MODEL_FORM_REFERENCE",
                "next_single_priority": "Stop the PINN route because at least one pilot reference failed the frozen reference gates.",
            }
        )
        _write_json(tables / "summary.json", summary)
        _write_report(report, summary)
        return summary

    train_results = [
        result for result in pilot_results if _split_for_case(result.case.case_id, config) == "train"
    ]
    scored_results = [
        result
        for result in pilot_results
        if _split_for_case(result.case.case_id, config) in {"validation", "test"}
    ]
    test_results = [
        result for result in scored_results if _split_for_case(result.case.case_id, config) == "test"
    ]
    outcomes: dict[str, TrainingOutcome] = {}
    anchors: dict[str, dict[str, list[int]]] = {}
    metric_rows: list[dict[str, Any]] = []
    predictions: dict[str, dict[str, Mapping[str, np.ndarray]]] = {}
    for model_name in ("B0", "B1", "M0"):
        outcome, anchor_index = train_model(
            model_name, context, config, train_results
        )
        outcomes[model_name] = outcome
        anchors[model_name] = anchor_index
        predictions[model_name] = {}
        for result in scored_results:
            metrics, predicted = evaluate_case(outcome.model, result, config)
            metrics["split"] = _split_for_case(result.case.case_id, config)
            metric_rows.append(metrics)
            predictions[model_name][result.case.case_id] = predicted
    if not (anchors["B0"] == anchors["B1"] == anchors["M0"]):
        raise RuntimeError("matched-anchor identity was not preserved")

    m0_rows = [row for row in metric_rows if row["model"] == "M0"]
    near = [float(row["field_score"]) for row in m0_rows if "near-transition" in row["case_id"]]
    other = [float(row["field_score"]) for row in m0_rows if "near-transition" not in row["case_id"]]
    concentration = float(np.mean(near) / max(np.mean(other), 1.0e-30)) if near and other else 0.0
    rescue_config = config["pinn"]["rescue"]
    m0_finite = outcomes["M0"].finite and all(bool(row["finite"]) for row in m0_rows)
    m0_any_pass = any(
        bool(row["engineering_gate_pass"]) and row["split"] == "test" for row in m0_rows
    )
    rescue_eligible = bool(
        rescue_config["allowed_once"]
        and m0_finite
        and not m0_any_pass
        and concentration >= float(rescue_config["near_transition_concentration_ratio_min"])
    )
    if rescue_eligible:
        joule_schedule = [
            value
            for value, count in zip(
                rescue_config["joule_feedback_multipliers"],
                rescue_config["steps_per_stage"],
                strict=True,
            )
            for _ in range(int(count))
        ]
        phase_width_schedule = [
            value
            for value, count in zip(
                rescue_config["transition_width_multipliers"],
                rescue_config["steps_per_stage"],
                strict=True,
            )
            for _ in range(int(count))
        ]
        outcome, anchor_index = train_model(
            "M1",
            context,
            config,
            train_results,
            adam_steps=sum(int(value) for value in rescue_config["steps_per_stage"]),
            joule_schedule=joule_schedule,
            phase_width_schedule=phase_width_schedule,
        )
        outcomes["M1"] = outcome
        anchors["M1"] = anchor_index
        predictions["M1"] = {}
        for result in scored_results:
            metrics, predicted = evaluate_case(outcome.model, result, config)
            metrics["split"] = _split_for_case(result.case.case_id, config)
            metric_rows.append(metrics)
            predictions["M1"][result.case.case_id] = predicted

    history_rows = [row for outcome in outcomes.values() for row in outcome.history]
    history_frame = pd.DataFrame(history_rows)
    history_frame.to_csv(tables / "training_history.csv", index=False)
    metrics_frame = pd.DataFrame(metric_rows)
    metrics_frame.to_csv(tables / "test_metrics.csv", index=False)
    test_frame = metrics_frame[metrics_frame["split"] == "test"].copy()
    aggregate = {
        model: aggregate_metrics(
            test_frame[test_frame["model"] == model].to_dict(orient="records")
        )
        for model in outcomes
    }
    candidate = "M1" if rescue_eligible else "M0"
    screen = _screen_disposition(aggregate, candidate, config)
    representative = next(
        result for result in test_results if result.case.case_id == "heating_near-transition_localized-sink"
    )
    representative_predictions = {
        model: predictions[model][representative.case.case_id] for model in outcomes
    }
    _plot_field_comparison(
        representative,
        representative_predictions,
        figures / "pinn_field_comparison.png",
    )
    _plot_training_history(history_frame, figures / "training_group_losses.png")
    _plot_ledgers(test_frame, figures / "port_and_energy_ledger.png")
    figure_paths.extend(
        [
            (figures / "pinn_field_comparison.png").relative_to(root).as_posix(),
            (figures / "training_group_losses.png").relative_to(root).as_posix(),
            (figures / "port_and_energy_ledger.png").relative_to(root).as_posix(),
        ]
    )
    summary["training"] = {
        "seed": int(config["pinn"]["seed"]),
        "anchor_fraction": float(config["pilot_dataset"]["anchor_fraction"]),
        "matched_anchor_indices": True,
        "outcomes": {
            name: {
                "finite": outcome.finite,
                "completed_steps": outcome.completed_steps,
                "wall_time_s": outcome.wall_time_s,
                "parameter_count": outcome.parameter_count,
            }
            for name, outcome in outcomes.items()
        },
        "aggregate_test_metrics": aggregate,
        "near_transition_error_concentration_ratio": concentration,
        "rescue_eligible": rescue_eligible,
        "rescue_executed": "M1" in outcomes,
        "screen": screen,
    }
    summary["disposition"] = screen["disposition"]
    summary["claim_status"] = (
        "qualified_supported" if screen["idea_level_go"] else "failed_but_informative"
    )
    summary["next_single_priority"] = (
        "Execute Q2_GEOSTATE_PINN_FORMAL_OOD_V1 with 40-48 complete cases, geometry and thermal-boundary OOD, five seeds, and matched B0/B1/M0/M1 budgets."
        if screen["idea_level_go"]
        else "Stop architecture expansion and preserve this bounded screen as a physics-optimization or surrogate limitation."
    )
    _write_json(tables / "summary.json", summary)
    _write_report(report, summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    summary = run(args.config)
    print(
        json.dumps(
            {
                "task_id": summary["task_id"],
                "selected_reference_model": summary["selected_reference_model"],
                "disposition": summary.get("disposition"),
                "summary": summary["model_form"]["key_rows"][0]["evidence_type"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
