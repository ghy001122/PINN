# Status: completed

This task was implemented by `scripts\invert_gamma_sub_constrained.py` with
configuration `configs\gamma_sub_constrained_inversion.yaml`. The generated
lightweight evidence is stored in
`outputs\tables\gamma_sub_constrained_inversion_summary.json` and
`outputs\tables\gamma_sub_prior_width_sweep.csv`.

The key conclusion is conditional: nominal fixed-prior `gamma_sub` inversion is
stable, while `T_sw` is the most dangerous confounder.

---
# Next Task: Literature-Backed Constrained gamma_sub Inversion

This is the prepared next task. It is not executed by the local context
integration task.

## Objective

Complete the current paper-method loop by testing whether `gamma_sub` remains a
stable reduced inverse target when confounding parameters are bounded by
literature-guided or engineering priors.

## Scope

- `gamma_sub` is the only primary inverse parameter.
- `D_v0`, `mu_v0`, and other microscopic defect-transport parameters remain
  frozen.
- `T_sw`, `tau_m`, `sigma_on0`, and `eta_A` are used only for narrow prior-width
  or mismatch sweeps.
- Clean, 2 percent noise, and 5 percent noise cases should be evaluated.

## Expected Outputs

- `docs/literature_gamma_sub_evidence_chain.md`
- `docs/parameter_prior_registry.md`
- `scripts/invert_gamma_sub_constrained.py`
- `outputs/tables/gamma_sub_constrained_inversion_summary.json`
- `outputs/tables/gamma_sub_prior_width_sweep.csv`
- `docs/gamma_sub_constrained_inversion_report.md`
- `docs/codex_reports/gamma_sub_constrained_inversion_report.md`

## Required Questions

- Does literature-prior confinement make `gamma_sub` stable enough for the
  reduced inverse-problem paper narrative?
- Which confounder is most dangerous?
- At what prior width does `gamma_sub` inversion become unstable?
- Does the result support moving to a gamma_sub-PINN with physics-constrained
  sigma closure?

## Boundaries

Do not modify frozen Ground Truth v1.1. Do not present synthetic benchmark
evidence as experimental data. Do not start F-Pyramid, STL, observability, or
system-level extensions in this task.
