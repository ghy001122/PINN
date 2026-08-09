# Active Phase

Active phase ID: `Q2_PHASE1B_MF_GEOSTATE_2P5D_PINN_FASTTRACK`

Status: `stopped_after_valid_idea_screen_no_go`

Current checkpoint: `Q2_MF_GEOSTATE_MC_PINN_FASTTRACK_V1_VALID_NO_GO`

## Task Contract

- Objective/manuscript destination: determine whether a sparse-anchor,
  interface-resolved mixed-conservative hybrid PINN is worth a formal OOD
  campaign for `state-conditioned quasi-static electrothermal fields`.
- Inputs: the Qiu-inspired 100 nm by 500 nm coplanar geometry, source-traceable
  device-effective VO2 closure, and existing conservative x-y FVM operators.
- Outputs: six model-form runs, one selected reference, twelve complete-case
  fields, actual B0/B1/M0 training, numeric tables, five figures, and one report.
- Allowed scope: a versioned fixed-voltage M0/M1/M2 reference adapter, a new
  GeoState mixed PINN path, one config-driven runner, and one focused test file.
- Prohibited: Frozen GT edits; current-clamp/BranchConserve/NLS/equivalence
  reruns; threshold movement; inverse, MoE, dynamic RC, NbO2, or formal OOD.
- Success gate: the frozen model-form ledgers and engineering-screen metrics in
  `configs/q2_mf_geostate_mc_pinn_fasttrack_v1.yaml` pass without search.
- Failure route: `NO_GO_MODEL_FORM_REFERENCE` blocks training; otherwise a
  non-improving M0/sole homotopy M1 ends as `NO_GO_GEOSTATE_PINN_IDEA_SCREEN`.
- Budget: M0/M1/M2 times C0/C1 only, twelve pilot cases, seed `20260809`, at
  most 1500 Adam steps and 30 minutes per network, and one training rescue.

## Frozen Scientific Premise

The reference solves steady in-plane sheet current and areal energy balance.
M0 uses ideal electrodes and a local vertical sink; M1 adds electrical and
thermal contact Robin closures; M2 adds one passive 2D effective substrate
temperature field. The conductive state is a deterministic branch-conditioned
white-box closure, not a learned or measured phase fraction.

The PINN inputs are normalized x-y coordinates, device voltage, branch/protocol
metadata, electrode/sink signed distances, region features, and sink amplitude;
outputs are phi, T, Jx, Jy, qx, and qy. Fixed nondimensional anchor, strong-form,
mixed constitutive/conservation, interface, port, and ledger loss groups are
used with hard electrode Dirichlet lifting.

## Claim Boundary And Preserved History

Implementation facts may become `supported`; a selected reduced reference is
at most `qualified_supported`; this one-seed run is diagnostic/non-voting.
Formal PINN superiority, experimental validation, stable-branch physics, and
inverse recovery remain `forbidden`.

`NO_GO_CC_B_STABLE_PATTERNED_TRANSITION_SPAN`, all 34 positive-unstable L1
records, PR #29-#36 stops, dynamic/controller stops, D0, equivalence-v1/v2/v3,
and Frozen GT are immutable and are not rerun or reinterpreted by this phase.

## Executed Outcome And Stop

All six model-form runs passed the frozen residual and ledger gates. Correct
width-normalized resolved-hotspot selection chose M1; M0 missed the C1 hotspot
gate (`0.10 W > 0.05 W`), while M1 differed from M2 by at most `0.0497%` in
current and `0.00139 K` in Tmax. Twelve complete cases and two one-level
sentinel refinements were valid.

B0/B1/M0 each completed 1000 Adam steps at seed `20260809`. M0 improved the
mean joint field score over B0 by `55.37%`, but its mean T relative L2 was
`0.21194`, energy error `0.14167`, and interface-flux mismatch `0.74008`; zero
test cases passed. The near-transition concentration ratio `1.0727` did not
authorize M1 homotopy. Final disposition:

```text
NO_GO_GEOSTATE_PINN_IDEA_SCREEN
validity = valid
claim_status = failed_but_informative
scientific_vote = false
```

Do not start formal OOD or a second rescue. Preserve this result as an
interface/ledger physics-optimization limitation.
