# Next actions

## Immediate next step

Use the `gamma_sub` branch only as a constrained reduced inverse problem. The
next implementation task remains literature-backed constrained `gamma_sub`
inversion. Start from `CODEX_CONTEXT.md` and
`docs\research_strategy\active_phase.md`, then follow
`docs\research_strategy\context_loading_policy.md`.

Before implementing the next inverse script, prepare or update:

- `docs\literature_gamma_sub_evidence_chain.md`
- `docs\parameter_prior_registry.md`
- `scripts\invert_gamma_sub_constrained.py`

## Recommended tasks

1. Add stronger thermal observability or auxiliary thermal constraints before
   claiming hidden temperature recovery.
2. Add or simulate spatially resolved evidence if defect-field recovery is a
   target claim.
3. Before implementing gamma_sub-PINN as a main method, decide whether
   `T_sw`, `tau_m`, `sigma_on0`, and `eta_A` are fixed priors or jointly
   estimated with explicit identifiability caveats.
4. Replace or further constrain the direct `sigma` surrogate with a
   differentiable conductivity relation tied to `c_v`, `delta_T`, and `m`.
5. Test sparse-observation sensitivity by varying the number of terminal
   observations in `obs_triangle_sparse.npz`.
6. Keep the paper narrative explicit: port-only inversion diagnoses
   conductance-level dynamics but does not prove unique hidden-field recovery.
7. Keep all generated datasets and figures reproducible through scripts rather
   than committing large binary artifacts.

## Do not do next

- Do not modify frozen Ground Truth v1.1 acceptance configs or metrics.
- Do not describe synthetic numerical benchmark outputs as experimental data.
- Do not add paper claims before the inverse method is quantitatively audited.
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
