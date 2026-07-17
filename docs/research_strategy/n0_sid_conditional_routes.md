# N0/SID conditional route register

This register is conditional and authorizes no experiment beyond the v3r optimizer replay and solver-first SID/EC-OQ discovery map.

1. `quotient_goal_dwr_pinn`: eligible only if SID/EC-OQ passes. Compare uniform, residual-adaptive, and quotient-QoI DWR sampling under matched compute. Stop if quotient error per compute does not improve.
2. `conditional_quotient_inverse_with_abstention`: eligible only after full-PINN forward and independent-solver sensitivity fidelity pass. Conservation, OOD, and numerical-rank abstention are mandatory; unsupported raw-parameter recovery remains forbidden.
3. `quotient_collapse_group_holdout`: solver-first leave-one-protocol and leave-one-geometry splits only. Random point splits cannot support protocol/geometry generalization.
4. `external_defect_hypotheses`: only an external holdout with a localized model-defect signature can activate them, one at a time: H1 branch memory, H2 latent-heat enthalpy, then H3 field-dependent conductivity plus differentiable implicit current root. No multi-mechanism bundle is allowed.

If event/protocol subspace evidence is absent, return to the supported calibration-gated constrained rank-1 `gamma_sub` manuscript line. If event/protocol evidence exists without three-protocol training-geometry evidence, delete SID and retain only EC-OQ as a candidate. If neither exists, delete both labels rather than renaming the negative result.
