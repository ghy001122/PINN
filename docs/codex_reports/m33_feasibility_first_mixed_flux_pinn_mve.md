# M33 Feasibility-First Mixed-Flux Full-PINN MVE

Base snapshot: `664c3a0768e5de29fc68348827e18ed057b64862`

Preregistration commit: `b3f7068223fcf618b212c1919bddddba05b0b7b8`

Evidence: frozen synthetic numerical digital twin; no public data or experiment.

Claim status: `failed_but_informative`

## Scientific result

Preflight passed: `True`. Training executed: `True`.
The single locked Adam run used `1500` steps (1.25x v3r Adam budget) and seed `20260715`.

| Gate block | Value | Pass |
| --- | ---: | :---: |
| Port NRMSE95 | 0.11678283 | False |
| Max PDE residual RMS | 1048.3698 | False |
| Max constitutive RMS | 0.79534435 | False |
| Max field NRMSE95 | 1.7164177 | False |
| Max explicit interface-flux NRMSE95 | 267.65822 | False |
| Energy ledger | 0.99995479 | False |
| Defect ledger | 1 | False |
| No regression vs v3r | 10/20 | False |

Failed gates: constitutive, cv_residuals, defect_ledger, energy_ledger, fields, interface_flux, port, v3r_no_regression

All `16/16` no-training checks pass: matched parameter count, constant-equilibrium manufacture, non-trivial exact frozen-FVM parity, initial flux-head parity, one-sided interface trace, oriented jump law, independent ledger reconstruction, automatic/finite-difference gradient parity, tamper controls, finite outputs/gradients/multipliers, and frozen hashes. Preflight is therefore an implementation fact, not trained evidence.

## Training behavior and v3r comparison

The feasibility/coupled run remains finite and lowers its grouped conservation RMS from `8.61335e4` to `661.735`, while the augmented loss falls from `3.70949e8` to `2.69383e6`. Conservation and phase/current multipliers both hit the locked cap `100`; every penalty reaches its locked cap `10`. The constitutive group changes from `0.266262` to `0.532714` and the phase/current group from `0.408920` to `2.38011`, so feasibility is not achieved simultaneously.

| Metric | v3r post-Adam | M33 | Direction | Gate |
| --- | ---: | ---: | --- | ---: |
| Port NRMSE95 | `0.0955475` | `0.116783` | worse | `0.10` |
| `r_T` RMS | `56586.5` | `1048.37` | 54.0x lower | `0.01` |
| `r_m` RMS | `4.07622` | `3.60004` | lower | `0.01` |
| Interface heat NRMSE95 | `33211.9` | `267.658` | 124x lower | `0.05` |
| Interface defect NRMSE95 | `23.8718` | `9.63365` | 2.48x lower | `0.05` |
| Energy ledger | `0.999950` | `0.999955` | worse | `0.05` |
| Defect ledger | `1.0` | `1.0` | unchanged failure | `0.01` |

The explicit-head training ledger RMS values (`energy 0.0130801`, `defect 0.000223322`, current `2.84e-11`) pass their numeric thresholds, but the independent 400-time-point state-trajectory ledgers fail. They therefore cannot vote for conservation fidelity. Only `10/20` preregistered matched metrics are non-worse.

## Claim boundary

Allowed: `failed_but_informative`; the one-shot mixed-flux plus feasibility-first contract remains insufficient under at least one locked gate.

Forbidden: component novelty for mixed formulations or augmented Lagrangians; sensitivity fidelity; inverse recovery; experimental validation; cross-material generalization; gate relaxation; seed expansion.

## Disposition

A failed M33 permanently closes new full-PINN training exploration under this project contract and routes the project back to immediate assembly of the calibration-gated rank-1 `gamma_sub` manuscript. A passing M33 only registers an N1 sensitivity-fidelity gate; it does not execute it.

## Delivery impact and remaining gap

M33 resolves the last authorized question about whether a new residual representation, without labels or an optimizer search, could turn the complete PINN into a conservation-feasible forward model. The answer is no under the locked single-seed, matched-budget contract. It also localizes what changed: mixed fluxes alleviate part of the thermal/interface stiffness, while coupled constitutive closure, global trajectory conservation, fields, and the port remain incompatible at the required accuracy.

The target paper therefore still lacks positive trained full-PINN forward evidence, solver/PINN sensitivity fidelity, provenance-backed experimental validation, and any conditional PINN inverse. Those gaps cannot be repaired inside the authorized compute/evidence chain. The defensible submission is the calibration-gated rank-1 `gamma_sub` inverse with the complete PINN retained as a versioned architecture and transparently reported negative forward-fidelity program. The next highest-value feasible action is manuscript and submission-package assembly, not another training experiment.

## Execution and validation lock

- The preregistered preflight passed all `16/16` checks before training; exactly one seed and one 1500-step training run were executed. There was no rerun, continuation, retuning, threshold change, seed expansion, hidden-field label use, or 13 V access.
- Focused M33 validation passed `14` tests in `5.31 s`.
- The single full repository suite passed `296` tests in `163.62 s`; it was not rerun.
- Strict parsing passed for all `153` JSON artifacts present before creation of the final validation record; the final record also parses independently.
- The final governance audit has zero failed checks and passes the `24,576`-byte compact-context budget at `24,273` bytes. An earlier audit failed only this size check; repeated evidence prose was compacted without changing scientific evidence or gates.
- All eight frozen-GT hashes pass. The diff from the base snapshot contains no changes under frozen GT, v3r, CEBA, SCIS, CPCF, D0, or 13 V historical result paths.
- The result-commit diff passes whitespace checking. The full two-commit phase check reports only a terminal blank line in four preregistration-locked files. Those bytes are deliberately preserved because post-training cleanup would invalidate their training-authorization hashes; the warning has no effect on execution or evidence semantics.
- Machine validation record: `outputs/tables/prompt33_final_validation.json`.
