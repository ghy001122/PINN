"""Branch-aware latent surrogate MVE on protocol-selected M1 equilibria.

The benchmark keeps the protocol direction explicit, derives every learned
quantity from train-only fields, and evaluates all initializers through the
same damped conservative M1 projection.  It never averages roots or exposes a
numerical root identifier to a model.
"""

from __future__ import annotations

import csv
import copy
import hashlib
import json
import math
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import torch
from torch import Tensor

from pinnpcm.experiments.geostate_fasttrack import load_yaml
from pinnpcm.experiments.m1_latent_projection_mve import ThermalPOD, fit_train_only_pod
from pinnpcm.experiments.m1_protocol_selected_equilibrium_manifold import (
    ProtocolPoint,
    ProtocolRun,
    all_run_points,
    rehydrate_protocol_runs,
)
from pinnpcm.experiments.m1_self_consistent_imt_contraction import (
    build_operator,
    load_qiu_parameters,
    solve_fixed_point,
)
from pinnpcm.experiments.protocol_factorial_contexts import (
    _context_summaries,
    _sensitivity_rows,
    execute_new_context_protocols,
)
from pinnpcm.physics.m1_self_consistent_imt import M1SelfConsistentIMTProjection
from pinnpcm.pinn.protocol_manifold_surrogate import (
    Degree2Ridge,
    HistoryBlindLatentNet,
    InputNormalization,
    ProtocolGatedLatentNet,
    ProtocolSingleHeadLatentNet,
    decode_temperature,
    fit_degree2_ridge,
    fit_input_normalization,
    normalize_inputs,
    parameter_difference_fraction,
    predict_degree2_ridge,
    unknown_protocol_decision,
    validate_surrogate_schema,
)


EVIDENCE_TYPE = "literature-guided synthetic numerical digital-twin evidence"


@dataclass(frozen=True)
class ProtocolSample:
    sample_id: str
    context_id: str
    protocol_id: str
    branch_label: str
    branch_value: float
    direction_value: float
    protocol_start_voltage_V: float
    voltage_V: float
    contact_overlap_nm: float
    sink_amplitude: float
    point_kind: str
    sequence_index: int
    point: ProtocolPoint
    split: str
    fit_eligible: bool
    full_curve_test: bool
    headline_test: bool
    stability_class: str
    source_artifact: str
    temperature_sha256: str


@dataclass
class ModeOutput:
    temperature_K: Tensor
    fields: dict[str, Tensor]
    fixed_point_defect: float
    sigma_defect: float
    projection_count: int
    main_linear_solve_count: int
    diagnostic_projection_count: int = 1
    diagnostic_linear_solve_count: int = 2


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, Path):
        return value.as_posix()
    return value


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_json_safe(payload), indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _union_fields(rows: Sequence[Mapping[str, Any]]) -> list[str]:
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(str(key))
    return fields


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fields: Sequence[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    names = list(fields or _union_fields(rows))
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=names, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _json_safe(row.get(key)) for key in names})


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _temperature_hash(temperature_K: Tensor) -> str:
    array = np.ascontiguousarray(temperature_K.detach().cpu().numpy(), dtype=np.float64)
    return hashlib.sha256(array.tobytes()).hexdigest()


def _relative_l2(predicted: Tensor | np.ndarray, reference: Tensor | np.ndarray) -> float:
    pred = torch.as_tensor(predicted, dtype=torch.float64)
    ref = torch.as_tensor(reference, dtype=torch.float64)
    return float(torch.linalg.vector_norm(pred - ref) / torch.clamp(torch.linalg.vector_norm(ref), min=1.0e-30))


def _temperature_rise_error(predicted: Tensor, reference: Tensor, ambient: float) -> float:
    return _relative_l2(predicted - ambient, reference - ambient)


def _scalar_error(predicted: Tensor | float, reference: Tensor | float) -> float:
    pred = float(torch.as_tensor(predicted, dtype=torch.float64))
    ref = float(torch.as_tensor(reference, dtype=torch.float64))
    return abs(pred - ref) / max(abs(ref), 1.0e-30)


def _symmetric_separation(left: float, right: float) -> float:
    return abs(left - right) / max(abs(left), abs(right), 1.0e-30)


def _temperature_separation(left: Tensor, right: Tensor, ambient: float) -> float:
    numerator = torch.linalg.vector_norm(left - right)
    denominator = torch.maximum(
        torch.linalg.vector_norm(left - ambient), torch.linalg.vector_norm(right - ambient)
    )
    return float(numerator / torch.clamp(denominator, min=1.0e-30))


def _hotspot_error(predicted: Tensor, reference: Tensor) -> float:
    ny, nx = reference.shape
    pred_index = int(torch.argmax(predicted))
    ref_index = int(torch.argmax(reference))
    py, px = divmod(pred_index, nx)
    ry, rx = divmod(ref_index, nx)
    return math.hypot((px - rx) / max(nx - 1, 1), (py - ry) / max(ny - 1, 1))


def _coefficient_for_temperature(temperature_K: Tensor, pod: ThermalPOD, ambient: float) -> np.ndarray:
    rise = np.maximum(temperature_K.detach().cpu().numpy() - ambient, 0.0)
    transformed = np.log1p(rise).reshape(-1)
    return (transformed - pod.mean_y) @ pod.basis.T


def _build_all_operators(config: Mapping[str, Any], repository_root: Path) -> dict[str, M1SelfConsistentIMTProjection]:
    base_config = load_yaml(repository_root / str(config["reference"]["base_config"]))
    qiu = load_qiu_parameters(
        {
            "source_contract": {
                "path": config["reference"]["source_contract"],
                "section": "source_author_fitted_lumped_quantities",
                "beta_per_K": 0.253,
                "loop_width_K": 7.193,
                "critical_temperature_K": 332.8,
                "expected_Tc_up_K": config["reference"]["Tc_up_K"],
                "expected_Tc_down_K": config["reference"]["Tc_down_K"],
                "expected_nominal_wT_K": config["reference"]["nominal_transition_width_K"],
            }
        },
        repository_root,
    )
    return {
        context_id: build_operator(
            base_config=base_config,
            repository_root=repository_root,
            contact_overlap_nm=float(context["contact_overlap_nm"]),
            qiu_parameters=qiu,
            phase_width_multiplier=float(config["reference"]["phase_width_multiplier"]),
            joule_feedback_multiplier=float(config["reference"]["joule_feedback_multiplier"]),
            relaxation_alpha=float(config["reference"]["relaxation_alpha"]),
        )
        for context_id, context in config["contexts"].items()
        if isinstance(context, Mapping)
    }


def _headline_state_ids(config: Mapping[str, Any], repository_root: Path) -> set[str]:
    table_root = repository_root / str(config["reference"]["historical_table_root"])
    rows = _read_csv(table_root / "physical_stability_metrics.csv")
    selected = {
        str(row["state_id"])
        for row in rows
        if row.get("context_id") == "G1" and row.get("stability_class") == "stable"
    }
    if len(selected) != 10:
        raise ValueError(f"frozen G1 headline set must contain 10 unique stability states, got {len(selected)}")
    return selected


def _sample_split(
    point: ProtocolPoint,
    *,
    context_id: str,
    validation_indices: set[int],
    headline_ids: set[str],
) -> tuple[str, bool, bool, bool]:
    if context_id == "G1":
        headline = point.point_id in headline_ids
        full_curve = point.point_kind == "coarse"
        return ("test_headline" if headline else "test_diagnostic", False, full_curve, headline)
    if context_id in {"G0", "G2", "G3"}:
        if point.point_kind == "coarse" and point.valid and point.accepted:
            if point.sequence_index in validation_indices:
                return "validation", False, False, False
            return "train", True, False, False
        if point.point_kind in {"event_refinement", "event_reachability_confirmation"}:
            return "validation_event", False, False, False
        return "excluded_auxiliary", False, False, False
    raise ValueError(f"unexpected context {context_id}")


def build_protocol_samples(
    *,
    config: Mapping[str, Any],
    repository_root: Path,
    old_runs: Sequence[ProtocolRun],
    new_runs: Sequence[ProtocolRun],
) -> tuple[list[ProtocolSample], list[dict[str, Any]]]:
    headline_ids = _headline_state_ids(config, repository_root)
    validation_indices = {int(value) for value in config["split"]["validation_coarse_indices"]}
    historical_root = repository_root / str(config["reference"]["historical_processed_root"])
    new_root = repository_root / str(config["outputs"]["processed_root"])
    samples: list[ProtocolSample] = []
    rows: list[dict[str, Any]] = []
    for run in [*old_runs, *new_runs]:
        context = config["contexts"][run.spec.context_id]
        source_root = historical_root if run.spec.context_id in {"G0", "G1"} else new_root
        stability_class_by_id: dict[str, str] = {}
        if run.spec.context_id in {"G0", "G1"}:
            with np.load(source_root / f"{run.spec.protocol_id}.npz", allow_pickle=False) as data:
                stability_class_by_id = {
                    str(point_id): str(value)
                    for point_id, value in zip(data["point_id"], data["point_stability_class"])
                }
        for point in all_run_points(run):
            split, fit, full_curve, headline = _sample_split(
                point,
                context_id=run.spec.context_id,
                validation_indices=validation_indices,
                headline_ids=headline_ids,
            )
            sample = ProtocolSample(
                sample_id=point.point_id,
                context_id=run.spec.context_id,
                protocol_id=run.spec.protocol_id,
                branch_label=run.spec.branch_label,
                branch_value=float(run.spec.branch_value),
                direction_value=1.0 if run.spec.direction == "increasing" else -1.0,
                protocol_start_voltage_V=float(run.spec.start_voltage_V),
                voltage_V=float(point.voltage_V),
                contact_overlap_nm=float(context["contact_overlap_nm"]),
                sink_amplitude=float(context["sink_amplitude"]),
                point_kind=point.point_kind,
                sequence_index=int(point.sequence_index),
                point=point,
                split=split,
                fit_eligible=fit,
                full_curve_test=full_curve,
                headline_test=headline,
                stability_class=stability_class_by_id.get(point.point_id, "not_evaluated"),
                source_artifact=(source_root / f"{run.spec.protocol_id}.npz").as_posix(),
                temperature_sha256=_temperature_hash(point.result.temperature_K),
            )
            samples.append(sample)
            rows.append(
                {
                    "sample_id": sample.sample_id,
                    "source_artifact": sample.source_artifact,
                    "temperature_sha256": sample.temperature_sha256,
                    "context_id": sample.context_id,
                    "protocol_id": sample.protocol_id,
                    "branch_label": sample.branch_label,
                    "ramp_direction": sample.direction_value,
                    "protocol_start_voltage_V": sample.protocol_start_voltage_V,
                    "device_voltage_V": sample.voltage_V,
                    "contact_overlap_nm": sample.contact_overlap_nm,
                    "sink_amplitude": sample.sink_amplitude,
                    "point_kind": sample.point_kind,
                    "sequence_index": sample.sequence_index,
                    "split": sample.split,
                    "fit_eligible": sample.fit_eligible,
                    "full_curve_test": sample.full_curve_test,
                    "headline_stability_test": sample.headline_test,
                    "stability_class": sample.stability_class,
                    "root_identifier_used": False,
                }
            )
    train = [sample for sample in samples if sample.fit_eligible]
    if len(train) != 174:
        raise ValueError(f"frozen split expected 174 train coarse states, got {len(train)}")
    if any(sample.context_id == "G1" for sample in train):
        raise ValueError("compound holdout G1 leaked into train")
    if sum(sample.split == "validation" for sample in samples) != 24:
        raise ValueError("fixed coarse validation split must contain 24 states")
    if sum(sample.full_curve_test for sample in samples) != 66:
        raise ValueError("G1 full-curve diagnostic must contain 66 coarse states")
    if sum(sample.headline_test for sample in samples) != 10:
        raise ValueError("G1 headline must contain 10 unique certified states")
    return samples, rows


def protocol_raw_inputs(samples: Sequence[ProtocolSample]) -> np.ndarray:
    return np.asarray(
        [
            [
                sample.voltage_V,
                sample.direction_value,
                sample.protocol_start_voltage_V,
                sample.contact_overlap_nm,
                sample.sink_amplitude,
            ]
            for sample in samples
        ],
        dtype=np.float64,
    )


def history_raw_inputs(samples: Sequence[ProtocolSample]) -> np.ndarray:
    return np.asarray(
        [[sample.voltage_V, sample.contact_overlap_nm, sample.sink_amplitude] for sample in samples],
        dtype=np.float64,
    )


def fit_protocol_pod(
    samples: Sequence[ProtocolSample], config: Mapping[str, Any]
) -> ThermalPOD:
    train = sorted((sample for sample in samples if sample.fit_eligible), key=lambda item: item.sample_id)
    fields = {
        sample.sample_id: sample.point.result.temperature_K.detach().cpu().numpy()
        for sample in train
    }
    try:
        pod = fit_train_only_pod(
            fields,
            [sample.sample_id for sample in train],
            ambient_temperature_K=float(config["reference"]["ambient_temperature_K"]),
            cumulative_energy_target=float(config["pod"]["cumulative_energy_target"]),
            rank_cap=int(config["pod"]["rank_cap"]),
            training_sample_rank_cap=int(config["pod"]["rank_cap"]),
        )
    except RuntimeError as error:
        raise RuntimeError("NO_GO_PROTOCOL_MANIFOLD_LOW_RANK_CONTRACT") from error
    if pod.rank > int(config["pod"]["rank_cap"]):
        raise RuntimeError("NO_GO_PROTOCOL_MANIFOLD_LOW_RANK_CONTRACT")
    if set(pod.train_case_ids) != {sample.sample_id for sample in train}:
        raise ValueError("POD fit identity differs from the frozen train split")
    return pod


def _normalized_targets(samples: Sequence[ProtocolSample], pod: ThermalPOD, ambient: float) -> np.ndarray:
    physical = np.stack(
        [_coefficient_for_temperature(sample.point.result.temperature_K, pod, ambient) for sample in samples]
    )
    return (physical - pod.coefficient_center) / pod.coefficient_scale


