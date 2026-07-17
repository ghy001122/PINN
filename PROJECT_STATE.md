# Project State

## Authoritative Current Snapshot

- Delivery mode: `Q2_SCI_DELIVERY_MODE`.
- Active phase ID: `M_GAMMA_SUB_MANUSCRIPT_ASSEMBLY`.
- Frozen GT v1.1: unchanged and read-only.
- Complete PINN policy: mandatory architecture/paper scaffold; positive trained claims remain evidence-gated.
- Safe inverse result: calibration-gated constrained `gamma_sub` rank-1 recovery, `qualified_supported` under its locked synthetic conditions.
- Project-generated experimental validation: absent.
- Public VO2 result: D0a `failed_but_informative`; D0b-D0d were not run and 13 V remains sealed.
- N0: final stop after v1, exact-trace v2, and solver-consistent N0-CV-E v3 failed to establish trained forward evidence. The v3 operator preflight passes, but its locked primary optimization terminates on a non-finite L-BFGS closure before checkpoint or result-gate evaluation.
- N1-N3 and SC-LOS: not run; positive claims `forbidden`.
- N0-CV-E v3 execution base: `e3f5765801991ebd1006dc762f8804a48e2d7a5a`.

## Current Gate Ledger

| Gate | Status | Direct boundary |
| --- | --- | --- |
| Frozen GT v1.1 | `supported` integrity baseline | Equations, parameters, arrays, and acceptance files unchanged. |
| P0 | `qualified_supported` | Reduced synthetic physical semantics only. |
| P1 | `failed_but_informative` | Historical `E_T=0.37563055753707886`, `E_m=0.06811526417732239`, interface residual `106.15460205078125`, success `0.0`; not a universal prerequisite for the minimum 1D scaffold. |
| P2 | `failed_but_informative` | Thermal/material parameter-block identifiability unresolved. |
| P3 | `qualified_supported` | Static pure-electrical three-parameter local rank result only. |
| P4 | `forbidden` | No full STL or universal Fourier/F-SPS superiority. |
| D0a | `failed_but_informative` | Source/SI parity passes; time-step NRMSE95 `0.163148 > 0.01`. |
| D0b-D0d | `forbidden` as completed evidence | Not run; no fit lock; 13 V sealed. |
| N0 teacher/trajectory compatibility | `supported` | Manufactured and independent trajectory ledgers pass; the older conservation artifact alone is only bookkeeping smoke evidence. |
| N0-CV-E v3 operator contract | `supported` as implementation fact | Analytic series electrostatics, exact frozen CV RHS, hard IC/BC, dimensionless roundtrip, negative controls, and locked hashes pass 18/18 preflight checks. |
| N0-CV-E v3 trained forward | `failed_but_informative`; positive claim `forbidden` | Seed `20260715` stops on non-finite L-BFGS loss after 1200 Adam steps, before checkpoint/metrics; every result gate is fail-closed and unassessed. |
| N1-N3 / SC-LOS | `forbidden` | Not run; N0 never passed a complete trained gate. |

## Distance To Delivery Goal

| Deliverable | Current state | Remaining gap |
| --- | --- | --- |
| Frozen synthetic `gamma_sub` mainline | locked and preserved | Integrate claims, failures, figures, and reviewer defense into final manuscript |
| Public-data realism anchor | D0a provenance/source semantics plus convergence failure | Keep as limitation; no current refit or 13 V action |
| Full 1D PINN scaffold | versioned code/operator contracts exist; all bounded training attempts fail | Preserve as mandatory scaffold and explicit failure boundary, not positive evidence |
| Solver/PINN sensitivity and quotient inverse | absent | Not part of current execution; upstream gates failed |
| Submission package | incomplete | Assemble only supported/qualified claims and negative boundaries |

## Current Single Priority

Finalize the calibrated `gamma_sub` manuscript and reviewer-defense package. Incorporate D0a and all N0 failures without overclaiming. Do not reopen N0 optimization or promote the v3 no-training operator preflight to trained full-PINN evidence.

Compact routing is in `docs/project_state/current_evidence_index.md`; the final N0 report is `docs/codex_reports/n0_cv_e_v3_report.md`.
