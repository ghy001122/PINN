# Codex Context

This file is the first-read context for non-trivial Codex work in this repository. It is intentionally compact. Do not load the full project history by default.

## Active Phase

Current phase:

`F-SPS-PINN v2 small-run baseline`

The constrained reduced `gamma_sub` inversion stage is complete. The F-SPS-PINN architecture MVP and v2 smoke training pipeline are complete. The active work is a bounded small-run synthetic numerical baseline comparing a free `log_sigma` conductivity shortcut with the white-box `vo2_sigma(T, c_v, m)` closure, without replacing existing v0/v1/v1.1 paths or modifying frozen Ground Truth v1.1.

## Project Boundary

All Ground Truth and PINN outputs in this repository are synthetic numerical digital-twin benchmark results. They are not experimental measurements.

Do not modify frozen Ground Truth v1.1 files unless the user explicitly opens a new Ground Truth revision:

- `configs/gt_v1_acceptance_triangle.yaml`
- `configs/gt_v1_acceptance_ltp_ltd.yaml`
- `docs/gt_v1_acceptance_report.md`
- `data/processed/gt_v1_acceptance/manifest.json`
- frozen GT v1.1 data files under `data/processed/gt_v1_acceptance/`
- Ground Truth equations and default parameters

## Completed Evidence Chain

- Ground Truth v1.1 is frozen as a synthetic Nb/NbOx/V2O5/Ni-inspired benchmark.
- PINN inverse v0 established the training loop and showed field-anchor dependence.
- PINN inverse v1 and v1.1 added approximate physics regularization, but `delta_T` remained a dominant error source.
- The identifiability audit showed that terminal `V(t)`, `I(t)`, and `G(t)` constrain conductance-level response but do not uniquely recover `delta_T`, `c_v`, `m`, and `sigma`.
- The `gamma_sub` identifiability audit showed stable single-parameter recovery when micro-kinetic parameters are fixed.
- The `gamma_sub` confounding audit showed that `T_sw`, `tau_m`, `sigma_on0`, and `eta_A` can bias `gamma_sub` unless constrained by priors.
- F-SPS-PINN architecture MVP and v2 smoke training are complete as method-development evidence, not performance conclusions.

## Current Claim Boundary

Allowed claim:

Under literature-guided micro-kinetic priors and constrained confounding parameters, `gamma_sub` is a more identifiable reduced inverse target than full hidden-field reconstruction from purely electrical terminal data. F-SPS-PINN v2 is currently a synthetic method-development baseline for comparing conductivity closures.

Disallowed claims:

- Port-only observations uniquely recover all hidden fields.
- The current benchmark is experimental data.
- Current `gamma_sub` inversion proves device-level thermal parameters without prior constraints.
- Small-run F-SPS-PINN baselines prove performance superiority.

## Deferred Extensions

The following are deferred method enhancements, not current tasks unless `docs/research_strategy/active_phase.md` explicitly authorizes them:

- gamma_sub-PINN implementation
- stiff transfer learning or continuation training
- observability-augmented sparse temperature/state measurements
- NeuroSPICE, NeuroPINN, or system-level mapping

## Phase-Change Architecture Blueprint

Read `docs/research_strategy/phase_change_pinn_sci_sprint_blueprint.md` only for phase-change, VO2, F-SPS-PINN, or related architecture-refactoring tasks. It is a planning guide, not an experimental result report.

## Low-Token First Read

For any non-trivial future task, read only:

1. `CODEX_CONTEXT.md`
2. `docs/research_strategy/active_phase.md`

Then follow `docs/research_strategy/context_loading_policy.md` for additional context. Never load all long context by default. Future long-context reads must be justified by the active task.