def _decode_normalized(normalized: Tensor, pod: ThermalPOD, config: Mapping[str, Any]) -> Tensor:
    center = torch.as_tensor(pod.coefficient_center, dtype=torch.float64, device=normalized.device)
    scale = torch.as_tensor(pod.coefficient_scale, dtype=torch.float64, device=normalized.device)
    mean = torch.as_tensor(pod.mean_y, dtype=torch.float64, device=normalized.device)
    basis = torch.as_tensor(pod.basis, dtype=torch.float64, device=normalized.device)
    physical = center + scale * normalized
    y = mean + physical @ basis
    rise = torch.expm1(y)
    beta = float(config["pod"]["smooth_nonnegative_beta_K"])
    protected = beta * torch.nn.functional.softplus(rise / beta)
    ny = int(config["reference"]["production_grid"]["ny"])
    nx = int(config["reference"]["production_grid"]["nx"])
    return (float(config["reference"]["ambient_temperature_K"]) + protected).reshape(-1, ny, nx)


def _model_kwargs(pod: ThermalPOD, config: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "pod_mean_y": torch.as_tensor(pod.mean_y, dtype=torch.float64),
        "pod_basis": torch.as_tensor(pod.basis, dtype=torch.float64),
        "coefficient_center": torch.as_tensor(pod.coefficient_center, dtype=torch.float64),
        "coefficient_scale": torch.as_tensor(pod.coefficient_scale, dtype=torch.float64),
        "ambient_temperature_K": float(config["reference"]["ambient_temperature_K"]),
        "smooth_nonnegative_beta_K": float(config["pod"]["smooth_nonnegative_beta_K"]),
    }


def build_models(pod: ThermalPOD, config: Mapping[str, Any], seed: int) -> dict[str, torch.nn.Module]:
    torch.manual_seed(int(seed))
    kwargs = _model_kwargs(pod, config)
    history = HistoryBlindLatentNet(**kwargs).to(dtype=torch.float64)
    torch.manual_seed(int(seed))
    single = ProtocolSingleHeadLatentNet(**kwargs).to(dtype=torch.float64)
    torch.manual_seed(int(seed))
    gated = ProtocolGatedLatentNet(**kwargs).to(dtype=torch.float64)
    difference = parameter_difference_fraction(single, gated)
    maximum = float(config["network"]["maximum_single_vs_gated_parameter_difference_fraction"])
    if difference > maximum + 1.0e-12:
        raise ValueError(f"S/G parameter-count mismatch {difference:.6g} exceeds {maximum:.6g}")
    return {"H": history, "S": single, "G": gated}


def _model_normalized_coefficients(
    model_kind: str,
    model: torch.nn.Module,
    samples: Sequence[ProtocolSample],
    protocol_normalization: InputNormalization,
    history_normalization: InputNormalization,
) -> Tensor:
    if model_kind == "H":
        raw = torch.as_tensor(history_raw_inputs(samples), dtype=torch.float64)
        normalized = normalize_inputs(raw, history_normalization)
        return model(normalized)  # type: ignore[operator]
    raw = torch.as_tensor(protocol_raw_inputs(samples), dtype=torch.float64)
    normalized = normalize_inputs(raw, protocol_normalization)
    if model_kind == "G":
        direction = torch.as_tensor([sample.direction_value for sample in samples], dtype=torch.float64)
        return model(normalized, direction)  # type: ignore[operator]
    return model(normalized)  # type: ignore[operator]


def _batch_relative_l2(predicted: Tensor, reference: Tensor) -> Tensor:
    batch = predicted.shape[0]
    numerator = torch.linalg.vector_norm((predicted - reference).reshape(batch, -1), dim=1)
    denominator = torch.clamp(torch.linalg.vector_norm(reference.reshape(batch, -1), dim=1), min=1.0e-30)
    return torch.mean(numerator / denominator)


def _batch_fixed_defect(next_temperature: Tensor, temperature: Tensor, ambient: float) -> Tensor:
    batch = temperature.shape[0]
    numerator = torch.linalg.vector_norm((next_temperature - temperature).reshape(batch, -1), dim=1)
    denominator = torch.clamp(
        torch.linalg.vector_norm((next_temperature - ambient).reshape(batch, -1), dim=1), min=1.0e-30
    )
    return torch.mean(numerator / denominator)


def _training_loss_groups(
    *,
    model_kind: str,
    model: torch.nn.Module,
    samples: Sequence[ProtocolSample],
    target_normalized_coefficients: Tensor,
    pod: ThermalPOD,
    operators: Mapping[str, M1SelfConsistentIMTProjection],
    protocol_normalization: InputNormalization,
    history_normalization: InputNormalization,
    config: Mapping[str, Any],
) -> dict[str, Tensor]:
    predicted_norm = _model_normalized_coefficients(
        model_kind, model, samples, protocol_normalization, history_normalization
    )
    temperature0 = _decode_normalized(predicted_norm, pod, config)
    ambient = float(config["reference"]["ambient_temperature_K"])
    groups: dict[str, list[tuple[int, Tensor]]] = {
        name: []
        for name in (
            "one_projection_temperature",
            "one_projection_potential",
            "one_projection_current",
            "one_projection_fixed_point_defect",
            "two_projection_temperature",
            "two_projection_potential",
            "two_projection_current",
            "two_projection_fixed_point_defect",
        )
    }
    for context_id in sorted({sample.context_id for sample in samples}):
        indices = [index for index, sample in enumerate(samples) if sample.context_id == context_id]
        selected = [samples[index] for index in indices]
        operator = operators[context_id]
        index_tensor = torch.as_tensor(indices, dtype=torch.long)
        state0 = temperature0.index_select(0, index_tensor)
        voltage = torch.as_tensor([sample.voltage_V for sample in selected], dtype=torch.float64)
        branch = torch.as_tensor([sample.branch_value for sample in selected], dtype=torch.float64)
        sink = torch.as_tensor([sample.sink_amplitude for sample in selected], dtype=torch.float64)
        reference_T = torch.stack([sample.point.result.temperature_K for sample in selected])
        reference_phi = torch.stack([sample.point.result.fields["potential_V"] for sample in selected])
        reference_current = torch.as_tensor(
            [sample.point.result.metrics["terminal_current_A"] for sample in selected], dtype=torch.float64
        )
        projection1 = operator.projection(state0, voltage, branch, sink)
        temperature1 = projection1["temperature_K"]
        projection2 = operator.projection(temperature1, voltage, branch, sink)
        temperature2 = projection2["temperature_K"]
        projection3 = operator.projection(temperature2, voltage, branch, sink)
        temperature3 = projection3["temperature_K"]
        count = len(selected)
        groups["one_projection_temperature"].append(
            (count, _batch_relative_l2(temperature1 - ambient, reference_T - ambient))
        )
        groups["one_projection_potential"].append(
            (count, _batch_relative_l2(projection1["potential_V"], reference_phi))
        )
        groups["one_projection_current"].append(
            (
                count,
                torch.mean(
                    torch.abs(projection1["source_current_A"] - reference_current)
                    / torch.clamp(torch.abs(reference_current), min=1.0e-30)
                ),
            )
        )
        groups["one_projection_fixed_point_defect"].append(
            (count, _batch_fixed_defect(temperature2, temperature1, ambient))
        )
        groups["two_projection_temperature"].append(
            (count, _batch_relative_l2(temperature2 - ambient, reference_T - ambient))
        )
        groups["two_projection_potential"].append(
            (count, _batch_relative_l2(projection2["potential_V"], reference_phi))
        )
        groups["two_projection_current"].append(
            (
                count,
                torch.mean(
                    torch.abs(projection2["source_current_A"] - reference_current)
                    / torch.clamp(torch.abs(reference_current), min=1.0e-30)
                ),
            )
        )
        groups["two_projection_fixed_point_defect"].append(
            (count, _batch_fixed_defect(temperature3, temperature2, ambient))
        )
    reduced: dict[str, Tensor] = {
        "coefficient": torch.mean((predicted_norm - target_normalized_coefficients) ** 2)
    }
    for name, values in groups.items():
        total = sum(count for count, _ in values)
        reduced[name] = sum(count * value for count, value in values) / max(total, 1)
    return reduced


def train_network(
    *,
    model_kind: str,
    model: torch.nn.Module,
    train_samples: Sequence[ProtocolSample],
    pod: ThermalPOD,
    operators: Mapping[str, M1SelfConsistentIMTProjection],
    protocol_normalization: InputNormalization,
    history_normalization: InputNormalization,
    config: Mapping[str, Any],
    seed: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    training = config["training"]
    torch.manual_seed(int(seed))
    ordered = sorted(train_samples, key=lambda sample: sample.sample_id)
    target_np = _normalized_targets(ordered, pod, float(config["reference"]["ambient_temperature_K"]))
    target_all = torch.as_tensor(target_np, dtype=torch.float64)
    history: list[dict[str, Any]] = []
    started = time.perf_counter()

    optimizer = torch.optim.Adam(model.parameters(), lr=float(training["stage1_learning_rate"]))
    for step in range(1, int(training["stage1_steps"]) + 1):
        optimizer.zero_grad(set_to_none=True)
        predicted = _model_normalized_coefficients(
            model_kind, model, ordered, protocol_normalization, history_normalization
        )
        loss = torch.mean((predicted - target_all) ** 2)
        if not bool(torch.isfinite(loss)):
            raise FloatingPointError(f"nonfinite {model_kind} stage1 loss")
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), float(training["gradient_clip_norm"]))
        optimizer.step()
        history.append(
            {
                "seed": seed,
                "model": model_kind,
                "stage": 1,
                "step": step,
                "learning_rate": float(training["stage1_learning_rate"]),
                "coefficient": float(loss.detach()),
                "total": float(loss.detach()),
                "finite": True,
                "elapsed_s": time.perf_counter() - started,
            }
        )
        if time.perf_counter() - started > float(training["maximum_wall_time_s_per_network"]):
            raise TimeoutError(f"{model_kind} exceeded the frozen network wall budget")

    optimizer = torch.optim.Adam(model.parameters(), lr=float(training["stage2_learning_rate"]))
    batch_size = int(training["stage2_batch_size"])
    weights = {str(key): float(value) for key, value in training["fixed_loss_weights"].items()}
    count = len(ordered)
    for stage_step in range(1, int(training["stage2_steps"]) + 1):
        indices = [((stage_step - 1) * batch_size + offset) % count for offset in range(batch_size)]
        batch = [ordered[index] for index in indices]
        target = target_all.index_select(0, torch.as_tensor(indices, dtype=torch.long))
        optimizer.zero_grad(set_to_none=True)
        losses = _training_loss_groups(
            model_kind=model_kind,
            model=model,
            samples=batch,
            target_normalized_coefficients=target,
            pod=pod,
            operators=operators,
            protocol_normalization=protocol_normalization,
            history_normalization=history_normalization,
            config=config,
        )
        if set(losses) != set(weights):
            raise RuntimeError(f"{model_kind} training loss groups do not match the frozen contract")
        total = sum(weights[name] * losses[name] for name in weights)
        if not bool(torch.isfinite(total)):
            raise FloatingPointError(f"nonfinite {model_kind} stage2 loss")
        total.backward()
        gradient_norm = float(
            torch.nn.utils.clip_grad_norm_(model.parameters(), float(training["gradient_clip_norm"]))
        )
        optimizer.step()
        row: dict[str, Any] = {
            "seed": seed,
            "model": model_kind,
            "stage": 2,
            "step": int(training["stage1_steps"]) + stage_step,
            "learning_rate": float(training["stage2_learning_rate"]),
            "total": float(total.detach()),
            "gradient_norm": gradient_norm,
            "finite": True,
            "elapsed_s": time.perf_counter() - started,
        }
        row.update({name: float(value.detach()) for name, value in losses.items()})
        history.append(row)
        if time.perf_counter() - started > float(training["maximum_wall_time_s_per_network"]):
            raise TimeoutError(f"{model_kind} exceeded the frozen network wall budget")

    return history, {
        "seed": seed,
        "model": model_kind,
        "stage1_steps": int(training["stage1_steps"]),
        "stage2_steps": int(training["stage2_steps"]),
        "total_steps": int(training["stage1_steps"]) + int(training["stage2_steps"]),
        "wall_time_s": time.perf_counter() - started,
        "parameter_count": sum(parameter.numel() for parameter in model.parameters()),
    }


def _ridge_initial_temperature(
    samples: Sequence[ProtocolSample],
    ridge: Degree2Ridge,
    normalization: InputNormalization,
    pod: ThermalPOD,
    config: Mapping[str, Any],
) -> Tensor:
    raw = protocol_raw_inputs(samples)
    normalized = normalize_inputs(raw, normalization)
    coefficients = predict_degree2_ridge(ridge, normalized)
    return _decode_normalized(torch.as_tensor(coefficients, dtype=torch.float64), pod, config)


def _neural_initial_temperature(
    model_kind: str,
    model: torch.nn.Module,
    samples: Sequence[ProtocolSample],
    pod: ThermalPOD,
    protocol_normalization: InputNormalization,
    history_normalization: InputNormalization,
    config: Mapping[str, Any],
) -> Tensor:
    coefficients = _model_normalized_coefficients(
        model_kind, model, samples, protocol_normalization, history_normalization
    )
    return _decode_normalized(coefficients, pod, config)


def _zero_projection_output(
    operator: M1SelfConsistentIMTProjection,
    temperature_K: Tensor,
    sample: ProtocolSample,
) -> ModeOutput:
    electrical = operator.electrical(
        temperature_K, sample.voltage_V, sample.branch_value
    )
    thermal = operator.thermal_diagnostics(
        temperature_K,
        electrical["total_joule_cell_W"],
        sample.sink_amplitude,
    )
    fields = {**electrical, **thermal}
    fields["effective_conductive_state_coordinate"] = operator.equilibrium_state(
        temperature_K, sample.branch_value
    )
    fields["conductivity_S_m"] = operator.conductivity(
        temperature_K, sample.branch_value
    )
    lookahead = operator.projection(
        temperature_K, sample.voltage_V, sample.branch_value, sample.sink_amplitude
    )
    next_temperature = lookahead["temperature_K"]
    fixed = _fixed_defect(next_temperature, temperature_K, operator.ambient_temperature_K)
    sigma = _relative_l2(
        operator.conductivity(next_temperature, sample.branch_value),
        operator.conductivity(temperature_K, sample.branch_value),
    )
    return ModeOutput(
        temperature_K=temperature_K,
        fields=fields,
        fixed_point_defect=fixed,
        sigma_defect=sigma,
        projection_count=0,
        main_linear_solve_count=1,
    )


