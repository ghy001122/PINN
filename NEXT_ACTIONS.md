# Next actions

## Immediate next step

Review the constrained `gamma_sub` inversion evidence before opening any new
method work. The current conclusion is conditional: nominal fixed-prior
`gamma_sub` inversion is stable, but `T_sw` is the most dangerous confounder and
must be fixed, independently calibrated, or tightly bounded.

Primary evidence:

- `docs\gamma_sub_constrained_inversion_report.md`
- `docs\parameter_prior_registry.md`
- `docs\literature_gamma_sub_evidence_chain.md`
- `outputs\tables\gamma_sub_constrained_inversion_summary.json`
- `outputs\tables\gamma_sub_prior_width_sweep.csv`

## Recommended tasks

1. Decide whether the paper's main inverse claim is restricted to fixed or
   independently calibrated `T_sw`.
2. If authorized, implement a gamma_sub-PINN that keeps `gamma_sub` as the only
   primary inverse target and uses a physics-constrained sigma closure.
3. Add stronger thermal observability or auxiliary thermal constraints before
   claiming hidden temperature recovery.
4. Add or simulate spatially resolved evidence if defect-field recovery is a
   target claim.
5. Test sparse-observation sensitivity by varying the number of terminal
   observations in `obs_triangle_sparse.npz`.
6. Keep the paper narrative explicit: port-only inversion diagnoses
   conductance-level dynamics but does not prove unique hidden-field recovery.
7. Keep all generated datasets and figures reproducible through scripts rather
   than committing large binary artifacts.

## Do not do next

- Do not modify frozen Ground Truth v1.1 acceptance configs or metrics.
- Do not describe synthetic numerical benchmark outputs as experimental data.
- Do not add paper claims before the reduced inverse method is quantitatively
  bounded by priors.
- Do not start F-Pyramid, STL continuation, observability-augmented sparse
  temperature/state recovery, NeuroSPICE/NeuroPINN, or system-level mapping
  unless `docs\research_strategy\active_phase.md` is explicitly updated.

## Deferred Method Enhancements

Record these as future options, not current work:

- replace free `log_sigma` with physics-constrained sigma closure;
- implement gamma_sub-PINN;
- add F-Pyramid or multi-resolution Fourier features;
- add stiff transfer learning continuation;
- add observability-augmented sparse `T/m` extension.
