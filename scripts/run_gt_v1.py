"""Generate v1 synthetic Ground Truth data and sparse observations."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pinnpcm.physics.gt_solver import make_sparse_observations, simulate_ground_truth
from pinnpcm.utils.io import ensure_dir, write_json
from pinnpcm.utils.seed import seed_everything


def _save_npz(path: Path, payload: dict[str, Any]) -> None:
    """Save a compressed npz file from a dictionary."""

    array_payload = {key: value for key, value in payload.items() if key not in {"success", "message", "protocol"}}
    np.savez_compressed(path, **array_payload)


def build_parser() -> argparse.ArgumentParser:
    """Build CLI parser."""

    parser = argparse.ArgumentParser(description="Generate synthetic Ground Truth v1 data.")
    parser.add_argument("--protocol", choices=["triangle", "ltp_ltd"], required=True)
    parser.add_argument("--nx", type=int, default=31)
    parser.add_argument("--nt", type=int, default=400)
    parser.add_argument("--t-max", type=float, default=None)
    parser.add_argument("--rtol", type=float, default=1.0e-6)
    parser.add_argument("--atol", type=float, default=1.0e-8)
    parser.add_argument("--method", type=str, default="Radau")
    parser.add_argument("--outdir", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=2026)
    return parser


def main() -> None:
    """CLI entrypoint."""

    args = build_parser().parse_args()
    seed_everything(args.seed, seed_torch=False)
    outdir = ensure_dir(args.outdir)

    gt = simulate_ground_truth(
        protocol=args.protocol,
        params=None,
        nx=args.nx,
        nt=args.nt,
        t_max=args.t_max,
        rtol=args.rtol,
        atol=args.atol,
        method=args.method,
    )
    obs = make_sparse_observations(gt, protocol=args.protocol, noise_level=0.05, seed=args.seed)

    gt_path = outdir / f"gt_{args.protocol}.npz"
    obs_path = outdir / f"obs_{args.protocol}_sparse.npz"
    params_path = outdir / "params_gt_v1.json"

    _save_npz(gt_path, gt)
    np.savez_compressed(obs_path, **obs)
    write_json(params_path, json.loads(str(gt["params_json"])))

    print(f"Saved Ground Truth: {gt_path}")
    print(f"Saved sparse observations: {obs_path}")
    print(f"Saved parameter snapshot: {params_path}")


if __name__ == "__main__":
    main()
