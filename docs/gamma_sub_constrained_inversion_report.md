# Gamma_Sub Constrained Inversion Report

## Scope

This report covers the literature-backed constrained `gamma_sub` inversion for
frozen Ground Truth v1.1. All results are synthetic numerical digital-twin
benchmark results, not experimental data.

The stage proves only a constrained reduced inverse workflow: `gamma_sub` is the
sole primary inverse target. It does not prove port-only full hidden-field
recovery.

## Inputs

- Config: `configs/gamma_sub_constrained_inversion.yaml`
- Script: `scripts/invert_gamma_sub_constrained.py`
- Frozen target: `data/processed/gt_v1_acceptance/gt_triangle.npz`
- Sparse port observation: `data/processed/gt_v1_acceptance/obs_triangle_sparse.npz`
- Prior evidence: `docs/literature_gamma_sub_evidence_chain.md`
- Parameter registry: `docs/parameter_prior_registry.md`

## Method

The inversion searches only over `gamma_sub`. Candidate simulations are compared
to sparse terminal observations using a weighted port loss on `G(t)` and `I(t)`
plus a candidate heat-residual penalty. `D_v0`, `mu_v0`, and other microscopic
transport parameters remain frozen.

`T_sw`, `tau_m`, `sigma_on0`, and `eta_A` are not jointly inverted. They are used
only to generate bounded mismatch targets for the prior-width sweep.

## Outputs

- Summary JSON: `outputs/tables/gamma_sub_constrained_inversion_summary.json`
- Prior-width sweep CSV: `outputs/tables/gamma_sub_prior_width_sweep.csv`

## Key Results

- True `gamma_sub`: `450000000.0`
- Clean nominal estimate: `450000000.0`
- Clean nominal relative error: `0.0`
- Maximum relative error across tested noise and prior-width cases:
  `1.2222222222222223`
- Most dangerous confounder: `T_sw`
- First tested unstable prior width: `0.05`

Prior-width summary:

| Prior width | Max relative error | Worst confounder | Stable under 0.15 threshold |
| ---: | ---: | --- | --- |
| `0.0` | `0.0` | `none` | yes |
| `0.05` | `0.2222222222222222` | `T_sw` | no |
| `0.1` | `0.4444444444444444` | `T_sw` | no |
| `0.25` | `0.6666666666666666` | `T_sw` | no |
| `0.5` | `1.2222222222222223` | `T_sw` | no |
| `1.0` | `1.2222222222222223` | `T_sw` | no |

## Interpretation

Under nominal fixed-prior conditions, `gamma_sub` is recovered exactly on the
frozen benchmark candidate grid, including clean, 2% noise, and 5% noise nominal
cases in the generated evidence table.

The prior-width sweep shows that `T_sw` is the limiting confounder. Even narrow
uncontrolled `T_sw` mismatch can bias the recovered `gamma_sub`, while `tau_m`,
`sigma_on0`, and `eta_A` are less dangerous under the tested bounds but still
must remain constrained.

Therefore, `gamma_sub` can remain the paper's reduced inverse target only when
switching-temperature behavior is fixed, independently calibrated, or tightly
bounded by literature/engineering prior information.

## Claim Boundary

This result supports an identifiability-guided target-space reduction for a
synthetic numerical digital-twin benchmark. It does not support claims of
experimental parameter extraction, unconstrained joint parameter recovery, or
unique hidden-field inversion from port-only data.
