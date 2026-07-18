# Active Phase

Active phase ID: `D_PUBLIC_MULTIVOLTAGE_PREREGISTRATION`

## Objective

Preregister a provenance-locked public `9/11/15/17 V` repository-side fit while retaining sealed `13 V` for a later repository-withheld, preregistered cross-voltage evaluation. The constrained `gamma_sub` result remains the safe mainline. This phase prepares the contract only; it does not authorize fitting, 13 V access, or neural training/search. Complete PINN remains mandatory architecture, while trained full-PINN claims remain unsupported.

## Evidence routing

| Block | Status and boundary |
| --- | --- |
| D0a | `failed_but_informative`; convergence fails; D0b-D0d/13 V blocked. |
| N0 v1-v3r | `failed_but_informative`; trained fidelity fails; optimizer route stopped. |
| M33/M34 | M33 training is `failed_but_informative`. M34 finds a material optimizer-semantics defect but fails its stricter gradient-parity preflight, so no corrected run is authorized. M33-v1 is permanently closed; no neural search is active. |
| SID/EC-OQ | `failed_but_informative`; numerical/geometry gates fail; inactive. |
| CPCF | frontier `forbidden`; immutable non-voting diagnostic. |
| CEBA | parity `supported`; boundary `failed_but_informative`; no bracket, and its truth-dependent abstention is not deployable. |
| Figure 5 | bundled performance `qualified_supported`; isolated protocol gain/optimality `forbidden`. |
| SCIS | `failed_but_informative`; nominal coverage `0.93233`, but `2 K` mismatch acceptance `1.0` with point success `0.0`. |
| N1-N3 / SC-LOS | not run; positive claims `forbidden`. |

Current report: `docs/codex_reports/m34_optimization_and_ledger_contract_audit.md`; historical detail is routed by the evidence index.

## Single bottleneck

Define the public-data preregistration before any fit: provenance and licenses; public voltage-curve identifiers; source-paper reproduction versus repository-side refit roles; fixed preprocessing; 9/11/15/17 V fit/calibration partition; multistart and complete-trace metrics; solver step convergence; operational thresholds; failure handling; and a cryptographic fit lock that keeps 13 V inaccessible until all choices are frozen. The next action is preregistration, not fitting or neural repair.

## Forbidden claims

Full-PINN fidelity/inverse, quotient recovery, SID geometry, protocol rank/rotation, CPCF frontier, positive CEBA boundary, operational CEBA/SCIS refusal, isolated Figure 5 protocol gain, independent external or experimental validation, full hidden-field recovery, full STL reproduction, and universal Fourier/F-SPS superiority.
