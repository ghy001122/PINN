# N0-CV-E v3 Final Bounded Attempt

Base commit: `e3f5765801991ebd1006dc762f8804a48e2d7a5a`

Final claim status: `failed_but_informative`; positive trained full-PINN forward wording: `forbidden`.

## Scope And Evidence Semantics

This round audited frozen one-dimensional synthetic GT and attempted a data-free full-PINN optimization. Frozen arrays are `synthetic_gt`; operator/replay trajectories are `solver_generated`; a completed checkpoint would have produced `pinn_predicted` trajectories, but v3 produced none. No public external fit, 13 V access, or experimental validation occurred.

Analytic electrostatics, finite/control-volume residuals, hard constraints, causal schedules, and gradient balancing are prior-art components and are not claimed as standalone novelty.

## Phase A — Evidence Integrity And Frozen-Trajectory Compatibility

The v2 checkpoint is `missing_from_versioned_evidence`; remote CI is `no_runs_for_commit`; final pytest evidence is `missing`. Fail-closed v2 gate gaps are `ic_bc_max_normalized_error`, `positive_temperature_required`, `bounded_c_v_and_m_required`, `frozen_gt_hash_unchanged_required`, `minimum_passing_seeds`, `total_seeds`, `defect_mass_ledger_max`. Historical v2 hashes were not rewritten.

The old conservation JSON is classified only as an algebraic bookkeeping smoke test. The independent adjacent-state audit reports:

| Audit | Gate value | Result |
| --- | ---: | --- |
| frozen defect ledger | 4.03948394e-06 | pass (`<=0.01`) |
| frozen energy ledger | 0.00258233858 | pass (`<=0.05`) |
| Radau replay max relative RMS | 1.30271265e-07 | pass (`<=1e-5`) |
| tampered defect ledger | 1 | detected failure |
| tampered energy ledger | 0.996583045 | detected failure |

A common SI/frozen registry rescored both historical checkpoints. The global baseline and split repair have port NRMSE95 values `0.123764` and `0.120358`; both fail CV/ledger gates. Near-interface, near-transition, and ordinary fixed regions are all nonempty and used.

## Phase B — Solver-Consistent Full-PINN Contract

The 5501-parameter network predicts bounded cell-centered `c_v`, `T`, and `m` on the unchanged 31-cell grid. It returns `phi,c_v,T,m,sigma,E,J,I,G`; the electrical quantities follow a differentiable analytic series relation. Defect/heat faces, end fluxes, reaction, Joule heating, substrate sink, and phase relaxation reproduce the frozen teacher arithmetic exactly. Hard IC/electrical BCs and a fixed dimensionless registry are explicit. Port and hidden-field labels used for training: none.

Locked inputs include the config, deterministic diagnostic NPZ, Phase-A JSON, frozen GT/config/manifest, old diagnostic points, operator code, preflight, trainer, and evidence builder. The preregistration records their stable canonical/raw hashes before training.

## No-Training Preflight

Status: `pass`; training authorized: `True`; checks passed: `18/18`.

| Metric | Value | Gate |
| --- | ---: | ---: |
| electrostatic float64 relative RMS | 2.30787214e-08 | `<=1e-7` |
| current spatial spread | 3.83608766e-16 | `<=1e-7` |
| CV-RHS maximum relative RMS | 2.12585533e-08 | `<=1e-6` |
| minimum c/T/m gradient norm | 0.00259735462 | `>=1e-12` |
| gradient central-difference error | 1.63621012e-08 | `<=1e-3` |
| SI roundtrip relative RMS | 6.04779548e-17 | `<=1e-12` |
| hard IC/BC max normalized error | 3.40439482e-16 | `<=1e-3` |

| Preflight check | Pass |
| --- | --- |
| `current_spread` | `True` |
| `cv_rhs_parity` | `True` |
| `dimensionless_roundtrip` | `True` |
| `electrostatics_parity` | `True` |
| `finite_operator_outputs` | `True` |
| `frozen_defect_ledger` | `True` |
| `frozen_energy_ledger` | `True` |
| `frozen_gt_hash` | `True` |
| `gate_coverage_complete` | `True` |
| `gradient_finite` | `True` |
| `gradient_nonzero` | `True` |
| `gradient_parity` | `True` |
| `ic_bc` | `True` |
| `negative_candidate_separation` | `True` |
| `old_fixed_points_hash` | `True` |
| `phase_a_completed` | `True` |
| `radau_replay` | `True` |
| `result_keys_complete` | `True` |

## Conditional Training And Fail-Closed Attribution

Command: `.\.venv\Scripts\python.exe scripts\train_n0_cv_e_v3.py --config configs\full_pinn_n0_cv_e_v3.yaml`

The locked seed `20260715` primary arm reached its only L-BFGS stage after the scheduled `1200` Adam steps. A strong-Wolfe closure raised `RuntimeError: Non-finite N0-CV-E L-BFGS loss.` after approximately `54.1` s. The exception occurred before checkpoint serialization and trajectory scoring.

Consequently, port, cell residual, discrete electrical, field, interface, current, energy, defect, IC/BC, finite/bounds, hash/operator, and seed-vote result gates are all `unassessed_fail_closed`. Missing metrics are not represented as zero or pass. No balancing arm, seed expansion, sparse anchor, hyperparameter search, N1-N3, or SC-LOS run was performed.

The scientific lock still matched immediately after the exception. No checkpoint exists; the checkpoint manifest explicitly records `no_checkpoint_runtime_failure_before_serialization`.

## Validation

Environment: Python `3.11.9`, PyTorch `2.3.1+cpu`, device `cpu`, CUDA `False`.

| Command | Result | Counts |
| --- | --- | --- |
| `.\.venv\Scripts\python.exe -m pytest tests\test_electrostatics.py tests\test_gt_solver_smoke.py tests\test_full_pinn_contract.py tests\test_full_pinn_manufactured.py tests\test_full_pinn_n0_split.py tests\test_n0_fixed_diagnostics.py tests\test_n0_repair_evidence.py tests\test_n0_teacher_equation_compatibility.py tests\test_train_full_pinn_n0_repair.py tests\test_n0_r_v2_evidence_integrity.py tests\test_n0_cv_e_v3_operator.py tests\test_n0_cv_e_v3_gate_safety.py -q` | `pass` | errors=0, failed=0, passed=41, skipped=0, warnings=0, xfailed=0, xpassed=0 |
| `.\.venv\Scripts\python.exe scripts\audit_project_governance.py` | `pass` | errors=0, failed=0, passed=0, skipped=0, warnings=0, xfailed=0, xpassed=0 |
| `.\.venv\Scripts\python.exe -m pytest -q` | `pass` | errors=0, failed=0, passed=233, skipped=0, warnings=0, xfailed=0, xpassed=0 |
| `git diff --check` | `pass` | errors=0, failed=0, passed=0, skipped=0, warnings=0, xfailed=0, xpassed=0 |

## Claim And Manuscript Disposition

- `supported`: frozen teacher/operator compatibility and the v3 no-training operator contract under the locked synthetic protocol.
- `failed_but_informative`: v2 evidence completeness and all trained N0 paths, including the v3 runtime failure.
- `forbidden`: reliable trained full-PINN forward fidelity, sensitivity fidelity, inverse recovery, experimental validation, cross-material generalization, or novelty of the assembled numerical components.

N0 is closed after this final bounded attempt. The unique next step is manuscript assembly on the already supported calibration-gated constrained `gamma_sub` mainline, with D0a and N0 retained as explicit limitations.
