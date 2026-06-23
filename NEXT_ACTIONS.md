# Next actions

## Immediate next step

Use the identifiability audit to redesign observability before further PINN
tuning. Current terminal-only observations constrain integrated conductance but
do not uniquely identify `delta_T`, `c_v`, `m`, and `sigma`.

## Recommended tasks

1. Add stronger thermal observability or auxiliary thermal constraints before
   claiming hidden temperature recovery.
2. Add or simulate spatially resolved evidence if defect-field recovery is a
   target claim.
3. Replace or further constrain the direct `sigma` surrogate with a
   differentiable conductivity relation tied to `c_v`, `delta_T`, and `m`.
4. Test sparse-observation sensitivity by varying the number of terminal
   observations in `obs_triangle_sparse.npz`.
5. Keep the paper narrative explicit: port-only inversion diagnoses
   conductance-level dynamics but does not prove unique hidden-field recovery.
6. Keep all generated datasets and figures reproducible through scripts rather
   than committing large binary artifacts.

## Do not do next

- Do not modify frozen Ground Truth v1.1 acceptance configs or metrics.
- Do not describe synthetic numerical benchmark outputs as experimental data.
- Do not add paper claims before the inverse method is quantitatively audited.