def _projected_output(
    operator: M1SelfConsistentIMTProjection,
    temperature0_K: Tensor,
    sample: ProtocolSample,
    projection_count: int,
) -> ModeOutput:
    if projection_count not in {1, 2}:
        raise ValueError("matched-budget mode requires one or two projections")
    state = temperature0_K
    fields: dict[str, Tensor] | None = None
    for _ in range(projection_count):
        fields = operator.projection(
            state, sample.voltage_V, sample.branch_value, sample.sink_amplitude
        )
        state = fields["temperature_K"]
    assert fields is not None
    lookahead = operator.projection(
        state, sample.voltage_V, sample.branch_value, sample.sink_amplitude
    )
    fixed = _fixed_defect(lookahead["temperature_K"], state, operator.ambient_temperature_K)
    sigma = _relative_l2(
        operator.conductivity(lookahead["temperature_K"], sample.branch_value),
        operator.conductivity(state, sample.branch_value),
    )
    return ModeOutput(
        temperature_K=state,
        fields=fields,
        fixed_point_defect=fixed,
        sigma_defect=sigma,
        projection_count=projection_count,
        main_linear_solve_count=2 * projection_count,
    )


def _output_metrics(
    output: ModeOutput,
    sample: ProtocolSample,
    operator: M1SelfConsistentIMTProjection,
    config: Mapping[str, Any],
) -> dict[str, Any]:
    reference = sample.point.result
    potential = output.fields["potential_V"]
    current = output.fields["source_current_A"]
    mean_state = float(torch.mean(operator.equilibrium_state(output.temperature_K, sample.branch_value)))
    T_error = _temperature_rise_error(
        output.temperature_K,
        reference.temperature_K,
        float(config["reference"]["ambient_temperature_K"]),
    )
    phi_error = _relative_l2(potential, reference.fields["potential_V"])
    current_error = _scalar_error(current, reference.metrics["terminal_current_A"])
    terminal_ledger = float(output.fields["terminal_electrical_heat_ledger_error"])
    sink_ledger_value = output.fields.get(
        "raw_subsolve_feedback_heat_sink_ledger_error",
        output.fields.get("electrical_heat_sink_ledger_error", torch.as_tensor(math.nan)),
    )
    sink_ledger = float(sink_ledger_value)
    finite = bool(
        torch.isfinite(output.temperature_K).all()
        and torch.isfinite(potential).all()
        and math.isfinite(current_error)
        and math.isfinite(output.fixed_point_defect)
        and math.isfinite(output.sigma_defect)
        and math.isfinite(terminal_ledger)
        and math.isfinite(sink_ledger)
    )
    gates = config["evaluation"]["practical_gates"]
    complete = bool(
        finite
        and T_error <= float(gates["temperature_rise_relative_l2_max"])
        and phi_error <= float(gates["potential_relative_l2_max"])
        and current_error <= float(gates["terminal_current_relative_error_max"])
        and output.fixed_point_defect <= float(gates["fixed_point_defect_max"])
        and output.sigma_defect <= float(gates["sigma_defect_max"])
        and terminal_ledger <= float(gates["terminal_electrical_heat_ledger_max"])
        and sink_ledger <= float(gates["electrical_heat_sink_ledger_max"])
    )
    return {
        "temperature_rise_relative_l2": T_error,
        "potential_relative_l2": phi_error,
        "joint_field_score": 0.5 * (T_error + phi_error),
        "terminal_current_relative_error": current_error,
        "predicted_terminal_current_A": float(current),
        "reference_terminal_current_A": float(reference.metrics["terminal_current_A"]),
        "mean_state_absolute_error": abs(mean_state - float(reference.metrics["mean_effective_state_coordinate"])),
        "predicted_mean_state": mean_state,
        "reference_mean_state": float(reference.metrics["mean_effective_state_coordinate"]),
        "hotspot_coordinate_error": _hotspot_error(output.temperature_K, reference.temperature_K),
        "true_fixed_point_defect": output.fixed_point_defect,
        "sigma_defect": output.sigma_defect,
        "terminal_electrical_heat_ledger_error": terminal_ledger,
        "electrical_heat_sink_ledger_error": sink_ledger,
        "projection_count": output.projection_count,
        "main_linear_solve_count": output.main_linear_solve_count,
        "diagnostic_projection_count": output.diagnostic_projection_count,
        "diagnostic_linear_solve_count": output.diagnostic_linear_solve_count,
        "diagnostic_included_in_timing": False,
        "finite": finite,
        "practical_complete_case_pass": complete,
    }


def evaluate_modes(
    *,
    samples: Sequence[ProtocolSample],
    operators: Mapping[str, M1SelfConsistentIMTProjection],
    pod: ThermalPOD,
    ridge: Degree2Ridge,
    models_by_seed: Mapping[int, Mapping[str, torch.nn.Module]],
    protocol_normalization: InputNormalization,
    history_normalization: InputNormalization,
    config: Mapping[str, Any],
    include_baselines: bool = True,
) -> tuple[list[dict[str, Any]], dict[tuple[int, str, str], ModeOutput]]:
    targets = sorted(
        {
            sample.sample_id: sample
            for sample in samples
            if sample.split.startswith("validation") or sample.full_curve_test or sample.headline_test
        }.values(),
        key=lambda sample: sample.sample_id,
    )
    rows: list[dict[str, Any]] = []
    cache: dict[tuple[int, str, str], ModeOutput] = {}
    initial_seed = int(config["training"]["initial_seed"])
    with torch.no_grad():
        for sample in targets:
            operator = operators[sample.context_id]
            analytic0 = torch.full(
                (operator.ny, operator.nx),
                325.0 if sample.branch_label == "heating" else 360.0,
                dtype=torch.float64,
            )
            ridge0 = _ridge_initial_temperature(
                [sample], ridge, protocol_normalization, pod, config
            )[0]
            if include_baselines:
                baseline_initials = {"A": analytic0, "R": ridge0}
                for prefix, initial in baseline_initials.items():
                    for depth in (1, 2):
                        mode = f"{prefix}{depth}"
                        output = _projected_output(operator, initial, sample, depth)
                        cache[(0, mode, sample.sample_id)] = output
                        row = {
                            "seed": 0,
                            "mode": mode,
                            "sample_id": sample.sample_id,
                            "context_id": sample.context_id,
                            "protocol_id": sample.protocol_id,
                            "branch_label": sample.branch_label,
                            "device_voltage_V": sample.voltage_V,
                            "split": sample.split,
                            "full_curve_test": sample.full_curve_test,
                            "headline_test": sample.headline_test,
                            "event_neighborhood": False,
                        }
                        row.update(_output_metrics(output, sample, operator, config))
                        rows.append(row)

            for seed, models in sorted(models_by_seed.items()):
                kinds = ("H", "S", "G") if seed == initial_seed else ("S", "G")
                for kind in kinds:
                    initial = _neural_initial_temperature(
                        kind,
                        models[kind],
                        [sample],
                        pod,
                        protocol_normalization,
                        history_normalization,
                        config,
                    )[0]
                    depths = (0, 1, 2) if kind == "H" else (1, 2)
                    for depth in depths:
                        mode = f"{kind}{depth}"
                        output = (
                            _zero_projection_output(operator, initial, sample)
                            if depth == 0
                            else _projected_output(operator, initial, sample, depth)
                        )
                        cache[(seed, mode, sample.sample_id)] = output
                        row = {
                            "seed": seed,
                            "mode": mode,
                            "sample_id": sample.sample_id,
                            "context_id": sample.context_id,
                            "protocol_id": sample.protocol_id,
                            "branch_label": sample.branch_label,
                            "device_voltage_V": sample.voltage_V,
                            "split": sample.split,
                            "full_curve_test": sample.full_curve_test,
                            "headline_test": sample.headline_test,
                            "event_neighborhood": False,
                        }
                        row.update(_output_metrics(output, sample, operator, config))
                        rows.append(row)
    event_rows = [sample for sample in targets if sample.context_id == "G1" and sample.branch_label == "cooling"]
    event_center = 1.0640625
    half_width = float(config["evaluation"]["event_neighborhood_half_width_V"])
    event_ids = {sample.sample_id for sample in event_rows if abs(sample.voltage_V - event_center) <= half_width + 1.0e-12}
    for row in rows:
        row["event_neighborhood"] = row["sample_id"] in event_ids
    return rows, cache


def _fixed_defect(next_temperature: Tensor, temperature: Tensor, ambient: float) -> float:
    return float(
        torch.linalg.vector_norm(next_temperature - temperature)
        / torch.clamp(torch.linalg.vector_norm(next_temperature - ambient), min=1.0e-30)
    )


def _pair_joint_error(output: ModeOutput, reference: ProtocolSample, ambient: float) -> float:
    return 0.5 * (
        _temperature_rise_error(output.temperature_K, reference.point.result.temperature_K, ambient)
        + _relative_l2(output.fields["potential_V"], reference.point.result.fields["potential_V"])
    )


def _g1_common_pairs(samples: Sequence[ProtocolSample]) -> list[tuple[ProtocolSample, ProtocolSample]]:
    heating = {
        round(sample.voltage_V, 10): sample
        for sample in samples
        if sample.context_id == "G1" and sample.branch_label == "heating" and sample.full_curve_test
    }
    cooling = {
        round(sample.voltage_V, 10): sample
        for sample in samples
        if sample.context_id == "G1" and sample.branch_label == "cooling" and sample.full_curve_test
    }
    voltages = sorted(set(heating).intersection(cooling))
    if len(voltages) != 33:
        raise ValueError("G1 common-voltage full curve must contain 33 pairs")
    return [(heating[voltage], cooling[voltage]) for voltage in voltages]


def branch_separation_metrics(
    *,
    samples: Sequence[ProtocolSample],
    cache: Mapping[tuple[int, str, str], ModeOutput],
    modes_by_seed: Mapping[int, Sequence[str]],
    config: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], dict[tuple[int, str], dict[str, Any]]]:
    ambient = float(config["reference"]["ambient_temperature_K"])
    pairs = _g1_common_pairs(samples)
    rows: list[dict[str, Any]] = []
    summaries: dict[tuple[int, str], dict[str, Any]] = {}
    for seed, modes in modes_by_seed.items():
        for mode in modes:
            seed_key = 0 if mode.startswith(("A", "R")) else seed
            mode_rows: list[dict[str, Any]] = []
            for heating, cooling in pairs:
                output_heating = cache[(seed_key, mode, heating.sample_id)]
                output_cooling = cache[(seed_key, mode, cooling.sample_id)]
                reference_current_sep = _symmetric_separation(
                    float(heating.point.result.metrics["terminal_current_A"]),
                    float(cooling.point.result.metrics["terminal_current_A"]),
                )
                predicted_current_sep = _symmetric_separation(
                    float(output_heating.fields["source_current_A"]),
                    float(output_cooling.fields["source_current_A"]),
                )
                reference_temperature_sep = _temperature_separation(
                    heating.point.result.temperature_K, cooling.point.result.temperature_K, ambient
                )
                predicted_temperature_sep = _temperature_separation(
                    output_heating.temperature_K, output_cooling.temperature_K, ambient
                )
                current_sep_error = abs(predicted_current_sep - reference_current_sep) / max(
                    reference_current_sep, 1.0e-30
                )
                temperature_sep_error = abs(predicted_temperature_sep - reference_temperature_sep) / max(
                    reference_temperature_sep, 1.0e-30
                )
                direct = _pair_joint_error(output_heating, heating, ambient) + _pair_joint_error(
                    output_cooling, cooling, ambient
                )
                swapped = _pair_joint_error(output_heating, cooling, ambient) + _pair_joint_error(
                    output_cooling, heating, ambient
                )
                certified = bool(heating.headline_test and cooling.headline_test)
                row = {
                    "seed": seed,
                    "mode": mode,
                    "device_voltage_V": heating.voltage_V,
                    "certified_same_voltage_pair": certified,
                    "reference_current_separation": reference_current_sep,
                    "predicted_current_separation": predicted_current_sep,
                    "reference_temperature_rise_separation": reference_temperature_sep,
                    "predicted_temperature_rise_separation": predicted_temperature_sep,
                    "current_separation_relative_error": current_sep_error,
                    "temperature_separation_relative_error": temperature_sep_error,
                    "maximum_separation_relative_error": max(current_sep_error, temperature_sep_error),
                    "direct_assignment_joint_error": direct,
                    "swapped_assignment_joint_error": swapped,
                    "head_swap": bool(swapped + 1.0e-15 < direct),
                }
                rows.append(row)
                mode_rows.append(row)
            certified_rows = [row for row in mode_rows if row["certified_same_voltage_pair"]]
            certified_pass = bool(
                len(certified_rows) == int(config["branch_separation"]["certified_pair_count"])
                and sum(bool(row["head_swap"]) for row in certified_rows)
                <= int(config["branch_separation"]["certified_head_swap_max"])
                and max(float(row["maximum_separation_relative_error"]) for row in certified_rows)
                <= float(config["branch_separation"]["certified_separation_relative_error_max"])
            )
            full_fraction = float(
                np.mean(
                    [
                        float(row["maximum_separation_relative_error"])
                        <= float(config["branch_separation"]["full_curve_separation_relative_error_max"])
                        for row in mode_rows
                    ]
                )
            )
            full_pass = full_fraction >= float(
                config["branch_separation"]["full_curve_fraction_within_error_min"]
            )
            summaries[(seed, mode)] = {
                "certified_pair_count": len(certified_rows),
                "certified_head_swap_count": sum(bool(row["head_swap"]) for row in certified_rows),
                "certified_maximum_separation_relative_error": max(
                    (float(row["maximum_separation_relative_error"]) for row in certified_rows), default=math.inf
                ),
                "full_curve_fraction_within_0p20": full_fraction,
                "certified_gate_pass": certified_pass,
                "full_curve_gate_pass": full_pass,
                "branch_separation_gate_pass": bool(certified_pass and full_pass),
            }
    return rows, summaries


