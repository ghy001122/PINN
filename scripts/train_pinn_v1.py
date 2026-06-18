"""PINN v1 training placeholder.

The interface is intentionally present for the engineering scaffold, but the
first version must not be used to report inverse-identification performance.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pinnpcm.pinn.network import FourierFeatureMLP
from pinnpcm.pinn.trainer import PINNTrainer


def build_parser() -> argparse.ArgumentParser:
    """Build CLI parser."""

    parser = argparse.ArgumentParser(description="PINN v1 skeleton entrypoint.")
    parser.add_argument("--config", type=Path, default=Path("configs/pinn_v1.yaml"))
    return parser


def main() -> None:
    """Instantiate the v1 PINN skeleton."""

    args = build_parser().parse_args()
    _ = args
    model = FourierFeatureMLP()
    trainer = PINNTrainer()
    state = trainer.fit()
    n_params = sum(param.numel() for param in model.parameters())
    print("PINN training is under active development; no performance result is produced.")
    print(f"Instantiated FourierFeatureMLP parameters: {n_params}")
    print(f"Trainer state: epoch={state.epoch}, best_loss={state.best_loss}")


if __name__ == "__main__":
    main()
