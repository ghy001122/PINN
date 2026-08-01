# Controller-v3 Goal Terminal Report

## Conclusion

`GOAL_UNSUCCESSFUL_CONTROLLER_V3_EXHAUSTED`

The two preregistered controller-v3 numerical policies were both rejected before any complete qualification run was published. Fresh S0, Phase 2, C01, C06, baselines, OOD evaluation, figures, and positive PINN manuscript evidence were not executed.

This is a valid bounded controller-qualification result. It is not an S2 physics PASS/FAIL and casts no scientific vote.

## Task Contract

- Base: `main@b28aa97ccbdbc1b03b43e8deb13b3bbc35c71ead`.
- Goal: qualify at most two controller-v3 policies; only then run fresh S0 and conditionally C01/C06.
- Frozen: S2 equations/parameters, protocols, scientific thresholds, controller-v2 inner full/two-half estimator, 63/60/3 plan, historical E0/S0/equivalence evidence, and Frozen GT v1.1.
- Controller budget: at most two numerical policies, 12 active hours, 48 CPU-hours.
- Prohibited: third controller policy, forced acceptance, equivalence-v4/v5, S0 bypass, and downstream PINN before a complete valid S0 PASS.

## Actual Execution

Two external invocations, V1 and V3, ended at zero publication because the hosting shell could not durably own the long run. They are infrastructure provenance and do not consume numerical-policy votes.

Candidate 1 (`nonzero_drive_output_decoupled_controller_v3`) retained controller-v2 inner solves and gates but made only protocol discontinuities/final time mandatory solver landings. Fixed output was reconstructed from accepted two-half paths. In V2, the first 9 V trajectory stopped at `2.1094726562498093e-6 s`: the implicit step failed closed at the locked outer floor. Published qualification runs: 0.

Candidate 2 (`nonzero_drive_output_decoupled_subfloor_recovery_controller_v3`) added geometric recovery down to floor/16 while retaining all integrity, nonlinear, embedded-error, ledger, event, and finite gates. In V4, the first 9 V trajectory stopped at `2.2577221679678546e-6 s` when the frozen 1000-rejection per-case cap was exceeded. Published qualification runs: 0.

The second policy advanced `1.4824951171804533e-7 s` beyond candidate 1, but did not reach even one full 20 microsecond qualification trajectory. This is not sufficient evidence of runtime feasibility or physical validity.

## Disposition And Manuscript Impact

- Controller-v3 qualification: `failed_but_informative`.
- Fresh S0/Phase 1: `forbidden` / unassessed.
- `scientific_vote=false`; `formal_execution_count=0`.
- Phase 2, MLP, vanilla PINN, C01, C06, geometry/protocol OOD, and R1/R2/R3: not executed and `forbidden`.
- No new Methods/Results scientific paragraph or main figure is supported.

Allowed reviewer-defense use: the exact numerical-integration boundary, the two frozen policies, their failure-state hashes, and the fact that output-grid decoupling plus bounded subfloor recovery did not qualify the nonzero-drive trajectory under fixed gates.

Forbidden wording: S2 failed physically; Phase 1 failed scientifically; PINN/C01 failed; the campaign is infeasible; Qiu was reproduced; or any experimental validation claim.

## Evidence

- Machine summary: `outputs/tables/geophase_controller_v3/controller_v3_terminal_summary.json`.
- Candidate table: `outputs/tables/geophase_controller_v3/controller_v3_candidate_dispositions.csv`.
- V1-V4 config snapshots, registries, and V2/V4 atomic failure records: `outputs/tables/geophase_controller_v3/qualification/`.
- Immutable evidence commit: `73dc41f81760a805cec0f768179f327c3abcbe9d`.

## Next Scientific Bottleneck

The next useful experiment is not controller candidate 3 and not PINN. A future newly authorized goal should study the shared nonzero-drive implicit solver at the two content-addressed failure states, with fixed physics and a bounded solver-level policy. A complete valid S0 PASS remains mandatory before Phase 2/C01.