def unknown_protocol_metrics(
    *,
    samples: Sequence[ProtocolSample],
    cache: Mapping[tuple[int, str, str], ModeOutput],
    seeds: Sequence[int],
    config: Mapping[str, Any],
    operators: Mapping[str, M1SelfConsistentIMTProjection],
) -> tuple[list[dict[str, Any]], dict[tuple[int, str], dict[str, Any]]]:
    pairs = _g1_common_pairs(samples)
    rows: list[dict[str, Any]] = []
    summaries: dict[tuple[int, str], dict[str, Any]] = {}
    reference_threshold = float(config["unknown_protocol"]["reference_practical_ambiguity_min"])
    predicted_threshold = float(config["unknown_protocol"]["predicted_ambiguity_min"])
    for seed in seeds:
        for mode in ("S1", "S2", "G1", "G2"):
            mode_rows: list[dict[str, Any]] = []
            for heating, cooling in pairs:
                output_heating = cache[(seed, mode, heating.sample_id)]
                output_cooling = cache[(seed, mode, cooling.sample_id)]
                ref_I = _symmetric_separation(
                    float(heating.point.result.metrics["terminal_current_A"]),
                    float(cooling.point.result.metrics["terminal_current_A"]),
                )
                ref_T = _temperature_separation(
                    heating.point.result.temperature_K,
                    cooling.point.result.temperature_K,
                    float(config["reference"]["ambient_temperature_K"]),
                )
                pred_I = _symmetric_separation(
                    float(output_heating.fields["source_current_A"]),
                    float(output_cooling.fields["source_current_A"]),
                )
                pred_T = _temperature_separation(
                    output_heating.temperature_K,
                    output_cooling.temperature_K,
                    float(config["reference"]["ambient_temperature_K"]),
                )
                decision = unknown_protocol_decision(
                    heating_candidate={"sample_id": heating.sample_id, "mode": mode},
                    cooling_candidate={"sample_id": cooling.sample_id, "mode": mode},
                    predicted_current_separation=pred_I,
                    predicted_temperature_separation=pred_T,
                    ambiguity_threshold=predicted_threshold,
                )
                reference_ambiguous = bool(max(ref_I, ref_T) >= reference_threshold)
                predicted_ambiguous = decision.status == "AMBIGUOUS_PROTOCOL"
                direct_coverage = bool(
                    _output_metrics(output_heating, heating, operators["G1"], config)["practical_complete_case_pass"]
                    and _output_metrics(output_cooling, cooling, operators["G1"], config)["practical_complete_case_pass"]
                )
                swapped_coverage = bool(
                    _output_metrics(output_heating, cooling, operators["G1"], config)["practical_complete_case_pass"]
                    and _output_metrics(output_cooling, heating, operators["G1"], config)["practical_complete_case_pass"]
                )
                set_covered = bool(reference_ambiguous and (direct_coverage or swapped_coverage))
                certified = bool(heating.headline_test and cooling.headline_test)
                row = {
                    "seed": seed,
                    "mode": mode,
                    "device_voltage_V": heating.voltage_V,
                    "certified_same_voltage_pair": certified,
                    "reference_current_separation": ref_I,
                    "reference_temperature_rise_separation": ref_T,
                    "reference_practical_ambiguity": reference_ambiguous,
                    "predicted_current_separation": pred_I,
                    "predicted_temperature_rise_separation": pred_T,
                    "output_status": decision.status,
                    "predicted_ambiguous_protocol": predicted_ambiguous,
                    "false_unique": bool(reference_ambiguous and not predicted_ambiguous),
                    "two_candidate_set_covered": set_covered,
                    "candidate_assignment": "direct" if direct_coverage else ("swapped" if swapped_coverage else "uncovered"),
                    "candidate_averaging_used": decision.candidate_averaging_used,
                    "unique_region_false_refusal": bool(not reference_ambiguous and predicted_ambiguous),
                }
                rows.append(row)
                mode_rows.append(row)
            ambiguous = [row for row in mode_rows if row["reference_practical_ambiguity"]]
            certified_ambiguous = [
                row for row in ambiguous if row["certified_same_voltage_pair"]
            ]
            recall = float(np.mean([row["predicted_ambiguous_protocol"] for row in ambiguous])) if ambiguous else 1.0
            certified_recall = (
                float(np.mean([row["predicted_ambiguous_protocol"] for row in certified_ambiguous]))
                if certified_ambiguous
                else 1.0
            )
            coverage = float(np.mean([row["two_candidate_set_covered"] for row in ambiguous])) if ambiguous else 1.0
            certified_false_unique = sum(bool(row["false_unique"]) for row in certified_ambiguous)
            gate = bool(
                certified_recall >= float(config["unknown_protocol"]["certified_ambiguity_recall_min"])
                and recall >= float(config["unknown_protocol"]["full_curve_ambiguity_recall_min"])
                and certified_false_unique <= int(config["unknown_protocol"]["certified_false_unique_max"])
                and coverage >= float(config["unknown_protocol"]["two_candidate_set_coverage_min"])
                and not any(bool(row["candidate_averaging_used"]) for row in mode_rows)
            )
            summaries[(seed, mode)] = {
                "reference_ambiguous_pair_count": len(ambiguous),
                "certified_ambiguous_pair_count": len(certified_ambiguous),
                "certified_ambiguity_recall": certified_recall,
                "full_curve_ambiguity_recall": recall,
                "certified_false_unique_count": certified_false_unique,
                "two_candidate_set_coverage": coverage,
                "unique_region_false_refusal_count": sum(
                    bool(row["unique_region_false_refusal"]) for row in mode_rows
                ),
                "candidate_averaging_used": False,
                "unknown_protocol_gate_pass": gate,
            }
    return rows, summaries


def _timed_mode_call(
    *,
    sample: ProtocolSample,
    mode: str,
    seed: int,
    operator: M1SelfConsistentIMTProjection,
    pod: ThermalPOD,
    ridge: Degree2Ridge,
    models: Mapping[str, torch.nn.Module],
    protocol_normalization: InputNormalization,
    history_normalization: InputNormalization,
    config: Mapping[str, Any],
) -> Tensor:
    prefix = mode[0]
    depth = int(mode[1])
    if prefix == "A":
        state = torch.full(
            (operator.ny, operator.nx),
            325.0 if sample.branch_label == "heating" else 360.0,
            dtype=torch.float64,
        )
    elif prefix == "R":
        state = _ridge_initial_temperature(
            [sample], ridge, protocol_normalization, pod, config
        )[0]
    else:
        state = _neural_initial_temperature(
            prefix,
            models[prefix],
            [sample],
            pod,
            protocol_normalization,
            history_normalization,
            config,
        )[0]
    for _ in range(depth):
        state = operator.projection(
            state, sample.voltage_V, sample.branch_value, sample.sink_amplitude
        )["temperature_K"]
    return state


def benchmark_random_access(
    *,
    samples: Sequence[ProtocolSample],
    operators: Mapping[str, M1SelfConsistentIMTProjection],
    pod: ThermalPOD,
    ridge: Degree2Ridge,
    models_by_seed: Mapping[int, Mapping[str, torch.nn.Module]],
    protocol_normalization: InputNormalization,
    history_normalization: InputNormalization,
    config: Mapping[str, Any],
) -> list[dict[str, Any]]:
    torch.set_num_threads(int(config["evaluation"]["torch_threads"]))
    headline = sorted((sample for sample in samples if sample.headline_test), key=lambda item: item.sample_id)
    repeats = int(config["evaluation"]["fast_timing_repeats"])
    initial_seed = int(config["training"]["initial_seed"])
    rows: list[dict[str, Any]] = []
    with torch.no_grad():
        for seed, models in sorted(models_by_seed.items()):
            modes = ["A1", "A2", "R1", "R2", "H1", "H2", "S1", "S2", "G1", "G2"] if seed == initial_seed else ["S1", "S2", "G1", "G2"]
            for sample in headline:
                operator = operators[sample.context_id]
                for mode in modes:
                    mode_seed = 0 if mode.startswith(("A", "R")) else seed
                    _timed_mode_call(
                        sample=sample,
                        mode=mode,
                        seed=mode_seed,
                        operator=operator,
                        pod=pod,
                        ridge=ridge,
                        models=models,
                        protocol_normalization=protocol_normalization,
                        history_normalization=history_normalization,
                        config=config,
                    )
                    for repeat in range(repeats):
                        started = time.perf_counter()
                        _timed_mode_call(
                            sample=sample,
                            mode=mode,
                            seed=mode_seed,
                            operator=operator,
                            pod=pod,
                            ridge=ridge,
                            models=models,
                            protocol_normalization=protocol_normalization,
                            history_normalization=history_normalization,
                            config=config,
                        )
                        rows.append(
                            {
                                "timing_kind": "random_access",
                                "seed": mode_seed,
                                "mode": mode,
                                "sample_id": sample.sample_id,
                                "protocol_id": sample.protocol_id,
                                "device_voltage_V": sample.voltage_V,
                                "repeat_index": repeat,
                                "wall_s": time.perf_counter() - started,
                                "projection_count": int(mode[1]),
                                "linear_solve_count": 2 * int(mode[1]),
                                "network_forward_included": mode.startswith(("H", "S", "G")),
                                "diagnostic_lookahead_included": False,
                            }
                        )
    return rows


def benchmark_sequential_continuation(
    *,
    old_runs: Sequence[ProtocolRun],
    operator: M1SelfConsistentIMTProjection,
    config: Mapping[str, Any],
) -> list[dict[str, Any]]:
    repeats = int(config["evaluation"]["sequential_timing_repeats"])
    rows: list[dict[str, Any]] = []
    with torch.no_grad():
        for run in old_runs:
            if run.spec.context_id != "G1":
                continue
            edge_medians: list[float] = []
            for edge_index, (previous, target) in enumerate(
                zip(run.coarse_points, run.coarse_points[1:]), start=1
            ):
                durations: list[float] = []
                for repeat in range(repeats):
                    started = time.perf_counter()
                    result = solve_fixed_point(
                        operator=operator,
                        initial_temperature_K=previous.result.temperature_K,
                        voltage_V=target.voltage_V,
                        branch=run.spec.branch_value,
                        sink_amplitude=run.spec.sink_amplitude,
                        solver_config=config["solver"],
                    )
                    duration = time.perf_counter() - started
                    durations.append(duration)
                    rows.append(
                        {
                            "timing_kind": "sequential_stored_edge_replay",
                            "seed": 0,
                            "mode": "SEQUENTIAL",
                            "sample_id": target.point_id,
                            "protocol_id": run.spec.protocol_id,
                            "device_voltage_V": target.voltage_V,
                            "repeat_index": repeat,
                            "wall_s": duration,
                            "projection_count": int(result.metrics["iterations"]),
                            "linear_solve_count": 2 * int(result.metrics["iterations"]) + 1,
                            "network_forward_included": False,
                            "diagnostic_lookahead_included": False,
                            "stored_predecessor_replay": True,
                            "finite": bool(result.metrics["finite"]),
                            "converged": bool(result.metrics["converged"]),
                        }
                    )
                edge_medians.append(float(np.median(durations)))
                rows.append(
                    {
                        "timing_kind": "sequential_endpoint_to_target_summary",
                        "seed": 0,
                        "mode": "SEQUENTIAL",
                        "sample_id": target.point_id,
                        "protocol_id": run.spec.protocol_id,
                        "device_voltage_V": target.voltage_V,
                        "repeat_index": -1,
                        "wall_s": float(np.sum(edge_medians)),
                        "edge_count": edge_index,
                        "stored_predecessor_replay": True,
                    }
                )
    return rows


def timing_medians(rows: Sequence[Mapping[str, Any]]) -> dict[tuple[int, str], float]:
    groups: dict[tuple[int, str], list[float]] = {}
    for row in rows:
        if row.get("timing_kind") != "random_access":
            continue
        key = (int(row["seed"]), str(row["mode"]))
        groups.setdefault(key, []).append(float(row["wall_s"]))
    return {key: float(np.median(values)) for key, values in groups.items()}


def aggregate_mode_metrics(rows: Sequence[Mapping[str, Any]]) -> dict[tuple[int, str], dict[str, Any]]:
    groups: dict[tuple[int, str], list[Mapping[str, Any]]] = {}
    for row in rows:
        if not bool(row.get("headline_test", False)):
            continue
        key = (int(row["seed"]), str(row["mode"]))
        groups.setdefault(key, []).append(row)
    result: dict[tuple[int, str], dict[str, Any]] = {}
    for key, values in groups.items():
        result[key] = {
            "headline_case_count": len(values),
            "headline_complete_pass_count": sum(bool(value["practical_complete_case_pass"]) for value in values),
            "headline_complete_pass_fraction": float(
                np.mean([bool(value["practical_complete_case_pass"]) for value in values])
            ),
            "mean_temperature_rise_relative_l2": float(np.mean([float(value["temperature_rise_relative_l2"]) for value in values])),
            "mean_potential_relative_l2": float(np.mean([float(value["potential_relative_l2"]) for value in values])),
            "mean_joint_field_score": float(np.mean([float(value["joint_field_score"]) for value in values])),
            "mean_terminal_current_relative_error": float(np.mean([float(value["terminal_current_relative_error"]) for value in values])),
            "maximum_fixed_point_defect": max(float(value["true_fixed_point_defect"]) for value in values),
            "maximum_sigma_defect": max(float(value["sigma_defect"]) for value in values),
        }
    return result


def _improvement(candidate: float, baseline: float) -> float:
    return (baseline - candidate) / max(abs(baseline), 1.0e-30)


