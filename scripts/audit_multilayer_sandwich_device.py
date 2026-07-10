"""Run the boundary-aware multilayer sandwich forward benchmark."""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pinnpcm.physics.multilayer_sandwich import simulate_multilayer_case, summarize_cases
from scripts.gamma_sub_validation_common import write_json

DEFAULT_CONFIG = Path("configs/multilayer_sandwich_device.yaml")
SUMMARY_JSON = Path("outputs/tables/multilayer_sandwich_device_summary.json")
CASES_CSV = Path("outputs/tables/multilayer_sandwich_device_cases.csv")
FIG_TEMP = Path("outputs/figures/multilayer_temperature_stack.png")
FIG_J = Path("outputs/figures/multilayer_current_density_map.png")
FIG_BC = Path("outputs/figures/multilayer_boundary_residuals.png")
FIG_ABL = Path("outputs/figures/multilayer_structure_ablation.png")
CSV_FIELDS = ["structure", "geometry", "transition_width", "pulse", "seed", "finite_result", "interface_bc_residual", "potential_jump_residual", "normal_current_mismatch", "temperature_jump_residual", "heat_flux_mismatch", "substrate_robin_residual", "current_continuity_error", "energy_balance_error", "joule_input_energy", "thermal_storage_energy", "sink_loss_energy", "boundary_loss_energy", "max_delta_T", "max_m", "conductance_ratio", "mean_abs_power"]


def _write_cases(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field) for field in CSV_FIELDS})


def _plots(rows: list[dict[str, Any]], sample: dict[str, Any]) -> None:
    FIG_TEMP.parent.mkdir(parents=True, exist_ok=True)
    T = sample["temperature"][-1]
    J = sample["current_density_last"]
    fig, ax = plt.subplots(figsize=(6.2, 3.8))
    im = ax.imshow(T - 300.0, aspect="auto", cmap="inferno")
    ax.set_title("Final stack temperature rise")
    ax.set_xlabel("lateral index")
    ax.set_ylabel("layer")
    plt.colorbar(im, ax=ax, label="Delta T (K)")
    fig.tight_layout(); fig.savefig(ROOT / FIG_TEMP, dpi=150); plt.close(fig)
    fig, ax = plt.subplots(figsize=(6.2, 3.8))
    im = ax.imshow(J, aspect="auto", cmap="coolwarm")
    ax.set_title("Current density map")
    ax.set_xlabel("lateral index")
    ax.set_ylabel("layer")
    plt.colorbar(im, ax=ax, label="A/m2")
    fig.tight_layout(); fig.savefig(ROOT / FIG_J, dpi=150); plt.close(fig)
    fig, ax = plt.subplots(figsize=(7.0, 3.8))
    ax.scatter([r["interface_bc_residual"] for r in rows], [r["current_continuity_error"] for r in rows], s=14)
    ax.set_xlabel("interface BC residual")
    ax.set_ylabel("current continuity error")
    ax.set_title("Boundary residual audit")
    fig.tight_layout(); fig.savefig(ROOT / FIG_BC, dpi=150); plt.close(fig)
    structures = sorted({r["structure"] for r in rows})
    med = [float(np.median([r["max_delta_T"] for r in rows if r["structure"] == s])) for s in structures]
    fig, ax = plt.subplots(figsize=(8.0, 4.0))
    ax.bar(np.arange(len(structures)), med)
    ax.set_xticks(np.arange(len(structures)))
    ax.set_xticklabels(structures, rotation=35, ha="right")
    ax.set_ylabel("median max Delta T (K)")
    ax.set_title("Structure ablation")
    fig.tight_layout(); fig.savefig(ROOT / FIG_ABL, dpi=150); plt.close(fig)


def run_multilayer_sandwich_device(config_path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    with (ROOT / config_path).open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    profile = cfg.get("quick_profile", {})
    numerics = cfg.get("numerics", {})
    rows: list[dict[str, Any]] = []
    sample: dict[str, Any] | None = None
    for structure in profile.get("structures", []):
        for geometry in profile.get("geometry", []):
            for width in profile.get("transition_width", []):
                for pulse in profile.get("pulse", []):
                    for seed in profile.get("seeds", []):
                        result = simulate_multilayer_case(str(structure), str(geometry), float(width), str(pulse), int(seed), numerics)
                        rows.append(result)
                        if sample is None and structure == "full_stack_with_SnSe_barrier" and geometry == "localized_filament":
                            sample = result
    gate = cfg.get("claim_gate", {})
    summary = summarize_cases(rows, interface_threshold=float(gate.get("interface_bc_residual_threshold", 0.35)), current_threshold=float(gate.get("current_continuity_threshold", 0.05)), energy_threshold=float(gate.get("energy_balance_threshold", 0.35)))
    summary["outputs"] = {"summary_json": str(SUMMARY_JSON).replace("\\", "/"), "cases_csv": str(CASES_CSV).replace("\\", "/"), "figures": [str(FIG_TEMP).replace("\\", "/"), str(FIG_J).replace("\\", "/"), str(FIG_BC).replace("\\", "/"), str(FIG_ABL).replace("\\", "/")]}
    _write_cases(ROOT / CASES_CSV, rows)
    _plots(rows, sample or rows[0])
    write_json(ROOT / SUMMARY_JSON, summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    print(run_multilayer_sandwich_device(args.config))


if __name__ == "__main__":
    main()
