# Literature Gamma_Sub Evidence Chain

## Scope

This document supports the constrained `gamma_sub` reduced inverse problem for a
synthetic numerical digital-twin benchmark. It does not claim measured material
parameters or experimental validation.

## Evidence Used

- Local project digest: `docs/literature_notes/gamma_sub_evidence_digest.md`
- Paper routing registry: `references/papers/PAPER_REGISTRY.md`
- Prior audit: `docs/gamma_sub_confounding_report.md`
- Prior audit data:
  `outputs/tables/gamma_sub_confounding_summary.json` and
  `outputs/tables/gamma_sub_sensitivity_ranking.csv`

Google Drive full-text literature was not accessed for this task because the
local digest and registry were sufficient for the constrained-inversion scope.

## Directly Relevant Literature Support

### Stiff PINN / continuation support

The local literature digest records stiff-PINN and transfer-learning ideas as
method support for future training stabilization. These ideas justify keeping
stiffness and continuation in the long-term method roadmap, but they are not
used as new physics or as evidence that the current scalar inversion is a full
PDE-constrained inverse PINN.

### Memristor and phase-transition PINN support

The digest and registry support the use of synthetic memristive or
phase-transition benchmarks to test inverse workflows under sparse terminal
observations. For this repository, the relevant claim is algorithmic: whether a
reduced thermal dissipation parameter can be identified in a controlled
synthetic digital twin.

### Thermal-parameter inversion support

Thermal inverse problems commonly require priors, independent calibration, or
reduced target spaces because terminal observables mix heat generation,
transport, switching kinetics, and conductivity response. This supports the
current design: `gamma_sub` is the only primary inverse parameter, while
`T_sw`, `tau_m`, `sigma_on0`, and `eta_A` are treated as bounded confounders.

## Evidence From Current Repository

Prior audits showed:

- Port-only full hidden-field recovery is underdetermined.
- Single-parameter `gamma_sub` inversion is stable when microscopic and
  switching parameters are fixed.
- Confounding is real: `T_sw` is the strongest sensitivity driver, while
  `sigma_on0` and `tau_m` have response directions close to `gamma_sub`.

The constrained inversion therefore tests a literature-guided reduced inverse
problem, not a broad full-field or unconstrained multi-parameter inverse claim.

## Synthetic Benchmark Assumptions

- Ground Truth v1.1 is synthetic numerical digital-twin data.
- Parameter values are literature-guided and engineering priors, not measured
  device parameters.
- `gamma_sub` represents an effective substrate or environmental heat-loss
  coefficient in the model, not a directly measured material constant.
- Stability conclusions apply only under the tested frozen benchmark,
  observation protocol, noise levels, and bounded confounder priors.
