# Q2 M1 protocol-manifold branch-aware surrogate MVE

- Evidence identity: `literature-guided synthetic numerical digital-twin evidence`.
- PR #42 is preserved as the immutable `GO_PROTOCOL_SELECTED_EQUILIBRIUM_MANIFOLD` reference; its ramps, gates, and interpretation were not changed.
- G2/G3 physical reference gate: `PASS_PROTOCOL_FACTORIAL_CONTEXT_REFERENCE`; G0/G1 were read and copied without rerunning their main ramps.
- G2/G3 each completed heating and cooling ramps with 33/33 valid coarse points. Their cooling events refined to `[1.078125, 1.081250] V` and `[0.837500, 0.840625] V`; both half-step checks reproduced the same interval within numerical precision.
- All 16 required new-context spectrum states were stable; none were unstable or indeterminate, and the frozen 20-state limit was respected.
- Split: 174 train coarse states, 24 fixed-index coarse validation states plus event confirmations, 66-point G1 diagnostic curve, and 10 unique spectrum-certified G1 headline states.
- Train-only POD rank: **2** at cumulative energy target 99.9%; G1 was excluded from POD, normalization, ridge, training, and checkpoint selection.
- Conditional seeds executed: **False**.
- Final disposition: **`NO_GO_PROTOCOL_MANIFOLD_NEURAL_VALUE`**.
- Focused validation: `10 passed`; a projection-current field-name defect was repaired before the valid training run, while the already completed G2/G3 ramps and spectra were rehydrated without another physical execution.

## Headline matched-budget metrics

| mode | seed | pass | mean joint | T-rise | phi | current | median time (s) |
|---|---:|---:|---:|---:|---:|---:|---:|
| A1 | 0 | 0/10 | 15.0325 | 30.0473 | 0.0177564 | 10.0879 | 0.00801735 |
| A2 | 0 | 0/10 | 11.5318 | 23.0457 | 0.0177978 | 10.1785 | 0.0155117 |
| R1 | 0 | 0/10 | 0.460089 | 0.907749 | 0.0124294 | 0.12796 | 0.0080607 |
| R2 | 0 | 0/10 | 0.324271 | 0.636634 | 0.0119072 | 0.13245 | 0.0162981 |
| H1 | 20260809 | 0/10 | 0.46778 | 0.917261 | 0.0182994 | 0.500346 | 0.0082698 |
| H2 | 20260809 | 0/10 | 0.394579 | 0.770985 | 0.0181737 | 0.497932 | 0.0163599 |
| S1 | 20260809 | 0/10 | 0.185618 | 0.354001 | 0.0172361 | 0.134504 | 0.00857195 |
| S2 | 20260809 | 2/10 | 0.146033 | 0.277368 | 0.014698 | 0.134219 | 0.0170328 |
| G1 | 20260809 | 0/10 | 0.192055 | 0.37027 | 0.0138401 | 0.161764 | 0.0085059 |
| G2 | 20260809 | 0/10 | 0.151681 | 0.290739 | 0.0126217 | 0.145849 | 0.0162742 |

## Branch selection and unknown-protocol behavior

- S1: branch gate `False`, certified head swaps 1, full-curve separation fraction 0.909; refusal gate `False`, certified recall 1.000, full-curve recall 1.000, set coverage 0.000.
- S2: branch gate `False`, certified head swaps 1, full-curve separation fraction 0.909; refusal gate `False`, certified recall 1.000, full-curve recall 1.000, set coverage 0.182.
- G1: branch gate `False`, certified head swaps 0, full-curve separation fraction 0.758; refusal gate `False`, certified recall 1.000, full-curve recall 1.000, set coverage 0.000.
- G2: branch gate `False`, certified head swaps 1, full-curve separation fraction 0.697; refusal gate `False`, certified recall 1.000, full-curve recall 1.000, set coverage 0.000.

The unknown-protocol interface returns explicit heating and cooling candidates when the predicted separation reaches the frozen ambiguity threshold; it never averages candidates and never exposes a root identifier.

## Claim boundary

This is a single- or conditional three-seed diagnostic MVE, not formal superiority. The supported implementation facts are the M1 conservative projection and explicit hard direction gate. Protocol-manifold and new-context physical evidence remain qualified within the frozen synthetic ideal voltage-clamp protocol. Full hysteresis, dynamic attractors, Qiu source-RC reproduction, experimental validation, formal PINN superiority, inverse inference, and zero-shot transfer remain forbidden.

## Artifacts

- Tables: `E:/Python demo/PINN/outputs/tables/q2_protocol_manifold_branch_aware_surrogate_mve_v1/Q2-PROTOCOL-MANIFOLD-BRANCH-AWARE-SURROGATE-MVE-20260810-V1`
- Figures: `E:/Python demo/PINN/outputs/figures/q2_protocol_manifold_branch_aware_surrogate_mve_v1/Q2-PROTOCOL-MANIFOLD-BRANCH-AWARE-SURROGATE-MVE-20260810-V1`
- Checkpoints: `E:/Python demo/PINN/outputs/checkpoints/q2_protocol_manifold_branch_aware_surrogate_mve_v1/Q2-PROTOCOL-MANIFOLD-BRANCH-AWARE-SURROGATE-MVE-20260810-V1/H_seed_20260809.pt, E:/Python demo/PINN/outputs/checkpoints/q2_protocol_manifold_branch_aware_surrogate_mve_v1/Q2-PROTOCOL-MANIFOLD-BRANCH-AWARE-SURROGATE-MVE-20260810-V1/S_seed_20260809.pt, E:/Python demo/PINN/outputs/checkpoints/q2_protocol_manifold_branch_aware_surrogate_mve_v1/Q2-PROTOCOL-MANIFOLD-BRANCH-AWARE-SURROGATE-MVE-20260810-V1/G_seed_20260809.pt`

## Next priority

No neural path survived the initial gate, so formal OOD and additional neural-forward architecture work are ineligible. Retain the conservative operator, four-context protocol data, and fixed ridge baseline as numerical assets; the next priority is a limitation/negative manuscript synthesis explaining why random-access finite-depth projection fails near protocol-selected branch components despite accurate train-manifold initialization.
