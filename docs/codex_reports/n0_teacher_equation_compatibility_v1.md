# N0 Teacher–Equation Compatibility Audit v1

- Base commit: `583cb441687001c7df9a8ee9d4d5cf45258f8efb`
- Status: `repair_authorized`
- Manufactured checks: `True`
- Frozen FVM discrete conservation: `True`

## Core finding

The frozen FVM is internally conservative and the declared continuous equations pass manufactured tests, but full_pinn_architecture_v1 reverses the frozen electrical boundary orientation and its finite-band interface proxy is not the frozen FVM face law. A bounded exact-trace split-domain repair is authorized.

The frozen GT stores potential with the driven left electrode at `V(t)` and the right electrode at zero. The v1 single-network PINN imposes the opposite orientation while retaining `E=-dphi/dx` and a positive-voltage port operator. This reverses drift and local current signs relative to the teacher even though the scalar port operator remains positive.

The frozen `nx=31` material mask places its arithmetic-averaged interface face at `2.258064516e-08 m`, an offset of `5.806451613e-10 m` from the declared `L_int`. Exact continuum traces must therefore be scored with this discretization difference recorded, not hidden.

## Disposition

A bounded dual-domain repair with the corrected electrode orientation and exact one-sided interface traces is allowed. The audit does not change frozen GT, does not pass N0, and does not support interface novelty, sensitivity fidelity, or inverse claims.

Machine evidence: `outputs/tables/n0_teacher_equation_compatibility_v1.json`, `outputs/tables/n0_equation_parity_registry_v1.csv`, and `outputs/tables/n0_global_conservation_audit_v1.json`.
