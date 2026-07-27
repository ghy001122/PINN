"""Execute the preregistered, non-formal Phase 1-v2 S1 sensitivity MVE.

The runner cannot select a production closure, emit formal case identifiers, or
change the nominal S2 model.  It writes the two CSV evidence tables before the
summary JSON and report, as locked by the v2 amendment.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import platform
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

import numpy as np
import scipy
import yaml

from pinnpcm.physics.geophase_s1_diffusive import (
    CauerIIThermalNetwork,
    DiffusiveThermalImpedance,
    FosterThermalImpedance,
    analytic_reference_discrepancy,
    analytic_reference_response_cache,
    candidate_eligible,
    fit_foster_candidate,
    fit_grids,
    foster_to_cauer_ii,
    metrics_pass,
    pulse_event_times,
    select_training_candidate,
    validation_grids,
    validation_metrics,
)
from pinnpcm.physics.geophase_s2_thermal import derive_nominal_s2_source_scale


ROOT = Path(__file__).resolve().parents[1]
BASE_CONFIG_PATH = ROOT / "configs" / "geophase_phase1_s1_diffusive_sensitivity_mve.yaml"
AMENDMENT_CONFIG_PATH = (
    ROOT / "configs" / "geophase_phase1_s1_diffusive_sensitivity_mve_v2.yaml"
)
PREREGISTRATION_PATH = (
    ROOT
    / "outputs"
    / "tables"
    / "geophase_phase1_v2"
    / "s1_diffusive_mve_v2_preregistration.json"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected a YAML mapping in {path}")
    return payload


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected a JSON mapping in {path}")
    return payload


def _git(*args: str) -> str:
    return subprocess.check_output(
        ["git", *args], cwd=ROOT, text=True, stderr=subprocess.STDOUT
    ).strip()


def _require_ancestor(ancestor: str, descendant: str) -> None:
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor, descendant],
        cwd=ROOT,
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if result.returncode != 0:
        raise RuntimeError("S1-v2 preregistration commit is not an ancestor of HEAD")


def _atomic_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=path.name + ".", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _atomic_json(path: Path, payload: object) -> None:
    _atomic_text(
        path,
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
    )


def _atomic_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise RuntimeError(f"refusing to write empty S1 evidence CSV: {path}")
    fields = sorted({key for row in rows for key in row})
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=path.name + ".", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _repo_path(config_value: str) -> Path:
    path = ROOT / config_value
    try:
        path.resolve().relative_to(ROOT.resolve())
    except ValueError as error:
        raise ValueError("S1 output escaped the repository") from error
    return path


def _verify_preregistration(
    amendment_path: Path,
    amendment: dict[str, Any],
    preregistration_path: Path,
    preregistration: dict[str, Any],
) -> dict[str, str]:
    amendment_hash = _sha256(amendment_path)
    if amendment_hash != preregistration["amendment_config_sha256"]:
        raise RuntimeError("S1-v2 amendment hash drifted after preregistration")
    s2_path = _repo_path(amendment["source_scale_identity"]["S2_config_path"])
    s2_hash = _sha256(s2_path)
    locked_s2_hash = amendment["source_scale_identity"]["S2_config_sha256"]
    if s2_hash != locked_s2_hash or s2_hash != preregistration["s2_config_sha256"]:
        raise RuntimeError("S2 source-scale config drifted after S1 preregistration")
    if preregistration["formal_execution_count"] != 0:
        raise RuntimeError("S1 MVE cannot run after a formal count mutation")
    if preregistration["production_selection_authorized"] is not False:
        raise RuntimeError("S1 production selection is not authorized")
    head = _git("rev-parse", "HEAD")
    preregistration_commit = str(preregistration["preregistration_commit"])
    _require_ancestor(preregistration_commit, head)
    commit_epoch = int(_git("show", "-s", "--format=%ct", preregistration_commit))
    return {
        "head": head,
        "preregistration_commit": preregistration_commit,
        "amendment_config_sha256": amendment_hash,
        "s2_config_sha256": s2_hash,
        "preregistration_sha256": _sha256(preregistration_path),
        "preregistration_commit_epoch": str(commit_epoch),
    }


def _source_scale(
    base: dict[str, Any], amendment: dict[str, Any], s2: dict[str, Any]
) -> dict[str, float]:
    scale = derive_nominal_s2_source_scale(s2)
    result = {
        "active_plane_area_m2": float(scale["device_area_m2"]),
        "C_explicit_J_K": float(scale["nominal_explicit_capacity_J_K"]),
        "C_m_J_K": float(scale["nominal_memory_coefficient_J_K"]),
        "gtheta_A_W_m2K": float(scale["vertical_conductance_W_m2K"]),
        "cm_A_J_m2K": float(scale["memory_areal_coefficient_J_m2K"]),
        "Gtheta_W_K": float(scale["target_uniform_conductance_W_K"]),
        "Ctheta_J_K": float(scale["target_uniform_capacity_J_K"]),
    }
    required = amendment["source_scale_identity"]["required_fields"]
    if set(required) - set(result):
        raise RuntimeError("S1 source-scale evidence is missing a required field")
    if result["C_m_J_K"] <= 0.0:
        raise RuntimeError("S1 requires C_m > 0")
    mirrored = base["shared_source_moments"]
    if float(mirrored["Gtheta_W_K"]) != result["Gtheta_W_K"]:
        raise RuntimeError("mirrored S1 Gtheta does not exactly match S2")
    if (
        float(mirrored["Ctheta_low_frequency_coefficient_J_K"])
        != result["Ctheta_J_K"]
    ):
        raise RuntimeError("mirrored S1 Ctheta does not exactly match S2")
    return result


def _reference_pointwise_rows(
    production: DiffusiveThermalImpedance,
    comparator: DiffusiveThermalImpedance,
    *,
    fit_time: np.ndarray,
    validation_time: np.ndarray,
    pulse_width: float,
    pulse_amplitude: float,
    response_cache: dict[str, np.ndarray],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for split, coordinates in (("fit", fit_time), ("validation", validation_time)):
        for domain, production_values, comparator_values in (
            (
                "reference_step",
                response_cache[f"{split}_step_production"],
                response_cache[f"{split}_step_comparator"],
            ),
            (
                "reference_pulse",
                response_cache[f"{split}_pulse_production"],
                response_cache[f"{split}_pulse_comparator"],
            ),
        ):
            for coordinate, left, right in zip(
                coordinates, production_values, comparator_values, strict=True
            ):
                rows.append(
                    {
                        "record_id": "S1MVE2-REFERENCE",
                        "split": split,
                        "domain": domain,
                        "order": 0,
                        "start_id": "analytic_modal_comparator",
                        "coordinate": float(coordinate),
                        "reference": float(right),
                        "candidate": float(left),
                        "absolute_error": float(abs(left - right)),
                    }
                )
    return rows


def _candidate_pointwise_rows(
    *,
    order: int,
    start_id: str,
    analytic: DiffusiveThermalImpedance,
    foster: FosterThermalImpedance,
    cauer: CauerIIThermalNetwork,
    frequency: np.ndarray,
    time_grid: np.ndarray,
    event_times: np.ndarray,
    pulse_width: float,
    pulse_amplitude: float,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    s = 1j * 2.0 * np.pi * frequency
    analytic_z = analytic.impedance(s)
    foster_z = foster.impedance(s)
    cauer_z = cauer.impedance(s)
    state_z = cauer.state_space_impedance(s)
    for coordinate, reference, candidate, converted, state_value in zip(
        frequency, analytic_z, foster_z, cauer_z, state_z, strict=True
    ):
        rows.append(
            {
                "record_id": f"S1MVE2-K{order}-{start_id}",
                "split": "validation",
                "domain": "frequency",
                "order": order,
                "start_id": start_id,
                "coordinate": float(coordinate),
                "reference_real": float(reference.real),
                "reference_imag": float(reference.imag),
                "reference_magnitude": float(abs(reference)),
                "reference_phase_rad": float(np.angle(reference)),
                "candidate_real": float(candidate.real),
                "candidate_imag": float(candidate.imag),
                "candidate_magnitude": float(abs(candidate)),
                "candidate_phase_rad": float(np.angle(candidate)),
                "cauer_real": float(converted.real),
                "cauer_imag": float(converted.imag),
                "state_space_real": float(state_value.real),
                "state_space_imag": float(state_value.imag),
            }
        )
    for domain, coordinates in (("step", time_grid), ("pulse", time_grid)):
        if domain == "step":
            reference = analytic.step_temperature_K(coordinates)
            candidate = foster.step_temperature_K(coordinates)
            converted = cauer.step_temperature_K(coordinates)
        else:
            reference = analytic.rectangular_pulse_temperature_K(
                coordinates,
                pulse_width_s=pulse_width,
                pulse_amplitude_W_m2=pulse_amplitude,
            )
            candidate = foster.rectangular_pulse_temperature_K(
                coordinates,
                pulse_width_s=pulse_width,
                pulse_amplitude_W_m2=pulse_amplitude,
            )
            converted = cauer.rectangular_pulse_temperature_K(
                coordinates,
                pulse_width_s=pulse_width,
                pulse_amplitude_W_m2=pulse_amplitude,
            )
        for coordinate, left, middle, right in zip(
            coordinates, reference, candidate, converted, strict=True
        ):
            rows.append(
                {
                    "record_id": f"S1MVE2-K{order}-{start_id}",
                    "split": "validation",
                    "domain": domain,
                    "order": order,
                    "start_id": start_id,
                    "coordinate": float(coordinate),
                    "reference": float(left),
                    "candidate": float(middle),
                    "cauer": float(right),
                }
            )
    reference_event = analytic.rectangular_pulse_temperature_K(
        event_times,
        pulse_width_s=pulse_width,
        pulse_amplitude_W_m2=pulse_amplitude,
    )
    candidate_event = foster.rectangular_pulse_temperature_K(
        event_times,
        pulse_width_s=pulse_width,
        pulse_amplitude_W_m2=pulse_amplitude,
    )
    cauer_event = cauer.rectangular_pulse_temperature_K(
        event_times,
        pulse_width_s=pulse_width,
        pulse_amplitude_W_m2=pulse_amplitude,
    )
    for coordinate, left, middle, right in zip(
        event_times, reference_event, candidate_event, cauer_event, strict=True
    ):
        rows.append(
            {
                "record_id": f"S1MVE2-K{order}-{start_id}",
                "split": "pulse_event_audit",
                "domain": "pulse",
                "order": order,
                "start_id": start_id,
                "coordinate": float(coordinate),
                "reference": float(left),
                "candidate": float(middle),
                "cauer": float(right),
            }
        )
    return rows


def _report(summary: dict[str, Any]) -> str:
    status = summary["disposition"]
    selected = summary["selected_sensitivity_order"]
    return f"""# Phase 1-v2 S1 diffusive sensitivity MVE

