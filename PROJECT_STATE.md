# Project State

## Authoritative Current Snapshot

- Delivery mode: `Q2_SCI_DELIVERY_MODE`.
- Active phase ID: `N0_FULL_PINN_NUMERICAL_REPAIR`.
- Frozen GT v1.1: unchanged and read-only.
- Complete PINN policy: mandatory architecture/paper scaffold; positive claims remain evidence-gated.
- Safe manuscript inverse result: calibration-gated rank-1 `gamma_sub`, `qualified_supported` under its existing synthetic conditions.
- Project-generated experimental validation: absent.
- Public VO2 result: D0a `failed_but_informative`; source/SI semantics agree, but time-step convergence fails.
- 13 V: still sealed; no fit lock, refit, cross-voltage evaluation, or independent external validation exists.
- N0: architecture/manufactured preflight passes, trained single-seed MVE fails. Full-PINN forward evidence remains `forbidden`.
- N1-N3: not run because the N0 gate failed.
- Execution base commit: `73571ee7a6e69545b67d516654ccfbfa653323eb`.

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
| N0 implementation contract | `supported` as code fact | State network, physics closure, residuals, IC/BC, interface diagnostics and port operator exist. |
| N0 trained forward evidence | `failed_but_informative`; positive claim `forbidden` | Single-seed 1200-epoch MVE misses port and all residual gates. |
| N1-N3 | `forbidden` | Not run; upstream N0 gate failed. |

## Distance To Delivery Goal

| Deliverable | Current state | Remaining gap |
| --- | --- | --- |
| Frozen synthetic mainline and gamma-sub evidence | locked and preserved | Integrate without overclaiming |
| Public-data realism anchor | provenance/source semantics available; D0a failed | Resolve numerical convergence before any refit or 13 V access |
| Full 1D PINN scaffold | implementation exists | Pass unchanged N0 forward gate in 2/3 seeds |
| Solver/PINN sensitivity evidence | absent | N1 and N2 blocked by N0 |
| Conditional quotient inverse | absent | D0c/D0d and N1/N2 gates all required |
| Complete manuscript/submission package | incomplete | Preserve failure-boundary figures/tables and finish only supported narrative |

## Current Single Priority

Run one bounded N0 numerical diagnosis and produce a preregistered repair decision. Do not expand into D0 calibration, protocol effects, sensitivity, or inverse methods while N0 remains failed. The constrained `gamma_sub` result remains the safe fallback.

Compact routing is in `docs/project_state/current_evidence_index.md`; the cumulative execution report is `docs/codex_reports/vo2_protocol_quotient_full_pinn_v2_report.md`.
