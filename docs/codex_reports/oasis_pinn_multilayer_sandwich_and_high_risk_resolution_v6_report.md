# OASIS-PINN Multilayer Sandwich And High-Risk Resolution v6 Report

Repository: `https://github.com/ghy001122/PINN`  
Branch: `main`  
Base commit before this task: `7d4f15d6e68ad2db829ee0e21248f2ed7cc40fe3`. Final pushed commit hash is reported in the final response; embedding a commit own hash in a tracked file would change that hash.

## Scope

This task extends the supplementary claim-gate evidence chain. All outputs are synthetic numerical digital-twin benchmark evidence. No experimental data were fabricated. Frozen Ground Truth v1.1 was not modified.

## Changed Files

Key new files include:

- `configs/literature_priors_phase_change.yaml`
- `configs/multilayer_sandwich_device.yaml`
- `configs/high_risk_claim_resolution_v6.yaml`
- `src/pinnpcm/physics/multilayer_sandwich.py`
- `src/pinnpcm/pinn/oasis_components.py`
- `src/pinnpcm/experiments/claim_resolution_2d_field.py`
- `scripts/audit_literature_prior_consistency.py`
- `scripts/audit_multilayer_sandwich_device.py`
- `scripts/audit_claim_resolution_2d_field.py`
- `scripts/audit_terminal_only_active_protocol_rescue.py`
- `scripts/audit_phase_aware_stl_repair.py`
- `scripts/audit_adaptive_fourier_fsps_superiority.py`
- `scripts/audit_multilayer_sandwich_low_dim_inverse.py`
- `tests/test_literature_prior_consistency.py`
- `tests/test_multilayer_sandwich_device.py`
- `tests/test_oasis_components.py`
- `tests/test_claim_resolution_2d_field.py`
- `tests/test_terminal_only_active_protocol_rescue.py`
- `tests/test_phase_aware_stl_repair.py`
- `tests/test_adaptive_fourier_fsps_superiority.py`
- `tests/test_multilayer_sandwich_low_dim_inverse.py`

## Result Summaries

- Literature prior registry: `qualified_supported`; required families present `True`; provenance fields `True`.
- Multilayer sandwich forward: `qualified_supported`; finite rate `1.0`; interface BC residual median `0.0`; current continuity median `0.0`.
- 2D recovery resolution ladder: `qualified_supported` under `multi_terminal_plus_fisher_anchors`; best median field error `0.19897395319670247`; terminal-only full field remains `forbidden`.
- Terminal-only active protocol: `qualified_supported` for low-dimensional parameters under `combined_terminal_protocol`; single-trace arbitrary full field remains `forbidden`.
- Phase-aware STL repair: `failed_but_informative`; best algorithm `progressive_width_stl`; full STL-PINN reproduction remains `forbidden`.
- Adaptive Fourier/F-SPS: `failed_but_informative`; sharp gain `0.4079553978360986`; Pareto win rate `0.6666666666666666`; universal superiority remains `forbidden`.
- Low-dimensional sandwich inverse: `qualified_supported` under `combined`; median parameter error `0.04044092905036974`.

## Claim Upgrades

- Literature-prior registry: qualified support for using three literature-grounded device families as shape/parameter plausibility priors.
- Boundary-aware multilayer sandwich forward: qualified support for a reduced multilayer benchmark with explicit boundary residual auditing.
- Augmented 2D field recovery: qualified support only under Fisher-anchor augmented observations, not terminal-only recovery.
- Active terminal protocols: qualified support only for low-dimensional parameter diagnosis under combined protocols.
- Low-dimensional sandwich inverse: qualified support for reduced parameter inversion under combined protocol.

## Partial Or Failed-But-Informative Results

- Phase-aware STL repair remains failed-but-informative; progressive width improved over continuation but below the success gate.
- Adaptive F-SPS remains failed-but-informative; sharp gains are real in actual autograd training, but Pareto win rate and smooth-regime degradation miss the gate.

## Still Forbidden Claims

- Experimental validation.
- Full FEM or device-grade reproduction.
- Terminal-only arbitrary full 2D hidden-field recovery.
- Full STL-PINN reproduction.
- Universal Fourier/F-SPS superiority.
- Sparse port data uniquely recovering all hidden fields.

## Validation

Validation commands run before commit:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_literature_prior_consistency.py tests/test_multilayer_sandwich_device.py tests/test_oasis_components.py
# 5 passed

.\.venv\Scripts\python.exe -m pytest tests/test_claim_resolution_2d_field.py tests/test_terminal_only_active_protocol_rescue.py tests/test_phase_aware_stl_repair.py tests/test_adaptive_fourier_fsps_superiority.py
# 4 passed

.\.venv\Scripts\python.exe -m pytest tests/test_multilayer_sandwich_low_dim_inverse.py tests/test_port_physical_2d_inverse.py tests/test_stiffness_gated_fourier_fsps.py tests/test_claim_gate_resolution_matrix.py
# 4 passed

.\.venv\Scripts\python.exe -m pytest
# 148 passed
```

Official audit scripts were run and generated the listed summary JSON/CSV outputs.

## Frozen GT And Ethics

Frozen GT modified: No.  
Experimental data fabricated: No.  
Evidence type: synthetic / numerical / digital-twin benchmark.
