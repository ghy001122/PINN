"""Run PINN inverse v0 ablation audit experiments."""

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

from train_pinn_inverse_v0 import train


ABLATION_CONFIGS = {
    "triangle_full_anchor": Path("configs/pinn_inverse_v0_triangle_full_anchor.yaml"),
    "triangle_weak_anchor": Path("configs/pinn_inverse_v0_triangle_weak_anchor.yaml"),
    "triangle_port_only": Path("configs/pinn_inverse_v0_triangle_port_only.yaml"),
}

METRIC_KEYS = (
    "final_total_loss",
    "final_port_loss",
    "relative_G_error",
    "relative_I_error",
    "rmse_delta_T",
    "rmse_delta_c_v",
    "rmse_delta_m",
    "rmse_sigma",
    "nrmse_delta_T",
    "nrmse_delta_c_v",
    "nrmse_delta_m",
    "nrmse_sigma",
    "max_abs_error_delta_T",
    "max_abs_error_delta_c_v",
    "max_abs_error_delta_m",
)


def build_parser() -> argparse.ArgumentParser:
    """Build CLI parser."""

    parser = argparse.ArgumentParser(description="Run PINN inverse v0 ablation audit.")
    parser.add_argument("--epochs", type=int, default=None, help="Override epochs for every ablation run.")
    parser.add_argument(
        "--smoke-test",
        action="store_true",
        help="Run a one-epoch smoke test in a separate ignored output directory.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("outputs/pinn_inverse_v0"),
        help="Root output directory for ablation runs.",
    )
    parser.add_argument(
        "--summary",
        type=Path,
        default=Path("outputs/tables/pinn_inverse_v0_ablation_summary.json"),
        help="Summary JSON path.",
    )
    return parser


def _rel(path: Path) -> str:
    """Return a path relative to the repository root when possible."""

    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _artifact_paths(output_dir: Path) -> dict[str, str]:
    """Return expected artifact paths for one ablation run."""

    return {
        "train_history": _rel(output_dir / "train_history.json"),
        "metrics": _rel(output_dir / "metrics.json"),
        "loss_curve": _rel(output_dir / "loss_curve.png"),
        "compare_g_time": _rel(output_dir / "compare_g_time.png"),
        "pred_delta_T_map": _rel(output_dir / "pred_delta_T_map.png"),
        "pred_delta_c_v_map": _rel(output_dir / "pred_delta_c_v_map.png"),
        "pred_delta_m_map": _rel(output_dir / "pred_delta_m_map.png"),
        "pred_sigma_map": _rel(output_dir / "pred_sigma_map.png"),
    }


def _summarize_metrics(metrics: dict[str, Any]) -> dict[str, float]:
    """Keep only scalar metrics used by the audit report."""

    return {key: float(metrics[key]) for key in METRIC_KEYS if key in metrics}


def run_ablation(
    *,
    epochs_override: int | None = None,
    output_root: Path = Path("outputs/pinn_inverse_v0"),
    summary_path: Path = Path("outputs/tables/pinn_inverse_v0_ablation_summary.json"),
) -> dict[str, Any]:
    """Run all configured ablations and write a compact summary JSON."""

    experiments: list[dict[str, Any]] = []
    for name, config_path in ABLATION_CONFIGS.items():
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
                "field_anchor_points": int(cfg.get("field_anchor_points", 0)),
                "metrics": _summarize_metrics(metrics),
                "artifacts": _artifact_paths(output_dir),
            }
        )

    summary = {
        "repo_url": "https://github.com/ghy001122/PINN",
        "benchmark": "Frozen Ground Truth v1.1 triangle synthetic numerical digital-twin benchmark.",
        "note": "PINN inverse v0 is a pipeline proof-of-concept, not a strict PDE-constrained inverse PINN.",
        "summary_json_path": str(summary_path),
        "experiments": experiments,
    }
    ensure_dir((ROOT / summary_path).parent)
    write_json(ROOT / summary_path, summary)
    print(f"Saved ablation summary: {summary_path}")
    return summary


def main() -> None:
    """CLI entry point."""

    args = build_parser().parse_args()
    if args.smoke_test:
        args.epochs = 1 if args.epochs is None else args.epochs
        if args.output_root == Path("outputs/pinn_inverse_v0"):
            args.output_root = Path("outputs/pinn_inverse_v0_smoke")
        if args.summary == Path("outputs/tables/pinn_inverse_v0_ablation_summary.json"):
            args.summary = Path("outputs/tables/pinn_inverse_v0_ablation_smoke_summary.json")
    run_ablation(epochs_override=args.epochs, output_root=args.output_root, summary_path=args.summary)


if __name__ == "__main__":
    main()