def seed_gate_summary(
    *,
    seed: int,
    aggregates: Mapping[tuple[int, str], Mapping[str, Any]],
    branch_summaries: Mapping[tuple[int, str], Mapping[str, Any]],
    refusal_summaries: Mapping[tuple[int, str], Mapping[str, Any]],
    timing: Mapping[tuple[int, str], float],
    config: Mapping[str, Any],
) -> dict[str, Any]:
    """Apply the preregistered matched-budget paths for one neural seed."""

    gates = config["decision_gates"]

    def aggregate(mode: str) -> Mapping[str, Any]:
        key = (0, mode) if mode.startswith(("A", "R")) else (seed, mode)
        if key not in aggregates:
            raise KeyError(f"missing aggregate for {key}")
        return aggregates[key]

    def joint(mode: str) -> float:
        return float(aggregate(mode)["mean_joint_field_score"])

    def passes(mode: str) -> int:
        return int(aggregate(mode)["headline_complete_pass_count"])

    def pass_fraction(mode: str) -> float:
        return float(aggregate(mode)["headline_complete_pass_fraction"])

    def branch_pass(mode: str) -> bool:
        return bool(branch_summaries[(seed, mode)]["branch_separation_gate_pass"])

    def refusal_pass(mode: str) -> bool:
        return bool(refusal_summaries[(seed, mode)]["unknown_protocol_gate_pass"])

    a2_time = float(timing[(0, "A2")])
    h_improvement_a1 = _improvement(joint("G1"), joint("A1"))
    h_improvement_r1 = _improvement(joint("G1"), joint("R1"))
    h_improvement_s1 = _improvement(joint("G1"), joint("S1"))
    h_speedup = a2_time / max(float(timing[(seed, "G1")]), 1.0e-30)
    path_h = bool(
        pass_fraction("G1") >= float(gates["headline_complete_pass_fraction_min"])
        and h_improvement_a1 >= float(gates["one_projection_improvement_vs_A1_min"])
        and h_improvement_r1 >= float(gates["one_projection_improvement_vs_R1_min"])
        and h_improvement_s1 >= float(gates["one_projection_improvement_vs_S1_min"])
        and h_speedup >= float(gates["one_projection_speedup_vs_A2_min"])
        and branch_pass("G1")
        and refusal_pass("G1")
    )

    s_improvement_a2 = _improvement(joint("G2"), joint("A2"))
    s_additional_passes = passes("G2") - passes("A2")
    s_improvement_r2 = _improvement(joint("G2"), joint("R2"))
    s_improvement_s2 = _improvement(joint("G2"), joint("S2"))
    s_wall_ratio = float(timing[(seed, "G2")]) / max(a2_time, 1.0e-30)
    path_s = bool(
        pass_fraction("G2") >= float(gates["headline_complete_pass_fraction_min"])
        and (
            s_improvement_a2 >= float(gates["two_projection_improvement_vs_A2_min"])
            or s_additional_passes >= int(gates["two_projection_additional_passes_vs_A2_min"])
        )
        and s_improvement_r2 >= float(gates["two_projection_improvement_vs_R2_min"])
        and s_improvement_s2 >= float(gates["two_projection_improvement_vs_S2_min"])
        and s_wall_ratio <= float(gates["two_projection_wall_ratio_vs_A2_max"])
        and branch_pass("G2")
        and refusal_pass("G2")
    )

    s1_value = bool(
        pass_fraction("S1") >= float(gates["headline_complete_pass_fraction_min"])
        and _improvement(joint("S1"), joint("A1"))
        >= float(gates["one_projection_improvement_vs_A1_min"])
        and _improvement(joint("S1"), joint("R1"))
        >= float(gates["one_projection_improvement_vs_R1_min"])
        and a2_time / max(float(timing[(seed, "S1")]), 1.0e-30)
        >= float(gates["one_projection_speedup_vs_A2_min"])
        and branch_pass("S1")
        and refusal_pass("S1")
    )
    s2_value = bool(
        pass_fraction("S2") >= float(gates["headline_complete_pass_fraction_min"])
        and (
            _improvement(joint("S2"), joint("A2"))
            >= float(gates["two_projection_improvement_vs_A2_min"])
            or passes("S2") - passes("A2")
            >= int(gates["two_projection_additional_passes_vs_A2_min"])
        )
        and _improvement(joint("S2"), joint("R2"))
        >= float(gates["two_projection_improvement_vs_R2_min"])
        and float(timing[(seed, "S2")]) / max(a2_time, 1.0e-30)
        <= float(gates["two_projection_wall_ratio_vs_A2_max"])
        and branch_pass("S2")
        and refusal_pass("S2")
    )
    partial = bool(
        (s1_value and h_improvement_s1 < float(gates["one_projection_improvement_vs_S1_min"]))
        or (s2_value and s_improvement_s2 < float(gates["two_projection_improvement_vs_S2_min"]))
    )
    candidate_path = "path_h" if path_h else ("path_s" if path_s else ("partial" if partial else "none"))
    return {
        "seed": seed,
        "path_h_pass": path_h,
        "path_s_pass": path_s,
        "partial_path_pass": partial,
        "candidate_path": candidate_path,
        "G1_headline_complete_pass_fraction": pass_fraction("G1"),
        "G1_mean_joint_field_score": joint("G1"),
        "G1_improvement_vs_A1": h_improvement_a1,
        "G1_improvement_vs_R1": h_improvement_r1,
        "G1_improvement_vs_S1": h_improvement_s1,
        "G1_speedup_vs_A2": h_speedup,
        "G1_branch_gate_pass": branch_pass("G1"),
        "G1_refusal_gate_pass": refusal_pass("G1"),
        "G2_headline_complete_pass_fraction": pass_fraction("G2"),
        "G2_mean_joint_field_score": joint("G2"),
        "G2_improvement_vs_A2": s_improvement_a2,
        "G2_additional_passes_vs_A2": s_additional_passes,
        "G2_improvement_vs_R2": s_improvement_r2,
        "G2_improvement_vs_S2": s_improvement_s2,
        "G2_wall_ratio_vs_A2": s_wall_ratio,
        "G2_branch_gate_pass": branch_pass("G2"),
        "G2_refusal_gate_pass": refusal_pass("G2"),
        "S1_neural_specific_value_pass": s1_value,
        "S2_neural_specific_value_pass": s2_value,
    }


def final_seed_decision(
    seed_rows: Sequence[Mapping[str, Any]], config: Mapping[str, Any]
) -> dict[str, Any]:
    initial_seed = int(config["training"]["initial_seed"])
    initial = next(row for row in seed_rows if int(row["seed"]) == initial_seed)
    candidate_path = str(initial["candidate_path"])
    dispositions = config["decision_gates"]["dispositions"]
    if candidate_path == "none":
        return {
            "initial_candidate_path": "none",
            "conditional_seeds_executed": False,
            "same_path_pass_count": 0,
            "final_disposition": dispositions["no_go"],
        }
    if len(seed_rows) != 3:
        raise ValueError("an admitted initial neural path requires exactly three seeds")
    field = {
        "path_h": "path_h_pass",
        "path_s": "path_s_pass",
        "partial": "partial_path_pass",
    }[candidate_path]
    same_path_count = sum(bool(row[field]) for row in seed_rows)
    admitted = same_path_count >= int(config["decision_gates"]["conditional_seed_same_path_minimum"])
    return {
        "initial_candidate_path": candidate_path,
        "conditional_seeds_executed": True,
        "same_path_pass_count": same_path_count,
        "same_path_required_count": int(
            config["decision_gates"]["conditional_seed_same_path_minimum"]
        ),
        "final_disposition": dispositions[candidate_path] if admitted else dispositions["no_go"],
    }


def _pod_spectrum_rows(pod: ThermalPOD) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    energy = np.square(pod.singular_values)
    denominator = max(float(np.sum(energy)), 1.0e-30)
    for index, singular in enumerate(pod.singular_values, start=1):
        rows.append(
            {
                "mode_index": index,
                "singular_value": float(singular),
                "energy_fraction": float(energy[index - 1] / denominator),
                "cumulative_energy_fraction": float(pod.cumulative_energy[index - 1]),
                "selected": index <= pod.rank,
                "selected_rank": pod.rank,
                "train_sample_count": len(pod.train_case_ids),
            }
        )
    return rows


def _normalization_payload(normalization: InputNormalization) -> dict[str, Any]:
    return {
        "mean": normalization.mean,
        "scale": normalization.scale,
        "feature_names": normalization.feature_names,
        "train_sample_ids": normalization.train_sample_ids,
    }


def save_checkpoint(
    *,
    path: Path,
    seed: int,
    model_kind: str,
    model: torch.nn.Module,
    pod: ThermalPOD,
    protocol_normalization: InputNormalization,
    history_normalization: InputNormalization,
    training_summary: Mapping[str, Any],
    config: Mapping[str, Any],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "task_id": config["task_id"],
            "run_id": config["run_id"],
            "seed": seed,
            "model_kind": model_kind,
            "state_dict": model.state_dict(),
            "pod_mean_y": pod.mean_y,
            "pod_basis": pod.basis,
            "pod_coefficient_center": pod.coefficient_center,
            "pod_coefficient_scale": pod.coefficient_scale,
            "pod_rank": pod.rank,
            "pod_fit_sample_ids": pod.train_case_ids,
            "protocol_normalization": _normalization_payload(protocol_normalization),
            "history_normalization": _normalization_payload(history_normalization),
            "training_summary": dict(training_summary),
            "claim_role": "diagnostic_non_voting",
        },
        path,
    )


def save_g1_predictions(
    *,
    processed_root: Path,
    samples: Sequence[ProtocolSample],
    cache: Mapping[tuple[int, str, str], ModeOutput],
    modes_by_seed: Mapping[int, Sequence[str]],
    operators: Mapping[str, M1SelfConsistentIMTProjection],
) -> list[str]:
    selected = sorted(
        {sample.sample_id: sample for sample in samples if sample.context_id == "G1" and (sample.full_curve_test or sample.headline_test)}.values(),
        key=lambda sample: (sample.protocol_id, sample.voltage_V, sample.sample_id),
    )
    prediction_root = processed_root / "predictions"
    paths: list[str] = []
    for seed, modes in modes_by_seed.items():
        for mode in modes:
            seed_key = 0 if mode.startswith(("A", "R")) else seed
            if not all((seed_key, mode, sample.sample_id) in cache for sample in selected):
                continue
            outputs = [cache[(seed_key, mode, sample.sample_id)] for sample in selected]
            path = prediction_root / f"seed_{seed_key}" / f"{mode}_G1_predictions.npz"
            path.parent.mkdir(parents=True, exist_ok=True)
            np.savez_compressed(
                path,
                sample_id=np.asarray([sample.sample_id for sample in selected]),
                protocol_id=np.asarray([sample.protocol_id for sample in selected]),
                branch_label=np.asarray([sample.branch_label for sample in selected]),
                voltage_V=np.asarray([sample.voltage_V for sample in selected], dtype=np.float64),
                headline_test=np.asarray([sample.headline_test for sample in selected], dtype=bool),
                temperature_K=np.stack([output.temperature_K.detach().cpu().numpy() for output in outputs]),
                potential_V=np.stack([output.fields["potential_V"].detach().cpu().numpy() for output in outputs]),
                conductivity_S_m=np.stack(
                    [
                        operators["G1"].conductivity(output.temperature_K, sample.branch_value).detach().cpu().numpy()
                        for output, sample in zip(outputs, selected)
                    ]
                ),
                effective_conductive_state_coordinate=np.stack(
                    [
                        operators["G1"].equilibrium_state(output.temperature_K, sample.branch_value).detach().cpu().numpy()
                        for output, sample in zip(outputs, selected)
                    ]
                ),
                terminal_current_A=np.asarray(
                    [float(output.fields["source_current_A"]) for output in outputs], dtype=np.float64
                ),
                fixed_point_defect=np.asarray([output.fixed_point_defect for output in outputs]),
                sigma_defect=np.asarray([output.sigma_defect for output in outputs]),
                projection_count=np.asarray([output.projection_count for output in outputs], dtype=np.int64),
                candidate_averaging_used=np.asarray(False),
            )
            paths.append(path.as_posix())
    return paths


def _copy_frozen_protocol_data(
    config: Mapping[str, Any], repository_root: Path, processed_root: Path
) -> list[str]:
    historical_root = repository_root / str(config["reference"]["historical_processed_root"])
    copied: list[str] = []
    for protocol_id in ("G0_heating", "G0_cooling", "G1_heating", "G1_cooling"):
        source = historical_root / f"{protocol_id}.npz"
        destination = processed_root / f"{protocol_id}.npz"
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        copied.append(destination.as_posix())
    return copied


