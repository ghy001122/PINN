# Active Phase

Active phase ID: `Q2_PHASE1C_M1_ROBIN_CONTROL_VOLUME_PINN_RESCUE`

Status: `stopped_after_valid_structural_rescue_no_go`

Current checkpoint: `Q2_M1_ROBIN_CONTROL_VOLUME_PINN_RESCUE_V1_VALID_NO_GO`

## Task Contract

- Objective/manuscript destination: test the only authorized structural rescue
  after making the M1 teacher, Robin boundaries, subdomain traces,
  control-volume conservation, ports, ledgers, and evaluation isomorphic.
- Inputs: PR #37's frozen 12-case M1 data; no reference nonlinear solve rerun.
- Outputs: compatibility evidence, actual B0-R/B1-R/P0-RCV training, three
  checkpoints, complete test predictions, numeric tables, seven figures, and
  one report.
- Allowed scope: one versioned M1-consistent implementation and one focused
  test file, seed `20260809`, float64, fixed 5% phi/T anchors, and 1500 Adam
  steps per model.
- Prohibited: Frozen GT edits; current-clamp/BranchConserve/NLS/equivalence
  reruns; threshold movement; inverse, MoE, dynamic RC, NbO2, or formal OOD.
- Success gate and routing are frozen in
  `configs/q2_m1_robin_control_volume_pinn_rescue_v1.yaml`.
- Failure route: teacher incompatibility stops before training; otherwise the
  exact GO/PARTIAL-GO/NO-GO test-case rules bind without threshold movement.

## Frozen Scientific Premise

The scientific object remains phase-state-conditioned quasi-static
electrothermal fields. M1 uses finite external electrical contact resistance,
contact-corrected vertical thermal conductance, contact/bare in-plane thermal
conductance differences, localized sink, and prescribed state-conditioned
conductivity. Branch and state are protocol/state metadata, not dynamics.

All models use one shared trunk and three explicit static-region heads. B0-R is
phi/T data-only, B1-R derives fluxes and applies per-region strong form, and
P0-RCV predicts phi/T/J/q with first-order constitutive and locked weak-CV
losses. M0 terminal hard lifting and legacy `np.gradient` flux anchors are absent.

## Claim Boundary And Preserved History

Implementation facts may become `supported`; a selected reduced reference is
at most `qualified_supported`; this one-seed run is diagnostic/non-voting.
Formal PINN superiority, experimental validation, stable-branch physics, and
inverse recovery remain `forbidden`.

PR #37 at `c4ccd7a995fbd4027d92a10fcbf42b1e14906092` is the immutable
`NO_GO_GEOSTATE_PINN_IDEA_SCREEN` baseline and was squash-merged unchanged as
`183f129545a2a047137745d36a0c432d02a28219`. All earlier stops, dynamic work,
equivalence evidence, and Frozen GT remain immutable.

## Executed Outcome And Stop

Discrete teacher/objective compatibility passed all 12 cases. Worst normalized
current/energy P95 were `7.287e-15` and `9.332e-8`; worst Robin/interface and
both global ledgers were below `1.392e-9`. No implementation repair or reference
nonlinear solve was used.

B0-R/B1-R/P0-RCV each completed exactly 1500 steps. Their mean test T-rise / phi
/ current / energy / interface / current-CV / energy-CV metrics were:
`0.2062/0.0413/35.9296/0.7714/1.2963/0.2670/31.5428`,
`0.9444/0.2645/0.8965/0.9995/0.1036/0.000075/0.0946`, and
`0.6193/0.1829/0.8914/0.8736/0.1029/0.0050/0.9470`. Each passed 0/2 test cases.
Final disposition:

```text
NO_GO_M1_RCV_PINN_RESCUE
validity = valid
claim_status = failed_but_informative
scientific_vote = false
```

Do not start formal OOD or another direct coordinate-PINN rescue. The single
next priority is a preregistration for a solver-projected conservative surrogate;
execution requires separate authorization.
