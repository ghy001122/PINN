# Next actions

## Immediate next step

Move from PINN inverse v0 proof-of-concept toward PINN inverse v0.1 or v1 with
a more physical differentiable closure for `sigma(x,t)` and stronger thermal
constraints.

## Recommended tasks

1. Replace or augment the direct `sigma` surrogate with a differentiable
   conductivity relation tied to `c_v`, `delta_T`, and `m`.
2. Add a light but explicit physics residual audit for temperature and state
   evolution without claiming full PDE-constrained performance prematurely.
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