def rehydrate_completed_new_contexts(
    *,
    config: Mapping[str, Any],
    repository_root: Path,
    processed_root: Path,
    table_root: Path,
) -> dict[str, Any]:
    """Resume after a non-physical implementation defect without rerunning ramps."""

    resume_config = copy.deepcopy(
        load_yaml(repository_root / str(config["reference"]["historical_protocol_config"]))
    )
    resume_config["contexts"] = {
        context_id: copy.deepcopy(dict(config["contexts"][context_id]))
        for context_id in ("G2", "G3")
    }
    resume_config["budgets"]["main_protocol_ramps"] = 4
    runs = rehydrate_protocol_runs(config=resume_config, processed_root=processed_root)
    if {run.spec.protocol_id for run in runs} != {
        "G2_heating",
        "G2_cooling",
        "G3_heating",
        "G3_cooling",
    }:
        raise ValueError("resume artifacts do not contain exactly the four new-context ramps")
    all_operators = _build_all_operators(config, repository_root)
    operators = {key: all_operators[key] for key in ("G2", "G3")}

    stability_rows_raw = _read_csv(table_root / "new_context_stability_metrics.csv")
    stability_rows: list[dict[str, Any]] = []
    for row in stability_rows_raw:
        stability_rows.append(
            {
                **row,
                "finite": str(row.get("finite", "")).lower() == "true",
                "stability_class": str(row["stability_class"]),
                "context_id": str(row["context_id"]),
            }
        )
    stability_by_point: dict[str, dict[str, Any]] = {}
    for run in runs:
        with np.load(processed_root / f"{run.spec.protocol_id}.npz", allow_pickle=False) as data:
            for point_id, stability_class in zip(
                data["point_id"], data["point_stability_class"]
            ):
                label = str(stability_class)
                if label != "not_evaluated":
                    stability_by_point[str(point_id)] = {"stability_class": label}
    sensitivity_rows = _sensitivity_rows(
        runs=runs, stability_by_point=stability_by_point, config=config
    )
    context_summaries = _context_summaries(
        runs=runs,
        stability_rows=stability_rows,
        sensitivity_rows=sensitivity_rows,
        config=config,
    )
    gate_pass = bool(
        len(stability_rows) <= int(config["stability"]["maximum_new_context_states"])
        and all(summary["qualified"] for summary in context_summaries.values())
    )
    physics_rows = _read_csv(table_root / "new_context_physics_metrics.csv")
    manifest_rows = [
        row
        for row in _read_csv(table_root / "factorial_context_manifest.csv")
        if row.get("context_id") in {"G2", "G3"}
    ]
    summary = {
        "stage": "factorial_context_reference",
        "context_ids": ["G2", "G3"],
        "main_protocol_ramp_count": 4,
        "completed_protocol_ramp_count": sum(run.completed for run in runs),
        "main_protocol_point_count": sum(len(run.coarse_points) for run in runs),
        "valid_main_protocol_point_count": sum(
            point.valid for run in runs for point in run.coarse_points
        ),
        "event_count": sum(run.event is not None for run in runs),
        "resolved_event_count": sum(
            run.event is not None and run.event.resolved for run in runs
        ),
        "new_stability_spectrum_evaluation_count": len(stability_rows),
        "new_stability_budget_maximum": int(config["stability"]["maximum_new_context_states"]),
        "stable_state_count": sum(row["stability_class"] == "stable" for row in stability_rows),
        "unstable_state_count": sum(row["stability_class"] == "unstable" for row in stability_rows),
        "indeterminate_state_count": sum(
            row["stability_class"] == "indeterminate" for row in stability_rows
        ),
        "step_sensitivity_event_count": sum(bool(row.get("executed", False)) for row in sensitivity_rows),
        "step_sensitivity_all_executed_events_pass": all(
            not bool(row.get("executed", False)) or bool(row.get("pass", False))
            for row in sensitivity_rows
        ),
        "contexts": context_summaries,
        "new_context_reference_gate_pass": gate_pass,
        "surrogate_training_eligible": gate_pass,
        "stage_disposition": (
            "PASS_PROTOCOL_FACTORIAL_CONTEXT_REFERENCE"
            if gate_pass
            else "NO_GO_PROTOCOL_FACTORIAL_CONTEXT_REFERENCE"
        ),
        "failure_reasons": [] if gate_pass else ["rehydrated_context_gate_failed"],
        "root_identifier_used": False,
        "root_averaging_used": False,
        "historical_G0_G1_ramps_reexecuted": 0,
        "new_G2_G3_main_ramps_reexecuted_during_repair": 0,
        "resume_classification": "implementation_field_name_repair_after_completed_physics",
    }
    return {
        "runs": runs,
        "operators": operators,
        "stability_rows": stability_rows,
        "stability_by_point": stability_by_point,
        "sensitivity_rows": sensitivity_rows,
        "physics_rows": physics_rows,
        "manifest_rows": manifest_rows,
        "summary": summary,
    }


def _factorial_manifest_rows(
    config: Mapping[str, Any],
    repository_root: Path,
    new_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    historical = _read_csv(
        repository_root
        / str(config["reference"]["historical_table_root"])
        / "protocol_manifest.csv"
    )
    rows: list[dict[str, Any]] = []
    for row in historical:
        if row.get("context_id") not in {"G0", "G1"}:
            continue
        item = dict(row)
        item.update(
            {
                "factorial_context_label": config["contexts"][str(row["context_id"])]["label"],
                "factorial_source": "frozen_pr42_reused_without_rerun",
                "historical_protocol_reused": True,
                "main_ramp_reexecuted": False,
            }
        )
        rows.append(item)
    for row in new_rows:
        item = dict(row)
        context_id = str(row["context_id"])
        item.update(
            {
                "factorial_context_label": config["contexts"][context_id]["label"],
                "factorial_source": "new_bounded_execution",
                "historical_protocol_reused": False,
                "main_ramp_reexecuted": True,
            }
        )
        rows.append(item)
    if len(rows) != 8:
        raise ValueError(f"2x2 factorial manifest must contain eight ramps, got {len(rows)}")
    return rows


def _fit_preprocessing(
    *,
    samples: Sequence[ProtocolSample],
    pod: ThermalPOD,
    config: Mapping[str, Any],
) -> tuple[InputNormalization, InputNormalization, Degree2Ridge, list[dict[str, Any]]]:
    train = sorted((sample for sample in samples if sample.fit_eligible), key=lambda item: item.sample_id)
    holdout = [sample.sample_id for sample in samples if not sample.fit_eligible]
    protocol_names = tuple(str(value) for value in config["network"]["protocol_input_order"])
    history_names = tuple(str(value) for value in config["network"]["history_blind_input_order"])
    validate_surrogate_schema(protocol_names, mode="G")
    validate_surrogate_schema(history_names, mode="H")
    protocol_normalization = fit_input_normalization(
        protocol_raw_inputs(train),
        [sample.sample_id for sample in train],
        feature_names=protocol_names,
        forbidden_sample_ids=holdout,
    )
    history_normalization = fit_input_normalization(
        history_raw_inputs(train),
        [sample.sample_id for sample in train],
        feature_names=history_names,
        forbidden_sample_ids=holdout,
    )
    targets = _normalized_targets(
        train, pod, float(config["reference"]["ambient_temperature_K"])
    )
    normalized_inputs = normalize_inputs(protocol_raw_inputs(train), protocol_normalization)
    ridge = fit_degree2_ridge(
        np.asarray(normalized_inputs, dtype=np.float64),
        targets,
        regularization_lambda=float(config["ridge"]["regularization_lambda"]),
    )
    predicted = np.asarray(predict_degree2_ridge(ridge, normalized_inputs), dtype=np.float64)
    coefficient_rmse = np.sqrt(np.mean(np.square(predicted - targets), axis=0))
    ridge_rows = [
        {
            "metric_scope": "train_coefficient_fit",
            "coefficient_index": index + 1,
            "normalized_coefficient_rmse": float(value),
            "train_sample_count": len(train),
            "polynomial_degree": 2,
            "design_feature_count": int(ridge.weights.shape[0]),
            "ridge_lambda": ridge.regularization_lambda,
            "intercept_penalized": False,
            "design_condition_number": ridge.design_condition_number,
            "G1_holdout_used_in_fit": False,
        }
        for index, value in enumerate(coefficient_rmse)
    ]
    return protocol_normalization, history_normalization, ridge, ridge_rows


def _write_preprocessing_artifacts(
    *,
    processed_root: Path,
    pod: ThermalPOD,
    ridge: Degree2Ridge,
    protocol_normalization: InputNormalization,
    history_normalization: InputNormalization,
    samples: Sequence[ProtocolSample],
) -> None:
    processed_root.mkdir(parents=True, exist_ok=True)
    np.save(processed_root / "thermal_pod_mean.npy", pod.mean_y)
    np.save(processed_root / "thermal_pod_basis.npy", pod.basis)
    np.save(processed_root / "ridge_coefficients.npy", ridge.weights)
    np.savez_compressed(
        processed_root / "input_normalization.npz",
        protocol_mean=protocol_normalization.mean,
        protocol_scale=protocol_normalization.scale,
        protocol_feature_names=np.asarray(protocol_normalization.feature_names),
        history_mean=history_normalization.mean,
        history_scale=history_normalization.scale,
        history_feature_names=np.asarray(history_normalization.feature_names),
        train_sample_ids=np.asarray(protocol_normalization.train_sample_ids),
    )
    split_payload = {
        "train_sample_ids": sorted(sample.sample_id for sample in samples if sample.fit_eligible),
        "validation_sample_ids": sorted(
            sample.sample_id for sample in samples if sample.split.startswith("validation")
        ),
        "G1_full_curve_test_sample_ids": sorted(
            sample.sample_id for sample in samples if sample.full_curve_test
        ),
        "G1_headline_stability_certified_sample_ids": sorted(
            sample.sample_id for sample in samples if sample.headline_test
        ),
        "POD_fit_sample_ids": list(pod.train_case_ids),
        "ridge_fit_sample_ids": list(protocol_normalization.train_sample_ids),
        "G1_used_in_fit": False,
        "future_split_required_for_formal_OOD": True,
    }
    _write_json(processed_root / "exact_split_manifest.json", split_payload)


def _aggregate_rows(
    aggregates: Mapping[tuple[int, str], Mapping[str, Any]],
    timing: Mapping[tuple[int, str], float],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for (seed, mode), metrics in sorted(aggregates.items()):
        row = {"seed": seed, "mode": mode, **dict(metrics)}
        row["median_random_access_wall_s"] = timing.get((seed, mode))
        rows.append(row)
    return rows


def _mode_summary_lookup(rows: Sequence[Mapping[str, Any]]) -> dict[tuple[int, str], Mapping[str, Any]]:
    return {(int(row["seed"]), str(row["mode"])): row for row in rows}


def _plot_factorial_contexts(
    samples: Sequence[ProtocolSample], figure_root: Path
) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(10, 7), sharex=True)
    for axis, context_id in zip(axes.flat, ("G0", "G2", "G3", "G1")):
        for branch, color in (("heating", "tab:red"), ("cooling", "tab:blue")):
            points = sorted(
                (
                    sample
                    for sample in samples
                    if sample.context_id == context_id
                    and sample.branch_label == branch
                    and sample.point_kind == "coarse"
                ),
                key=lambda item: item.voltage_V,
            )
            axis.plot(
                [sample.voltage_V for sample in points],
                [sample.point.result.metrics["mean_effective_state_coordinate"] for sample in points],
                color=color,
                label=branch,
            )
        axis.set_title(context_id)
        axis.set_xlabel("Device-terminal voltage (V)")
        axis.set_ylabel("Mean effective state")
        axis.grid(alpha=0.25)
    axes[0, 0].legend()
    fig.suptitle("2x2 protocol-selected physical context matrix")
    fig.tight_layout()
    fig.savefig(figure_root / "factorial_contexts_and_protocol_manifolds.png", dpi=180)
    plt.close(fig)


def _plot_pod(pod: ThermalPOD, config: Mapping[str, Any], figure_root: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    indices = np.arange(1, len(pod.singular_values) + 1)
    axes[0].semilogy(indices, np.maximum(pod.singular_values, 1.0e-30), marker="o")
    axes[0].axvline(pod.rank, color="tab:red", linestyle="--", label=f"rank={pod.rank}")
    axes[0].set_xlabel("POD mode")
    axes[0].set_ylabel("Singular value")
    axes[0].legend()
    axes[0].grid(alpha=0.25)
    ny = int(config["reference"]["production_grid"]["ny"])
    nx = int(config["reference"]["production_grid"]["nx"])
    mode_count = min(pod.rank, 3)
    mosaic = np.concatenate([pod.basis[index].reshape(ny, nx) for index in range(mode_count)], axis=1)
    image = axes[1].imshow(mosaic, origin="lower", aspect="auto", cmap="coolwarm")
    axes[1].set_title("Selected train-only thermal modes")
    fig.colorbar(image, ax=axes[1], shrink=0.8)
    fig.tight_layout()
    fig.savefig(figure_root / "train_only_pod_spectrum_and_modes.png", dpi=180)
    plt.close(fig)


def _plot_accuracy(
    aggregate_rows: Sequence[Mapping[str, Any]], initial_seed: int, figure_root: Path
) -> None:
    wanted = ("A1", "A2", "R1", "R2", "H1", "H2", "S1", "S2", "G1", "G2")
    lookup = _mode_summary_lookup(aggregate_rows)
    values = [
        float(lookup[(0 if mode.startswith(("A", "R")) else initial_seed, mode)]["mean_joint_field_score"])
        for mode in wanted
    ]
    passes = [
        float(lookup[(0 if mode.startswith(("A", "R")) else initial_seed, mode)]["headline_complete_pass_fraction"])
        for mode in wanted
    ]
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    axes[0].bar(wanted, values)
    axes[0].set_yscale("log")
    axes[0].set_ylabel("Mean joint field score")
    axes[0].tick_params(axis="x", rotation=45)
    axes[1].bar(wanted, passes)
    axes[1].axhline(0.9, color="tab:red", linestyle="--")
    axes[1].set_ylim(0, 1.05)
    axes[1].set_ylabel("Headline complete-pass fraction")
    axes[1].tick_params(axis="x", rotation=45)
    fig.tight_layout()
    fig.savefig(figure_root / "analytic_ridge_single_gated_accuracy.png", dpi=180)
    plt.close(fig)


def _plot_field_comparison(
    *,
    samples: Sequence[ProtocolSample],
    cache: Mapping[tuple[int, str, str], ModeOutput],
    initial_seed: int,
    figure_root: Path,
    ambient: float,
) -> None:
    candidates = [
        sample
        for sample in samples
        if sample.context_id == "G1" and sample.branch_label == "cooling" and sample.full_curve_test
    ]
    sample = min(candidates, key=lambda item: abs(item.voltage_V - 1.0640625))
    panels: list[tuple[str, np.ndarray]] = [
        ("Reference", (sample.point.result.temperature_K - ambient).detach().cpu().numpy()),
        ("A2", (cache[(0, "A2", sample.sample_id)].temperature_K - ambient).detach().cpu().numpy()),
        ("R2", (cache[(0, "R2", sample.sample_id)].temperature_K - ambient).detach().cpu().numpy()),
        ("S2", (cache[(initial_seed, "S2", sample.sample_id)].temperature_K - ambient).detach().cpu().numpy()),
        ("G2", (cache[(initial_seed, "G2", sample.sample_id)].temperature_K - ambient).detach().cpu().numpy()),
    ]
    lower = min(float(np.min(array)) for _, array in panels)
    upper = max(float(np.max(array)) for _, array in panels)
    fig, axes = plt.subplots(1, len(panels), figsize=(15, 3.2), constrained_layout=True)
    for axis, (label, array) in zip(axes, panels):
        image = axis.imshow(array, origin="lower", aspect="auto", vmin=lower, vmax=upper, cmap="inferno")
        axis.set_title(label)
        axis.set_xticks([])
        axis.set_yticks([])
    fig.colorbar(image, ax=axes, shrink=0.8, label="Temperature rise (K)")
    fig.suptitle(f"Compound holdout near cooling event, V={sample.voltage_V:.3f} V")
    fig.savefig(figure_root / "compound_context_field_comparison.png", dpi=180)
    plt.close(fig)


def _plot_branch_separation(
    rows: Sequence[Mapping[str, Any]], initial_seed: int, figure_root: Path
) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    for mode, color in (("S1", "tab:orange"), ("G1", "tab:green"), ("S2", "tab:red"), ("G2", "tab:blue")):
        selected = sorted(
            (row for row in rows if int(row["seed"]) == initial_seed and row["mode"] == mode),
            key=lambda row: float(row["device_voltage_V"]),
        )
        axes[0].plot(
            [float(row["device_voltage_V"]) for row in selected],
            [float(row["predicted_current_separation"]) for row in selected],
            label=mode,
            color=color,
        )
        axes[1].plot(
            [float(row["device_voltage_V"]) for row in selected],
            [float(row["predicted_temperature_rise_separation"]) for row in selected],
            label=mode,
            color=color,
        )
    reference = sorted(
        (row for row in rows if int(row["seed"]) == initial_seed and row["mode"] == "G1"),
        key=lambda row: float(row["device_voltage_V"]),
    )
    axes[0].plot(
        [float(row["device_voltage_V"]) for row in reference],
        [float(row["reference_current_separation"]) for row in reference],
        color="black",
        linestyle="--",
        label="reference",
    )
    axes[1].plot(
        [float(row["device_voltage_V"]) for row in reference],
        [float(row["reference_temperature_rise_separation"]) for row in reference],
        color="black",
        linestyle="--",
        label="reference",
    )
    axes[0].set_ylabel("Current separation")
    axes[1].set_ylabel("Temperature-rise separation")
    for axis in axes:
        axis.set_xlabel("Voltage (V)")
        axis.grid(alpha=0.25)
    axes[0].legend(ncol=2)
    fig.tight_layout()
    fig.savefig(figure_root / "branch_separation_and_averaging.png", dpi=180)
    plt.close(fig)


def _plot_event_neighborhood(
    rows: Sequence[Mapping[str, Any]], initial_seed: int, figure_root: Path
) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.8), sharex=True)
    for mode in ("A2", "R2", "S2", "G2"):
        seed = 0 if mode.startswith(("A", "R")) else initial_seed
        selected = sorted(
            (
                row
                for row in rows
                if int(row["seed"]) == seed
                and row["mode"] == mode
                and row["context_id"] == "G1"
                and row["branch_label"] == "cooling"
                and bool(row["event_neighborhood"])
            ),
            key=lambda row: float(row["device_voltage_V"]),
        )
        axes[0].plot([row["device_voltage_V"] for row in selected], [row["temperature_rise_relative_l2"] for row in selected], marker="o", label=mode)
        axes[1].plot([row["device_voltage_V"] for row in selected], [row["terminal_current_relative_error"] for row in selected], marker="o", label=mode)
        axes[2].plot([row["device_voltage_V"] for row in selected], [row["mean_state_absolute_error"] for row in selected], marker="o", label=mode)
    for axis, label in zip(axes, ("T-rise error", "Current error", "Mean-state error")):
        axis.set_ylabel(label)
        axis.set_xlabel("Voltage (V)")
        axis.grid(alpha=0.25)
    axes[0].legend()
    fig.tight_layout()
    fig.savefig(figure_root / "event_neighborhood_accuracy.png", dpi=180)
    plt.close(fig)


