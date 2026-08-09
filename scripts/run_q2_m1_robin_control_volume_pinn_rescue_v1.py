"""Execute the single authorized M1 Robin/control-volume PINN rescue."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import torch


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from pinnpcm.experiments.geostate_fasttrack import (  # noqa: E402
    build_reference_context,
    load_yaml,
)
from pinnpcm.experiments.geostate_m1_compatibility import (  # noqa: E402
    ConservativeTeacherFields,
    M1TeacherCase,
    compatibility_passes,
    load_teacher_cases,
    reconstruct_conservative_teacher,
)
from pinnpcm.experiments.geostate_m1_rcv_training import (  # noqa: E402
    FixedCaseSamples,
    TrainingOutcome,
    aggregate_metrics,
    build_anchor_indices,
    build_fixed_samples,
    case_inputs,
    decide_disposition,
    evaluate_case,
    train_model,
)


CONFIG_PATH = ROOT / "configs/q2_m1_robin_control_volume_pinn_rescue_v1.yaml"


def _json_ready(value: Any) -> Any:
    if isinstance(value, Mapping):
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
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_json_ready(payload), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields: list[str] = []
    for row in rows:
        for name in row:
            if name not in fields:
                fields.append(name)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _save_fixed_samples(
    path: Path,
    samples: Mapping[str, FixedCaseSamples],
) -> None:
    payload: dict[str, np.ndarray] = {}
    for case_id, item in samples.items():
        prefix = case_id.replace("-", "_")
        payload[f"{prefix}__collocation_xy"] = item.collocation_xy
        payload[f"{prefix}__control_volume_bounds"] = item.control_volume_bounds
        payload[f"{prefix}__control_volume_regions"] = item.control_volume_regions
        payload[f"{prefix}__interface_y"] = item.interface_y
        payload[f"{prefix}__interface_ids"] = item.interface_ids
        payload[f"{prefix}__boundary_y"] = item.boundary_y
        payload[f"{prefix}__volume_xy"] = item.volume_xy
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, **payload)


def _plot_compatibility(
    figure_path: Path,
    case: M1TeacherCase,
    fields: ConservativeTeacherFields,
) -> None:
    figure_path.parent.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 2, figsize=(10.0, 3.8), constrained_layout=True)
    for axis, values, title in zip(
        axes,
        (fields.normalized_current_residual, fields.normalized_energy_residual),
        ("normalized local current residual", "normalized local energy residual"),
        strict=True,
    ):
        image = axis.imshow(values, origin="lower", aspect="auto", cmap="magma")
        axis.set_title(title)
        axis.set_xlabel("x cell")
        axis.set_ylabel("y cell")
        fig.colorbar(image, ax=axis, shrink=0.82)
    fig.suptitle(f"Worst teacher/objective case: {case.case_id}")
    fig.savefig(figure_path, dpi=220)
    plt.close(fig)


def _plot_boundary_profiles(
    path: Path,
    case: M1TeacherCase,
    teacher: ConservativeTeacherFields,
    outcomes: Mapping[str, TrainingOutcome],
) -> None:
    y = np.linspace(0.0, 1.0, 64)
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 3.9), constrained_layout=True)
    rc_face = 5.0 * teacher.source_face_current_A.size
    model_width_m = next(iter(outcomes.values())).model.width_m
    teacher_face_width_m = model_width_m / teacher.source_face_current_A.size
    teacher_left_surface = case.device_voltage_V - teacher.source_face_current_A * rc_face
    teacher_right_surface = teacher.ground_face_current_A * rc_face
    y_teacher = (np.arange(teacher.source_face_current_A.size) + 0.5) / teacher.source_face_current_A.size
    axes[0].plot(y_teacher, teacher_left_surface, "k-", label="teacher left")
    axes[0].plot(y_teacher, teacher_right_surface, "k--", label="teacher right")
    axes[1].plot(
        y_teacher,
        teacher.source_face_current_A / teacher_face_width_m,
        "k-",
        label="teacher left",
    )
    axes[1].plot(
        y_teacher,
        teacher.ground_face_current_A / teacher_face_width_m,
        "k--",
        label="teacher right",
    )
    for name, outcome in outcomes.items():
        model = outcome.model
        left = case_inputs(case, np.zeros(y.size), y, model, requires_grad=True)
        right = case_inputs(case, np.ones(y.size), y, model, requires_grad=True)
        _, values = model.external_robin(left, right)
        left_state = model.state_fields(left, region_override=0)["phi_V"].detach().numpy().reshape(-1)
        right_state = model.state_fields(right, region_override=2)["phi_V"].detach().numpy().reshape(-1)
        axes[0].plot(y, left_state, label=f"{name} left")
        axes[0].plot(y, right_state, linestyle="--", label=f"{name} right")
        axes[1].plot(y, values["left_contact_J_A_m"].detach().numpy().reshape(-1), label=f"{name} left")
        axes[1].plot(y, values["right_contact_J_A_m"].detach().numpy().reshape(-1), linestyle="--", label=f"{name} right")
    axes[0].set(title="device-surface Robin potential", xlabel="normalized y", ylabel="V")
    axes[1].set(title="predicted contact sheet current", xlabel="normalized y", ylabel="A m$^{-1}$")
    axes[0].legend(fontsize=6, ncol=2)
    axes[1].legend(fontsize=6, ncol=2)
    fig.suptitle(case.case_id)
    fig.savefig(path, dpi=220)
    plt.close(fig)


def _plot_field_comparison(
    path: Path,
    case: M1TeacherCase,
    predictions: Mapping[str, Mapping[str, np.ndarray]],
) -> None:
    names = ["teacher", "B0-R", "B1-R", "P0-RCV"]
    fig, axes = plt.subplots(2, 4, figsize=(13.2, 6.0), constrained_layout=True)
    temperature_values = [case.temperature_K - 325.0] + [
        predictions[name]["T_K"] - 325.0 for name in names[1:]
    ]
    potential_values = [case.potential_V] + [predictions[name]["phi_V"] for name in names[1:]]
    t_min = min(float(np.min(value)) for value in temperature_values)
    t_max = max(float(np.max(value)) for value in temperature_values)
    p_min = min(float(np.min(value)) for value in potential_values)
    p_max = max(float(np.max(value)) for value in potential_values)
    for column, name in enumerate(names):
        top = axes[0, column].imshow(
            temperature_values[column], origin="lower", aspect="auto", vmin=t_min, vmax=t_max, cmap="inferno"
        )
        bottom = axes[1, column].imshow(
            potential_values[column], origin="lower", aspect="auto", vmin=p_min, vmax=p_max, cmap="viridis"
        )
        axes[0, column].set_title(name)
        axes[0, column].set_xlabel("x cell")
        axes[1, column].set_xlabel("x cell")
        if column == 0:
            axes[0, column].set_ylabel("y cell\nT rise (K)")
            axes[1, column].set_ylabel("y cell\nphi (V)")
    fig.colorbar(top, ax=axes[0, :], shrink=0.7)
    fig.colorbar(bottom, ax=axes[1, :], shrink=0.7)
    fig.suptitle(case.case_id)
    fig.savefig(path, dpi=220)
    plt.close(fig)


def _plot_metric_bars(
    path: Path,
    rows: Sequence[Mapping[str, Any]],
    metrics: Sequence[tuple[str, str]],
    title: str,
) -> None:
    models = ["B0-R", "B1-R", "P0-RCV"]
    cases = sorted({str(row["case_id"]) for row in rows})
    fig, axes = plt.subplots(1, len(metrics), figsize=(5.0 * len(metrics), 3.8), constrained_layout=True)
    axes_array = np.atleast_1d(axes)
    width = 0.24
    x = np.arange(len(cases))
    for axis, (metric, label) in zip(axes_array, metrics, strict=True):
        for index, model in enumerate(models):
            values = [
                float(next(row[metric] for row in rows if row["model"] == model and row["case_id"] == case))
                for case in cases
            ]
            axis.bar(x + (index - 1) * width, values, width=width, label=model)
        axis.set_xticks(x, [case.replace("near-transition", "near") for case in cases], rotation=18, ha="right", fontsize=7)
        axis.set_ylabel(label)
        axis.set_yscale("log")
        axis.grid(axis="y", alpha=0.25)
    axes_array[0].legend(fontsize=8)
    fig.suptitle(title)
    fig.savefig(path, dpi=220)
    plt.close(fig)


def _plot_local_cv(path: Path, prediction: Mapping[str, np.ndarray], title: str) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(10.0, 3.8), constrained_layout=True)
    for axis, key, label in zip(
        axes,
        ("local_current_cv_residual", "local_energy_cv_residual"),
        ("local current-CV residual", "local energy-CV residual"),
        strict=True,
    ):
        image = axis.imshow(prediction[key], origin="lower", aspect="auto", cmap="magma")
        axis.set_title(label)
        axis.set_xlabel("x cell")
        axis.set_ylabel("y cell")
        fig.colorbar(image, ax=axis, shrink=0.82)
    fig.suptitle(title)
    fig.savefig(path, dpi=220)
    plt.close(fig)


def _plot_training(path: Path, history: Sequence[Mapping[str, Any]]) -> None:
    models = ["B0-R", "B1-R", "P0-RCV"]
    groups = [
        "anchor_loss",
        "constitutive_loss",
        "local_current_cv_loss",
        "local_energy_cv_loss",
        "external_robin_loss",
        "interface_state_loss",
        "interface_flux_loss",
        "port_loss",
        "ledger_loss",
        "total_loss",
    ]
    fig, axes = plt.subplots(1, 3, figsize=(15.0, 4.2), constrained_layout=True)
    for axis, model in zip(axes, models, strict=True):
        subset = [row for row in history if row["model"] == model]
        steps = [int(row["step"]) for row in subset]
        for group in groups:
            values = np.asarray([float(row[group]) for row in subset])
            if np.any(values > 0.0):
                axis.semilogy(steps, np.maximum(values, 1.0e-18), label=group.removesuffix("_loss"))
        axis.axvline(300, color="0.5", linestyle=":", linewidth=1)
        axis.set(title=model, xlabel="Adam step", ylabel="dimensionless loss")
        axis.grid(alpha=0.2)
        axis.legend(fontsize=6, ncol=2)
    fig.savefig(path, dpi=220)
    plt.close(fig)


def _write_report(
    path: Path,
    summary: Mapping[str, Any],
    test_rows: Sequence[Mapping[str, Any]],
    figure_root: Path,
) -> None:
    compatibility = summary["teacher_objective_compatibility"]
    decision = summary["decision"]
    table_lines = [
        "| model | T-rise L2 | phi L2 | current | energy | interface | current-CV P95 | energy-CV P95 | passes |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for model in ("B0-R", "B1-R", "P0-RCV"):
        aggregate = summary["test_aggregates"][model]
        table_lines.append(
            "| {model} | {t:.4f} | {p:.4f} | {i:.4f} | {e:.4f} | {f:.4f} | {ci:.4f} | {ce:.4f} | {passes}/2 |".format(
                model=model,
                t=aggregate["mean_temperature_rise_relative_l2"],
                p=aggregate["mean_potential_relative_l2"],
                i=aggregate["mean_terminal_current_relative_error"],
                e=aggregate["mean_energy_ledger_relative_error"],
                f=aggregate["mean_interface_flux_mismatch"],
                ci=aggregate["mean_local_current_cv_residual_p95"],
                ce=aggregate["mean_local_energy_cv_residual_p95"],
                passes=aggregate["complete_case_pass_count"],
            )
        )
    figures = "\n".join(
        f"- `{figure_root.as_posix()}/{name}`"
        for name in (
            "teacher_objective_residual_maps.png",
            "m1_robin_boundary_profiles.png",
            "field_comparison_b0_b1_p0.png",
            "interface_flux_comparison.png",
            "local_cv_residuals.png",
            "port_energy_ledger_comparison.png",
            "training_group_losses.png",
        )
    )
    disposition = summary["disposition"]
    if disposition == "GO_M1_RCV_PINN_IDEA_SCREEN":
        next_priority = "Preregister `Q2_M1_RCV_PINN_FORMAL_OOD_V1`; do not begin it in this round."
        allowed = "A single-seed diagnostic supports advancing the M1-consistent RCV idea to formal OOD."
    elif disposition == "PARTIAL_GO_M1_STRONG_FORM_ONLY":
        next_priority = "Remove the mixed/CV headline and close a bounded strong-form-only candidate statement."
        allowed = "The M1-consistent strong-form hybrid is retained as a diagnostic low-spec candidate."
    else:
        next_priority = "Stop direct coordinate-PINN expansion and route to a limitation manuscript or solver-projected surrogate."
        allowed = "The M1 teacher/objective contract is compatible, but the bounded single-seed direct coordinate-PINN rescue failed."
    content = f"""# Q2 M1 Robin control-volume PINN rescue v1

