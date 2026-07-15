"""Run the D0a exact-source and SI semantic-equivalence audit."""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import torch
import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pinnpcm.external_data.vo2_zhang import (
    load_manifest,
    load_rt_curve,
    load_tektronix_trace,
    load_theory_trace,
)
from pinnpcm.physics.vo2_thermal_neuristor import (
    NeuristorTrace,
    VO2ThermalNeuristorParameters,
    resistance_path_ohm,
    simulate_source_compat_si,
)

DEFAULT_CONFIG = Path("configs/vo2_d0a_exact_source_v2.yaml")
DISCREPANCY_FIELDS = [
    "source_surface",
    "item",
    "source_value",
    "repository_value",
    "unit",
    "status",
    "note",
]


def _resolve(path: str | Path) -> Path:
    value = Path(path)
    return value if value.is_absolute() else ROOT / value


def _display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _load_config(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(_resolve(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("D0a config must be a mapping.")
    return payload


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def _git_output(*args: str) -> str:
    return subprocess.check_output(
        ["git", *args],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
    ).strip()


def _nrmse95(prediction: np.ndarray, target: np.ndarray, *, floor: float = 1.0e-30) -> float:
    pred = np.asarray(prediction, dtype=np.float64)
    truth = np.asarray(target, dtype=np.float64)
    if pred.shape != truth.shape:
        raise ValueError("NRMSE inputs must have equal shapes.")
    scale = max(float(np.quantile(truth, 0.95) - np.quantile(truth, 0.05)), floor)
    return float(np.sqrt(np.mean((pred - truth) ** 2)) / scale)


def _load_author_module(path: Path) -> Any:
    spec = importlib.util.spec_from_file_location("zhang_author_model_v1_0_0", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load author model from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _author_dynamic_reference(
    module: Any,
    params: VO2ThermalNeuristorParameters,
    *,
    input_voltage_V: float,
    t_max_ns: float,
    dt_ns: float,
) -> NeuristorTrace:
    old_dtype = torch.get_default_dtype()
    torch.set_default_dtype(torch.float64)
    try:
        circuit = module.Circuit2D(
            batch=1,
            Nx=1,
            Ny=1,
            V=input_voltage_V,
            R=params.R_load_ohm / 1000.0,
            noise_strength=0.0,
            Cth_factor=params.Cth_factor,
            couple_factor=params.couple_factor,
            width_factor=1.0,
            T_base=params.T_base_K,
        )
        y = torch.stack(
            [
                torch.zeros(1, 1, dtype=torch.float64),
                torch.ones(1, 1, dtype=torch.float64) * params.T_base_K,
            ],
            dim=1,
        )
        n_steps = int(t_max_ns / dt_ns)
        time_ns = 0.0
        times = np.empty(n_steps, dtype=np.float64)
        current = np.empty(n_steps, dtype=np.float64)
        voltage = np.empty(n_steps, dtype=np.float64)
        temperature = np.empty(n_steps, dtype=np.float64)
        resistance = np.empty(n_steps, dtype=np.float64)
        branch = np.empty(n_steps, dtype=np.float64)
        event_times: list[float] = []
        for index in range(n_steps):
            previous_delta = float(circuit.VO2.delta[0].item())
            dy = circuit.step(time_ns, y)
            current[index] = float(circuit.IR[0, 0].item()) * 1.0e-3
            voltage[index] = float(y[0, 0, 0].item())
            temperature[index] = float(y[0, 1, 0].item())
            resistance[index] = (
                float(circuit.VO2.R(y[:, 1].reshape(-1))[0].item()) * 1000.0
            )
            branch[index] = float(circuit.VO2.delta[0].item())
            if branch[index] != previous_delta:
                event_times.append(time_ns * 1.0e-9)
            time_ns += dt_ns
            y += dy * dt_ns
            times[index] = time_ns * 1.0e-9
        return NeuristorTrace(
            time_s=times,
            current_A=current,
            voltage_V=voltage,
            temperature_K=temperature,
            resistance_ohm=resistance,
            event_times_s=np.asarray(event_times, dtype=np.float64),
            branch=branch,
            source_kind="author_exact",
        )
    finally:
        torch.set_default_dtype(old_dtype)


def _author_rt_reference(
    module: Any,
    temperature_K: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    old_dtype = torch.get_default_dtype()
    torch.set_default_dtype(torch.float64)
    try:
        model = module.VO2(1)
        first = float(temperature_K[0])
        model.initialize(first)
        values: list[float] = []
        branches: list[float] = []
        events: list[int] = []
        for index, value in enumerate(temperature_K):
            before = float(model.delta[0].item())
            tensor = torch.tensor([float(value)], dtype=torch.float64)
            model.reversal(tensor)
            after = float(model.delta[0].item())
            if after != before:
                events.append(index)
            values.append(float(model.R(tensor)[0].item()) * 1000.0)
            branches.append(after)
        return (
            np.asarray(values, dtype=np.float64),
            np.asarray(branches, dtype=np.float64),
            np.asarray(events, dtype=np.int64),
        )
    finally:
        torch.set_default_dtype(old_dtype)


def _parameter_discrepancies(
    module: Any,
    params: VO2ThermalNeuristorParameters,
) -> list[dict[str, Any]]:
    old_dtype = torch.get_default_dtype()
    torch.set_default_dtype(torch.float64)
    try:
        model = module.VO2(1)
        circuit = module.Circuit2D(
            batch=1,
            Nx=1,
            Ny=1,
            V=11.0,
            R=params.R_load_ohm / 1000.0,
            noise_strength=0.0,
            Cth_factor=params.Cth_factor,
            couple_factor=params.couple_factor,
            width_factor=1.0,
            T_base=params.T_base_K,
        )
        checks = [
            ("w", model.w, params.w_K, "K"),
            ("Tc", model.Tc, params.T_c_K, "K"),
            ("beta", model.beta, params.beta_per_K, "K^-1"),
            ("R0", model.R0, params.R0_ohm, "ohm"),
            ("Ea", model.Ea, params.E_a_K, "K"),
            ("gamma", model.gamma, params.gamma_per_K, "K^-1"),
            ("Rm0", model.Rm0, params.Rm0_ohm, "ohm"),
            ("Rm_factor", model.Rm_factor, params.Rm_factor, "1"),
            ("Rm_product", model.Rm, params.R_metal_ohm, "ohm"),
            ("C0", circuit.C0, params.C_F * 1.0e12, "pF"),
            ("Cth", circuit.Cth, params.C_th_J_per_K * 1.0e12, "mW ns K^-1"),
            ("Sth", circuit.Sth, params.S_th_W_per_K * 1.0e3, "mW K^-1"),
            ("T_base", circuit.T_base, params.T_base_K, "K"),
            ("R_load", circuit.R0, params.R_load_ohm / 1000.0, "kOhm"),
        ]
        rows: list[dict[str, Any]] = []
        for item, source, repository, unit in checks:
            matches = bool(np.isclose(float(source), float(repository), rtol=1.0e-12, atol=1.0e-12))
            rows.append(
                {
                    "source_surface": "github_tag_v1.0.0_model.py",
                    "item": item,
                    "source_value": float(source),
                    "repository_value": float(repository),
                    "unit": unit,
                    "status": "match" if matches else "unexplained_mismatch",
                    "note": "Direct author-code versus YAML comparison.",
                }
            )
        rows.extend(
            [
                {
                    "source_surface": "github_tag_v1.0.0_model.py",
                    "item": "Rm_parameterization",
                    "source_value": "Rm0 * Rm_factor",
                    "repository_value": "single observable product R_metal",
                    "unit": "ohm",
                    "status": "structural_equivalence_recorded",
                    "note": "Rm0 and Rm_factor cannot be separately identified from this model output.",
                },
                {
                    "source_surface": "nature_methods",
                    "item": "parameter_development_boundary",
                    "source_value": "parameters optimized to reproduce experimental results",
                    "repository_value": "13 V is not an independent external holdout",
                    "unit": "evidence_semantics",
                    "status": "claim_boundary_recorded",
                    "note": "Only repository-withheld preregistered cross-voltage wording is allowed.",
                },
            ]
        )
        return rows
    finally:
        torch.set_default_dtype(old_dtype)


def _event_difference_dt(
    author_events: np.ndarray,
    repository_events: np.ndarray,
    dt_s: float,
) -> float:
    if author_events.size != repository_events.size:
        return float("inf")
    if author_events.size == 0:
        return 0.0
    return float(np.max(np.abs(author_events - repository_events)) / dt_s)


def run_d0a(config_path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    started_at_utc = datetime.now(timezone.utc).isoformat()
    cfg = _load_config(config_path)
    paths = cfg["paths"]
    manifest = load_manifest(_resolve(paths["manifest_json"]))
    if manifest["sealed_member_content_read_prelock"]:
        raise RuntimeError("Manifest reports pre-lock 13 V content access.")
    params = VO2ThermalNeuristorParameters.from_config(cfg)
    author_model_path = _resolve(paths["author_code_dir"]) / "model.py"
    author = _load_author_module(author_model_path)

    discrepancy_rows = _parameter_discrepancies(author, params)
    discrepancy_path = _resolve(paths["discrepancy_csv"])
    discrepancy_path.parent.mkdir(parents=True, exist_ok=True)
    with discrepancy_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=DISCREPANCY_FIELDS)
        writer.writeheader()
        writer.writerows(discrepancy_rows)

    source_root = _resolve(paths["allowed_extract_dir"]) / "Source Data" / "Fig. 1"
    rt = load_rt_curve(source_root / "Fig. 1b.csv")
    experiment = load_tektronix_trace(
        source_root / "Fig. 1c" / "Experiment_11V.csv",
        current_sense_ohm=float(
            cfg["measurement_semantics"]["current_channel_input_impedance_ohm"]
        ),
    )
    theory = load_theory_trace(source_root / "Fig. 1c" / "Theory_11V.csv")

    author_rt, author_rt_branch, author_rt_events = _author_rt_reference(
        author, rt["temperature_K"]
    )
    repository_rt, repository_rt_branch, repository_rt_events = resistance_path_ohm(
        rt["temperature_K"], params
    )
    rt_parity_nrmse = _nrmse95(repository_rt, author_rt)
    rt_data_nrmse = _nrmse95(author_rt, rt["resistance_ohm"])

    mve = cfg["parity_mve"]
    dt_values_ns = [float(value) for value in mve["dt_values_ns"]]
    author_trace = _author_dynamic_reference(
        author,
        params,
        input_voltage_V=float(mve["voltage_V"]),
        t_max_ns=float(mve["t_max_ns"]),
        dt_ns=dt_values_ns[0],
    )
    repository_traces: dict[float, NeuristorTrace] = {}
    for dt_ns in dt_values_ns:
        repository_traces[dt_ns] = simulate_source_compat_si(
            params,
            input_voltage_V=float(mve["voltage_V"]),
            t_max_s=float(mve["t_max_ns"]) * 1.0e-9,
            dt_s=dt_ns * 1.0e-9,
            noise_strength=float(mve["noise_strength"]),
            seed=int(mve["seed"]),
        )
    repository_at_source_dt = repository_traces[dt_values_ns[0]]
    dynamic_parity_nrmse = _nrmse95(
        repository_at_source_dt.current_A,
        author_trace.current_A,
    )
    dynamic_voltage_nrmse = _nrmse95(
        repository_at_source_dt.voltage_V,
        author_trace.voltage_V,
    )
    dynamic_temperature_nrmse = _nrmse95(
        repository_at_source_dt.temperature_K,
        author_trace.temperature_K,
    )
    event_time_difference_dt = _event_difference_dt(
        author_trace.event_times_s,
        repository_at_source_dt.event_times_s,
        dt_values_ns[0] * 1.0e-9,
    )

    fine_dt = dt_values_ns[-1]
    medium_dt = dt_values_ns[-2]
    fine = repository_traces[fine_dt]
    medium = repository_traces[medium_dt]
    fine_current_on_medium = np.interp(medium.time_s, fine.time_s, fine.current_A)
    fine_dt_nrmse = _nrmse95(fine_current_on_medium, medium.current_A)

    time_window_us = cfg["measurement_semantics"]["primary_time_window_us"]
    exp_mask = (
        (experiment["time_s"] >= float(time_window_us[0]) * 1.0e-6)
        & (experiment["time_s"] <= float(time_window_us[1]) * 1.0e-6)
    )
    exp_time = experiment["time_s"][exp_mask]
    exp_current = experiment["current_A"][exp_mask]
    theory_on_exp = np.interp(exp_time, theory["time_s"], theory["current_A"])
    author_on_theory = np.interp(
        theory["time_s"], author_trace.time_s, author_trace.current_A
    )
    author_on_exp = np.interp(exp_time, author_trace.time_s, author_trace.current_A)
    public_metrics = {
        "rt_author_no_fit_nrmse95": rt_data_nrmse,
        "publisher_theory_vs_experiment_11v_nrmse95": _nrmse95(
            theory_on_exp, exp_current
        ),
        "author_code_vs_publisher_theory_11v_nrmse95": _nrmse95(
            author_on_theory, theory["current_A"]
        ),
        "author_code_vs_experiment_11v_nrmse95": _nrmse95(
            author_on_exp, exp_current
        ),
        "note": "Reported without refitting; these errors are not relaxed or hidden.",
    }

    gates = cfg["gates"]
    unexplained = [
        row for row in discrepancy_rows if row["status"] == "unexplained_mismatch"
    ]
    license_ids = {item["license_id"] for item in manifest["artifacts"]}
    gate_results = {
        "provenance_complete": all(
            item.get("source_url") and item.get("license_id")
            for item in manifest["artifacts"]
        ),
        "license_separation": {"CC-BY-4.0", "MIT"}.issubset(license_ids),
        "sealed_13v_untouched": (
            manifest["sealed_member_count"] >= 1
            and not manifest["sealed_member_content_read_prelock"]
        ),
        "no_unexplained_parameter_mismatch": not unexplained,
        "rt_source_si_nrmse": rt_parity_nrmse
        <= float(gates["source_compat_nrmse_max"]),
        "rt_event_count_exact": author_rt_events.size == repository_rt_events.size,
        "rt_branch_exact": bool(np.array_equal(author_rt_branch, repository_rt_branch)),
        "dynamic_source_si_nrmse": dynamic_parity_nrmse
        <= float(gates["source_compat_nrmse_max"]),
        "dynamic_event_count_exact": (
            author_trace.event_times_s.size
            == repository_at_source_dt.event_times_s.size
        ),
        "dynamic_event_time_within_dt": event_time_difference_dt
        <= float(gates["source_compat_event_time_dt_max"]),
        "finest_time_step_convergence": fine_dt_nrmse
        <= float(gates["finest_dt_nrmse_max"]),
    }
    passed = all(gate_results.values())
    status = cfg["claim_status_pass"] if passed else cfg["claim_status_fail"]

    processed_dir = _resolve(paths["processed_dir"])
    processed_dir.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        processed_dir / "source_and_si_parity.npz",
        author_time_s=author_trace.time_s,
        author_current_A=author_trace.current_A,
        repository_time_s=repository_at_source_dt.time_s,
        repository_current_A=repository_at_source_dt.current_A,
        repository_temperature_K=repository_at_source_dt.temperature_K,
        author_event_times_s=author_trace.event_times_s,
        repository_event_times_s=repository_at_source_dt.event_times_s,
        source_kind=np.asarray(["author_exact", "repository_si_solver"]),
    )

    summary = {
        "schema_version": "vo2_d0a_evidence_v2",
        "benchmark": cfg["benchmark"],
        "stage_id": cfg["stage_id"],
        "run_class": "source_paper_model_reproduction",
        "base_sha": _git_output("rev-parse", "HEAD"),
        "git_dirty": bool(_git_output("status", "--short")),
        "config_path": _display(_resolve(config_path)),
        "config_sha256": _sha256(_resolve(config_path)),
        "data_manifest_sha256": _sha256(_resolve(paths["manifest_json"])),
        "seed": int(mve["seed"]),
        "started_at_utc": started_at_utc,
        "ended_at_utc": datetime.now(timezone.utc).isoformat(),
        "evidence_type": "public_external_and_solver_reproduction",
        "claim_status": status,
        "gate_passed": passed,
        "gate_results": gate_results,
        "source_semantics": cfg["source_semantics"],
        "measurement_semantics": cfg["measurement_semantics"],
        "source_si_metrics": {
            "rt_nrmse95": rt_parity_nrmse,
            "dynamic_current_nrmse95": dynamic_parity_nrmse,
            "dynamic_voltage_nrmse95": dynamic_voltage_nrmse,
            "dynamic_temperature_nrmse95": dynamic_temperature_nrmse,
            "event_time_max_difference_dt": event_time_difference_dt,
            "medium_vs_fine_dt_current_nrmse95": fine_dt_nrmse,
            "author_rt_event_count": int(author_rt_events.size),
            "repository_rt_event_count": int(repository_rt_events.size),
            "author_dynamic_event_count": int(author_trace.event_times_s.size),
            "repository_dynamic_event_count": int(
                repository_at_source_dt.event_times_s.size
            ),
        },
        "public_no_fit_metrics": public_metrics,
        "forward_evaluations": 1 + len(dt_values_ns) + 2,
        "forward_evaluation_budget": int(mve["maximum_forward_evaluations"]),
        "sealed_member_count": manifest["sealed_member_count"],
        "sealed_member_content_read_prelock": False,
        "evidence_semantics": manifest["evidence_semantics"],
        "outputs": {
            "manifest_json": paths["manifest_json"],
            "discrepancy_csv": paths["discrepancy_csv"],
            "parity_npz": _display(processed_dir / "source_and_si_parity.npz"),
            "summary_json": paths["summary_json"],
        },
        "machine_summary": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "torch": torch.__version__,
            "numpy": np.__version__,
            "device": "cpu",
        },
        "allowed_wording": cfg["claim_boundary"]["allowed"] if passed else "",
        "forbidden_wording": cfg["claim_boundary"]["forbidden"],
        "failure_interpretation": (
            ""
            if passed
            else "D0a failed; D0b-D0d remain stopped. N0 may continue independently."
        ),
    }
    summary_path = _resolve(paths["summary_json"])
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    summary = run_d0a(args.config)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
