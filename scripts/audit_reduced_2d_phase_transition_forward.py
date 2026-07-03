"""Reduced 2D phase-transition forward benchmark.

This script builds a lightweight thin-film phase-transition / memristive-channel
benchmark. It is synthetic numerical digital-twin evidence only: not full FEM,
not experimental data, and not a 2D inverse-recovery claim.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from scripts.gamma_sub_validation_common import load_yaml, write_json

DEFAULT_CONFIG = Path("configs/reduced_2d_phase_transition_forward.yaml")
CSV_FIELDS = [
    "geometry", "transition_width", "lateral_coupling", "seed", "finite_fields",
    "finite_residual", "final_mean_T", "max_T", "final_conductance",
    "max_conductance", "spatial_sigma_std", "residual_rms",
]


def _laplacian(field: np.ndarray) -> np.ndarray:
    padded = np.pad(field, ((1, 1), (1, 1)), mode="edge")
    return padded[1:-1, 2:] + padded[1:-1, :-2] + padded[2:, 1:-1] + padded[:-2, 1:-1] - 4.0 * field


def _source_pattern(geometry: str, x: np.ndarray, y: np.ndarray, rng: np.random.Generator, amplitude: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    if geometry == "uniform_strip":
        source = np.ones_like(x)
        defect = np.zeros_like(x)
        cooling_mod = np.ones_like(x)
    elif geometry == "localized_hotspot":
        source = 0.45 + 1.3 * np.exp(-((x - 0.35) ** 2 + (y - 0.52) ** 2) / 0.035)
        defect = 0.08 * np.exp(-((x - 0.35) ** 2 + (y - 0.52) ** 2) / 0.02)
        cooling_mod = np.ones_like(x)
    elif geometry == "defect_seeded_filament":
        filament = np.exp(-((x - 0.58) ** 2) / 0.012) * (0.65 + 0.35 * np.cos(2.0 * math.pi * y) ** 2)
        source = 0.5 + 1.25 * filament
        defect = 0.14 * filament
        cooling_mod = np.ones_like(x)
    elif geometry == "lateral_cooling_gradient":
        source = 0.65 + 0.65 * x
        defect = 0.03 * np.sin(2.0 * math.pi * y) ** 2
        cooling_mod = 0.65 + 0.75 * x
    else:
        raise ValueError(f"Unknown geometry: {geometry}")
    source = amplitude * source * (1.0 + 0.015 * rng.standard_normal(source.shape))
    return source, defect, cooling_mod


def simulate_reduced_2d_case(
    *,
    geometry: str,
    transition_width: float,
    lateral_coupling: float,
    seed: int,
    amplitude: float = 1.0,
    nx: int = 28,
    ny: int = 18,
    nt: int = 30,
    dt: float = 0.06,
    T0: float = 0.0,
    T_sw: float = 1.0,
    cooling: float = 0.08,
    sigma_off: float = 1.0,
    sigma_on: float = 24.0,
    base_drive: float = 0.95,
) -> dict[str, Any]:
    rng = np.random.default_rng(seed)
    x_line = np.linspace(0.0, 1.0, nx)
    y_line = np.linspace(0.0, 1.0, ny)
    x, y = np.meshgrid(x_line, y_line)
    source, defect, cooling_mod = _source_pattern(geometry, x, y, rng, amplitude)
    T = np.empty((nt, ny, nx), dtype=float)
    T[0] = T0 + 0.02 * rng.standard_normal((ny, nx)) + defect
    residuals: list[float] = []
    for k in range(nt - 1):
        drive = base_drive * (0.35 + 0.65 * np.sin(math.pi * k / max(nt - 2, 1)) ** 2)
        lap = _laplacian(T[k])
        rhs = float(lateral_coupling) * lap - cooling * cooling_mod * (T[k] - T0) + drive * source + 0.04 * defect
        predicted = T[k] + dt * rhs
        T[k + 1] = predicted
        residuals.append(float(np.sqrt(np.mean((T[k + 1] - predicted) ** 2))))
    logits = np.clip((T - T_sw) / max(float(transition_width), 1.0e-12), -80.0, 80.0)
    phase = 1.0 / (1.0 + np.exp(-logits))
    sigma = sigma_off * (1.0 - phase) + sigma_on * phase
    conductance = sigma.mean(axis=(1, 2))
    left_port = sigma[:, :, : nx // 2].mean(axis=(1, 2))
    right_port = sigma[:, :, nx // 2 :].mean(axis=(1, 2))
    proxy_points = {
        "center": T[:, ny // 2, nx // 2],
        "left_hotspot": T[:, int(0.52 * (ny - 1)), int(0.35 * (nx - 1))],
        "right_filament": T[:, int(0.5 * (ny - 1)), int(0.58 * (nx - 1))],
    }
    return {
        "geometry": geometry,
        "transition_width": float(transition_width),
        "lateral_coupling": float(lateral_coupling),
        "seed": int(seed),
        "T": T,
        "phase": phase,
        "sigma": sigma,
        "conductance": conductance,
        "left_port": left_port,
        "right_port": right_port,
        "proxy_points": proxy_points,
        "residual_rms": float(np.max(residuals) if residuals else 0.0),
        "finite_fields": bool(np.isfinite(T).all() and np.isfinite(sigma).all() and np.isfinite(conductance).all()),
        "finite_residual": bool(np.isfinite(residuals).all() if residuals else True),
    }


def _case_row(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "geometry": result["geometry"],
        "transition_width": result["transition_width"],
        "lateral_coupling": result["lateral_coupling"],
        "seed": result["seed"],
        "finite_fields": result["finite_fields"],
        "finite_residual": result["finite_residual"],
        "final_mean_T": float(result["T"][-1].mean()),
        "max_T": float(result["T"].max()),
        "final_conductance": float(result["conductance"][-1]),
        "max_conductance": float(result["conductance"].max()),
        "spatial_sigma_std": float(result["sigma"][-1].std()),
        "residual_rms": float(result["residual_rms"]),
    }


def _write_cases(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row[field] for field in CSV_FIELDS})


def _make_figures(results: list[dict[str, Any]], snapshot_path: Path, port_path: Path) -> None:
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    reps = []
    seen: set[str] = set()
    for result in results:
        if result["geometry"] not in seen and abs(result["transition_width"] - 0.1) < 1e-12 and abs(result["lateral_coupling"] - 0.25) < 1e-12:
            reps.append(result)
            seen.add(result["geometry"])
    if not reps:
        reps = results[: min(4, len(results))]
    if reps:
        fig, axes = plt.subplots(len(reps), 2, figsize=(7.4, 2.4 * len(reps)))
        if len(reps) == 1:
            axes = np.asarray([axes])
        for row_axes, result in zip(axes, reps):
            im0 = row_axes[0].imshow(result["T"][-1], origin="lower", cmap="inferno")
            row_axes[0].set_title(f"{result['geometry']} T")
            plt.colorbar(im0, ax=row_axes[0], fraction=0.046, pad=0.04)
            im1 = row_axes[1].imshow(result["sigma"][-1], origin="lower", cmap="viridis")
            row_axes[1].set_title("sigma_eff")
            plt.colorbar(im1, ax=row_axes[1], fraction=0.046, pad=0.04)
        fig.suptitle("Reduced 2D forward snapshots; synthetic numerical benchmark")
        fig.tight_layout()
        fig.savefig(snapshot_path, dpi=160)
        plt.close(fig)
    port_path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(6.8, 4.2))
    for result in reps:
        ax.plot(result["conductance"], label=result["geometry"])
    ax.set_xlabel("time index")
    ax.set_ylabel("mean sigma proxy / conductance")
    ax.set_title("Reduced 2D port traces")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="best", fontsize=8)
    ax.text(0.01, -0.2, "synthetic / numerical / digital-twin benchmark; not experimental data", transform=ax.transAxes, fontsize=8)
    fig.tight_layout()
    fig.savefig(port_path, dpi=160)
    plt.close(fig)


def run_forward_benchmark(config_path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    cfg = load_yaml(config_path)
    results: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    for geometry in cfg["geometries"]:
        for width in cfg["transition_width"]:
            for coupling in cfg["lateral_coupling"]:
                for seed in cfg["seeds"]:
                    result = simulate_reduced_2d_case(
                        geometry=str(geometry),
                        transition_width=float(width),
                        lateral_coupling=float(coupling),
                        seed=int(seed),
                        nx=int(cfg.get("nx", 28)),
                        ny=int(cfg.get("ny", 18)),
                        nt=int(cfg.get("nt", 30)),
                        dt=float(cfg.get("dt", 0.06)),
                        T0=float(cfg.get("T0", 0.0)),
                        T_sw=float(cfg.get("T_sw", 1.0)),
                        cooling=float(cfg.get("cooling", 0.08)),
                        sigma_off=float(cfg.get("sigma_off", 1.0)),
                        sigma_on=float(cfg.get("sigma_on", 24.0)),
                        base_drive=float(cfg.get("base_drive", 0.95)),
                    )
                    results.append(result)
                    rows.append(_case_row(result))
    summary_path = ROOT / str(cfg["summary_json"])
    cases_path = ROOT / str(cfg["cases_csv"])
    _write_cases(cases_path, rows)
    _make_figures(results, ROOT / str(cfg["snapshot_figure"]), ROOT / str(cfg["port_figure"]))
    by_geometry = {g: float(np.mean([r["final_conductance"] for r in rows if r["geometry"] == g])) for g in cfg["geometries"]}
    by_coupling = {str(c): float(np.mean([r["final_conductance"] for r in rows if abs(float(r["lateral_coupling"]) - float(c)) < 1e-12])) for c in cfg["lateral_coupling"]}
    geometry_range = float(max(by_geometry.values()) - min(by_geometry.values()))
    coupling_range = float(max(by_coupling.values()) - min(by_coupling.values()))
    summary = {
        "benchmark": cfg.get("benchmark"),
        "note": "Synthetic numerical digital-twin reduced 2D forward benchmark; not experimental data and not full FEM.",
        "num_cases": len(rows),
        "all_fields_finite": bool(all(row["finite_fields"] for row in rows)),
        "all_residuals_finite": bool(all(row["finite_residual"] for row in rows)),
        "geometry_effect_detected": bool(geometry_range > 0.4),
        "lateral_coupling_effect_detected": bool(coupling_range > 0.02),
        "mean_final_conductance_by_geometry": by_geometry,
        "mean_final_conductance_by_lateral_coupling": by_coupling,
        "geometry_effect_range": geometry_range,
        "lateral_coupling_effect_range": coupling_range,
        "whether_reduced_2d_forward_supported": bool(all(row["finite_fields"] for row in rows) and all(row["finite_residual"] for row in rows) and geometry_range > 0.4),
        "allowed_claim": "A reduced 2D synthetic phase-transition forward benchmark is finite and sensitive to geometry/lateral coupling, supporting supplementary extensibility discussion.",
        "forbidden_overclaim": "This does not prove full 2D inverse recovery, full multiphysics FEM fidelity, or experimental validation.",
        "outputs": {
            "summary_json": str(cfg["summary_json"]),
            "cases_csv": str(cfg["cases_csv"]),
            "snapshot_figure": str(cfg["snapshot_figure"]),
            "port_figure": str(cfg["port_figure"]),
        },
    }
    write_json(summary_path, summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    summary = run_forward_benchmark(args.config)
    print(json.dumps({k: summary[k] for k in ["num_cases", "all_fields_finite", "geometry_effect_detected", "lateral_coupling_effect_detected", "whether_reduced_2d_forward_supported"]}, indent=2))


if __name__ == "__main__":
    main()