## Frozen baseline

PR #37 at `c4ccd7a995fbd4027d92a10fcbf42b1e14906092` remains the immutable bounded negative result `NO_GO_GEOSTATE_PINN_IDEA_SCREEN`; it was squash-merged unchanged as `183f129545a2a047137745d36a0c432d02a28219`.

## Teacher--objective compatibility

Passed: `{str(compatibility['passed']).lower()}` across `{compatibility['case_count']}/12` finite cases. Worst current/energy P95 were `{compatibility['max_local_current_balance_p95']:.3e}` and `{compatibility['max_local_energy_balance_p95']:.3e}`; worst Robin/interface errors were `{compatibility['max_external_robin_residual_p95']:.3e}` and `{compatibility['max_interface_flux_mismatch']:.3e}`. No reference nonlinear solve was rerun.

## Structural corrections

The rescue removes M0 terminal hard lifting, uses M1 electrical Robin contacts and contact-corrected vertical thermal conductance, evaluates explicit three-region traces, trains only phi/T anchors, and replaces pointwise mixed-flux divergence with locked control-volume balances for P0-RCV.

## Actual single-seed results

All three models used seed `20260809`, float64, the same 5% geometry-only phi/T anchors, the same split, and exactly 1500 Adam steps.

{chr(10).join(table_lines)}

