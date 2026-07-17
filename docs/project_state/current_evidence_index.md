# Current Evidence Index

This is a routing index; current status remains authoritative in `PROJECT_STATE.md`.

## Locked safe mainline

- Evidence lock: `docs/paper/gamma_sub_evidence_lock.md`.
- Claim matrix: `docs/paper/final_claim_matrix.md`.
- Safe inverse wording: calibration-gated rank-1 `gamma_sub`, synthetic and prior-qualified.

## VO2 D0, full-PINN N0, and prompt-29 evidence

| Block | Status | Primary evidence |
| --- | --- | --- |
| D0a provenance/source semantics | `qualified_supported` sub-result | `data/external/vo2_zhang_2024/manifest.json`; `outputs/tables/vo2_d0a_source_discrepancies.csv` |
| D0a completion gate | `failed_but_informative` | `outputs/tables/vo2_d0a_source_reproduction.json`; `outputs/figures/vo2_d0a_source_semantics_v2.png` |
| D0b-D0d | not run / positive claims `forbidden` | D0a stop rule; 13 V sealed; no fit lock |
| N0 architecture contracts | `supported` as implementation facts | `outputs/tables/full_pinn_contract_v1.json`; `src/pinnpcm/pinn/full_pinn_1d.py`; `src/pinnpcm/pinn/full_pinn_n0_cv_e.py` |
| N0 v1 trained forward | `failed_but_informative` | `outputs/tables/full_pinn_single_seed_mve_v1.json` |
| N0 teacher/FVM and exact-trace v2 | mixed implementation support; trained result `failed_but_informative` | `outputs/tables/n0_teacher_equation_compatibility_v1.json`; `outputs/tables/n0_full_pinn_bounded_repair_v2_summary.json` |
| Historical N0-CV-E v3 | `failed_but_informative / runtime_abort_unassessed` | `outputs/tables/n0_cv_e_v3_semantic_amendment.json`; `outputs/tables/n0_cv_e_v3_summary.json` |
| N0-CV-E v3r preregistration | locked at clean remote commit | `outputs/tables/n0_cv_e_v3r_preregistration.json`; `configs/n0_cv_e_v3r_optimizer_forensics.yaml` |
| N0-CV-E v3r post-Adam and crash forensics | `failed_but_informative`; N0 stopped | `outputs/tables/n0_cv_e_v3r_forensic_resolution.json`; `outputs/tables/n0_cv_e_v3r_post_adam_score.json`; `outputs/tables/n0_cv_e_v3r_lbfgs_diagnostic_crash.json` |
| Solver-first SID/EC-OQ | `failed_but_informative`; both ideas deleted | `outputs/tables/sid_ec_oq_summary.json`; `outputs/tables/sid_ec_oq_cases.csv`; `outputs/tables/sid_ec_oq_bootstrap.csv` |
| N1-N3 / SC-LOS | not run / `forbidden` | failed upstream trained-forward and geometry gates |

Final prompt-29 report: `docs/codex_reports/n0_optimizer_forensics_sid_discovery_final.md`.

Detailed reports:

- `docs/codex_reports/n0_cv_e_v3r_optimizer_forensics.md`
- `docs/codex_reports/sid_ec_oq_strict_review.md`

Literature overlap audit: `docs/literature/n0_sid_optimizer_red_team.md`.

## Preserved extension ledger

| Gate | Status | Boundary |
| --- | --- | --- |
| P0 | `qualified_supported` | reduced synthetic physical semantics |
| P1 | `failed_but_informative` | historical interface/training failure preserved |
| P2 | `failed_but_informative` | thermal/full-rank inverse gates fail |
| P3 | `qualified_supported` | local rank `1 -> 3` in a three-parameter basis only |
| P4 | `forbidden` | no full STL or universal Fourier/F-SPS claim |

## Evidence-type separation

- `public_external_raw`: Zhang paper/Source Data/Zenodo/GitHub artifacts.
- `derived` or `interpolated`: processed copies with raw-parent hashes.
- `solver_generated`: author-compatible, repository SI, event-geometry, and operator-preflight trajectories.
- `pinn_predicted`: completed neural trajectories, including the scoreable v3r post-Adam trajectory.
- `synthetic_gt`: frozen benchmark arrays, never N0 training labels.

None is project-generated experimental measurement.
