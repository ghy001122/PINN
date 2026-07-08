"""Run the port-physical reduced 2D inverse audit."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pinnpcm.experiments.port_physical_2d_inverse import run_port_physical_2d_inverse


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/high_risk_claim_ladder.yaml"))
    parser.add_argument("--profile", default="quick")
    args = parser.parse_args()
    summary = run_port_physical_2d_inverse(args.config, profile=args.profile)
    print(json.dumps({
        "num_cases": summary["num_cases"],
        "all_finite_results": summary["all_finite_results"],
        "uses_port_physical_observation": summary["uses_port_physical_observation"],
        "uses_phase_mean_as_terminal_observation": summary["uses_phase_mean_as_terminal_observation"],
        "best_protocol": summary["best_protocol"],
        "field_recovery_status": summary["field_recovery_status"],
        "improves_over_v2_best_actual_inverse": summary["improves_over_v2_best_actual_inverse"],
    }, indent=2))


if __name__ == "__main__":
    main()