Decision diagnostics: P0 field improvement over B0 `{decision['p0_field_improvement_over_b0']:.2%}`; conservation factor over B1 `{decision['p0_conservation_improvement_factor_over_b1']:.3f}x`; catastrophic regression `{decision['catastrophic_regression_vs_b1']}`.

## Disposition

`{disposition}`

## Figures

{figures}

## Claim boundary

Allowed manuscript sentence: "{allowed}" M1 reference sufficiency remains `qualified_supported`; teacher--objective compatibility is an implementation/contract fact; this single-seed rescue is diagnostic and non-voting.

Forbidden manuscript sentence: any claim of formal PINN superiority, experimental validation, dynamic stability, complete hysteresis, or inverse recovery. Formal superiority requires a later authorized formal OOD and multiple seeds.

## Single next priority

{next_priority}
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main() -> None:
    torch.set_default_dtype(torch.float64)
    torch.set_num_threads(1)
    rescue = load_yaml(CONFIG_PATH)
    base = load_yaml(ROOT / rescue["reference"]["config"])
    context = build_reference_context(base, ROOT)
    output_config = rescue["outputs"]
    processed_root = ROOT / output_config["processed_root"]
    table_root = ROOT / output_config["table_root"]
    figure_root = ROOT / output_config["figure_root"]
    checkpoint_root = ROOT / output_config["checkpoint_root"]
    for directory in (processed_root, table_root, figure_root, checkpoint_root):
        directory.mkdir(parents=True, exist_ok=True)

    cases = load_teacher_cases(ROOT / rescue["reference"]["data_root"])
    if len(cases) != int(rescue["reference"]["expected_cases"]):
        raise RuntimeError("the frozen 12-case M1 dataset is incomplete")
    compatibility_rows: list[dict[str, Any]] = []
    reconstructed: dict[str, ConservativeTeacherFields] = {}
    for case in cases:
        row, fields = reconstruct_conservative_teacher(context, case, base)
        compatibility_rows.append(row)
        reconstructed[case.case_id] = fields
    compatibility_ok, compatibility_summary = compatibility_passes(
        compatibility_rows, rescue
    )
    compatibility_summary.update(
        {
            "task_id": rescue["task_id"],
            "run_id": rescue["run_id"],
            "implementation_repairs_used": 0,
            "reference_nonlinear_solves_rerun": 0,
        }
    )
    _write_csv(table_root / "teacher_objective_compatibility.csv", compatibility_rows)
    _write_json(
        table_root / "teacher_objective_compatibility_summary.json",
        compatibility_summary,
    )
    worst_row = max(
        compatibility_rows,
        key=lambda row: float(row["local_current_balance_p95"])
        + float(row["local_energy_balance_p95"]),
    )
    worst_case = next(case for case in cases if case.case_id == worst_row["case_id"])
    _plot_compatibility(
        figure_root / "teacher_objective_residual_maps.png",
        worst_case,
        reconstructed[worst_case.case_id],
    )
    print(
        "compatibility",
        json.dumps(_json_ready(compatibility_summary), sort_keys=True),
        flush=True,
    )
    if not compatibility_ok:
        summary = {
            "task_id": rescue["task_id"],
            "run_id": rescue["run_id"],
            "disposition": "NO_GO_TEACHER_OBJECTIVE_INCOMPATIBLE",
            "teacher_objective_compatibility": compatibility_summary,
            "training_runs": [],
            "claim_boundary": rescue["claim_boundary"],
        }
        _write_json(table_root / "summary.json", summary)
        return

    validation_ids = set(rescue["dataset"]["validation_cases"])
    test_ids = set(rescue["dataset"]["test_cases"])
    train_cases = [case for case in cases if case.case_id not in validation_ids | test_ids]
    validation_cases = [case for case in cases if case.case_id in validation_ids]
    test_cases = [case for case in cases if case.case_id in test_ids]
    rectangle = base["physical_model"]["localized_sink"]["rectangle_m"]
    rescue_for_sampling = dict(rescue)
    rescue_for_sampling["_sink_rectangle_norm"] = (
        float(rectangle["x"][0]) / context.length_m,
        float(rectangle["x"][1]) / context.length_m,
        float(rectangle["y"][0]) / context.width_m,
        float(rectangle["y"][1]) / context.width_m,
    )
    anchor_indices = build_anchor_indices(train_cases, context, rescue_for_sampling)
    fixed_samples = build_fixed_samples(train_cases, context, rescue)
    np.savez_compressed(
        processed_root / "anchor_indices.npz",
        **{key.replace("-", "_"): np.asarray(value, dtype=int) for key, value in anchor_indices.items()},
    )
    _save_fixed_samples(processed_root / "fixed_training_samples.npz", fixed_samples)
    target_currents = {
        str(row["case_id"]): abs(float(row["source_current_A"]))
        for row in compatibility_rows
    }

    outcomes: dict[str, TrainingOutcome] = {}
    history: list[dict[str, Any]] = []
    for model_name in ("B0-R", "B1-R", "P0-RCV"):
        print(f"training_start {model_name}", flush=True)
        outcome = train_model(
            model_name,
            context,
            rescue,
            base,
            train_cases,
            anchor_indices,
            fixed_samples,
            target_currents,
        )
        if not outcome.finite or outcome.completed_steps != 1500:
            raise RuntimeError(
                f"{model_name} did not complete the frozen 1500-step contract"
            )
        outcomes[model_name] = outcome
        history.extend(outcome.history)
        torch.save(
            {
                "task_id": rescue["task_id"],
                "run_id": rescue["run_id"],
                "model": model_name,
                "state_dict": outcome.model.state_dict(),
                "completed_steps": outcome.completed_steps,
                "parameter_count": outcome.parameter_count,
                "seed": int(rescue["model"]["seed"]),
                "dtype": "float64",
            },
            checkpoint_root / f"{model_name.lower().replace('-', '_')}.pt",
        )
        print(
            f"training_done {model_name} steps={outcome.completed_steps} wall_s={outcome.wall_time_s:.3f} params={outcome.parameter_count} grad_ratio={outcome.gradient_ratio:.6g}",
            flush=True,
        )
    parameter_counts = [outcome.parameter_count for outcome in outcomes.values()]
    parameter_spread = (max(parameter_counts) - min(parameter_counts)) / min(parameter_counts)
    if parameter_spread > 0.05:
        raise RuntimeError("model parameter counts differ by more than 5%")
    _write_csv(table_root / "training_history.csv", history)

    all_metric_rows: list[dict[str, Any]] = []
    predictions: dict[tuple[str, str], dict[str, np.ndarray]] = {}
    for model_name, outcome in outcomes.items():
        for split, split_cases in (("validation", validation_cases), ("test", test_cases)):
            for case in split_cases:
                row, prediction = evaluate_case(
                    outcome,
                    case,
                    context,
                    rescue,
                    target_currents[case.case_id],
                    split=split,
                )
                all_metric_rows.append(row)
                predictions[(model_name, case.case_id)] = prediction
                if split == "test":
                    prediction_dir = processed_root / "predictions" / model_name.lower().replace("-", "_")
                    prediction_dir.mkdir(parents=True, exist_ok=True)
                    np.savez_compressed(
                        prediction_dir / f"{case.case_id}.npz",
                        **prediction,
                        case_id=np.asarray(case.case_id),
                        model=np.asarray(model_name),
                        evidence_type=np.asarray(rescue["evidence_type"]),
                    )
    test_rows = [row for row in all_metric_rows if row["split"] == "test"]
    validation_rows = [row for row in all_metric_rows if row["split"] == "validation"]
    _write_csv(table_root / "test_metrics.csv", test_rows)
    _write_csv(table_root / "validation_metrics.csv", validation_rows)
    aggregate_rows: list[dict[str, Any]] = []
    aggregates_by_split: dict[str, dict[str, dict[str, Any]]] = {
        "test": {},
        "validation": {},
    }
    for split, rows in (("test", test_rows), ("validation", validation_rows)):
        for model_name in outcomes:
            aggregate = aggregate_metrics(
                [row for row in rows if row["model"] == model_name]
            )
            aggregates_by_split[split][model_name] = aggregate
            aggregate_rows.append({"model": model_name, "split": split, **aggregate})
    _write_csv(table_root / "aggregate_metrics.csv", aggregate_rows)
    disposition, decision = decide_disposition(aggregates_by_split["test"], rescue)

    representative = test_cases[0]
    representative_predictions = {
        name: predictions[(name, representative.case_id)] for name in outcomes
    }
    _plot_boundary_profiles(
        figure_root / "m1_robin_boundary_profiles.png",
        representative,
        reconstructed[representative.case_id],
        outcomes,
    )
    _plot_field_comparison(
        figure_root / "field_comparison_b0_b1_p0.png",
        representative,
        representative_predictions,
    )
    _plot_metric_bars(
        figure_root / "interface_flux_comparison.png",
        test_rows,
        (("interface_flux_mismatch", "relative interface mismatch"),),
        "Interface flux comparison",
    )
    _plot_local_cv(
        figure_root / "local_cv_residuals.png",
        representative_predictions["P0-RCV"],
        f"P0-RCV: {representative.case_id}",
    )
    _plot_metric_bars(
        figure_root / "port_energy_ledger_comparison.png",
        test_rows,
        (
            ("terminal_current_relative_error", "terminal-current error"),
            ("energy_ledger_relative_error", "energy-ledger error"),
        ),
        "Port and energy ledger comparison",
    )
    _plot_training(figure_root / "training_group_losses.png", history)

    training_summary = {
        name: {
            "completed_steps": outcome.completed_steps,
            "wall_time_s": outcome.wall_time_s,
            "parameter_count": outcome.parameter_count,
            "finite": outcome.finite,
            "gradient_norms_at_first_joint_step": outcome.gradient_norms,
            "gradient_scale_ratio": outcome.gradient_ratio,
        }
        for name, outcome in outcomes.items()
    }
    summary = {
        "task_id": rescue["task_id"],
        "run_id": rescue["run_id"],
        "evidence_type": rescue["evidence_type"],
        "frozen_baseline": rescue["frozen_baseline"],
        "teacher_objective_compatibility": compatibility_summary,
        "implementation_repairs_used": 0,
        "training_contract": {
            "seed": int(rescue["model"]["seed"]),
            "dtype": rescue["model"]["dtype"],
            "anchor_fraction": float(rescue["dataset"]["anchor_fraction"]),
            "steps_per_model": 1500,
            "parameter_spread_fraction": parameter_spread,
            "reference_nonlinear_solves_rerun": 0,
        },
        "training_runs": training_summary,
        "validation_aggregates": aggregates_by_split["validation"],
        "test_aggregates": aggregates_by_split["test"],
        "decision": decision,
        "disposition": disposition,
        "formal_ood_activated": False,
        "claim_boundary": rescue["claim_boundary"],
        "paths": output_config,
    }
    _write_json(table_root / "summary.json", summary)
    _write_report(ROOT / output_config["report"], summary, test_rows, Path(output_config["figure_root"]))
    print("final_disposition", disposition, flush=True)
    print(json.dumps(_json_ready(summary), sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
