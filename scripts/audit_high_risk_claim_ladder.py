"""Run the integrated high-risk claim ladder quick/extended profile."""
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

from pinnpcm.experiments.high_risk_claim_ladder import run_high_risk_claim_ladder

DEFAULT_CONFIG = Path("configs/high_risk_claim_ladder.yaml")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--profile", choices=["quick", "extended"], default="quick")
    args = parser.parse_args()
    summary = run_high_risk_claim_ladder(args.config, profile=args.profile)
    print(json.dumps({
        "profile": summary["profile"],
        "num_cases": summary["num_cases"],
        "all_finite_results": summary["all_finite_results"],
        "2d_hidden_field_recovery_supported_level": summary["2d_hidden_field_recovery_supported_level"],
        "terminal_only_full_field_status": summary["terminal_only_full_field_status"],
        "terminal_only_low_dimensional_status": summary["terminal_only_low_dimensional_status"],
    }, indent=2))


if __name__ == "__main__":
    main()
