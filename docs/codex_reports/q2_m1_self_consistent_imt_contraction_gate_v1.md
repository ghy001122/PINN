# Q2 M1 self-consistent IMT contraction gate v1

## Conclusion

Disposition: `NO_GO_SINGLE_VALUED_IMT_FORWARD_MAP`.

The six bounded Stage A cases were actually solved from both ambient and 360 K initial fields. All 6/6 pairs were numerically valid, but only 1/6 satisfied the preregistered uniqueness gate. The fixed-parameter to steady-fixed-point solution relation is therefore not single-valued under the initialization-independent surrogate contract; the deterministic P_alpha(T) operator itself remains single-valued. Stage B/C and every neural stage are ineligible.

## Frozen PR #40

PR #40 head `a4a20a919dd4eca907269cf0aef351ecdb0c37b3` retained `NO_GO_M1_NEURAL_SPECIFIC_VALUE_A2_OR_RIDGE_DOMINATES` unchanged and was squash-merged as `22e3760f1505691f55d5d2366ca7659d7a7723a6` before this branch.

## Constitutive identity

The Qiu source contract gives beta `0.253` K^-1, loop width `7.193` K, and Tc0 `332.8` K. The resulting centres are `336.3965` K and `329.2035` K, with nominal tanh scale `3.952569169960474` K.
The modeled phase coordinate is an effective conductive-state coordinate, not a metallic volume fraction; no minor loop, reversal rule, or dynamic state is implemented.

## Voltage admission and uniqueness

| case | cold Tmean K | hot Tmean K | T-rise difference | current difference | unique |
|---|---:|---:|---:|---:|---:|
| heating_0.95V | 325.089 | 325.089 | 1.57308e-07 | 8.07118e-10 | True |
| heating_1.15V | 325.13 | 347.955 | 0.994331 | 0.994327 | False |
| heating_1.35V | 325.18 | 356.748 | 0.994336 | 0.994331 | False |
| cooling_0.95V | 325.16 | 340.765 | 0.989883 | 0.989875 | False |
| cooling_1.15V | 325.24 | 348.225 | 0.989678 | 0.989669 | False |
| cooling_1.35V | 325.342 | 356.753 | 0.989244 | 0.989234 | False |

Non-unique cases: `heating_1.15V, heating_1.35V, cooling_0.95V, cooling_1.15V, cooling_1.35V`.

## Contraction, A1/A2 and neural route

The contraction atlas, A1/A2 headroom vote, and conditional neural execution were not run because they require a valid single-valued Stage A map. Empty schema-bearing CSVs and explicitly labelled not-executed figures preserve this prerequisite failure without fabricating contraction data.

## Claim boundary

Evidence type: `literature-guided synthetic numerical digital-twin evidence`. The self-consistent implementation is a supported implementation fact after focused validation; the bounded multi-fixed-point result is `failed_but_informative`. Unique-atlas, contraction, neural-value, full-hysteresis, dynamic-stability, experimental-validation, Qiu-quantitative-reproduction, formal-superiority, inverse, and transfer claims remain forbidden or unassessed as recorded in `docs/paper/q2_pinn_route_evidence_map_after_imt_gate.md`.

## Artifacts and validation

- Tables: `outputs/tables/q2_m1_self_consistent_imt_contraction_gate_v1/Q2-M1-SELF-CONSISTENT-IMT-CONTRACTION-GATE-20260810-V1`
- Fields: `data/processed/q2_m1_self_consistent_imt_contraction_gate_v1/Q2-M1-SELF-CONSISTENT-IMT-CONTRACTION-GATE-20260810-V1`
- Figures: `outputs/figures/q2_m1_self_consistent_imt_contraction_gate_v1/Q2-M1-SELF-CONSISTENT-IMT-CONTRACTION-GATE-20260810-V1`
- Focused test: `pytest -q tests/test_q2_m1_self_consistent_imt_contraction_gate_v1.py` -> `8 passed`.
- Base: `22e3760f1505691f55d5d2366ca7659d7a7723a6`.
- Branch: `codex/q2-m1-self-consistent-imt-contraction-gate-v1`.
- Final commit, push, and draft-PR identity are recorded in the final handoff because a commit cannot contain its own SHA.

## Next priority

Resolve or explicitly accept the physical multi-valued major-branch forward relation before any surrogate question is meaningful; under the present contract, stop neural-forward work and use the cold/hot branch separation as limitation-manuscript evidence.
