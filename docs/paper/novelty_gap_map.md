# Novelty Gap Map

All results are synthetic numerical digital-twin benchmark evidence.

| Novelty axis | Current strength | Evidence | Gap | Action |
| --- | --- | --- | --- | --- |
| Identifiability-guided target reduction | Strong | `pinn_identifiability`, `gamma_sub` constrained inversion, confounding audits | Needs concise manuscript narrative | Keep as main innovation. |
| Calibration-gated `gamma_sub` inversion | Strong but conditional | T_sw tolerance, ODE spot-check, protocol disentanglement | Must state fixed/tightly bounded priors | Use as main result. |
| Phase-transition stiffness defense | Moderate supplementary | `phase_transition_stiffness_continuation_audit`: cliff ratio `11.9`; all finite `True` | Not full STL; Fourier gain not uniform | Use as reviewer-defense appendix. |
| Phase-field inverse literature alignment | Moderate supplementary | `phase_field_inverse_alignment_smoke`: median M relative error `0.04331`; success rate `0.815` | Full-field anchors only; not sparse-port | Use in related-work alignment. |
| F-SPS-PINN performance | Weak | Small-run and medium-budget tests finite but not superior | Needs controlled larger ablations | Keep future-work/appendix only. |
| Experimental validation | Absent | No provenance-backed curves or measured device data | Blocks stronger device claims | Do not claim. |

## Practical Gap Closure

The immediate paper-strengthening route is not to add another large model. It is to assemble figures/tables around the locked `gamma_sub` evidence, use stiffness/phase-field work as supplementary defense, and keep limitations explicit.
