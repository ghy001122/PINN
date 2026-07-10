"""Run the 2D hidden-field claim-resolution ladder."""
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

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pinnpcm.experiments.claim_resolution_2d_field import PROTOCOLS, run_claim_resolution_2d_field
from scripts.gamma_sub_validation_common import write_json

SUMMARY_JSON = Path("outputs/tables/claim_resolution_2d_field_summary.json")
CASES_CSV = Path("outputs/tables/claim_resolution_2d_field_cases.csv")
FIG_ERROR = Path("outputs/figures/claim_resolution_2d_field_error_ladder.png")
FIG_RANK = Path("outputs/figures/claim_resolution_observability_rank.png")
CSV_FIELDS = ["protocol", "basis_mode", "noise", "seed", "field_error", "T_error", "m_error", "success", "fisher_rank", "fisher_condition_number", "observation_count", "uses_holdout_target", "no_target_leakage", "uses_multilayer_sandwich_fields", "finite_result"]


def _write_cases(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field) for field in CSV_FIELDS})


def _plot(summary: dict[str, Any]) -> None:
    FIG_ERROR.parent.mkdir(parents=True, exist_ok=True)
    protocols = PROTOCOLS
    errors = [summary["median_field_error_by_protocol"][p] for p in protocols]
    rates = [summary["success_rate_by_protocol"][p] for p in protocols]
    x = np.arange(len(protocols))
    fig, ax = plt.subplots(figsize=(9, 4.2))
    ax.bar(x, errors, color="#4c78a8")
    ax.axhline(0.25, color="black", linestyle="--", linewidth=1.0)
    ax.set_xticks(x); ax.set_xticklabels(protocols, rotation=35, ha="right")
    ax.set_ylabel("median field error")
    ax.set_title("2D field recovery error ladder")
    fig.tight_layout(); fig.savefig(ROOT / FIG_ERROR, dpi=150); plt.close(fig)
    ranks = [summary["fisher_rank_by_protocol"][p] for p in protocols]
    cond = [summary["condition_number_by_protocol"][p] for p in protocols]
    fig, ax1 = plt.subplots(figsize=(9, 4.2))
    ax1.bar(x - 0.17, ranks, width=0.34, label="rank", color="#72b7b2")
    ax2 = ax1.twinx(); ax2.bar(x + 0.17, np.log10(np.maximum(cond, 1.0)), width=0.34, label="log10 cond", color="#f58518")
    ax1.set_xticks(x); ax1.set_xticklabels(protocols, rotation=35, ha="right")
    ax1.set_ylabel("Fisher rank"); ax2.set_ylabel("log10 condition number")
    ax1.set_title("Observation-rank audit")
    fig.tight_layout(); fig.savefig(ROOT / FIG_RANK, dpi=150); plt.close(fig)


def run_audit() -> dict[str, Any]:
    rows, summary = run_claim_resolution_2d_field()
    summary["outputs"] = {"summary_json": str(SUMMARY_JSON).replace("\\", "/"), "cases_csv": str(CASES_CSV).replace("\\", "/"), "figures": [str(FIG_ERROR).replace("\\", "/"), str(FIG_RANK).replace("\\", "/")]}
    _write_cases(ROOT / CASES_CSV, rows)
    _plot(summary)
    write_json(ROOT / SUMMARY_JSON, summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.parse_args()
    print(run_audit())


if __name__ == "__main__":
    main()
