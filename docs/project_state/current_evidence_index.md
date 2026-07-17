# Current Evidence Index

This is a routing index; current status remains authoritative in `PROJECT_STATE.md`.

## Locked Safe Mainline

- Existing evidence lock: `docs/paper/gamma_sub_evidence_lock.md`.
- Claim matrix: `docs/paper/final_claim_matrix.md`.
- Safe inverse wording: calibration-gated rank-1 `gamma_sub`, synthetic and prior-qualified.

## VO2 D0 and Full-PINN N0 Evidence

| Block | Status | Primary evidence |
| --- | --- | --- |
| D0a provenance/source semantics | `qualified_supported` sub-result | `data/external/vo2_zhang_2024/manifest.json`; `outputs/tables/vo2_d0a_source_discrepancies.csv` |
| D0a completion gate | `failed_but_informative` | `outputs/tables/vo2_d0a_source_reproduction.json`; `outputs/figures/vo2_d0a_source_semantics_v2.png` |
| D0b-D0d | not run / positive claims `forbidden` | D0a stop rule; 13 V sealed; no fit lock |
| N0 architecture contracts | `supported` as implementation facts | `outputs/tables/full_pinn_contract_v1.json`; `src/pinnpcm/pinn/full_pinn_1d.py`; `src/pinnpcm/pinn/full_pinn_n0_cv_e.py` |
| N0 v1 trained forward | `failed_but_informative`; positive claim `forbidden` | `outputs/tables/full_pinn_single_seed_mve_v1.json`; `outputs/figures/full_pinn_n0_mve_gate_v1.png` |
| N0 teacher/FVM audit | `supported` with corrected scope | `outputs/tables/n0_teacher_equation_compatibility_v1.json`; `outputs/tables/n0_r_v2_evidence_integrity_audit.json` |
| N0-R v2 exact-trace repair | `failed_but_informative` | `outputs/tables/full_pinn_n0_repair_data_free_seed_20260715_v2.json`; `outputs/tables/n0_full_pinn_bounded_repair_v2_summary.json` |
| N0-CV-E v3 no-training preflight | `supported` operator fact | `configs/full_pinn_n0_cv_e_v3.yaml`; `outputs/tables/n0_cv_e_v3_preregistration.json`; `outputs/tables/n0_cv_e_v3_preflight.json` |
| N0-CV-E v3 training | `failed_but_informative`; positive claim `forbidden` | `outputs/tables/n0_cv_e_v3_seed_20260715.json`; `outputs/tables/n0_cv_e_v3_summary.json`; `outputs/figures/n0_cv_e_v3_gate_comparison.png` |
| N1-N3 / SC-LOS | not run / `forbidden` | N0 final stop and upstream dependency rule |

Final N0 report: `docs/codex_reports/n0_cv_e_v3_report.md`.

Phase-A integrity report: `docs/codex_reports/n0_r_v2_evidence_integrity_audit.md`.

Literature overlap audit: `docs/literature/identifiability_neural_red_team_v2.md`.

## Preserved Extension Ledger

| Gate | Status | Boundary |
| --- | --- | --- |
| P0 | `qualified_supported` | reduced synthetic physical semantics |
| P1 | `failed_but_informative` | historical interface/training failure preserved |
| P2 | `failed_but_informative` | thermal/full-rank inverse gates fail |
| P3 | `qualified_supported` | local rank `1 -> 3` in a three-parameter basis only |
| P4 | `forbidden` | no full STL or universal Fourier/F-SPS claim |

## Evidence-Type Separation

- `public_external_raw`: Zhang paper/Source Data/Zenodo/GitHub artifacts.
- `derived` or `interpolated`: processed copies with raw-parent hashes.
- `solver_generated`: author-compatible, repository SI, and operator-preflight trajectories.
- `pinn_predicted`: completed neural trajectories only; v3 produced no checkpoint or score trajectory.
- `synthetic_gt`: frozen benchmark arrays, never N0 training labels.

None is project-generated experimental measurement.