def _plot_unknown_protocol(
    rows: Sequence[Mapping[str, Any]], initial_seed: int, figure_root: Path
) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    for mode, color in (("S1", "tab:orange"), ("G1", "tab:green"), ("S2", "tab:red"), ("G2", "tab:blue")):
        selected = sorted(
            (row for row in rows if int(row["seed"]) == initial_seed and row["mode"] == mode),
            key=lambda row: float(row["device_voltage_V"]),
        )
        axes[0].plot(
            [row["device_voltage_V"] for row in selected],
            [max(float(row["predicted_current_separation"]), float(row["predicted_temperature_rise_separation"])) for row in selected],
            label=mode,
            color=color,
        )
        axes[1].plot(
            [row["device_voltage_V"] for row in selected],
            [1.0 if row["output_status"] == "AMBIGUOUS_PROTOCOL" else 0.0 for row in selected],
            label=mode,
            color=color,
        )
    axes[0].axhline(0.1, color="black", linestyle="--", label="refusal threshold")
    axes[0].set_ylabel("Predicted maximum branch separation")
    axes[1].set_ylabel("AMBIGUOUS_PROTOCOL output")
    for axis in axes:
        axis.set_xlabel("Voltage (V)")
        axis.grid(alpha=0.25)
    axes[0].legend(ncol=2)
    fig.tight_layout()
    fig.savefig(figure_root / "unknown_protocol_set_and_refusal.png", dpi=180)
    plt.close(fig)


def _plot_speed_accuracy(
    aggregate_rows: Sequence[Mapping[str, Any]], initial_seed: int, figure_root: Path
) -> None:
    wanted = ("A1", "A2", "R1", "R2", "S1", "S2", "G1", "G2")
    lookup = _mode_summary_lookup(aggregate_rows)
    fig, axis = plt.subplots(figsize=(7, 5))
    for mode in wanted:
        seed = 0 if mode.startswith(("A", "R")) else initial_seed
        row = lookup[(seed, mode)]
        axis.scatter(float(row["median_random_access_wall_s"]), float(row["mean_joint_field_score"]), s=55)
        axis.annotate(mode, (float(row["median_random_access_wall_s"]), float(row["mean_joint_field_score"])))
    axis.set_xscale("log")
    axis.set_yscale("log")
    axis.set_xlabel("Median random-access wall time (s)")
    axis.set_ylabel("Mean headline joint field score")
    axis.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(figure_root / "speed_accuracy_pareto.png", dpi=180)
    plt.close(fig)


def _plot_decision(seed_rows: Sequence[Mapping[str, Any]], decision: Mapping[str, Any], figure_root: Path) -> None:
    fig, axis = plt.subplots(figsize=(10, 4.8))
    axis.axis("off")
    lines = [
        "ProtocolManifold-ProjPINN route decision",
        f"Disposition: {decision['final_disposition']}",
        f"Initial path: {decision['initial_candidate_path']}",
        f"Conditional seeds executed: {decision['conditional_seeds_executed']}",
    ]
    for row in seed_rows:
        lines.append(
            f"seed {row['seed']}: H={row['path_h_pass']} S={row['path_s_pass']} partial={row['partial_path_pass']}"
        )
    lines.extend(
        [
            "Evidence role: diagnostic_non_voting",
            "Formal superiority, full hysteresis, dynamic attractor, experiment, and inverse remain forbidden.",
        ]
    )
    axis.text(0.02, 0.95, "\n".join(lines), va="top", family="monospace", fontsize=11)
    fig.tight_layout()
    fig.savefig(figure_root / "paper_route_decision.png", dpi=180)
    plt.close(fig)


def generate_figures(
    *,
    samples: Sequence[ProtocolSample],
    pod: ThermalPOD,
    matched_rows: Sequence[Mapping[str, Any]],
    aggregate_rows: Sequence[Mapping[str, Any]],
    branch_rows: Sequence[Mapping[str, Any]],
    refusal_rows: Sequence[Mapping[str, Any]],
    cache: Mapping[tuple[int, str, str], ModeOutput],
    seed_rows: Sequence[Mapping[str, Any]],
    decision: Mapping[str, Any],
    config: Mapping[str, Any],
    figure_root: Path,
) -> None:
    figure_root.mkdir(parents=True, exist_ok=True)
    initial_seed = int(config["training"]["initial_seed"])
    _plot_factorial_contexts(samples, figure_root)
    _plot_pod(pod, config, figure_root)
    _plot_accuracy(aggregate_rows, initial_seed, figure_root)
    _plot_field_comparison(
        samples=samples,
        cache=cache,
        initial_seed=initial_seed,
        figure_root=figure_root,
        ambient=float(config["reference"]["ambient_temperature_K"]),
    )
    _plot_branch_separation(branch_rows, initial_seed, figure_root)
    _plot_event_neighborhood(matched_rows, initial_seed, figure_root)
    _plot_unknown_protocol(refusal_rows, initial_seed, figure_root)
    _plot_speed_accuracy(aggregate_rows, initial_seed, figure_root)
    _plot_decision(seed_rows, decision, figure_root)


