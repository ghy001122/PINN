# Parameter Prior Registry

All entries are literature-guided or engineering priors for the synthetic
numerical digital-twin benchmark. They are not measured material parameters.

| Parameter | Current value | Unit | Meaning | Frozen? | Inverted? | Allowed perturbation in constrained audit | Main confounders | Basis | Claim boundary |
| --- | ---: | --- | --- | --- | --- | --- | --- | --- | --- |
| `gamma_sub` | `4.5e8` | W m^-3 K^-1 | Effective volumetric heat loss to substrate/environment | No in inverse target | Yes, only primary inverse target | Candidate grid from `1.5e8` to `1.0e9` | `T_sw`, `tau_m`, `sigma_on0`, `eta_A` | Engineering thermal-dissipation prior from frozen GT v1.1 | Identifiable only as a reduced scalar target under fixed or tightly bounded confounders |
| `D_v0` | `8.0e-16` | m^2 s^-1 | Vacancy diffusion prefactor | Yes | No | None | Literature-guided defect-transport prior | Must remain fixed in this audit |
| `mu_v0` | `5.0e-16` | m^2 V^-1 s^-1 | Vacancy mobility prefactor | Yes | No | None | Literature-guided defect-transport prior | Must remain fixed in this audit |
| `T_sw` | `313.0` | K | Switching midpoint temperature | Yes as model parameter; stressed as bounded confounder | No | Additive prior-width sweep up to +/-2 K | Strongly confounds `gamma_sub` | Engineering switching prior | Most dangerous confounder; requires independent calibration or very tight prior |
| `tau_m` | `4.0e-4` | s | Conductive-state relaxation time | Yes as model parameter; stressed as bounded confounder | No | Relative prior-width sweep up to +/-50% | `gamma_sub`, `sigma_on0` | Engineering kinetic prior | Can bias `gamma_sub` under wide mismatch |
| `sigma_on0` | `1.65` | S m^-1 | On-state conductivity scale | Yes as model parameter; stressed as bounded confounder | No | Relative prior-width sweep up to +/-15%; layer on-state scales are adjusted consistently | `gamma_sub`, `tau_m` | Literature-guided conductivity prior | Response direction can resemble `gamma_sub`; keep bounded |
| `eta_A` | `1.0e-6` | dimensionless | Effective active-area factor | Yes as model parameter; stressed as bounded confounder | No | Relative prior-width sweep up to +/-15% | Current amplitude and conductance scaling | Engineering contact/active-area prior | Needs calibration before broad experimental claim |

## Active Inversion Policy

- Primary inverse parameter: `gamma_sub` only.
- Frozen microscopic transport parameters: `D_v0`, `mu_v0`, activation energies,
  and Ground Truth v1.1 default equations.
- Bounded confounders: `T_sw`, `tau_m`, `sigma_on0`, and `eta_A`.
- No unconstrained joint inversion is claimed in this stage.


## V9 Multidomain OASIS Priors

These entries are literature-guided / engineering priors for synthetic numerical digital-twin benchmarks, not measured parameters.

| Parameter | Current v9 nominal | Unit | Meaning | Frozen? | Inverted? | Basis | Claim boundary |
| --- | ---: | --- | --- | --- | --- | --- | --- |
| `SnSe_k_th` | `0.35` | W m^-1 K^-1 | SnSe thermal-barrier conductivity | Yes in v9 audit | No | Low-k chalcogenide engineering prior | Not measured; only supports reduced thermal-barrier modeling |
| `SnSe_sigma` | `1.0e4` | S m^-1 | Electrically conducting SnSe barrier prior | Yes in v9 audit | No | Engineering prior to prevent substrate/barrier from replacing PCM as switching bottleneck | Not measured; no device calibration claim |
| `Rc_TE_PCM`, `Rc_PCM_barrier`, `Rc_barrier_BE`, `Rc_BE_substrate` | independent map | ohm m^2 | Interface electrical contact map | Yes in v9 audit | P2 perturbs grouped `Rc` | Interface-specific engineering prior | No shared PCM-neighbor shortcut claim |
| `Rth_TE_PCM`, `Rth_PCM_barrier`, `Rth_barrier_BE`, `Rth_BE_substrate` | independent map | m^2 K W^-1 | Interface thermal-boundary map | Yes in v9 audit | P2 perturbs grouped `Rth` | Interface-specific thermal-boundary prior | Reduced stack only, not TBR measurement |
| `Tc`, `width` | family-specific | K | VO2/NbO2/generic switching thresholds and widths | Yes in P0; P2 synthetic target | P2 sequential inverse target | Phase-transition shape prior | Synthetic activation gate only |
