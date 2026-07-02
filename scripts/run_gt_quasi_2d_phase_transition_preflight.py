"""Generate a lightweight quasi-2D phase-transition forward preflight benchmark."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.gamma_sub_validation_common import load_yaml, write_json

DEFAULT_CONFIG = Path("configs/gt_quasi_2d_phase_transition_preflight.yaml")
STRUCTURE_ROLES = ["vo2_phase_field_slab", "vo2_localized_heater_strip", "vo2_sin_threshold_switch", "nbo2_threshold_closure", "generic_2d_pinn_phase_change"]
FORBIDDEN_CLAIMS = ["experimental validation", "full 2D inverse diagnosis solved", "direct VO2/NbO2 device replication"]


def _resolve(path_text: str | Path) -> Path:
    p = Path(path_text)
    return p if p.is_absolute() else ROOT / p


def _sigmoid(z: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(z, -60.0, 60.0)))


def _case_shapes(case: str, xx: np.ndarray, yy: np.ndarray, lx: float, ly: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    base_strip = 1.0 + 0.15 * np.cos(2.0 * np.pi * yy / ly)
    hotspot = np.exp(-((xx - 0.35 * lx) ** 2 / (2.0 * (0.12 * lx) ** 2) + (yy - 0.55 * ly) ** 2 / (2.0 * (0.18 * ly) ** 2)))
    filament = np.exp(-((xx - 0.55 * lx) ** 2 / (2.0 * (0.08 * lx) ** 2))) * np.exp(-((yy - 0.50 * ly) ** 2 / (2.0 * (0.12 * ly) ** 2)))
    cooling = 1.0 - 0.35 * yy / ly
    if case == "uniform_strip":
        return base_strip, 0.2 * base_strip, np.ones_like(base_strip)
    if case == "localized_hotspot":
        return base_strip + 1.8 * hotspot, 0.2 * base_strip + 0.5 * hotspot, np.ones_like(base_strip)
    if case == "defect_seeded_filament":
        return base_strip + 0.8 * filament, 0.2 * base_strip + 1.4 * filament, np.ones_like(base_strip)
    if case == "lateral_cooling_gradient":
        return base_strip * cooling + 0.7 * hotspot, 0.2 * base_strip + 0.35 * hotspot, cooling
    raise ValueError(f"Unknown case: {case}")


def _case_fields(case: str, cfg: dict[str, Any]) -> dict[str, np.ndarray]:
    grid, phys = cfg["grid"], cfg["physics"]
    nx, ny, nt = int(grid["nx"]), int(grid["ny"]), int(grid["nt"])
    lx, ly, t_max = float(grid["Lx"]), float(grid["Ly"]), float(grid["t_max"])
    x = (np.arange(nx) + 0.5) / nx * lx
    y = (np.arange(ny) + 0.5) / ny * ly
    xx, yy = np.meshgrid(x, y, indexing="ij")
    t = np.linspace(0.0, t_max, nt)
    drive = np.sin(np.pi * t / max(t_max, 1.0e-30)) ** 2
    v_port = float(phys["voltage_peak"]) * np.sin(2.0 * np.pi * t / max(t_max, 1.0e-30))
    thermal_shape, defect_shape, cooling_shape = _case_shapes(case, xx, yy, lx, ly)
    T = np.empty((nt, nx, ny), dtype=float)
    c_v = np.empty_like(T)
    m = np.empty_like(T)
    sigma = np.empty_like(T)
    phi = np.empty_like(T)
    V_field = np.empty_like(T)
    I = np.empty(nt, dtype=float)
    G = np.empty(nt, dtype=float)
    hotspot_temperature = np.empty(nt, dtype=float)
    metallic_fraction = np.empty(nt, dtype=float)
    phase_front_area = np.empty(nt, dtype=float)
    for k, amp in enumerate(drive):
        T[k] = float(phys["T0"]) + (5.0 + 15.0 * amp) * thermal_shape * cooling_shape
        c_v[k] = np.clip(float(phys["c_v0"]) + float(phys["delta_c"]) * defect_shape * (0.4 + 0.6 * amp), 0.0, 1.0)
        m[k] = _sigmoid((T[k] - float(phys["T_c"]) + 18.0 * (c_v[k] - float(phys["c_v0"]))) / float(phys["transition_width"]))
        sigma[k] = float(phys["sigma_ins0"]) * (1.0 + 3.0 * c_v[k]) + float(phys["sigma_met0"]) * m[k]
        lateral = 0.03 * np.sin(np.pi * yy / ly) * np.sin(np.pi * xx / lx)
        phi[k] = v_port[k] * (1.0 - xx / lx + lateral)
        V_field[k] = phi[k]
        grad_phi_x = -v_port[k] / lx
        current_density = sigma[k] * abs(grad_phi_x)
        I[k] = float(np.trapz(np.mean(current_density, axis=1), x) * ly)
        G[k] = float(I[k] / max(abs(v_port[k]), 1.0e-12))
        hotspot_temperature[k] = float(np.max(T[k]))
        metallic_fraction[k] = float(np.mean(m[k] > 0.5))
        phase_front_area[k] = float(np.mean((m[k] > 0.35) & (m[k] < 0.65)) * lx * ly)
    return {"x": x, "y": y, "t": t, "T": T, "phi": phi, "c_v": c_v, "m": m, "sigma": sigma, "V": V_field, "V_port": v_port, "I": I, "G": G, "hotspot_temperature": hotspot_temperature, "metallic_fraction": metallic_fraction, "phase_front_area": phase_front_area}


def _plot_case(case: str, fields: dict[str, np.ndarray], fig_dir: Path) -> str:
    fig_dir.mkdir(parents=True, exist_ok=True)
    idx = int(np.argmax(fields["hotspot_temperature"]))
    path = fig_dir / f"{case}_temperature_sigma_snapshot.png"
    fig, axes = plt.subplots(1, 2, figsize=(7.0, 2.6), constrained_layout=True)
    im0 = axes[0].imshow(fields["T"][idx].T, origin="lower", aspect="auto")
    axes[0].set_title("T snapshot")
    fig.colorbar(im0, ax=axes[0], fraction=0.046)
    im1 = axes[1].imshow(fields["sigma"][idx].T, origin="lower", aspect="auto")
    axes[1].set_title("sigma snapshot")
    fig.colorbar(im1, ax=axes[1], fraction=0.046)
    fig.savefig(path, dpi=140)
    plt.close(fig)
    return str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)


def run_quasi_2d_preflight(config_path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    cfg = load_yaml(config_path)
    out_dir = _resolve(cfg["output_dir"])
    fig_dir = _resolve(cfg["figure_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    fig_dir.mkdir(parents=True, exist_ok=True)
    case_rows = []
    figures = []
    all_finite_fields = True
    all_finite_obs = True
    for case in cfg["cases"]:
        fields = _case_fields(str(case), cfg)
        npz_path = out_dir / f"{case}.npz"
        np.savez_compressed(npz_path, **fields)
        fig_path = _plot_case(str(case), fields, fig_dir)
        figures.append(fig_path)
        finite_fields = bool(all(np.isfinite(fields[key]).all() for key in ["T", "phi", "c_v", "sigma", "V"]))
        finite_obs = bool(all(np.isfinite(fields[key]).all() for key in ["I", "G", "hotspot_temperature", "metallic_fraction", "phase_front_area"]))
        all_finite_fields = all_finite_fields and finite_fields
        all_finite_obs = all_finite_obs and finite_obs
        case_rows.append({"case": str(case), "npz": str(npz_path.relative_to(ROOT)) if npz_path.is_relative_to(ROOT) else str(npz_path), "figure": fig_path, "fields_finite": finite_fields, "observables_finite": finite_obs, "max_temperature": float(np.max(fields["hotspot_temperature"])), "max_metallic_fraction": float(np.max(fields["metallic_fraction"])), "max_phase_front_area": float(np.max(fields["phase_front_area"]))})
    summary = {
        "benchmark": cfg.get("benchmark"),
        "note": "Synthetic literature-anchored quasi-2D forward/preflight benchmark; not experimental data and not a full inverse claim.",
        "num_cases": len(case_rows),
        "case_summaries": case_rows,
        "all_fields_finite": bool(all_finite_fields),
        "all_observables_finite": bool(all_finite_obs),
        "literature_structure_roles_used": STRUCTURE_ROLES,
        "synthetic_not_experimental": True,
        "ready_for_residual_preflight": bool(all_finite_fields and all_finite_obs),
        "forbidden_claims": FORBIDDEN_CLAIMS,
        "outputs": {"output_dir": cfg["output_dir"], "figure_dir": cfg["figure_dir"], "summary_json": cfg["summary_json"], "figures": figures},
    }
    write_json(cfg["summary_json"], summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    print(json.dumps(run_quasi_2d_preflight(args.config), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
