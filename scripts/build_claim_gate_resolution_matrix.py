"""Build claim-gate resolution matrix from 2D and stiffness audit outputs."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

DEFAULT_FORWARD = Path("outputs/tables/reduced_2d_phase_transition_forward_summary.json")
DEFAULT_OBS = Path("outputs/tables/reduced_2d_observability_limited_inverse_summary.json")
DEFAULT_STIFF = Path("outputs/tables/stiffness_aware_algorithm_benchmark_summary.json")
DEFAULT_STORY = Path("outputs/tables/stiffness_2d_story_figure_manifest.json")
DEFAULT_OUT = Path("docs/paper/claim_gate_resolution_matrix.md")


def _load(path: Path) -> dict[str, Any]:
    with (ROOT / path).open("r", encoding="utf-8") as f:
        return json.load(f)


def _row(claim: str, status: str, table: str, figure: str, allowed: str, forbidden: str, qualification: str) -> dict[str, str]:
    return {
        "claim": claim,
        "status": status,
        "supporting_table": table,
        "supporting_figure": figure,
        "allowed_sentence": allowed,
        "forbidden_overclaim": forbidden,
        "required_qualification": qualification,
    }


def build_claim_gate_matrix(
    forward_summary: Path = DEFAULT_FORWARD,
    observability_summary: Path = DEFAULT_OBS,
    stiffness_summary: Path = DEFAULT_STIFF,
    story_manifest: Path = DEFAULT_STORY,
    out_path: Path = DEFAULT_OUT,
) -> Path:
    fwd = _load(forward_summary)
    obs = _load(observability_summary)
    stiff = _load(stiffness_summary)
    story = _load(story_manifest)
    rows = [
        _row("2D reduced forward supported?", "supported" if fwd.get("whether_reduced_2d_forward_supported") else "failed_but_informative", str(forward_summary).replace("\\", "/"), "outputs/figures/reduced_2d_forward_snapshots.png; outputs/figures/reduced_2d_port_traces.png", "A reduced 2D synthetic phase-transition forward benchmark is finite and geometry-sensitive.", "This is full 2D FEM or experimental validation.", "Reduced thin-film model only; supplementary evidence."),
        _row("2D low-dimensional inverse supported?", "qualified_supported" if obs.get("augmented_observation_2d_low_dim_inverse_allowed") else "failed_but_informative", str(observability_summary).replace("\\", "/"), "outputs/figures/reduced_2d_observability_claim_gate.png", "Low-dimensional reduced 2D inverse diagnosis is feasible under augmented sparse observations.", "Sparse terminal data uniquely recover 2D fields.", "Only low-dimensional parameters and only under augmented observations."),
        _row("Terminal-only 2D inverse supported?", "failed_but_informative" if obs.get("terminal_only_failure_confirmed") else "qualified_supported", str(observability_summary).replace("\\", "/"), "outputs/figures/reduced_2d_observability_claim_gate.png", "Terminal-only sparse observations fail this reduced 2D inverse claim gate.", "Terminal-only data solve 2D inverse diagnosis.", "Use as honest negative evidence."),
        _row("Augmented-observation 2D inverse supported?", "qualified_supported" if obs.get("augmented_observation_2d_low_dim_inverse_allowed") else "failed_but_informative", str(observability_summary).replace("\\", "/"), "outputs/figures/reduced_2d_observability_claim_gate.png", "Augmented sparse proxy observations can support low-dimensional reduced 2D parameter diagnosis.", "Augmented observations recover full 2D fields.", "Success threshold is benchmark-specific; not experimental."),
        _row("Full 2D hidden-field recovery supported?", "forbidden", str(observability_summary).replace("\\", "/"), "none", "Full 2D hidden-field recovery remains unsupported.", "Full 2D hidden fields are uniquely recovered.", "No full-field 2D inverse training evidence exists."),
        _row("Stiffness cliff exists?", "supported" if story.get("stiffness_key_results", {}).get("whether_stiffness_cliff_claim_supported") else "failed_but_informative", "outputs/tables/stiffness_2d_story_figure_manifest.json", "outputs/figures/stiffness_residual_vs_transition_width.png", "Narrow phase-transition widths create a residual stiffness cliff in the synthetic preflight.", "This proves stiff PINN training is solved.", "Residual preflight only."),
        _row("Stiffness cliff mitigated?", "supported" if stiff.get("whether_stiffness_cliff_mitigated") else "failed_but_informative", str(stiffness_summary).replace("\\", "/"), "outputs/figures/stiffness_algorithm_error_vs_width.png", "Continuation plus scale-aware weighting mitigates stiffness-induced degradation in the residual-proxy benchmark.", "Stiffness is solved generally.", "Synthetic algorithm benchmark, not full training proof."),
        _row("Mini-STL-style transfer supported?", "qualified_supported" if stiff.get("whether_mini_STL_style_transfer_supported") else "failed_but_informative", str(stiffness_summary).replace("\\", "/"), "outputs/figures/stiffness_algorithm_claim_gate.png", "Mini-STL-style transfer is supported as a lightweight continuation/initialization audit.", "Full STL-PINN reproduction is complete.", "Use mini-STL-style wording only."),
        _row("Full STL-PINN reproduction supported?", "forbidden", str(stiffness_summary).replace("\\", "/"), "none", "Full STL-PINN reproduction remains future work.", "The repository reproduced full stiff transfer learning.", "No full STL training implementation was run."),
        _row("Fourier/F-SPS superiority supported?", "forbidden", "outputs/tables/pinn_inverse_v2_fourier_ablation_summary.json; outputs/tables/f_sps_balanced_medium_budget_benchmark_summary.json", "none", "F-SPS and Fourier evidence remain appendix/future-work diagnostics.", "F-SPS-PINN or Fourier features are superior.", "Existing small-run evidence does not establish superiority."),
    ]
    out = ROOT / out_path
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Claim-Gate Resolution Matrix",
        "",
        "All entries are synthetic numerical digital-twin benchmark evidence, not experimental data.",
        "",
        "## Authoritative V10 Claim Gate",
        "",
        "| Claim | Status | Evidence | Allowed wording | Forbidden wording |",
        "| --- | --- | --- | --- | --- |",
        "| Electrical/thermal topology and mechanism routing are implemented | qualified_supported | `outputs/tables/physical_semantics_v10_summary.json` | A reduced synthetic multilayer model separates electrical and thermal domains and routes VO2/NbO2 mechanisms explicitly. | Device-grade or experimentally calibrated model. |",
        "| CV multidomain OASIS solves the activated fields | failed_but_informative | `outputs/tables/cv_multidomain_oasis_training_summary.json` | Strict CV/interface training exposes unresolved thermal and interface optimization. | P1 passed or OASIS field solver validated. |",
        "| Active terminal inverse is noise robust | failed_but_informative | `outputs/tables/sequential_terminal_inverse_v3_summary.json` | Re-inverting noisy targets identifies block-specific failures. | Robust terminal inverse solved. |",
        "| Segmented-electrode y-z forward is implemented | qualified_supported | `outputs/tables/multiterminal_yz_forward_summary.json` | The finite-volume forward solver passes current-balance and uniform-limit checks and increases local observability rank. | Full 2D hidden-field recovery. |",
        "| STL/Fourier/F-SPS on v10 | forbidden | `outputs/tables/oasis_algorithm_gate_v10_summary.json` | Experiments remain blocked by the failed P1 gate. | Algorithm superiority or full STL reproduction. |",
        "| OASIS generalizes across stacks/materials | failed_but_informative | `outputs/tables/oasis_generalization_v10_summary.json` | Leave-one-factor preflight exposes stack, pulse, interface, and cross-family gaps. | Cross-material neural-operator generalization. |",
        "",
        "Historical claim evolution remains in `docs/paper/final_claim_matrix.md`, reports, and `RESEARCH_LOG.md`; this generated matrix keeps the current gate plus the active reduced-2D/stiffness audit.",
        "",
        "## Reduced 2D And Stiffness Audit",
        "",
        "| Claim | Status | Supporting table | Supporting figure | Allowed manuscript sentence | Forbidden overclaim | Required qualification |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(row[k] for k in ["claim", "status", "supporting_table", "supporting_figure", "allowed_sentence", "forbidden_overclaim", "required_qualification"]) + " |")
    lines.extend([
        "",
        "## Summary",
        "",
        f"- Reduced 2D forward supported: `{bool(fwd.get('whether_reduced_2d_forward_supported'))}`.",
        f"- Terminal-only 2D inverse failed: `{bool(obs.get('terminal_only_failure_confirmed'))}`.",
        f"- Augmented low-dimensional 2D inverse allowed: `{bool(obs.get('augmented_observation_2d_low_dim_inverse_allowed'))}`.",
        f"- Full 2D field recovery allowed: `{bool(obs.get('full_2d_field_recovery_allowed'))}`.",
        f"- Stiffness cliff mitigated: `{bool(stiff.get('whether_stiffness_cliff_mitigated'))}`.",
        f"- Full STL claim allowed: `{bool(stiff.get('whether_full_STL_claim_allowed'))}`.",
    ])
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    out = build_claim_gate_matrix(out_path=args.out)
    print(out.relative_to(ROOT))


if __name__ == "__main__":
    main()
