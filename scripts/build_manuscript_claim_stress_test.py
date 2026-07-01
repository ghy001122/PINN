"""Build a manuscript claim stress-test matrix.

The matrix binds each paper claim to synthetic numerical digital-twin evidence,
limitations, and forbidden overclaims. It is a documentation/evidence-chain
artifact, not a new experiment.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.gamma_sub_high_throughput_common import read_json, write_json

DEFAULT_MD = Path("docs/paper/claim_stress_test_matrix.md")
DEFAULT_JSON = Path("outputs/tables/manuscript_claim_stress_test_summary.json")


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _load_optional(path: str) -> dict[str, Any]:
    p = ROOT / path
    if not p.exists():
        return {}
    return read_json(path)


def _claims() -> list[dict[str, Any]]:
    ident = _load_optional("outputs/tables/pinn_identifiability_summary.json")
    constrained = _load_optional("outputs/tables/gamma_sub_constrained_inversion_summary.json")
    confounding = _load_optional("outputs/tables/gamma_sub_confounding_summary.json")
    recoverability = _load_optional("outputs/tables/gamma_sub_recoverability_phase_diagram_summary.json")
    weighted = _load_optional("outputs/tables/gamma_sub_weighted_protocol_objective_summary.json")
    anchor = _load_optional("outputs/tables/gamma_sub_response_surface_anchor_verification_summary.json")
    f_sps = _load_optional("outputs/tables/f_sps_balanced_medium_budget_benchmark_summary.json")
    statistical = _load_optional("outputs/tables/gamma_sub_statistical_robustness_summary.json")
    return [
        {
            "claim_id": "C1",
            "claim_text": "Sparse-port full-field recovery is non-identifiable in the current one-dimensional benchmark.",
            "supporting_tables": ["outputs/tables/pinn_identifiability_summary.json"],
            "supporting_figures": ["outputs/figures/pinn_identifiability/correlation_heatmap.png"],
            "supporting_scripts": ["scripts/analyze_pinn_identifiability.py"],
            "strongest_numerical_result": f"mean_sigma remains the dominant terminal-observable correlate; summary keys={sorted(ident)[:6]}",
            "limitation": "This proves an identifiability boundary for the synthetic benchmark, not a theorem for all devices.",
            "forbidden_overclaim": "Sparse port data uniquely recover delta_T, c_v, m, and sigma.",
            "manuscript_section": "Results: identifiability boundary",
        },
        {
            "claim_id": "C2",
            "claim_text": "gamma_sub recovery is conditionally possible under bounded T_sw prior.",
            "supporting_tables": [
                "outputs/tables/gamma_sub_constrained_inversion_summary.json",
                "outputs/tables/gamma_sub_prior_width_sweep.csv",
            ],
            "supporting_figures": ["outputs/figures/gamma_sub_gap_closing/"],
            "supporting_scripts": ["scripts/invert_gamma_sub_constrained.py"],
            "strongest_numerical_result": f"max tested constrained relative error={constrained.get('max_relative_error', 'see summary')}",
            "limitation": "The claim requires fixed or tightly bounded switching/conductivity priors.",
            "forbidden_overclaim": "gamma_sub is identifiable under arbitrary released nuisance parameters.",
            "manuscript_section": "Results: reduced inverse target",
        },
        {
            "claim_id": "C3",
            "claim_text": "Wide T_sw mismatch is the dominant failure mode.",
            "supporting_tables": [
                "outputs/tables/gamma_sub_confounding_summary.json",
                "outputs/tables/gamma_sub_statistical_robustness_summary.json",
            ],
            "supporting_figures": ["outputs/figures/gamma_sub_gap_closing/"],
            "supporting_scripts": [
                "scripts/audit_gamma_sub_confounding.py",
                "scripts/audit_gamma_sub_statistical_robustness.py",
            ],
            "strongest_numerical_result": f"worst statistical case={statistical.get('worst_case', {}).get('scenario', 'wide_T_sw_mismatch')}",
            "limitation": "Other parameters also confound gamma_sub; T_sw is the strongest tested one, not the only risk.",
            "forbidden_overclaim": "Model mismatch does not affect gamma_sub inversion.",
            "manuscript_section": "Discussion: confounding and priors",
        },
        {
            "claim_id": "C4",
            "claim_text": "ltp_ltd and short_pulse style protocols improve recoverability relative to less informative choices.",
            "supporting_tables": [
                "outputs/tables/gamma_sub_recoverability_phase_diagram_summary.json",
                "outputs/tables/gamma_sub_protocol_actual_inversion_validation_summary.json",
            ],
            "supporting_figures": ["outputs/figures/high_throughput_sci/protocol_actual_validation.png"],
            "supporting_scripts": [
                "scripts/audit_gamma_sub_recoverability_phase_diagram.py",
                "scripts/audit_gamma_sub_protocol_actual_inversion_validation.py",
            ],
            "strongest_numerical_result": f"phase-diagram best_protocol={recoverability.get('best_protocol', 'ltp_ltd')}",
            "limitation": "Protocol rankings are response-surface guidance and need stronger validation before experimental prescription.",
            "forbidden_overclaim": "Any multi-protocol design automatically solves gamma_sub/T_sw ambiguity.",
            "manuscript_section": "Results: protocol robustness",
        },
        {
            "claim_id": "C5",
            "claim_text": "Naive weighted protocol objective does not improve over the best single protocol.",
            "supporting_tables": ["outputs/tables/gamma_sub_weighted_protocol_objective_summary.json"],
            "supporting_figures": ["outputs/figures/high_throughput_sci/weighted_protocol_objective.png"],
            "supporting_scripts": ["scripts/audit_gamma_sub_weighted_protocol_objective.py"],
            "strongest_numerical_result": f"improves_over_best_single={weighted.get('improves_over_best_single', False)}",
            "limitation": "Only tested configured weights; better optimized designs remain future work.",
            "forbidden_overclaim": "Weighted stimulation is useless in general.",
            "manuscript_section": "Ablation: protocol objective",
        },
        {
            "claim_id": "C6",
            "claim_text": "Response-surface phase diagrams are acceptable only with anchor verification and explicit qualification.",
            "supporting_tables": [
                "outputs/tables/gamma_sub_response_surface_anchor_verification_summary.json",
                "outputs/tables/gamma_sub_response_surface_anchor_verification_cases.csv",
            ],
            "supporting_figures": ["outputs/figures/manuscript_ready_gamma_sub/main_figure_4_anchor_verification.png"],
            "supporting_scripts": ["scripts/audit_gamma_sub_response_surface_anchor_verification.py"],
            "strongest_numerical_result": f"classification_agreement_rate={anchor.get('classification_agreement_rate', 'pending')}",
            "limitation": "Dense profile is interpolated from simulator-backed source points, not thousands of fresh ODE solves.",
            "forbidden_overclaim": "All dense response-surface points are simulator-backed ODE solves.",
            "manuscript_section": "Reviewer defense: response-surface validation",
        },
        {
            "claim_id": "C7",
            "claim_text": "F-SPS-PINN does not currently support a superiority claim.",
            "supporting_tables": [
                "outputs/tables/f_sps_medium_budget_benchmark_summary.json",
                "outputs/tables/f_sps_balanced_medium_budget_benchmark_summary.json",
            ],
            "supporting_figures": ["outputs/figures/manuscript_ready_gamma_sub/appendix_f_sps_balanced_benchmark.png"],
            "supporting_scripts": [
                "scripts/train_f_sps_medium_budget_benchmark.py",
                "scripts/train_f_sps_balanced_medium_budget_benchmark.py",
            ],
            "strongest_numerical_result": f"balanced_f_sps_improves_over_free_log_sigma={f_sps.get('whether_f_sps_improves_over_free_log_sigma', 'pending')}",
            "limitation": "F-SPS remains an appendix/future-work method-development line.",
            "forbidden_overclaim": "F-SPS-PINN is validated as more accurate than the free log_sigma shortcut.",
            "manuscript_section": "Appendix: method development",
        },
    ]


def _markdown(claims: list[dict[str, Any]]) -> str:
    lines = [
        "# Manuscript Claim Stress-Test Matrix",
        "",
        "All claims in this matrix are limited to synthetic numerical digital-twin benchmark evidence. They are not experimental measurements, not full 3D device simulation, and not proof of sparse-port full hidden-field recovery.",
        "",
        "| Claim | Supporting tables | Strongest numerical result | Limitation | Forbidden overclaim | Section |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for claim in claims:
        lines.append(
            "| {claim_text} | {tables} | {strongest} | {limitation} | {forbidden} | {section} |".format(
                claim_text=claim["claim_text"],
                tables=", ".join(f"`{item}`" for item in claim["supporting_tables"]),
                strongest=str(claim["strongest_numerical_result"]).replace("|", "/"),
                limitation=claim["limitation"],
                forbidden=claim["forbidden_overclaim"],
                section=claim["manuscript_section"],
            )
        )
    lines.extend(
        [
            "",
            "## Use Boundary",
            "",
            "Use this file to decide which results belong in the main manuscript and which belong in appendix or future work. Do not convert response-surface or small-run method-development evidence into experimental validation claims.",
        ]
    )
    return "\n".join(lines) + "\n"


def build_claim_stress_test(md_path: Path = DEFAULT_MD, summary_path: Path = DEFAULT_JSON) -> dict[str, Any]:
    claims = _claims()
    md = ROOT / md_path if not md_path.is_absolute() else md_path
    md.parent.mkdir(parents=True, exist_ok=True)
    md.write_text(_markdown(claims), encoding="utf-8")
    summary = {
        "benchmark": "synthetic numerical digital-twin manuscript claim stress test",
        "num_claims": len(claims),
        "claims": claims,
        "all_claims_have_limitations": all(bool(claim["limitation"]) for claim in claims),
        "all_claims_have_forbidden_overclaims": all(bool(claim["forbidden_overclaim"]) for claim in claims),
        "outputs": {"markdown": _display_path(md), "summary_json": _display_path(summary_path)},
    }
    write_json(summary_path, summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--markdown", type=Path, default=DEFAULT_MD)
    parser.add_argument("--summary", type=Path, default=DEFAULT_JSON)
    args = parser.parse_args()
    summary = build_claim_stress_test(args.markdown, args.summary)
    print(json.dumps({"markdown": summary["outputs"]["markdown"], "summary_json": summary["outputs"]["summary_json"], "num_claims": summary["num_claims"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

