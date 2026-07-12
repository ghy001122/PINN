# Phase-Activated Multidomain OASIS-PINN v9 Report

Repository: `https://github.com/ghy001122/PINN`

Branch: `main`

Base commit before task: `0030fc567d4265ead08d762dcef4b77d2f14a8f5`

This report is part of the final v9 commit. All results are synthetic numerical digital-twin benchmark evidence, not experimental data. Frozen Ground Truth v1.1 was not modified.

## Changed Files

- `src/pinnpcm/physics/multilayer_sandwich.py`
- `src/pinnpcm/pinn/oasis_components.py`
- `scripts/audit_phase_activated_multilayer_forward.py`
- `scripts/train_multidomain_oasis_v9.py`
- `scripts/audit_active_protocol_identifiability_v2.py`
- `scripts/audit_oasis_2d_field_resolution_v2.py`
- `scripts/audit_phase_activated_algorithms_v9.py`
- `tests/test_phase_activated_multilayer_forward.py`
- `tests/test_multidomain_oasis_training_v9.py`
- `tests/test_active_protocol_identifiability_v2.py`
- `tests/test_oasis_v9_gates.py`
- `outputs/tables/phase_activated_multilayer_forward_summary.json`
- `outputs/tables/phase_activated_multilayer_forward_cases.csv`
- `outputs/tables/multidomain_oasis_training_summary.json`
- `outputs/tables/active_protocol_identifiability_v2_summary.json`
- `outputs/tables/sequential_terminal_inverse_v2_summary.json`
- `outputs/tables/oasis_2d_field_resolution_v2_summary.json`
- `outputs/tables/phase_activated_algorithm_summary.json`
- state, registry, claim-matrix, prior-registry, and equation docs listed in Git.

## P0 Activation

VO2 activation rate: `0.8888888888888888`. NbO2 activation rate: `0.8888888888888888`. Activated finite cases used for inverse routing: `50`. P0 gate: `True`.

Median response: max delta T `15.140535460408756`, delta m `0.7834880687603829`, conductance ratio `2.561625048607053`, energy-balance error `1.2158644865974921e-13`.

Validation: manufactured lateral Laplacian relative error `0.0001317775483549986`; mesh/time max-delta-T change `0.0009102884494205883`; conductance-ratio change `0.000812468857103493`.

Physical corrections: SnSe now uses low-thermal-conductivity / high-electrical-conductivity priors; NbO2 uses monotonic Poole-Frenkel conduction; VO2 uses branch-memory heating/cooling thresholds; generic uses a reduced Allen-Cahn/free-energy target; interface maps are independent.

## P1 Multidomain Training

P1 gate: `True`. Full mortar success: `True`. Best final-loss variant: `ordered_multidomain`. This is a small actual-training smoke on activated simulator anchors, not performance superiority.

## P2 Active Terminal Inverse

Best D-optimal protocol: `combined_d_optimal`. All block Jacobian gates: `True`. Profile-likelihood minimum success rate across noise: `1.0`.

Sequential inverse status: `failed_but_informative`. Median relative error: `0.021286031042128555`. Strict block-error gate: `False`. Block errors: `{'Rc_Ea': 0.017565485362095547, 'Rth_h_sub': 0.33886178861788613, 'Tc_width': 0.22916666666666669}`.

Interpretation: v9 greatly improves terminal-trace sensitivity after activation, but strict block-wise sequential recovery remains incomplete. This should be written as `failed_but_informative`, not a solved inverse claim.

## P3 2D Recovery

Status: `blocked`. Reason: `blocked_until_actual_electrode_BC_multi_terminal_yz_solver_is_implemented`. The audit does not use sigma half-means and does not claim 2D field recovery without an actual electrode-BC multi-terminal y-z solver.

## P4 STL/Fourier

STL status: `blocked`. Fourier/F-SPS status: `blocked`. Reason: `canonical Seiler reproduction, front-aligned LoRA transfer, and matched-budget activated-PDE Fourier/F-SPS are not yet implemented`. No canonical Seiler reproduction, LoRA-STL, or Fourier/F-SPS superiority claim is made.

## OOD And Generalization Planning

The v9 forward table includes geometry, stack, pulse-family, and material-family variation. Full leave-one-geometry/interface/stack/pulse OOD and uncertainty coverage are not yet implemented as formal train/test splits. They are the next realistic extension after the P2 block-error gate improves.

## SCI Impact

Real gain: v9 fixes the v8 non-activation problem and makes OASIS-PINN supplementary evidence more physically credible. It adds meaningful workload and innovation around activated reduced-device physics, material-family kernels, non-identity mortar losses, and terminal-trace sensitivity.

Remaining gap: the safest paper core remains calibration-gated constrained `gamma_sub`. v9 can support supplementary method-development and future OASIS claims, but not full-field recovery, full STL-PINN reproduction, or F-SPS superiority.

## Validation

Commands run before commit:

```powershell
.\.venv\Scripts\python.exe scripts\audit_phase_activated_multilayer_forward.py
.\.venv\Scripts\python.exe scripts\train_multidomain_oasis_v9.py --epochs 10
.\.venv\Scripts\python.exe scripts\audit_active_protocol_identifiability_v2.py
.\.venv\Scripts\python.exe scripts\audit_oasis_2d_field_resolution_v2.py
.\.venv\Scripts\python.exe scripts\audit_phase_activated_algorithms_v9.py
.\.venv\Scripts\python.exe -m pytest tests/test_phase_activated_multilayer_forward.py tests/test_multidomain_oasis_training_v9.py tests/test_active_protocol_identifiability_v2.py tests/test_oasis_v9_gates.py tests/test_multidomain_oasis_pinn.py tests/test_oasis_components.py
.\.venv\Scripts\python.exe -m pytest
```

Validation result: targeted v9/key regression tests passed (`20 passed in 11.22s`), and full repository pytest passed (`168 passed in 161.06s`).
