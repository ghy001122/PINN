# Next actions

## Immediate next step

Use the v2a `gamma_sub` audit as the reduced inverse-problem branch while
keeping the hidden-field identifiability limitations explicit. Current
terminal-only observations do not uniquely identify all hidden fields, but they
can support a fixed-microphysics scalar inversion for `gamma_sub`.

## Recommended tasks

1. Add stronger thermal observability or auxiliary thermal constraints before
   claiming hidden temperature recovery.
2. Add or simulate spatially resolved evidence if defect-field recovery is a
   target claim.
3. Run a future joint-identifiability audit for `gamma_sub`, `T_sw`, and
   `tau_m` before claiming multi-parameter thermal-switching recovery.
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
