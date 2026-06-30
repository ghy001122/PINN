# Gamma_Sub Auxiliary Observability Sweep Report

All results are synthetic numerical digital-twin benchmark evidence. The auxiliary observations are synthetic information probes, not experimental measurements, and they do not imply full hidden-field recovery.

## Scope

This audit estimates only `gamma_sub` under a controlled synthetic `T_sw` mismatch. It compares port-only inversion with sparse/dense temperature information, a temperature temporal-derivative proxy, switching-state `m` proxy, aggregate `sigma` proxy, and an independently calibrated `T_sw` case.

## Key Results

- Cases evaluated: `172`.
- All finite results: `True`.
- Recoverable at <=0.1 relative error: `2` / `172`.
- Recoverable at <=0.2 relative error: `2` / `172`.
- Port-only baseline relative error: `1.2222222222222223`.
- Best overall mode: `port_plus_calibrated_T_sw` with relative error `0.0`.
- Best non-calibrated auxiliary mode: `port_plus_T_temporal_derivative_proxy` with relative error `1.0`.
- Calibrated T_sw best relative error: `0.0`.
- Frozen inputs unchanged: `True`.

## Best Case By Mode

| mode | anchor_count | weight | noise | gamma_est | relative_error | auxiliary_loss |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `port_only` | 0 | 0.0 | 0.0 | 1000000000.0 | 1.2222222222222223 | 0.0 |
| `port_plus_T_temporal_derivative_proxy` | 4 | 10.0 | 0.0 | 900000000.0 | 1.0 | 0.009275922114674442 |
| `port_plus_calibrated_T_sw` | 0 | 0.0 | 0.0 | 450000000.0 | 0.0 | 0.0 |
| `port_plus_dense_T` | 0 | 0.1 | 0.0 | 1000000000.0 | 1.2222222222222223 | 0.002521865083160583 |
| `port_plus_m_proxy` | 2 | 0.1 | 0.0 | 1000000000.0 | 1.2222222222222223 | 0.19330579520873786 |
| `port_plus_sigma_aggregate_proxy` | 2 | 0.1 | 0.0 | 1000000000.0 | 1.2222222222222223 | 0.07407286999608985 |
| `port_plus_sparse_T` | 2 | 10.0 | 0.0 | 900000000.0 | 1.0 | 0.0015085948664446064 |

## Interpretation

The calibrated `T_sw` case improves recovery, supporting the claim that independent switching-temperature calibration is the most direct way to control this confounder.

The best non-calibrated auxiliary proxy reduces bias relative to port-only but remains outside the recoverable region; this is weak observability guidance and still supports `T_sw` calibration as dominant.

The manuscript claim remains conditional: auxiliary synthetic observability can guide experimental design, but the current evidence does not prove unconditional `gamma_sub` identifiability, real-device thermal extraction, or sparse-port full hidden-field recovery.
