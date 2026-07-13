# Current Research Handoff

## One-Sentence Status

The project has a frozen synthetic Ground Truth v1.1 benchmark and has shifted
from port-only full hidden-field recovery toward literature-backed constrained
`gamma_sub` inversion because identifiability audits exposed hidden-field
non-uniqueness.

## Completed Base

- Ground Truth v1.1: frozen synthetic Nb/NbOx/V2O5/Ni-inspired benchmark.
- PINN inverse v0: runnable inverse pipeline and full/weak/port-only ablation.
- PINN inverse v1: approximate autograd physics residuals.
- PINN inverse v1.1: residual balancing and warmup, with limited improvement.
- Identifiability audit: terminal observations do not uniquely determine the
  hidden fields.
- `gamma_sub` identifiability audit: stable scalar recovery under fixed
  micro-kinetic priors.
- `gamma_sub` confounding audit: `T_sw`, `tau_m`, `sigma_on0`, and `eta_A` can
  bias the scalar inversion if released or mismatched.

## Current Interpretation

Port-only `V(t)`, `I(t)`, and `G(t)` are strong constraints on the integrated
conductance response. They are not enough to uniquely identify the thermal,
defect, internal state, and conductivity fields without additional priors,
anchors, or observability.

The paper route should therefore emphasize identifiability-guided target-space
reduction: define a reduced inverse target, keep confounding physics parameters
literature-guided or bounded, and quantify robustness under prior-width and
noise sweeps.

## Current Next Task

Prepare and then run literature-backed constrained `gamma_sub` inversion:

- `gamma_sub` is the only primary inverse parameter.
- `D_v0`, `mu_v0`, and related micro-kinetic parameters remain frozen.
- `T_sw`, `tau_m`, `sigma_on0`, and `eta_A` are evaluated only through narrow
  prior-width or mismatch sweeps.
- Results must remain synthetic numerical digital-twin benchmark evidence.

## Do Not Claim

- Do not claim completed experimental validation.
- Do not claim unique full hidden-field reconstruction from port-only data.
- Do not claim strict PDE-constrained PINN status for v0/v1/v1.1 pipelines.
