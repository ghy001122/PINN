# Next actions

## Immediate next step

Move from PINN inverse v1.1 to a targeted thermal-identifiability redesign. The
current v1.1 improves port-physics terminal fit but still does not reduce
`delta_T` error.

## Recommended tasks

1. Add stronger thermal observability or auxiliary thermal constraints before
   claiming hidden temperature recovery.
2. Replace or further constrain the direct `sigma` surrogate with a
   differentiable conductivity relation tied to `c_v`, `delta_T`, and `m`.
3. Test sparse-observation sensitivity by varying the number of terminal
   observations in `obs_triangle_sparse.npz`.
4. Add diagnostics for identifiability, especially whether multiple hidden
   fields can produce similar terminal `G(t)`.
5. Keep all generated datasets and figures reproducible through scripts rather
   than committing large binary artifacts.

## Do not do next

- Do not modify frozen Ground Truth v1.1 acceptance configs or metrics.
- Do not describe synthetic numerical benchmark outputs as experimental data.
- Do not add paper claims before the inverse method is quantitatively audited.
