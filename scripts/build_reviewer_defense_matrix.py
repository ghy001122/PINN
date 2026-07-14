"""Build the current reviewer-defense matrix for the locked gamma_sub manuscript line."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/manuscript/reviewer_defense_matrix.md"
ALLOWED_STATUSES = {"supported", "qualified_supported", "failed_but_informative", "forbidden"}

QUESTIONS = [
    ("Why is this not black-box fitting?", "The target is chosen after identifiability audit and estimated with a port objective plus a reduced heat residual under declared priors.", "qualified_supported", "outputs/tables/pinn_identifiability_summary.json; outputs/tables/gamma_sub_constrained_inversion_summary.json", "A reduced physics-constrained gamma_sub inverse is supported under fixed or tight priors.", "A black-box network solves complete device physics.", "Methods; Discussion"),
    ("Why not recover full hidden fields?", "Port V/I/G constrain integrated conductance but the audited full-field inverse fails to uniquely recover T, c_v, m, and sigma.", "supported", "outputs/tables/pinn_identifiability_summary.json; outputs/tables/pinn_inverse_v0_ablation_summary.json", "The configured sparse-port full-field recovery is ill-posed in the frozen benchmark.", "Sparse ports uniquely recover arbitrary hidden fields, or the audit is a universal impossibility theorem.", "Results; Limitations"),
    ("Why is gamma_sub the inverse target?", "Target-space reduction removes weakly identifiable microscopic degrees of freedom and retains a lumped effective thermal parameter.", "qualified_supported", "outputs/tables/gamma_sub_constrained_inversion_summary.json; outputs/tables/gamma_sub_continuous_refinement_summary.json", "gamma_sub is recoverable as a reduced target under declared priors.", "gamma_sub is an unconditional or measured material constant.", "Methods; Results"),
    ("Why must T_sw be calibrated?", "T_sw is the dominant audited confounder and its mismatch moves the gamma_sub optimum along a response ridge.", "qualified_supported", "outputs/tables/gamma_sub_tsw_confounding_phase_map_summary.json", "T_sw must be calibrated or tightly bounded before gamma_sub inversion in this benchmark.", "gamma_sub remains identifiable with freely varying T_sw.", "Results; Discussion"),
    ("Is the 0.1 K tolerance a real-device requirement?", "No. It is a benchmark-specific marker under the configured 15 percent median-error criterion and is supported by a 270-case ODE spot-check.", "qualified_supported", "outputs/tables/gamma_sub_tsw_calibration_tolerance_sweep_summary.json; outputs/tables/gamma_sub_tsw_tolerance_ode_spotcheck_summary.json", "The synthetic tolerance audit supports a marker near 0.1 K under its stated criterion.", "A real device requires or achieves 0.1 K calibration accuracy.", "Results; Limitations"),
    ("Is the inverse robust to noise, seed, observation count, and off-grid truth?", "Only conditionally. Calibrated or tight priors pass the audited cases, while wide T_sw mismatch fails systematically.", "qualified_supported", "outputs/tables/gamma_sub_statistical_robustness_summary.json; outputs/tables/gamma_sub_paper_readiness_summary.json; outputs/tables/gamma_sub_continuous_refinement_summary.json", "Conditional robustness and its failed prior region are both reported.", "Aggregate averages establish unconditional robustness.", "Results; Limitations"),
    ("Why is protocol gain secondary to calibration?", "The equal-prior disentanglement attributes most gain to T_sw calibration; protocol choice adds a smaller residual benefit.", "qualified_supported", "outputs/tables/gamma_sub_calibration_protocol_disentanglement_summary.json", "Protocol design improves robustness after prior control.", "Protocol identity alone solves the inverse.", "Results; Discussion"),
    ("Which evidence is Figure 5?", "The main figure uses the 720-case calibrated sequential ODE validation. The broader 2400-case stress audit explicitly reports that it is not main-figure ready.", "qualified_supported", "outputs/tables/gamma_sub_calibrated_sequential_protocol_validation_summary.json; outputs/tables/gamma_sub_calibrated_protocol_robustness_final_summary.json", "The best tested calibrated sequential protocol passes the configured 720-case synthetic gate.", "The stress audit is silently substituted, or the protocol is experimental/global-optimal.", "Results; Figure 5"),
    ("Why is there no real experiment?", "No measured dataset with provenance exists; all results are synthetic numerical digital-twin evidence.", "forbidden", "docs/gt_v1_acceptance_report.md; outputs/tables/gamma_sub_evidence_lock_summary.json", "The absence of experimental validation is stated explicitly.", "Measured-device validation was completed.", "Introduction; Limitations"),
    ("Why is there no external-curve fit?", "No provenance-backed digitized curve table is available, so the project blocks the fit instead of fabricating points.", "forbidden", "outputs/tables/literature_targeted_curve_extraction_attempt_summary.json; outputs/tables/literature_curve_fit_external_anchor_v2_summary.json", "External quantitative validation remains an explicit delivery gap.", "Public curves were fitted without provenance-backed data.", "Related Work; Limitations"),
    ("What is the value of a 1D synthetic benchmark?", "It isolates observation-induced non-identifiability, confounding, target reduction, and calibration gates before device-scale extensions.", "qualified_supported", "docs/paper/gamma_sub_evidence_lock.md", "The 1D benchmark is a controlled inverse-method testbed.", "The benchmark reproduces full device-grade multiphysics.", "Methods; Discussion"),
    ("Does the neural model replace FVM or FEM?", "No. Reliable numerical forward models support evidence generation; neural methods require separate added-value gates for inverse speed, assimilation, or generalization.", "qualified_supported", "docs/codex_reports/post_d23a576_research_decision_audit.md", "Numerical solvers and neural inverse tools have complementary roles.", "PINN has replaced full FEM/FVM or is superior without a matched comparison.", "Discussion; Limitations"),
    ("Did v10 P1 solve the multidomain neural fields?", "No. Three-seed strict training gives median E_T 0.3756, E_m 0.0681, interface residual 106.15, and success rate 0.", "failed_but_informative", "outputs/tables/cv_multidomain_oasis_training_summary.json; outputs/tables/cv_multidomain_oasis_cases.csv", "P1 exposes scaling, coordinate, and interface-optimization repair targets.", "Loss decrease establishes a validated OASIS field solver.", "Supplementary; Limitations"),
    ("Did v10 P2 solve the material-specific inverse?", "No. Rank-deficient protocols are selected before the rank flag is checked, and the implemented inverse is local linear block recovery near a nominal prior.", "failed_but_informative", "outputs/tables/active_protocol_design_v3_summary.json; outputs/tables/sequential_terminal_inverse_v3_summary.json", "P2 provides block-specific local recoverability and failure boundaries.", "Global nonlinear multi-parameter recovery is solved.", "Supplementary; Limitations"),
    ("What does segmented-terminal rank 1 to 3 mean?", "It is the local rank for a three-parameter Gaussian conductivity profile basis: center, width, and contrast.", "qualified_supported", "outputs/tables/multiterminal_yz_forward_summary.json", "Segmented terminals improve low-dimensional local observability in the synthetic forward model.", "Segmented terminals recover arbitrary 2D fields.", "Supplementary; Discussion"),
    ("Why are STL and Fourier/F-SPS not main claims?", "The v10 algorithm gate blocks them because P1 fails; earlier proxy or reduced audits cannot be promoted to v10 superiority.", "forbidden", "outputs/tables/oasis_algorithm_gate_v10_summary.json", "These methods remain bounded future or supplementary audits.", "Full STL reproduction or universal Fourier/F-SPS superiority.", "Supplementary; Future Work"),
    ("Does OASIS generalize across materials and stacks?", "No. The current evidence is a 48-case ridge leave-one-factor preflight, with severe cross-material and non-geometric holdout failures.", "failed_but_informative", "outputs/tables/oasis_generalization_v10_summary.json", "The failure supports material-specific constitutive kernels and within-family validation first.", "A trained cross-material neural operator generalizes.", "Supplementary; Discussion"),
]


def build_reviewer_defense_matrix(out_path: Path = OUT) -> Path:
    invalid = sorted({row[2] for row in QUESTIONS} - ALLOWED_STATUSES)
    if invalid:
        raise ValueError(f"Invalid reviewer-defense statuses: {invalid}")
    out = out_path if out_path.is_absolute() else ROOT / out_path
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Reviewer-Defense Matrix",
        "",
        "This matrix is aligned to the locked constrained `gamma_sub` mainline. All evidence is synthetic numerical digital-twin evidence unless a row explicitly states that external evidence is absent.",
        "",
        "| Reviewer question | Short answer | Claim status | Supporting evidence | Allowed claim | Forbidden overclaim | Manuscript section |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in QUESTIONS:
        lines.append("| " + " | ".join(row[:2] + (f"`{row[2]}`",) + row[3:]) + " |")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def main() -> None:
    print(build_reviewer_defense_matrix().relative_to(ROOT))


if __name__ == "__main__":
    main()