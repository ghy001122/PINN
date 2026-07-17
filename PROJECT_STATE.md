# Project State

## Authoritative Current Snapshot

- Delivery mode: `Q2_SCI_DELIVERY_MODE`.
- Active phase ID: `N0_CV_LEDGER_REFORMULATION_PREFLIGHT`.
- Frozen GT v1.1: unchanged and read-only.
- Complete PINN policy: mandatory architecture/paper scaffold; positive claims remain evidence-gated.
- Safe manuscript inverse result: calibration-gated rank-1 `gamma_sub`, `qualified_supported` under its existing synthetic conditions.
- Project-generated experimental validation: absent.
- Public VO2 result: D0a `failed_but_informative`; source/SI semantics agree, but time-step convergence fails.
- 13 V: still sealed; no fit lock, refit, cross-voltage evaluation, or independent external validation exists.
- N0: teacher/FVM compatibility audit passes and exposes the v1 electrode-orientation mismatch; a preregistered matched-budget exact-trace dual-domain repair still fails residual, field, current, energy, and port gates. Full-PINN forward evidence remains `forbidden`.
- N1-N3: not run because the N0 gate failed.
- N0-R execution base commit: `583cb441687001c7df9a8ee9d4d5cf45258f8efb`.

## Current Gate Ledger

| Gate | Status | Direct boundary |
| --- | --- | --- |
| Frozen GT v1.1 | `supported` integrity baseline | No equations, parameters, arrays, or acceptance files changed. |
| P0 | `qualified_supported` | Reduced synthetic physical semantics only. |
| P1 | `failed_but_informative` | Historical `E_T=0.37563055753707886`, `E_m=0.06811526417732239`, interface residual `106.15460205078125`, success `0.0`; not a universal prerequisite for the minimum 1D scaffold. |
| P2 | `failed_but_informative` | Thermal/material parameter-block identifiability remains unresolved. |
| P3 | `qualified_supported` | Static pure-electrical three-parameter local rank improvement only. |
| P4 | `forbidden` | No full STL or universal Fourier/F-SPS superiority. |
| D0a | `failed_but_informative` | Source/SI parity passes; 5-to-2.5 ns NRMSE95 `0.163148 > 0.01`. |
| D0b-D0d | `forbidden` as completed evidence | Not run after D0a stop; 13 V remains sealed. |
| N0 teacher-equation compatibility | `supported` | Manufactured electrical/thermal/defect/bilayer cases and frozen FVM ledgers pass; v1 PINN reverses the teacher electrode orientation. |
| N0 exact-trace dual-domain implementation | `supported` | `5704` versus `5812` parameters, local layer coordinates, global-SI derivatives, physical conductivity, and independent one-sided traces. |
| N0 trained forward evidence | `failed_but_informative`; positive claim `forbidden` | Repair port `0.120358`; max held-out residual `0.048286`; current error `0.519809`; energy imbalance `0.998556`. Anchor and seed expansion were blocked. |
| N1-N3 | `forbidden` | Not run; upstream N0 gate failed. |

## Distance To Delivery Goal

| Deliverable | Current state | Remaining gap |
| --- | --- | --- |
| Frozen synthetic mainline and gamma-sub evidence | locked and preserved | Integrate without overclaiming |
| Public-data realism anchor | provenance/source semantics available; D0a failed | Resolve numerical convergence before any refit or 13 V access |
| Full 1D PINN scaffold | v1 and exact-trace split implementations exist; both trained MVEs fail | A solver-consistent residual must close local and global ledgers before 2/3-seed evidence |
| Solver/PINN sensitivity evidence | absent | N1 and N2 blocked by N0 |
| Conditional quotient inverse | absent | D0c/D0d and N1/N2 gates all required |
| Complete manuscript/submission package | incomplete | Preserve failure-boundary figures/tables and finish only supported narrative |

## Current Single Priority

Do not enter SC-LOS or N1-N3. The only admissible next N0 action is a no-training preregistration/preflight for a solver-consistent control-volume or weak-form residual that directly exposes face fluxes and global ledgers. It must reuse the fixed diagnostic set and unchanged gates; otherwise stop N0 tuning and retain the constrained `gamma_sub` fallback.

Compact routing is in `docs/project_state/current_evidence_index.md`; the current execution report is `docs/codex_reports/n0_full_pinn_bounded_repair_v2_report.md`.
