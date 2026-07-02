"""Build external-anchor claim stress-test matrix."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MD = ROOT / "docs/paper/external_anchor_claim_stress_test_matrix.md"
DEFAULT_SUMMARY = ROOT / "outputs/tables/external_anchor_claim_stress_test_summary.json"

def _display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


CLAIMS = [
    ("Literature parameter sanity supports order-of-magnitude plausibility", "data/literature/literature_parameter_sanity_table.csv", "Priors only; not measured device parameters", "measured material calibration"),
    ("Digitized curve fitting, if available, supports normalized shape plausibility only", "outputs/tables/literature_curve_fit_external_anchor_v2_summary.json", "Blocked if no provenance-backed curve exists", "direct device validation"),
    ("External curves do not validate gamma_sub inversion", "docs/literature/literature_curve_provenance_notes.md", "External anchors are separate from inverse-target proof", "gamma_sub validated by literature curves"),
    ("T_sw calibration is necessary for reliable gamma_sub recovery", "outputs/tables/gamma_sub_tsw_calibration_workflow_summary.json", "Synthetic benchmark workflow evidence", "unconditional gamma_sub identifiability"),
    ("Calibrated sequential protocol improves synthetic ODE-backed recovery, if supported", "outputs/tables/gamma_sub_calibrated_sequential_protocol_validation_summary.json", "Simulator-backed synthetic setting only", "experimental protocol optimization"),
    ("F-SPS remains appendix or negative evidence", "outputs/tables/f_sps_balanced_medium_budget_benchmark_summary.json", "No current superiority claim", "F-SPS performance superiority"),
    ("All results remain synthetic numerical digital-twin benchmark", "CODEX_CONTEXT.md", "No experimental measurements", "real device validation"),
]


def build_external_anchor_claim_stress_test(md_path: Path = DEFAULT_MD, summary_path: Path = DEFAULT_SUMMARY) -> dict[str, Any]:
    lines = ["# External Anchor Claim Stress Test Matrix", "", "All claims refer to synthetic numerical digital-twin benchmark evidence, not experimental measurements.", "", "| Claim | Evidence | Limitation | Forbidden wording |", "| --- | --- | --- | --- |"]
    for claim, evidence, limitation, forbidden in CLAIMS:
        lines.append(f"| {claim} | `{evidence}` | {limitation} | {forbidden} |")
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    summary = {"benchmark": "external_anchor_claim_stress_test", "note": "Synthetic numerical digital-twin claim guardrail; not experimental evidence.", "num_claims": len(CLAIMS), "all_claims_have_limitations": True, "all_claims_have_forbidden_overclaims": True, "claims": [c[0] for c in CLAIMS], "outputs": {"matrix_md": _display(md_path), "summary_json": _display(summary_path)}}
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix-md", type=Path, default=DEFAULT_MD)
    parser.add_argument("--summary-json", type=Path, default=DEFAULT_SUMMARY)
    args = parser.parse_args()
    print(json.dumps(build_external_anchor_claim_stress_test(args.matrix_md, args.summary_json), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
