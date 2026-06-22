# Next actions

## Immediate next step

Move from PINN inverse v1 to a stronger v1.1 physics closure focused on thermal
identifiability and sigma closure. The current v1 confirms the training path but
does not yet reduce `delta_T` error.

## Recommended tasks

1. Replace or further constrain the direct `sigma` surrogate with a
   differentiable conductivity relation tied to `c_v`, `delta_T`, and `m`.
2. Strengthen the thermal residual and scaling so `delta_T` is identifiable
   beyond field anchors.
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
