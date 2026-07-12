# Active Phase

## Current Phase

`phase-activated multidomain OASIS-PINN v9 evidence actualization`

The current phase activates the conservative multidomain OASIS-PINN branch after v8 exposed non-degenerate-physics gaps. It does not revise frozen Ground Truth v1.1 and does not replace the main manuscript line: calibration-gated constrained `gamma_sub` inversion remains the safest SCI core claim.

## Evidence Added Or Corrected

- P0 phase-activated multilayer forward now uses SnSe as a low-`k`, high-`sigma` barrier prior, material-family-specific VO2/NbO2/generic kernels, independent per-interface `Rc/Rth`, coupled y-z lateral conduction, and activation gates.
- Official P0 activation rates: VO2 `0.8888888888888888`, NbO2 `0.8888888888888888`; P0 activation gate `True`.
- P0 median response: max delta T `15.140535460408756`, delta m `0.7834880687603829`, conductance ratio `2.561625048607053`; manufactured/refinement checks pass `True` / `True`.
- P1 multidomain OASIS small training now uses an activated simulator case, non-identity interface mortar loss, and monolithic/ordered/hard-BC/full-mortar variants. Full mortar success `True`; P1 gate `True`.
- P2 active terminal inverse v2 uses full `I(t), G(t), Vdev(t)` traces from activated cases. The best protocol is `combined_d_optimal` and all block Jacobian rank/condition gates pass `True`, but strict sequential block-error gate is `False`; status `failed_but_informative`.
- P3 2D recovery remains `blocked` because `blocked_until_actual_electrode_BC_multi_terminal_yz_solver_is_implemented`.
- P4 STL/Fourier remains blocked on activated PDE because canonical Seiler reproduction, front-aligned LoRA transfer, and matched-budget activated-PDE Fourier/F-SPS are not implemented.

## Claim Boundary

Allowed: synthetic numerical digital-twin evidence that v9 fixes non-degenerate activation for the reduced multilayer stack, enables small-budget multidomain OASIS training, and improves terminal-trace parameter sensitivity under activated cases.

Qualified/limited: P2 terminal inverse has strong Jacobian rank evidence and low total median error, but strict block-wise sequential recovery is not fully supported.

Forbidden: experimental validation, full FEM/device-grade reproduction, terminal-only arbitrary full-field recovery, full STL-PINN reproduction, LoRA-STL implementation, universal Fourier/F-SPS superiority, or replacing the constrained `gamma_sub` manuscript core with OASIS-PINN claims.
