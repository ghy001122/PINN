"""Run PINN inverse v1.1 residual-balancing experiments."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pinnpcm.utils.config import load_yaml
from pinnpcm.utils.io import ensure_dir, write_json

from train_pinn_inverse_v1 import train


V1_1_CONFIGS = {
    "triangle_physics_balanced": Path("configs/pinn_inverse_v1_1_triangle_physics_balanced.yaml"),
    "triangle_port_physics_balanced": Path("configs/pinn_inverse_v1_1_triangle_port_physics_balanced.yaml"),
}

METRIC_KEYS = (
    "final_total_loss",
    "final_port_loss",
    "relative_G_error",
    "relative_I_error",
    "rmse_delta_T",
    "nrmse_delta_T",
    "rmse_delta_c_v",
    "nrmse_delta_c_v",
    "rmse_delta_m",
    "nrmse_delta_m",
    "rmse_sigma",
    "nrmse_sigma",
    "final_heat_residual",
    "final_state_residual",
    "final_defect_residual",
    "final_sigma_consistency",
    "final_sigma_initial_loss",
)


def build_parser() -> argparse.ArgumentParser:
    """Build CLI parser."""

    parser = argparse.ArgumentParser(description="Run PINN inverse v1.1 residual-balancing experiments.")
    parser.add_argument("--epochs", type=int, default=None, help="Override epochs for every experiment.")
    parser.add_argument("--smoke-test", action="store_true", help="Run one epoch per experiment in ignored smoke outputs.")
    parser.add_argument("--output-root", type=Path, default=Path("outputs/pinn_inverse_v1_1"))
    parser.add_argument("--summary", type=Path, default=Path("outputs/tables/pinn_inverse_v1_1_summary.json"))
    return parser


def _rel(path: Path) -> str:
    """Return a repository-relative path when possible."""

    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _artifact_paths(output_dir: Path) -> dict[str, str]:
    """Return expected artifacts for one v1.1 experiment."""

    return {
        "train_history": _rel(output_dir / "train_history.json"),
        "metrics": _rel(output_dir / "metrics.json"),
        "loss_curve": _rel(output_dir / "loss_curve.png"),
        "loss_components": _rel(output_dir / "loss_components.png"),
        "residual_components": _rel(output_dir / "residual_components.png"),
        "compare_g_time": _rel(output_dir / "compare_g_time.png"),
        "pred_delta_T_map": _rel(output_dir / "pred_delta_T_map.png"),
        "pred_delta_c_v_map": _rel(output_dir / "pred_delta_c_v_map.png"),
        "pred_delta_m_map": _rel(output_dir / "pred_delta_m_map.png"),
        "pred_sigma_map": _rel(output_dir / "pred_sigma_map.png"),
    }


def _summarize_metrics(metrics: dict[str, Any]) -> dict[str, float]:
    """Keep scalar audit metrics."""

    return {key: float(metrics[key]) for key in METRIC_KEYS if key in metrics}


def run_experiments(
    *,
    epochs_override: int | None = None,
    output_root: Path = Path("outputs/pinn_inverse_v1_1"),
    summary_path: Path = Path("outputs/tables/pinn_inverse_v1_1_summary.json"),
) -> dict[str, Any]:
    """Run all v1.1 experiments and write a lightweight summary JSON."""

    experiments: list[dict[str, Any]] = []
    for name, config_path in V1_1_CONFIGS.items():
        cfg = load_yaml(ROOT / config_path)
        output_dir = ROOT / output_root / name
        print(f"=== Running {name} ===")
        metrics = train(config_path, epochs_override=epochs_override, output_dir_override=output_dir)
        experiments.append(
            {
                "name": name,
                "config_path": str(config_path),
                "output_dir": _rel(output_dir),
                "loss_weights": cfg["loss_weights"],
                "loss_schedule": cfg.get("loss_schedule", {}),
                "residual_balancing": cfg.get("residual_balancing", {}),
                "metrics": _summarize_metrics(metrics),
                "artifacts": _artifact_paths(output_dir),
            }
        )

    summary = {
        "repo_url": "https://github.com/ghy001122/PINN",
        "benchmark": "Frozen Ground Truth v1.1 triangle synthetic numerical digital-twin benchmark.",
        "note": "PINN inverse v1.1 tunes residual balancing and schedules; it is not a complete PDE-constrained inverse PINN.",
        "summary_json_path": str(summary_path),
        "experiments": experiments,
    }
    ensure_dir((ROOT / summary_path).parent)
    write_json(ROOT / summary_path, summary)
    print(f"Saved v1.1 summary: {summary_path}")
    return summary


def main() -> None:
    """CLI entry point."""

    args = build_parser().parse_args()
    if args.smoke_test:
        args.epochs = 1 if args.epochs is None else args.epochs
        if args.output_root == Path("outputs/pinn_inverse_v1_1"):
            args.output_root = Path("outputs/pinn_inverse_v1_1_smoke")
        if args.summary == Path("outputs/tables/pinn_inverse_v1_1_summary.json"):
            args.summary = Path("outputs/tables/pinn_inverse_v1_1_smoke_summary.json")
    run_experiments(epochs_override=args.epochs, output_root=args.output_root, summary_path=args.summary)


if __name__ == "__main__":
    main()
