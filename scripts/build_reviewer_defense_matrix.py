"""Build reviewer-defense matrix for the locked gamma_sub manuscript line."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/manuscript/reviewer_defense_matrix.md"

QUESTIONS = [
    ("Why is this not black-box fitting?", "The inverse target is selected after identifiability audits and constrained by port physics, prior registries, and simulator-backed confounding checks.", "outputs/tables/pinn_identifiability_summary.json; outputs/tables/gamma_sub_constrained_inversion_summary.json", "Reduced scalar gamma_sub inversion is physics-constrained by the digital-twin model.", "A purely data-driven black-box fit solves device physics.", "Methods; Discussion"),
    ("Why not recover full hidden fields?", "Port-only V/I/G observations constrain integrated conductance but do not uniquely identify delta_T, c_v, m, and sigma fields.", "outputs/tables/pinn_identifiability_summary.json; outputs/tables/pinn_inverse_v0_ablation_summary.json", "Full-field recovery is ill-posed in this benchmark.", "Sparse-port data uniquely recover all hidden fields.", "Results; Limitations"),
    ("Why must T_sw be calibrated?", "T_sw is the dominant confounder and large mismatch pushes gamma_sub estimates to wrong candidates.", "outputs/tables/gamma_sub_tsw_confounding_phase_map_summary.json", "T_sw must be fixed or tightly bounded before gamma_sub inversion.", "gamma_sub is unconditionally identifiable with free T_sw.", "Results; Discussion"),
    ("Is 0.1 K tolerance too strict?", "It is a synthetic audit threshold under the configured <=15% error criterion, not an experimental calibration requirement.", "outputs/tables/gamma_sub_tsw_calibration_tolerance_sweep_summary.json; outputs/tables/gamma_sub_tsw_tolerance_ode_spotcheck_summary.json", "0.1 K is a benchmark-specific tolerance marker.", "A fabricated real-device calibration accuracy requirement.", "Results; Limitations"),
    ("Why is protocol gain smaller than calibration gain?", "Disentanglement shows calibration gain dominates; protocol design is a secondary robustness enhancer.", "outputs/tables/gamma_sub_calibration_protocol_disentanglement_summary.json", "Protocol choice helps after priors are controlled.", "Protocol identity alone solves the inverse problem.", "Results"),
    ("Why is F-SPS not the main innovation?", "F-SPS evidence is bounded small-run method-development evidence and does not prove performance superiority.", "outputs/tables/f_sps_balanced_medium_budget_benchmark_summary.json", "F-SPS can be appendix or future-work material.", "F-SPS-PINN is superior based on current small runs.", "Discussion; Supplementary"),
    ("Why no real experiment?", "The current work is a synthetic numerical digital-twin benchmark designed for identifiability and method validation.", "docs/gt_v1_acceptance_report.md", "The paper is method-oriented and simulation-benchmark based.", "Measured device validation was completed.", "Introduction; Limitations"),
    ("Why no external-curve fit?", "The automated search found no provenance-backed digitized curve table, so fitting is blocked instead of fabricated.", "outputs/tables/literature_targeted_curve_extraction_attempt_summary.json", "External curve fitting is future work after digitization provenance exists.", "Public curves were fitted without data.", "Related Work; Limitations"),
    ("What is the value of a 1D synthetic benchmark?", "It isolates sparse-port identifiability, target reduction, and confounding boundaries before expensive device-scale modeling.", "docs/paper/final_claim_matrix.md", "The 1D benchmark is a controlled inverse-method testbed.", "The 1D benchmark fully replicates device physics.", "Methods; Discussion"),
    ("Relation to FEM/full multiphysics simulation?", "The repository provides a lightweight reduced-order digital twin; FEM/full multiphysics would be a higher-fidelity validation extension.", "docs/paper/equation_variable_registry.md", "The model complements, not replaces, full multiphysics solvers.", "Equivalent to full 3D FEM.", "Methods; Limitations"),
    ("Why only quasi-2D preflight, not full 2D inverse?", "2D hidden-state dimension sharply increases, and sparse terminal current cannot identify full 2D fields without added observability.", "outputs/tables/pinn_quasi_2d_residual_preflight_summary.json", "Quasi-2D is extension feasibility and residual-preflight evidence.", "2D inverse diagnosis is solved.", "Discussion; Future Work"),
    ("Does the work address phase-transition stiffness?", "A lightweight residual preflight shows a stiffness cliff as transition width narrows; continuation helps in the proxy audit, while Fourier gains are not uniform.", "outputs/tables/phase_transition_stiffness_continuation_audit_summary.json", "Phase-transition cliffs are valid supplementary residual-stress tests.", "Stiff transfer learning is fully reproduced or stiffness is solved.", "Discussion; Supplementary"),
    ("How does the work relate to phase-field inverse PINNs?", "A small Allen-Cahn mobility inversion with synthetic full-field anchors aligns with phase-field inverse-PINN literature.", "outputs/tables/phase_field_inverse_alignment_smoke_summary.json", "The project is related at the inverse-parameter paradigm level.", "Phase-field smoke is a main sparse-port experiment or experimental validation.", "Related Work; Supplementary"),
]


def build_reviewer_defense_matrix() -> Path:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# Reviewer-Defense Matrix", "", "All entries refer to a synthetic numerical digital-twin benchmark, not experimental data.", "", "| Reviewer question | Short answer | Supporting result table | Allowed claim | Forbidden overclaim | Manuscript section |", "| --- | --- | --- | --- | --- | --- |"]
    for row in QUESTIONS:
        lines.append("| " + " | ".join(row) + " |")
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return OUT


def main() -> None:
    print(build_reviewer_defense_matrix().relative_to(ROOT))


if __name__ == "__main__":
    main()
