# Codex Context

This file is the first-read context for non-trivial Codex work in this repository. It is intentionally compact. Do not load the full project history by default.

## Active Phase

Current phase:

`conservative multidomain OASIS-PINN v8 evidence actualization`

The constrained reduced `gamma_sub` manuscript line is now locked around calibration-gated sparse-port inversion: T_sw calibration tolerance, calibration-vs-protocol disentanglement, ODE-backed calibrated protocol robustness, external-curve no-fabrication handling, and final figure/table/claim routing. The strongest claim remains conditional `gamma_sub` recovery under fixed or tightly bounded priors in a one-dimensional synthetic numerical digital-twin benchmark.

F-SPS-PINN evidence remains appendix or future-work material, not the main performance claim.

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
- The constrained inversion, paper-readiness, and continuous-refinement audits support `gamma_sub` only as a reduced inverse target under fixed or tightly bounded priors.
- The observability-augmented gamma_sub audit shows that sparse temperature anchors alone did not reduce the wide `T_sw` mismatch bias in the current candidate-grid setup, while a narrowed `T_sw` prior reduced the gamma relative error from `1.2222222222222223` to `0.2222222222222222`.
- The T_sw confounding phase-map audit separates calibration-error amplitude from residual prior width and maps recoverable `gamma_sub` regions; 27 of 42 official cells meet relative error <= 0.1 and 32 meet <= 0.2.
- The auxiliary observability sweep shows that synthetic sparse/dense T, T-derivative, m, and sigma proxies did not recover the wide T_sw mismatch case; only calibrated T_sw reached the recovery thresholds in the official sweep.
- The multi-protocol/profile-likelihood validation pack adds 48-case multi-protocol recoverability, a `gamma_sub` by `T_sw` objective landscape with condition number `10.762998753222757`, a joint-inversion boundary audit where `T_sw + tau_m` is most ambiguous and `sigma_on0` gives the worst gamma error, and a protocol observability design preflight that ranks `multi_pulse` highest by distinguishability while recommending `long_pulse` and `short_pulse` under the configured cosine threshold.
- F-SPS-PINN architecture MVP, v2 smoke training, v2 small-run baseline, v2 phase-transition stress preflight, and v2 Fourier ablation are complete as method-development evidence, not main performance conclusions.
- The literature-anchored calibration and simulator-backed protocol validation pack adds parameter sanity checks, a no-fabrication external-curve template, T_sw calibration-necessity evidence, and ODE-backed sequential protocol validation; it keeps T_sw as the dominant claim boundary.
- Conservative multidomain OASIS-PINN v8 adds a conservative multilayer P0 pass and finite multidomain component smoke, but active terminal rescue, 2D full-field recovery, full STL-PINN reproduction, LoRA-STL, and universal F-SPS/Fourier superiority remain unsupported.

## Current Claim Boundary

Allowed claim:

Under literature-guided micro-kinetic priors and constrained confounding parameters, `gamma_sub` is a more identifiable reduced inverse target than full hidden-field reconstruction from purely electrical terminal data. The defensible manuscript line is identifiability-guided target-space reduction in a one-dimensional synthetic numerical digital-twin benchmark.

Disallowed claims:

- Port-only observations uniquely recover all hidden fields.
- The current benchmark is experimental data.
- Current `gamma_sub` inversion proves device-level thermal parameters without prior constraints.
- Small-run, stress-preflight, or Fourier-ablation F-SPS-PINN results prove performance superiority.
- F-SPS-PINN is the current main paper result unless a separate method paper is explicitly opened.

## Deferred Extensions

The following are deferred method enhancements, not current tasks unless `docs/research_strategy/active_phase.md` explicitly authorizes them:

- gamma_sub-PINN implementation
- stiff transfer learning or continuation training
- observability-augmented full-field recovery or experimental sparse temperature/state extension
- NeuroSPICE, NeuroPINN, or system-level mapping
- a separate F-SPS-PINN method paper

## Phase-Change Architecture Blueprint

Read `docs/research_strategy/phase_change_pinn_sci_sprint_blueprint.md` only for phase-change, VO2, F-SPS-PINN, or related architecture-refactoring tasks. It is a planning guide, not an experimental result report.

## Operating Defaults

- In this Windows workspace, do not use `apply_patch`; it can trigger the known
  Codex sandbox helper popup. Use concise Python/PowerShell edits inside the
  workspace instead.
- Matplotlib/pyparsing deprecation warnings from pinned third-party packages are
  globally filtered in `pyproject.toml`. When tests pass, do not spend tokens
  re-analyzing or re-reporting these known external warnings.
- Prefer `.\.venv\Scripts\python.exe` for validation commands when available.

## Low-Token First Read

For any non-trivial future task, read only:

1. `CODEX_CONTEXT.md`
2. `docs/research_strategy/active_phase.md`

Then follow `docs/research_strategy/context_loading_policy.md` for additional context. Never load all long context by default. Future long-context reads must be justified by the active task.
