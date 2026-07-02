# Manuscript Outline v1

## Working Title

Sparse-port inverse identifiability and constrained thermal-parameter recovery in a synthetic oxide memristor digital-twin benchmark.

## Claim Boundary

The manuscript should be framed as a one-dimensional synthetic numerical digital-twin benchmark. It must not claim measured experimental validation, full three-dimensional device simulation, sparse-port full hidden-field recovery, or F-SPS-PINN performance superiority.

## Abstract Logic

1. Sparse terminal electrical measurements underdetermine coupled thermal, defect, state, and conductivity fields.
2. Identifiability diagnostics motivate reducing the inverse target to an effective thermal dissipation parameter, `gamma_sub`.
3. Constrained `gamma_sub` inversion is conditionally stable when switching and conductivity priors are fixed or tightly bounded.
4. `T_sw` mismatch is the dominant failure mode and defines the main claim boundary.
5. Response-surface phase diagrams, anchor verification, protocol-design preflight, and statistical robustness provide reviewer-facing support.

## Sections

1. Introduction: sparse inverse diagnosis problem and why full hidden-field claims are risky.
2. Synthetic digital-twin benchmark: Ground Truth v1.1 physics, voltage protocols, and generated observations.
3. Identifiability-guided target reduction: why port-only full-field inversion is ill-posed.
4. Constrained `gamma_sub` inversion: scalar reduced inverse formulation and prior registry.
5. Confounding and recoverability maps: `T_sw` ridge, phase diagrams, and prior-width limits.
6. Protocol and robustness analysis: actual-validation, sequential design preflight, and seed/noise robustness.
7. Appendix method development: v0/v1/v1.1 diagnostics and F-SPS-PINN bounded benchmarks.
8. Limitations: synthetic benchmark, no experimental validation, fixed-prior dependency, and response-surface qualifications.

## Minimum Submission Package

- Main figures listed in `docs/paper/proposed_main_figures.md`.
- Main tables listed in `docs/paper/proposed_tables.md`.
- Claim stress-test matrix in `docs/paper/claim_stress_test_matrix.md`.
- Reproducibility commands and lightweight JSON/CSV evidence in `EXPERIMENT_REGISTRY.md`, `DATASET_REGISTRY.md`, and `FIGURE_REGISTRY.md`.
## Literature-Anchored Revision Notes

The manuscript should add a short paragraph in Methods stating that Lee et al. (2024) and Jurj (2026) support compact/physics-regularized memristor surrogate framing and order-of-magnitude parameter sanity, but no measured curve is used as calibration in the current repository. Results should add a T_sw calibration-necessity panel and describe simulator-backed sequential protocol validation as a preflight result.

## Calibration-Gated Submission Lock Addendum

| Evidence block | Script/config | Summary file | Proposed figure/table | Allowed claim | Forbidden overclaim |
| --- | --- | --- | --- | --- | --- |
| T_sw calibration tolerance sweep | `scripts/audit_gamma_sub_tsw_calibration_tolerance_sweep.py`, `configs/gamma_sub_tsw_calibration_tolerance_sweep.yaml` | `outputs/tables/gamma_sub_tsw_calibration_tolerance_sweep_summary.json` | Figure 3 / Table 4 | Residual T_sw error must be about `0.1` K or tighter in this synthetic audit | Real calibration accuracy requirement |
| Calibration-vs-protocol disentanglement | `scripts/audit_gamma_sub_calibration_protocol_disentanglement.py` | `outputs/tables/gamma_sub_calibration_protocol_disentanglement_summary.json` | Figure 4 / Table 5 | Calibration dominates total gain; protocol gain is smaller and qualified | Protocol identity alone solves ambiguity |
| Calibrated protocol robustness final | `scripts/audit_gamma_sub_calibrated_protocol_robustness_final.py` | `outputs/tables/gamma_sub_calibrated_protocol_robustness_final_summary.json` | Figure 5 / Table 6 | `calibrated_short_pulse_to_ltp_ltd` is best in the tested ODE-backed synthetic grid | Experimental protocol validation |
| Targeted external curve extraction | `scripts/attempt_literature_curve_extraction_from_sources.py` | `outputs/tables/literature_targeted_curve_extraction_attempt_summary.json` | Figure 7 / Supplement | No provenance-backed digitized curves were found; no curve data were fabricated | Literature curve fit success |

