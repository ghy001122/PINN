# VO2 Protocol-Quotient and Full-PINN v2 Execution Report

Date: 2026-07-15

Delivery mode: `Q2_SCI_DELIVERY_MODE`

Base commit: `73571ee7a6e69545b67d516654ccfbfa653323eb`

## Executive disposition

The candidate hypothesis was **not tested** because two upstream credibility gates failed. This is not evidence against or for protocol-conditioned quotient inversion.

- D0a: `failed_but_informative`. Author-code/SI semantic parity passed, but the preregistered 5 ns versus 2.5 ns full-trace current convergence metric was `0.163148`, above the `0.01` gate.
- D0b, D0c, D0d: not run. No repository-side calibration was performed, no fit lock was created, and 13 V numerical content remains sealed.
- N0 contract audit: `preflight_passed`. The new versioned implementation contains state outputs `phi,c_v,T,m`, physical conductivity closure, four residuals, IC/BC, interface diagnostics, and the series-resistance port operator.
- N0 trained single-seed MVE: `failed_but_informative`. At 1200 fixed epochs, port NRMSE95 was `0.123764` versus `0.10`; residual RMS values were `{'r_T': 0.01937158778309822, 'r_c': 0.020203422755002975, 'r_m': 0.012171907350420952, 'r_phi': 0.012563918717205524}` versus `0.01` each.
- N1-N3: not run because N0 did not pass. No solver-sensitivity, PINN-sensitivity-fidelity, or inverse claim is available.

Budget accounting: D0a was executed twice with the identical fixed configuration (the second run added complete config/data-manifest hashes), for `12/60` forward evaluations in this round. N0 used `0` GPU-hours and `261.1` s of training wall time, below its 12 h cap. No budget transferred between stages.

## D0a evidence

| Check | Result | Gate |
| --- | ---: | ---: |
| Author/SI dynamic-current NRMSE95 | `4.546e-14` | `<=1e-6` |
| Author/SI dynamic-temperature NRMSE95 | `1.446e-14` | `<=1e-6` |
| Author/SI R-T NRMSE95 | `4.858e-16` | `<=1e-6` |
| Event count | `32` vs `32` | exact |
| 5 ns vs 2.5 ns current NRMSE95 | `0.163148` | `<=0.01` **failed** |
| Author no-fit R-T NRMSE95 | `0.059381` | report only |
| Author code vs experiment 11 V NRMSE95 | `0.446114` | report only |

Evidence semantics: `source_paper_model_reproduction` only. It is not a repository refit, cross-voltage evaluation, independent external validation, or project-generated experiment.

## N0 evidence

The hard electrical BC error was `0.000e+00` and the normalized IC error was `1.490e-08`. The constant-equilibrium manufactured solution returned zero for all four normalized residuals.

The trained MVE remained outside every training gate despite finite values and valid state bounds. Frozen full fields were read only after optimization and are labeled `synthetic_gt`; the network output is `pinn_predicted`. No full field entered training.

## Claim disposition

| Candidate claim | Status | Allowed use |
| --- | --- | --- |
| Source code and SI rewrite have matching declared semantics at 10 ns | `qualified_supported` sub-result | Reproduction-method check only |
| D0a exact-source reproduction gate | `failed_but_informative` | Time-step sensitivity boundary |
| 13 V external holdout/validation | `forbidden` | 13 V was not read or evaluated |
| Complete 1D PINN implementation contract exists | `supported` as code/contract fact | Architecture description, not trained accuracy |
| Complete 1D PINN forward evidence passes frozen GT | `forbidden` | N0 MVE failed |
| PINN sensitivity fidelity or inverse recovery | `forbidden` | N1-N3 not run |
| Historical calibrated rank-1 `gamma_sub` inverse | `qualified_supported` | Preserved safe manuscript fallback |

## Files and reproducibility

- Configs: `configs/vo2_d0a_exact_source_v2.yaml`, `configs/full_pinn_architecture_v1.yaml`.
- Code: `src/pinnpcm/external_data/vo2_zhang.py`, `src/pinnpcm/physics/vo2_thermal_neuristor.py`, `src/pinnpcm/pinn/full_pinn_1d.py`, `src/pinnpcm/pinn/full_residuals_1d.py`.
- Machine evidence: `outputs/tables/vo2_d0a_source_reproduction.json`, `outputs/tables/vo2_d0a_source_discrepancies.csv`, `outputs/tables/full_pinn_contract_v1.json`, `outputs/tables/full_pinn_pilot_v1.json`, `outputs/tables/full_pinn_single_seed_mve_v1.json`.
- Figures: `outputs/figures/vo2_d0a_source_semantics_v2.png`, `outputs/figures/full_pinn_n0_mve_gate_v1.png`.
- External raw archives and generated checkpoints/NPZ remain local and ignored; lightweight provenance, licenses, hashes, configs, code, tests, summaries, and figures are tracked.

Reproduction commands (PowerShell, repository root):

```powershell
.\.venv\Scripts\python.exe scripts\prepare_vo2_d0_sources.py --config configs\vo2_d0a_exact_source_v2.yaml --quarantine-13v
.\.venv\Scripts\python.exe scripts\run_vo2_d0a_exact_source.py --config configs\vo2_d0a_exact_source_v2.yaml
.\.venv\Scripts\python.exe scripts\audit_full_pinn_contract.py --config configs\full_pinn_architecture_v1.yaml
.\.venv\Scripts\python.exe scripts\train_full_pinn_1d.py --config configs\full_pinn_architecture_v1.yaml --pilot
.\.venv\Scripts\python.exe scripts\train_full_pinn_1d.py --config configs\full_pinn_architecture_v1.yaml --single-seed-mve
.\.venv\Scripts\python.exe scripts\build_vo2_d0_evidence.py
.\.venv\Scripts\python.exe -m pytest -q
```

Both training commands intentionally exit non-zero when the recorded gate fails. Do not continue to N1-N3 after that exit.

## Failure boundary and next single priority

The shortest next priority is a bounded N0 numerical diagnosis that separates collocation generalization error from residual scaling and bilayer-interface error, using the same frozen GT and unchanged gates. It must not proceed to inverse work until at least 2/3 fixed seeds pass. D0 can be revisited only with a preregistered stable integration policy that resolves the current time-step failure without fitting public traces.
