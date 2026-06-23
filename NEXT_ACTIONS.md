# Next actions

## Immediate next step

Use the `gamma_sub` branch only as a constrained reduced inverse problem. The
confounding audit shows that `gamma_sub` is stable under nominal fixed
microphysics, but mismatch in `T_sw`, `tau_m`, `sigma_on0`, or `eta_A` can
produce systematic bias.

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
