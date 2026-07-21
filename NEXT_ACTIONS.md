# Next Actions

## Authoritative Current Queue

Exactly one bottleneck is active:
`Q2_M40_QIU_VO2_REAL_DEVICE_2D_BRIDGE_E0`. The constrained `gamma_sub`
result remains the safe rank-1 synthetic inverse mainline and is unchanged.

### Priority M40 - Qiu VO2 conservative 2D E0

Lock the Qiu main/SI hashes, reported and fitted quantities, unresolved local
2D parameters, nominal smoke protocol, withheld future curve, equations,
implementation, and fixed E0 thresholds in a separate preregistration commit.
Then execute the formal verifier exactly once.

Execution order:

1. pass source/hash, geometry, constitutive, interface, and fail-closed tests;
2. create the independent preregistration commit without formal results;
3. run manufactured, layered, contact/TBR, substrate-tamper, current/energy,
   three-mesh, reduced-limit, and nominal Qiu smoke checks;
4. update evidence and authorize M41 only if every hard gate passes.

### Locked boundaries

- **Full PINN:** M33/M34 and earlier trained paths remain
  `failed_but_informative`; no neural run is authorized.
- **Public VO2:** M35/M36 remain failed. M37R nominal window parity passes,
  but perturbation topology fails before geometry. No M38 or fit is active.
- **M40:** no inverse, PINN, fit, parameter search, M38, Zhang sealed 13 V,
  `gamma_eff`, or real-device-calibrated wording.
- **Other routes:** SID/EC-OQ, CPCF/CEBA/SCIS, N1-N3/SC-LOS, latent heat,
  solver rescue, public parameter search, and new UQ remain inactive.

## Non-negotiable boundaries

No frozen-GT edits, 13 V access, post-hoc gate relaxation, hidden failures,
synthetic-as-experimental wording, solver/PINN attribution mixing, or novelty
claims for standard FVM, SVD/Fisher, event, mixed, or ALM components.
