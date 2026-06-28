# Next actions

## Immediate next step

Use the paper-readiness robustness pack plus the continuous off-grid `gamma_sub` refinement audit to frame a method-oriented SCI small paper around a one-dimensional reduced-order synthetic numerical digital-twin benchmark. The defensible main claim is constrained `gamma_sub` inversion under fixed or tightly bounded switching/conductivity priors, with simulator-backed scalar refinement for off-grid `gamma_sub`.

Primary evidence:

- `docs\paper\model_hierarchy_and_claim_boundary.md`
- `docs\paper\equation_variable_registry.md`
- `docs\paper\experiment_to_figure_mapping.md`
- `docs\gamma_sub_paper_readiness_report.md`
- `outputs\tables\gamma_sub_paper_readiness_summary.json`
- `outputs\tables\gamma_sub_observation_sensitivity.csv`
- `outputs\tables\gamma_sub_offgrid_summary.csv`
- `docs\gamma_sub_continuous_refinement_report.md`
- `outputs\tables\gamma_sub_continuous_refinement_summary.json`
- `outputs\tables\gamma_sub_continuous_refinement_cases.csv`

## Recommended tasks

1. Draft a method-and-results outline that explicitly labels all data as
   synthetic numerical digital-twin benchmark evidence.
2. Keep the main claim restricted to sparse-port identifiability and constrained
   `gamma_sub` inversion, with `T_sw` listed as the limiting confounder.
3. Decide whether to add only text-level reviewer defenses next, or explicitly
   authorize a later gamma_sub-PINN implementation.
4. If future method work is authorized, keep `gamma_sub` as the only primary
   inverse target and use a physics-constrained sigma closure.
5. Keep all generated datasets and figures reproducible through scripts rather
   than committing large binary artifacts.

## Do not do next

- Do not modify frozen Ground Truth v1.1 acceptance configs, data, metrics,
  manifest, equations, or default parameters.
- Do not describe synthetic numerical benchmark outputs as experimental data.
- Do not claim full 3D device simulation or sparse-port full hidden-field
  recovery.
- Do not start F-Pyramid, STL continuation, observability-augmented sparse
  temperature/state recovery, VO2-NbO2 oscillator work, NeuroSPICE/NeuroPINN,
  or system-level mapping unless explicitly authorized.

## Deferred Method Enhancements

Record these as future options, not current work:

- replace free `log_sigma` with physics-constrained sigma closure;
- implement gamma_sub-PINN;
- add F-Pyramid or multi-resolution Fourier features;
- add stiff transfer learning continuation;
- add observability-augmented sparse `T/m` extension.