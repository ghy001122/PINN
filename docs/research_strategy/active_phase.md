# Active Phase

Active phase ID: `D_PUBLIC_SOLVER_CONVERGENCE_RESOLUTION`

## Objective

Resolve the numerical full-waveform convergence blocker exposed by M35 using only the already-open public `9/11/15/17 V` source-model contract. M35 D-PREG remains immutable and D-FIT remains a failed, informative stop. This phase does not authorize repository fitting, 13 V access, neural training/search, or a change to the safe constrained `gamma_sub` mainline. Complete PINN remains mandatory architecture, while trained full-PINN claims remain unsupported.

## Evidence routing

| Block | Status and boundary |
| --- | --- |
| D0a | `failed_but_informative`; source/SI parity passes but the historical convergence metric is `0.163148 > 0.01`. |
| M35 D-PREG | `supported` protocol/provenance lock; `21/21` checks pass, 13 V remains metadata-only and sealed. |
| M35 D-FIT | `failed_but_informative`; all open voltages fail the locked 5 ns versus 2.5 ns current/voltage NRMSE gates. Event class, frequency, charge, and energy checks pass, but no Jacobian, fit, multistart, or fit lock was produced. |
| N0 v1-v3r | `failed_but_informative`; trained fidelity fails; optimizer route stopped. |
| M33/M34 | M33 training is `failed_but_informative`. M34's preregistered authorization gate failed. M34-A finds stable parity in `32/32` post-hoc directions, does not support an autograd error, and cannot authorize training. |
| SID/EC-OQ | `failed_but_informative`; numerical/geometry gates fail; inactive. |
| CPCF | frontier `forbidden`; immutable non-voting diagnostic. |
| CEBA | parity `supported`; boundary `failed_but_informative`; no bracket, and its truth-dependent abstention is not deployable. |
| Figure 5 | bundled performance `qualified_supported`; isolated protocol gain/optimality `forbidden`. |
| SCIS | `failed_but_informative`; nominal coverage `0.93233`, but `2 K` mismatch acceptance `1.0` with point success `0.0`. |
| N1-N3 / SC-LOS | not run; positive claims `forbidden`. |

Current report: `docs/codex_reports/m35_public_multivoltage_fit_and_gradient_amendment.md`; historical detail is routed by the evidence index.

## Single bottleneck

Preregister one solver-only resolution audit that separates (a) near-zero Q95-Q05 normalization at quiescent 9/17 V from (b) accumulated event-time/phase error at oscillatory 11/15 V. Compare finer fixed steps with an independent event-resolved/adaptive reference and lock instrument-scale absolute floors before inspecting the new solver results. Raw-time full-waveform convergence remains mandatory; event alignment is diagnostic only. Stop again without fitting if the numerical gate fails.

## Forbidden claims

Completed public VO2 refit, valid fit lock, 13 V cross-voltage evaluation, independent external or project-generated experimental validation, `S_e` validation of frozen-model `gamma_sub`, full-PINN fidelity/inverse, quotient recovery, SID geometry, protocol rank/rotation, CPCF frontier, positive CEBA boundary, operational CEBA/SCIS refusal, isolated Figure 5 protocol gain, full hidden-field recovery, full STL reproduction, and universal Fourier/F-SPS superiority.