## Result

- Disposition: `{status}`
- Evidence type: non-formal synthetic model-form sensitivity
- Selected sensitivity order: `{selected}`
- Production selected: `false`
- Nominal Phase 1-v2 closure: `S2`
- Formal execution count: `0`

The run tested only whether the preregistered analytic positive-real S1 family
could be represented by a passive common Foster/Cauer model with at most three
poles. It did not compare S1 against an eligible same-device thermal holdout.

## Reference control

- Maximum modal-reference discrepancy: `{summary['analytic_reference']['maximum_reference_discrepancy']:.6e}`
- Reference gate passed: `{summary['analytic_reference']['passed']}`

## Claim disposition

Allowed: {summary['claim_boundary']['allowed']}

Forbidden: S1 superiority over S2, an identified Qiu diffusive spectrum,
production-reference status, experimental validation, or a manuscript headline
claim.
"""


def run_mve(
    *,
    base_config_path: Path = BASE_CONFIG_PATH,
    amendment_config_path: Path = AMENDMENT_CONFIG_PATH,
    preregistration_path: Path = PREREGISTRATION_PATH,
    infrastructure_interruption_notes: list[str] | None = None,
) -> dict[str, Any]:
    start_clock = time.perf_counter()
    print("S1-MVE: verify preregistration", flush=True)
    base = _load_yaml(base_config_path)
    amendment = _load_yaml(amendment_config_path)
    preregistration = _load_json(preregistration_path)
    locks = _verify_preregistration(
        amendment_config_path, amendment, preregistration_path, preregistration
    )
    natural_elapsed = time.time() - float(locks["preregistration_commit_epoch"])
    if natural_elapsed > float(amendment["execution_boundary"]["natural_elapsed_s_max"]):
        raise RuntimeError("S1 natural elapsed budget was exhausted before execution")

    s2_path = _repo_path(amendment["source_scale_identity"]["S2_config_path"])
    s2 = _load_yaml(s2_path)
    scale = _source_scale(base, amendment, s2)
    response = base["response_contract"]
    pulse = response["regularized_impulse_response"]
    pulse_width = float(pulse["pulse_width_s"])
    pulse_amplitude = float(pulse["pulse_amplitude_W_m2"])
    fit_frequency, fit_time = fit_grids(response)
    validation_frequency, validation_time = validation_grids(response)
    reference_control = amendment["analytic_reference_control"]
    analytic = DiffusiveThermalImpedance(
        scale["gtheta_A_W_m2K"],
        scale["cm_A_J_m2K"],
        modal_terms=int(reference_control["production_modal_terms"]),
        modal_chunk_terms=int(reference_control["evaluation_chunk_terms"]),
    )
    comparator = DiffusiveThermalImpedance(
        scale["gtheta_A_W_m2K"],
        scale["cm_A_J_m2K"],
        modal_terms=int(reference_control["comparator_modal_terms"]),
        modal_chunk_terms=int(reference_control["evaluation_chunk_terms"]),
    )
    print("S1-MVE: certify 16384/32768 modal reference", flush=True)
    reference_cache = analytic_reference_response_cache(
        production=analytic,
        comparator=comparator,
        fit_time_s=fit_time,
        validation_time_s=validation_time,
        pulse_width_s=pulse_width,
        pulse_amplitude_W_m2=pulse_amplitude,
    )
    reference_metrics = analytic_reference_discrepancy(
        production=analytic,
        comparator=comparator,
        fit_time_s=fit_time,
        validation_time_s=validation_time,
        pulse_width_s=pulse_width,
        pulse_amplitude_W_m2=pulse_amplitude,
        response_cache=reference_cache,
    )
    reference_pass = bool(
        reference_metrics["maximum_reference_discrepancy"]
        <= float(reference_control["reference_discrepancy_max"])
    )
    print(
        "S1-MVE: modal reference "
        + ("passed" if reference_pass else "failed"),
        flush=True,
    )
    pointwise_rows = _reference_pointwise_rows(
        analytic,
        comparator,
        fit_time=fit_time,
        validation_time=validation_time,
        pulse_width=pulse_width,
        pulse_amplitude=pulse_amplitude,
        response_cache=reference_cache,
    )
    fits_rows: list[dict[str, object]] = []
    attempts: list[dict[str, Any]] = []
    disposition = str(reference_control["comparator_failure_disposition"])
    selected_order: int | None = None

    if reference_pass:
        reduction = base["foster_reduction"]
        optimizer = reduction["optimizer"]
        safety = amendment["optimizer_safety"]
        weight_bounds = safety["log_bounds"]["normalized_weight"]
        multiplier_bounds = safety["log_bounds"]["normalized_time_multiplier"]
        fit_weights = {
            key: float(value["weight"])
            for key, value in reduction["fitting_objective"]["terms"].items()
        }
        event_times = pulse_event_times(
            pulse_width, reference_control["pulse_event_audit_times_relative_to_width"]
        )
        for order in amendment["validation_amendments"]["K_schedule"]:
            candidates: list[
                tuple[FosterThermalImpedance | None, dict[str, object]]
            ] = []
            order_rows: list[dict[str, object]] = []
            for start in reduction["deterministic_multistarts"]["starts"]:
                print(
                    f"S1-MVE: fit K={int(order)} start={start['id']}", flush=True
                )
                model, metadata = fit_foster_candidate(
                    start_id=str(start["id"]),
                    multipliers=np.asarray(start[f"K{int(order)}_multipliers"]),
                    analytic=analytic,
                    fit_frequency_Hz=fit_frequency,
                    fit_time_s=fit_time,
                    pulse_width_s=pulse_width,
                    pulse_amplitude_W_m2=pulse_amplitude,
                    weights=fit_weights,
                    maximum_iterations=int(optimizer["maximum_iterations"]),
                    ftol=float(optimizer["ftol"]),
                    equality_tolerance=float(
                        amendment["candidate_eligibility"][
                            "equality_constraint_absolute_tolerance"
                        ]
                    ),
                    log_weight_bounds=(
                        float(weight_bounds["minimum"]),
                        float(weight_bounds["maximum"]),
                    ),
                    log_multiplier_bounds=(
                        float(multiplier_bounds["minimum"]),
                        float(multiplier_bounds["maximum"]),
                    ),
                    finite_penalty=float(safety["finite_penalty"]),
                    boundary_hit_tolerance=float(
                        safety["boundary_hit_tolerance_log_coordinate"]
                    ),
                )
                row = dict(metadata)
                row.update({"selected_for_validation": False, "validation_pass": ""})
                order_rows.append(row)
                candidates.append((model, metadata))
                print(
                    "S1-MVE: fit completed "
                    f"K={int(order)} start={start['id']} "
                    f"eligible={metadata['candidate_eligible']} "
                    f"objective={metadata['fit_objective']}",
                    flush=True,
                )
            fits_rows.extend(order_rows)
            selected_candidate = select_training_candidate(candidates)
            if selected_candidate is None:
                disposition = str(
                    amendment["candidate_eligibility"][
                        "all_starts_ineligible_disposition"
                    ]
                )
                attempts.append(
                    {"order": int(order), "eligible_start_count": 0, "passed": False}
                )
                break
            foster, selected_metadata = selected_candidate
            selected_id = str(selected_metadata["start_id"])
            selected_row = next(
                row
                for row in fits_rows
                if int(row["order"]) == int(order)
                and str(row["start_id"]) == selected_id
            )
            selected_row["selected_for_validation"] = True
            selected_row["foster_resistances_m2K_W"] = json.dumps(
                foster.resistances_m2K_W.tolist(), separators=(",", ":")
            )
            selected_row["foster_time_constants_s"] = json.dumps(
                foster.time_constants_s.tolist(), separators=(",", ":")
            )
            try:
                print(
                    f"S1-MVE: validate K={int(order)} start={selected_id}",
                    flush=True,
                )
                cauer = foster_to_cauer_ii(
                    foster,
                    gtheta_A_W_m2K=analytic.gtheta_A_W_m2K,
                    cm_A_J_m2K=analytic.cm_A_J_m2K,
                )
                metrics = validation_metrics(
                    analytic=analytic,
                    foster=foster,
                    cauer=cauer,
                    validation_frequency_Hz=validation_frequency,
                    validation_time_s=validation_time,
                    pulse_width_s=pulse_width,
                    pulse_amplitude_W_m2=pulse_amplitude,
                    ledger_contract=amendment["cauer_embedding_and_validation"][
                        "backward_euler_ledger"
                    ],
                )
                passed = metrics_pass(
                    metrics,
                    base["gates"],
                    cauer_reconstruction_tolerance=float(
                        amendment["cauer_embedding_and_validation"][
                            "reconstruction_relative_error_max"
                        ]
                    ),
                    ledger_tolerance=float(
                        amendment["cauer_embedding_and_validation"][
                            "backward_euler_ledger"
                        ]["relative_residual_max"]
                    ),
                )
                selected_row.update(metrics)
                selected_row["cauer_capacities_J_m2K"] = json.dumps(
                    cauer.capacities_J_m2K.tolist(), separators=(",", ":")
                )
                selected_row["cauer_series_resistances_m2K_W"] = json.dumps(
                    cauer.series_resistances_m2K_W.tolist(), separators=(",", ":")
                )
                selected_row["cauer_terminal_conductance_W_m2K"] = float(
                    cauer.terminal_conductance_W_m2K
                )
                selected_row["validation_pass"] = passed
                pointwise_rows.extend(
                    _candidate_pointwise_rows(
                        order=int(order),
                        start_id=selected_id,
                        analytic=analytic,
                        foster=foster,
                        cauer=cauer,
                        frequency=validation_frequency,
                        time_grid=validation_time,
                        event_times=event_times,
                        pulse_width=pulse_width,
                        pulse_amplitude=pulse_amplitude,
                    )
                )
            except (ValueError, FloatingPointError, np.linalg.LinAlgError) as error:
                metrics = {}
                passed = False
                selected_row["validation_pass"] = False
                selected_row["cauer_exception"] = f"{type(error).__name__}: {error}"
            attempts.append(
                {
                    "order": int(order),
                    "eligible_start_count": sum(
                        candidate_eligible(metadata) for _, metadata in candidates
                    ),
                    "selected_start_id": selected_id,
                    "training_objective": float(selected_metadata["fit_objective"]),
                    "passed": bool(passed),
                    "metrics": metrics,
                }
            )
            if passed:
                selected_order = int(order)
                disposition = "S1_MVE_SELF_CONSISTENCY_PASS_SENSITIVITY_ONLY"
                break
            disposition = str(
                amendment["candidate_eligibility"][
                    "selected_model_gate_failure_disposition"
                ]
            )

    if not fits_rows:
        fits_rows.append(
            {
                "order": 0,
                "start_id": "analytic_reference",
                "candidate_eligible": False,
                "selected_for_validation": False,
                "validation_pass": False,
                "disposition": disposition,
            }
        )

    output_config = amendment["outputs"]
    fits_path = _repo_path(output_config["fits"])
    pointwise_path = _repo_path(output_config["pointwise"])
    summary_path = _repo_path(output_config["summary"])
    report_path = _repo_path(output_config["report"])
    _atomic_csv(fits_path, fits_rows)
    _atomic_csv(pointwise_path, pointwise_rows)
    print("S1-MVE: wrote atomic CSV evidence", flush=True)

    runtime = time.perf_counter() - start_clock
    if runtime > float(amendment["execution_boundary"]["active_work_s_max"]):
        disposition = "STOP_S1_BUDGET"
        selected_order = None
    summary: dict[str, Any] = {
        "schema_version": "geophase_phase1_v2_s1_diffusive_mve_result_v2",
        "task_id": amendment["task_id"],
        "evidence_type": "nonformal_synthetic_model_form_sensitivity",
        "disposition": disposition,
        "claim_status": "qualified_supported"
        if selected_order is not None
        else "failed_but_informative",
        "formal_execution_count": 0,
        "formal_execution_consumed": False,
        "formal_artifacts_created": False,
        "production_selected": False,
        "S2_remains_nominal": True,
        "eligible_same_device_holdout_used": False,
        "selected_sensitivity_order": selected_order,
        "source_scale": scale | {"tau_s": float(analytic.tau_s)},
        "analytic_reference": reference_metrics | {"passed": reference_pass},
        "order_attempts": attempts,
        "locks": locks,
        "environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "scipy": scipy.__version__,
            "platform": platform.platform(),
            "cpu_only": True,
        },
        "budget": {
            "script_wall_clock_s": float(runtime),
            "natural_elapsed_since_preregistration_s": float(natural_elapsed),
            "active_work_s_max": int(
                amendment["execution_boundary"]["active_work_s_max"]
            ),
            "natural_elapsed_s_max": int(
                amendment["execution_boundary"]["natural_elapsed_s_max"]
            ),
        },
        "execution_history": [
            {
                "kind": "infrastructure_interruption",
                "note": note,
                "scientific_vote": False,
                "formal_execution_count_increment": 0,
                "formal_artifacts_created": False,
            }
            for note in (infrastructure_interruption_notes or [])
        ],
        "artifacts": {
            "fits": {"path": str(fits_path.relative_to(ROOT)), "sha256": _sha256(fits_path)},
            "pointwise": {
                "path": str(pointwise_path.relative_to(ROOT)),
                "sha256": _sha256(pointwise_path),
            },
        },
        "claim_boundary": {
            "allowed": amendment["claim_boundary"]["maximum_without_holdout"],
            "forbidden": amendment["claim_boundary"]["forbidden_without_holdout"],
        },
    }
    _atomic_json(summary_path, summary)
    _atomic_text(report_path, _report(summary))
    print(f"S1-MVE: completed disposition={disposition}", flush=True)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=AMENDMENT_CONFIG_PATH)
    parser.add_argument("--base-config", type=Path, default=BASE_CONFIG_PATH)
    parser.add_argument("--preregistration", type=Path, default=PREREGISTRATION_PATH)
    parser.add_argument(
        "--infrastructure-interruption-note",
        action="append",
        help="Non-voting provenance for a prior interrupted attempt.",
    )
    arguments = parser.parse_args()
    summary = run_mve(
        base_config_path=arguments.base_config,
        amendment_config_path=arguments.config,
        preregistration_path=arguments.preregistration,
        infrastructure_interruption_notes=arguments.infrastructure_interruption_note,
    )
    print(
        json.dumps(
            {
                "disposition": summary["disposition"],
                "selected_sensitivity_order": summary[
                    "selected_sensitivity_order"
                ],
                "production_selected": False,
                "formal_execution_count": 0,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