def write_report(
    *,
    path: Path,
    config: Mapping[str, Any],
    physics_summary: Mapping[str, Any],
    pod: ThermalPOD,
    aggregate_rows: Sequence[Mapping[str, Any]],
    branch_summaries: Mapping[tuple[int, str], Mapping[str, Any]],
    refusal_summaries: Mapping[tuple[int, str], Mapping[str, Any]],
    seed_rows: Sequence[Mapping[str, Any]],
    decision: Mapping[str, Any],
    table_root: Path,
    figure_root: Path,
    checkpoint_paths: Sequence[str],
) -> None:
    initial_seed = int(config["training"]["initial_seed"])
    lookup = _mode_summary_lookup(aggregate_rows)
    lines = [
        "# Q2 M1 protocol-manifold branch-aware surrogate MVE",
        "",
        f"- Evidence identity: `{EVIDENCE_TYPE}`.",
        "- PR #42 is preserved as the immutable `GO_PROTOCOL_SELECTED_EQUILIBRIUM_MANIFOLD` reference; its ramps, gates, and interpretation were not changed.",
        f"- G2/G3 physical reference gate: `{physics_summary['stage_disposition']}`; G0/G1 were read and copied without rerunning their main ramps.",
        f"- Split: 174 train coarse states, 24 fixed-index coarse validation states plus event confirmations, 66-point G1 diagnostic curve, and 10 unique spectrum-certified G1 headline states.",
        f"- Train-only POD rank: **{pod.rank}** at cumulative energy target 99.9%; G1 was excluded from POD, normalization, ridge, training, and checkpoint selection.",
        f"- Conditional seeds executed: **{decision['conditional_seeds_executed']}**.",
        f"- Final disposition: **`{decision['final_disposition']}`**.",
        "",
        "## Headline matched-budget metrics",
        "",
        "| mode | seed | pass | mean joint | T-rise | phi | current | median time (s) |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for mode in ("A1", "A2", "R1", "R2", "H1", "H2", "S1", "S2", "G1", "G2"):
        seed = 0 if mode.startswith(("A", "R")) else initial_seed
        row = lookup[(seed, mode)]
        lines.append(
            f"| {mode} | {seed} | {int(row['headline_complete_pass_count'])}/{int(row['headline_case_count'])} | "
            f"{float(row['mean_joint_field_score']):.6g} | {float(row['mean_temperature_rise_relative_l2']):.6g} | "
            f"{float(row['mean_potential_relative_l2']):.6g} | {float(row['mean_terminal_current_relative_error']):.6g} | "
            f"{float(row['median_random_access_wall_s']):.6g} |"
        )
    lines.extend(
        [
            "",
            "## Branch selection and unknown-protocol behavior",
            "",
        ]
    )
    for mode in ("S1", "S2", "G1", "G2"):
        branch = branch_summaries[(initial_seed, mode)]
        refusal = refusal_summaries[(initial_seed, mode)]
        lines.append(
            f"- {mode}: branch gate `{branch['branch_separation_gate_pass']}`, certified head swaps "
            f"{branch['certified_head_swap_count']}, full-curve separation fraction "
            f"{float(branch['full_curve_fraction_within_0p20']):.3f}; refusal gate "
            f"`{refusal['unknown_protocol_gate_pass']}`, certified recall "
            f"{float(refusal['certified_ambiguity_recall']):.3f}, full-curve recall "
            f"{float(refusal['full_curve_ambiguity_recall']):.3f}, set coverage "
            f"{float(refusal['two_candidate_set_coverage']):.3f}."
        )
    lines.extend(
        [
            "",
            "The unknown-protocol interface returns explicit heating and cooling candidates when the predicted separation reaches the frozen ambiguity threshold; it never averages candidates and never exposes a root identifier.",
            "",
            "## Claim boundary",
            "",
            "This is a single- or conditional three-seed diagnostic MVE, not formal superiority. The supported implementation facts are the M1 conservative projection and explicit hard direction gate. Protocol-manifold and new-context physical evidence remain qualified within the frozen synthetic ideal voltage-clamp protocol. Full hysteresis, dynamic attractors, Qiu source-RC reproduction, experimental validation, formal PINN superiority, inverse inference, and zero-shot transfer remain forbidden.",
            "",
            "## Artifacts",
            "",
            f"- Tables: `{table_root.as_posix()}`",
            f"- Figures: `{figure_root.as_posix()}`",
            f"- Checkpoints: `{', '.join(checkpoint_paths)}`",
            "",
            "## Next priority",
            "",
            (
                "Proceed only to the preregistered compound thermal-position/formal OOD campaign if a neural path survives the multi-seed gate; otherwise retain the conservative operator and protocol data while closing neural-forward expansion."
            ),
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_evidence_map(
    path: Path, decision: Mapping[str, Any], config: Mapping[str, Any]
) -> None:
    disposition = str(decision["final_disposition"])
    content = f"""# Protocol-manifold surrogate evidence map

| Evidence item | Lifecycle | Claim status | Bound |
|---|---|---|---|
| M1 conservative projection operator | numerically_validated | supported | Frozen synthetic M1 operator |
| PR #42 protocol-selected manifold | claim_supported | qualified_supported | Ideal device-terminal voltage protocol |
| G2/G3 factorial physical contexts | numerically_validated | qualified_supported | 20/30 nm and nominal/localized frozen contexts |
| ProtocolManifold-ProjPINN MVE | executed | failed_but_informative | `{disposition}`; diagnostic, non-voting |
| Formal PINN superiority | planned | forbidden | Requires a separately preregistered formal OOD stage |
| Full hysteresis, dynamic attractor, experiment, inverse | planned | forbidden | Not executed in this task |

The future input contract may use device voltage, explicit ramp direction, protocol start/end metadata, geometry, sink condition, and deployable previous-state summaries. `root_id`, cold/hot solution labels, and root averaging are forbidden.
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def run_experiment(
    config_path: Path,
    repository_root: Path,
    *,
    resume_completed_physics: bool = False,
) -> dict[str, Any]:
    config = load_yaml(config_path)
    processed_root = repository_root / str(config["outputs"]["processed_root"])
    table_root = repository_root / str(config["outputs"]["table_root"])
    figure_root = repository_root / str(config["outputs"]["figure_root"])
    checkpoint_root = repository_root / str(config["outputs"]["checkpoint_root"])
    for path in (processed_root, table_root, figure_root, checkpoint_root):
        path.mkdir(parents=True, exist_ok=True)

    old_config = load_yaml(repository_root / str(config["reference"]["historical_protocol_config"]))
    old_runs = rehydrate_protocol_runs(
        config=old_config,
        processed_root=repository_root / str(config["reference"]["historical_processed_root"]),
    )
    if {run.spec.context_id for run in old_runs} != {"G0", "G1"}:
        raise ValueError("frozen PR42 rehydration must contain only G0/G1")
    copied_old_paths = _copy_frozen_protocol_data(config, repository_root, processed_root)
    new_result = (
        rehydrate_completed_new_contexts(
            config=config,
            repository_root=repository_root,
            processed_root=processed_root,
            table_root=table_root,
        )
        if resume_completed_physics
        else execute_new_context_protocols(config, repository_root, processed_root)
    )
    factorial_manifest = _factorial_manifest_rows(
        config, repository_root, new_result["manifest_rows"]
    )
    _write_csv(table_root / "factorial_context_manifest.csv", factorial_manifest)
    _write_csv(table_root / "new_context_physics_metrics.csv", new_result["physics_rows"])
    _write_csv(table_root / "new_context_stability_metrics.csv", new_result["stability_rows"])
    _write_json(table_root / "new_context_reference_summary.json", new_result["summary"])
    if not bool(new_result["summary"]["new_context_reference_gate_pass"]):
        decision = {
            "task_id": config["task_id"],
            "run_id": config["run_id"],
            "evidence_type": EVIDENCE_TYPE,
            "PR42_frozen": True,
            "physics": new_result["summary"],
            "final_disposition": config["decision_gates"]["dispositions"]["physics_no_go"],
            "surrogate_training_executed": False,
        }
        _write_json(table_root / "decision_summary.json", decision)
        return decision

    samples, split_rows = build_protocol_samples(
        config=config,
        repository_root=repository_root,
        old_runs=old_runs,
        new_runs=new_result["runs"],
    )
    _write_csv(table_root / "protocol_point_split.csv", split_rows)
    try:
        pod = fit_protocol_pod(samples, config)
    except RuntimeError as error:
        if str(error) != "NO_GO_PROTOCOL_MANIFOLD_LOW_RANK_CONTRACT":
            raise
        decision = {
            "task_id": config["task_id"],
            "run_id": config["run_id"],
            "evidence_type": EVIDENCE_TYPE,
            "PR42_frozen": True,
            "physics": new_result["summary"],
            "final_disposition": config["decision_gates"]["dispositions"]["pod_no_go"],
            "surrogate_training_executed": False,
        }
        _write_json(table_root / "decision_summary.json", decision)
        return decision
    _write_csv(table_root / "thermal_pod_spectrum.csv", _pod_spectrum_rows(pod))

    protocol_normalization, history_normalization, ridge, ridge_rows = _fit_preprocessing(
        samples=samples, pod=pod, config=config
    )
    _write_preprocessing_artifacts(
        processed_root=processed_root,
        pod=pod,
        ridge=ridge,
        protocol_normalization=protocol_normalization,
        history_normalization=history_normalization,
        samples=samples,
    )
    operators = _build_all_operators(config, repository_root)
    operators.update(new_result["operators"])
    train_samples = [sample for sample in samples if sample.fit_eligible]
    initial_seed = int(config["training"]["initial_seed"])
    models_by_seed: dict[int, dict[str, torch.nn.Module]] = {}
    histories: list[dict[str, Any]] = []
    training_summaries: list[dict[str, Any]] = []
    checkpoint_paths: list[str] = []

    initial_models = build_models(pod, config, initial_seed)
    for kind in ("H", "S", "G"):
        history, training_summary = train_network(
            model_kind=kind,
            model=initial_models[kind],
            train_samples=train_samples,
            pod=pod,
            operators=operators,
            protocol_normalization=protocol_normalization,
            history_normalization=history_normalization,
            config=config,
            seed=initial_seed,
        )
        histories.extend(history)
        training_summaries.append(training_summary)
        checkpoint_path = checkpoint_root / f"{kind}_seed_{initial_seed}.pt"
        save_checkpoint(
            path=checkpoint_path,
            seed=initial_seed,
            model_kind=kind,
            model=initial_models[kind],
            pod=pod,
            protocol_normalization=protocol_normalization,
            history_normalization=history_normalization,
            training_summary=training_summary,
            config=config,
        )
        checkpoint_paths.append(checkpoint_path.as_posix())
    models_by_seed[initial_seed] = initial_models

    matched_rows, cache = evaluate_modes(
        samples=samples,
        operators=operators,
        pod=pod,
        ridge=ridge,
        models_by_seed={initial_seed: initial_models},
        protocol_normalization=protocol_normalization,
        history_normalization=history_normalization,
        config=config,
        include_baselines=True,
    )
    initial_modes = ["A1", "A2", "R1", "R2", "H0", "H1", "H2", "S1", "S2", "G1", "G2"]
    branch_rows, branch_summaries = branch_separation_metrics(
        samples=samples,
        cache=cache,
        modes_by_seed={initial_seed: initial_modes},
        config=config,
    )
    refusal_rows, refusal_summaries = unknown_protocol_metrics(
        samples=samples,
        cache=cache,
        seeds=[initial_seed],
        config=config,
        operators=operators,
    )
    speed_rows = benchmark_random_access(
        samples=samples,
        operators=operators,
        pod=pod,
        ridge=ridge,
        models_by_seed={initial_seed: initial_models},
        protocol_normalization=protocol_normalization,
        history_normalization=history_normalization,
        config=config,
    )
    speed_rows.extend(
        benchmark_sequential_continuation(
            old_runs=old_runs, operator=operators["G1"], config=config
        )
    )
    aggregates = aggregate_mode_metrics(matched_rows)
    timing = timing_medians(speed_rows)
    initial_gate = seed_gate_summary(
        seed=initial_seed,
        aggregates=aggregates,
        branch_summaries=branch_summaries,
        refusal_summaries=refusal_summaries,
        timing=timing,
        config=config,
    )
    seed_rows: list[dict[str, Any]] = [initial_gate]

    if initial_gate["candidate_path"] != "none":
        for seed in (int(value) for value in config["training"]["conditional_seeds"]):
            models = build_models(pod, config, seed)
            for kind in ("S", "G"):
                history, training_summary = train_network(
                    model_kind=kind,
                    model=models[kind],
                    train_samples=train_samples,
                    pod=pod,
                    operators=operators,
                    protocol_normalization=protocol_normalization,
                    history_normalization=history_normalization,
                    config=config,
                    seed=seed,
                )
                histories.extend(history)
                training_summaries.append(training_summary)
                checkpoint_path = checkpoint_root / f"{kind}_seed_{seed}.pt"
                save_checkpoint(
                    path=checkpoint_path,
                    seed=seed,
                    model_kind=kind,
                    model=models[kind],
                    pod=pod,
                    protocol_normalization=protocol_normalization,
                    history_normalization=history_normalization,
                    training_summary=training_summary,
                    config=config,
                )
                checkpoint_paths.append(checkpoint_path.as_posix())
            models_by_seed[seed] = models
            extra_rows, extra_cache = evaluate_modes(
                samples=samples,
                operators=operators,
                pod=pod,
                ridge=ridge,
                models_by_seed={seed: models},
                protocol_normalization=protocol_normalization,
                history_normalization=history_normalization,
                config=config,
                include_baselines=False,
            )
            matched_rows.extend(extra_rows)
            cache.update(extra_cache)
            extra_branch_rows, extra_branch_summaries = branch_separation_metrics(
                samples=samples,
                cache=cache,
                modes_by_seed={seed: ["S1", "S2", "G1", "G2"]},
                config=config,
            )
            branch_rows.extend(extra_branch_rows)
            branch_summaries.update(extra_branch_summaries)
            extra_refusal_rows, extra_refusal_summaries = unknown_protocol_metrics(
                samples=samples,
                cache=cache,
                seeds=[seed],
                config=config,
                operators=operators,
            )
            refusal_rows.extend(extra_refusal_rows)
            refusal_summaries.update(extra_refusal_summaries)
            speed_rows.extend(
                benchmark_random_access(
                    samples=samples,
                    operators=operators,
                    pod=pod,
                    ridge=ridge,
                    models_by_seed={seed: models},
                    protocol_normalization=protocol_normalization,
                    history_normalization=history_normalization,
                    config=config,
                )
            )
            aggregates = aggregate_mode_metrics(matched_rows)
            timing = timing_medians(speed_rows)
            seed_rows.append(
                seed_gate_summary(
                    seed=seed,
                    aggregates=aggregates,
                    branch_summaries=branch_summaries,
                    refusal_summaries=refusal_summaries,
                    timing=timing,
                    config=config,
                )
            )

    decision = final_seed_decision(seed_rows, config)
    aggregate_rows = _aggregate_rows(aggregate_mode_metrics(matched_rows), timing_medians(speed_rows))
    ridge_rows.extend(
        {
            "metric_scope": "headline_projected_mode",
            **row,
        }
        for row in aggregate_rows
        if row["mode"] in {"R1", "R2"}
    )
    _write_csv(table_root / "ridge_metrics.csv", ridge_rows)
    _write_csv(table_root / "neural_training_history.csv", histories)
    _write_csv(table_root / "matched_budget_metrics.csv", matched_rows)
    _write_csv(table_root / "branch_separation_metrics.csv", branch_rows)
    _write_csv(table_root / "unknown_protocol_refusal_metrics.csv", refusal_rows)
    _write_csv(table_root / "speed_benchmark.csv", speed_rows)
    _write_csv(table_root / "seed_summary.csv", seed_rows)

    modes_by_seed: dict[int, Sequence[str]] = {
        initial_seed: initial_modes,
        **{
            seed: ["S1", "S2", "G1", "G2"]
            for seed in models_by_seed
            if seed != initial_seed
        },
    }
    prediction_paths = save_g1_predictions(
        processed_root=processed_root,
        samples=samples,
        cache=cache,
        modes_by_seed=modes_by_seed,
        operators=operators,
    )
    decision_summary = {
        "task_id": config["task_id"],
        "run_id": config["run_id"],
        "evidence_type": EVIDENCE_TYPE,
        "frozen_PR42": {
            "head": config["frozen_baseline"]["head_sha"],
            "merge": config["frozen_baseline"]["merge_sha"],
            "disposition": config["frozen_baseline"]["disposition"],
            "historical_G0_G1_main_ramps_reexecuted": 0,
        },
        "factorial_context_physics": new_result["summary"],
        "split": {
            "train_count": sum(sample.fit_eligible for sample in samples),
            "validation_coarse_count": sum(sample.split == "validation" for sample in samples),
            "validation_event_count": sum(sample.split == "validation_event" for sample in samples),
            "G1_full_curve_diagnostic_count": sum(sample.full_curve_test for sample in samples),
            "G1_headline_unique_stability_count": sum(sample.headline_test for sample in samples),
            "G1_used_in_fit": False,
        },
        "POD": {
            "rank": pod.rank,
            "energy_target": config["pod"]["cumulative_energy_target"],
            "selected_cumulative_energy": float(pod.cumulative_energy[pod.rank - 1]),
            "rank_cap": config["pod"]["rank_cap"],
            "train_only": True,
        },
        "network_training": training_summaries,
        "seed_gates": seed_rows,
        "decision": decision,
        "final_disposition": decision["final_disposition"],
        "candidate_averaging_used": False,
        "root_identifier_used": False,
        "conditional_seeds_executed": decision["conditional_seeds_executed"],
        "claim_boundary": config["claim_boundary"],
        "artifact_paths": {
            "processed_root": processed_root,
            "table_root": table_root,
            "figure_root": figure_root,
            "checkpoint_paths": checkpoint_paths,
            "prediction_paths": prediction_paths,
            "frozen_protocol_copies": copied_old_paths,
        },
    }
    _write_json(table_root / "decision_summary.json", decision_summary)
    generate_figures(
        samples=samples,
        pod=pod,
        matched_rows=matched_rows,
        aggregate_rows=aggregate_rows,
        branch_rows=branch_rows,
        refusal_rows=refusal_rows,
        cache=cache,
        seed_rows=seed_rows,
        decision=decision,
        config=config,
        figure_root=figure_root,
    )
    write_report(
        path=repository_root / str(config["outputs"]["report"]),
        config=config,
        physics_summary=new_result["summary"],
        pod=pod,
        aggregate_rows=aggregate_rows,
        branch_summaries=branch_summaries,
        refusal_summaries=refusal_summaries,
        seed_rows=seed_rows,
        decision=decision,
        table_root=table_root,
        figure_root=figure_root,
        checkpoint_paths=checkpoint_paths,
    )
    write_evidence_map(
        repository_root / str(config["outputs"]["paper_evidence_map"]), decision, config
    )
    return decision_summary
