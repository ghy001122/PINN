# Gamma_Sub Multi-Protocol And Profile-Likelihood Validation Report

All results are synthetic numerical digital-twin benchmark evidence. They are not experimental measurements, not full three-dimensional device simulations, and not sparse-port full hidden-field recovery.

## Repository

- branch: `main`
- commit hash at report generation: `a8ceba65cc88fee76e1c26630835dedaea1bee6d`

## Changed Files

- `configs/gamma_sub_multi_protocol_recoverability.yaml`
- `configs/gamma_sub_tsw_profile_likelihood.yaml`
- `configs/gamma_sub_joint_inversion_boundary.yaml`
- `configs/gamma_sub_protocol_observability_design.yaml`
- `scripts/gamma_sub_validation_common.py`
- `scripts/audit_gamma_sub_multi_protocol_recoverability.py`
- `scripts/audit_gamma_sub_tsw_profile_likelihood.py`
- `scripts/audit_gamma_sub_joint_inversion_boundary.py`
- `scripts/audit_gamma_sub_protocol_observability_design.py`
- `scripts/build_gamma_sub_sci_validation_figures.py`
- `tests/test_gamma_sub_multi_protocol_recoverability.py`
- `tests/test_gamma_sub_tsw_profile_likelihood.py`
- `tests/test_gamma_sub_joint_inversion_boundary.py`
- `tests/test_gamma_sub_protocol_observability_design.py`
- lightweight JSON/CSV evidence under `outputs/tables/`
- project state, registry, and paper-evidence Markdown files

## Experiment Design

1. Multi-protocol recoverability compares triangle, LTP/LTD, derived multi-amplitude synthetic, and mixed objectives under nominal, wide `T_sw` mismatch, and narrowed-prior scenarios.
2. Profile likelihood scans the `gamma_sub` by `T_sw` port-objective landscape and extracts ridge/coupling diagnostics.
3. Joint inversion boundary releases nuisance parameters in lightweight candidate grids to show where conditional `gamma_sub` recovery becomes ambiguous.
4. Protocol observability design uses finite-difference sensitivity vectors to rank candidate stimulation protocols.

## Key Results

| block | key result | interpretation |
| --- | --- | --- |
| Multi-protocol recoverability | `48` cases; best protocol `ltp_ltd`; worst protocol `triangle` | Tests whether recovery generalizes beyond triangle. |
| Profile likelihood | condition number `10.762998753222757`; confounded `True` | Quantifies objective valley geometry. |
| Joint boundary | most ambiguous `gamma_plus_T_sw_plus_tau_m`; worst error `gamma_plus_sigma_on0` | Shows conditional, not arbitrary joint, identifiability. |
| Protocol design | best protocol `multi_pulse`; recommended `['long_pulse', 'short_pulse']` | Converts identifiability analysis into protocol-design guidance. |

## Validation Commands

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_gamma_sub_multi_protocol_recoverability.py tests/test_gamma_sub_tsw_profile_likelihood.py tests/test_gamma_sub_joint_inversion_boundary.py tests/test_gamma_sub_protocol_observability_design.py
.\.venv\Scripts\python.exe -m pytest tests/test_gamma_sub_auxiliary_observability_sweep.py tests/test_gamma_sub_tsw_confounding_phase_map.py tests/test_gamma_sub_tsw_prior_width_sweep.py tests/test_gamma_sub_temperature_anchor_placement.py tests/test_gamma_sub_scalar_baselines.py
.\.venv\Scripts\python.exe -m pytest
```

## Boundary

- Modified frozen GT: No.
- Added F-SPS-PINN experiments: No.
- Supported claim: synthetic numerical conditional identifiability and recoverability boundary for reduced `gamma_sub` inversion.
- Still unsupported: experimental validation, full hidden-field recovery, full 3D device extraction, and unconstrained joint parameter identifiability.

## Next Step

Use these tables to draft the main manuscript figures and a concise reviewer-defense section. Do not expand into new F-SPS-PINN training until the constrained `gamma_sub` manuscript is drafted.
