# Current Evidence Index

This is a routing index; current status remains authoritative in `PROJECT_STATE.md`.

## Locked Safe Mainline

- Existing evidence lock: `docs/paper/gamma_sub_evidence_lock.md`.
- Claim matrix: `docs/paper/final_claim_matrix.md`.
- Safe inverse wording: calibration-gated rank-1 `gamma_sub`, synthetic and prior-qualified.

## VO2 D0a and Full-PINN N0 Round

| Block | Status | Primary evidence |
| --- | --- | --- |
| D0a provenance/source semantics | `qualified_supported` sub-result | `data/external/vo2_zhang_2024/manifest.json`; `outputs/tables/vo2_d0a_source_discrepancies.csv` |
| D0a completion gate | `failed_but_informative` | `outputs/tables/vo2_d0a_source_reproduction.json`; `outputs/figures/vo2_d0a_source_semantics_v2.png` |
| D0b-D0d | not run / positive claims `forbidden` | D0a stop rule; 13 V sealed; no fit lock |
| N0 architecture contract | `supported` as implementation fact | `outputs/tables/full_pinn_contract_v1.json`; `src/pinnpcm/pinn/full_pinn_1d.py` |
| N0 trained forward evidence | `failed_but_informative`; positive claim `forbidden` | `outputs/tables/full_pinn_single_seed_mve_v1.json`; `outputs/figures/full_pinn_n0_mve_gate_v1.png` |
| N1-N3 | not run / `forbidden` | N0 upstream stop rule |

Round summary: `outputs/tables/vo2_protocol_quotient_full_pinn_v2_summary.json`.

Full report: `docs/codex_reports/vo2_protocol_quotient_full_pinn_v2_report.md`.

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
- `solver_generated`: author-compatible and repository SI trajectories.
- `pinn_predicted`: N0 neural trajectories.
- `synthetic_gt`: frozen benchmark arrays, used as post-training score only in N0.

None of these is project-generated experimental measurement.
