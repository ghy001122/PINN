---
task_name: M31_CPCF_SEMANTIC_SUPERSEDE_AND_CEBA_PARITY
base_sha: 16427d7d20b32c8d25fc7967b43657f0588ba8b2
definition_sha: 306f5c9fdc720c71cad18b7ab322d4d0ae73d938
final_sha: SELF_COMMIT_REPORTED_AT_HANDOFF
branch: main
tests:
  - focused result/contract tests: 19 passed across the final focused runs
  - full pytest: 270 passed in 382.12 s
  - governance/JSON and clean-clone status: recorded in final validation JSON and handoff
reproduction_commands:
  - .\.venv\Scripts\python.exe scripts\audit_prompt31_cpcf_semantics.py
  - .\.venv\Scripts\python.exe scripts\run_gamma_sub_ceba.py --mode parity
  - .\.venv\Scripts\python.exe scripts\run_gamma_sub_ceba.py --mode pilot
frozen_gt_modified: false
evidence_type: solver_generated_synthetic_and_software_contract_audit
claim_status: failed_but_informative
supported_claims:
  - CEBA reproduces six exact historical solver anchors under the locked implementation contract.
forbidden_claims:
  - CPCF establishes or rejects a calibration-protocol resource frontier.
  - CEBA estimates delta_T_sw_star or an optimal protocol.
  - Reliable trained full-PINN, SID/EC-OQ, D0, 13 V, experimental, or external-validation evidence was produced.
goal_distance_change: The invalid CPCF interpretation is removed and a direct-solver replacement is closed honestly at its abstention gate; the calibrated gamma_sub manuscript can proceed without an unresolved resource-frontier branch.
claim_changes:
  - CPCF frontier inference downgraded to forbidden; software diagnosis retained as failed_but_informative.
  - CEBA implementation parity supported; CEBA boundary hypothesis failed_but_informative.
new_blockers:
  - The locked discrete-profile ambiguity set crosses recovery classes at zero T_sw error, so the CEBA boundary is not estimable under this contract.
next_single_priority: Complete calibrated gamma_sub manuscript and reviewer-defense assembly.
disposition: manuscript
---

# Prompt 31 CPCF Semantic Supersession And CEBA Review

## Scope And Manuscript Use

This round audited whether the historical calibration-protocol cost-frontier (CPCF) result had a scientifically equivalent implementation contract, replaced it with a preregistered direct-solver Calibration-Excitation Boundary with Abstention (CEBA), and stopped at the first failed scientific gate. The only new numerical work was six parity anchors and the conditionally authorized bounded CEBA pilot. No N0/full-PINN training, SID/EC-OQ, D0, 13 V, CPCF full sweep, optimizer scan, or unlimited seed expansion ran.

The complete multidomain PINN remains the mandatory architecture and manuscript scaffold. Its historical trained failures are unchanged and no positive full-PINN claim is created here.

## CPCF Superseding Semantic Audit

### Scientific disposition

- `scientific_vote=false`
- `status=implementation_contract_invalid`
- `claim_status=failed_but_informative` for software-contract diagnosis
- `valid_scope=software/proxy mismatch diagnosis only`
- forbidden inference: no conclusion about existence or absence of a calibration-protocol resource frontier

The historical CPCF artifacts and the invalid first attempt remain byte-addressed by `configs/historical_evidence_manifest_v1.json`; none was overwritten. The manifest contains `23` entries with full historic commit, Git blob OID, SHA-256, claim scope, and current-check requirements.

### Contract findings

| Contract | Machine finding | Consequence |
| --- | --- | --- |
| Protocol | `ltp_ltd` is sample-equivalent. `short_pulse_to_ltp_ltd` maps a two-waveform `mixed_protocol` objective to one 15 ms LTP/LTD waveform. `multi_pulse_to_ltp_ltd` maps a 3 ms, ±0.26 V multi-amplitude waveform to a 15 ms, +0.10/-0.03 V LTP/LTD waveform. | Two of three mappings are `protocol_contract_mismatch`. |
| Solver | Historical: `nx=21`, `nt=160/180`, Radau `rtol=1e-5`, `atol=1e-7`. Fresh anchors: `nx=5`, `nt=24`, Radau `rtol=1e-3`, `atol=1e-5`. | Fresh anchors are not solver-equivalent votes. |
| Candidate grid | Historical grid has `15` gamma values; CPCF anchor grid has `5`. | Best-candidate and classification semantics differ. |
| Objective | Historical implementation uses `rRMSE(G)^2 + 0.5 rRMSE(I)^2`; CPCF anchors add `0.01` heat despite the historical implementation ignoring the declared heat weight. | Objective values/order are not equivalent. |
| Unit | `T_sw_prior_width` is a dimensionless multiplier, but CPCF emits `T_sw_prior_width_K` and `calibration_width_range_K`. | The calibration coordinate is mislabeled dimensionally. |
| Randomness | Four noise levels each have one different seed; the proxy function does not consume a seed. | Noise and seed are confounded; no same-noise independent replicates exist. |
| Bootstrap | Each operating point resamples four heterogeneous noise levels with one seed each. | This is heuristic scenario resampling, not an iid seed bootstrap. |
| Directness | `48` rows use proxy prediction; `40` are proxy-only and `8` add a fresh diagnostic. The eight diagnostics cost `48` solver trajectories, but zero rows use a direct-solver scientific vote. | CPCF cannot vote scientifically. |
| Pareto | `12` operating points: `6` risk-qualified, `6` unqualified, `5` stable nondominated. `cal_010_ltp_n16` and `proto_100_ltp_n16` are stable/nondominated despite failing locked risk qualification. | Nondominance does not enforce the declared risk gate. |

The historical Pareto image is removed from the scientific figure roster and may be described only as **NON-VOTING PROXY-CONTRACT DIAGNOSTIC**.

## CI And Historical-Evidence Contract

Commit `306f5c9fdc720c71cad18b7ab322d4d0ae73d938` contains the semantic audit, manifest validator, CI split, CEBA contract, scripts, schema, and focused tests. Fast CI now checks current artifacts, schemas, governance, and focused contracts without full history. Full/manual validation retains complete history and verifies historic blobs. Pip cache, path filters, concurrency cancellation, and timeouts are retained.

The CEBA registration is explicitly an internal commit-ordered preregistration tied to `306f5c9...`; it is not an independent remote timestamp. It records a clean tree before registration and no solver run at registration.

## CEBA Contract

- Protocols: exact triangle (`3 ms`, `0.2 V` peak) and exact LTP/LTD (`15 ms`, `12` pulses).
- Solver: historical `nx=21`, `nt=160/180`, Radau `rtol=1e-5`, `atol=1e-7`.
- Candidates: the historical `15`-point `gamma_sub` grid.
- Objective: port-only `rRMSE(G)^2 + 0.5 rRMSE(I)^2`.
- Calibration coordinate: absolute `delta_T_sw_K`, never a multiplier or normalized cost.
- Cache semantics: waveform/parameter/solver only; observation count, noise, and seed are post-trajectory scoring operations.
- Pilot grid: observations `{8,32}`, noise `{0,0.02}`, five discovery and five held-out seeds for noisy cases.
- Locked gates: success error `<=0.15`, success probability `>=0.80`, abstention `<=0.20`, direct lower/upper bracket, and unchanged classification under one refined solver.
- Budget: at most six anchors, `60` unique solver trajectories, two workers, and `30 min`.

## Parity Result

All required gate families pass in all `6/6` anchors:

| Anchor | Protocol | `delta_T_sw_K` | Historical/CEBA best gamma | Historical/CEBA relative error | All gates |
| --- | --- | ---: | ---: | ---: | --- |
| triangle nominal | triangle | 0.0 | `4.5e8` | `0` | pass |
| triangle narrow | triangle | 0.2 | `5.5e8` | `0.222222` | pass |
| triangle mismatch | triangle | 2.0 | `1.0e9` | `1.222222` | pass |
| LTP/LTD nominal | LTP/LTD | 0.0 | `4.5e8` | `0` | pass |
| LTP/LTD narrow | LTP/LTD | 0.2 | `5.0e8` | `0.111111` | pass |
| LTP/LTD mismatch | LTP/LTD | 2.0 | `1.0e9` | `1.222222` | pass |

Best gamma, relative error, recoverability classification, objective value, objective ordering, waveform hash, and solver-config hash each pass `6/6`. Parity used `36` unique solver trajectories, zero cache hits, one worker, and `29.2195 s`. This supports implementation parity only and authorized the bounded pilot.

## Conditional CEBA Pilot Result

The pilot ran and produced `72` scoring cases. It reused all `36` parity trajectories, added `0` ODE trajectories, recorded `36` cache hits in the pilot process, used one worker, and brought combined parity-plus-pilot time to `29.4809 s`. It queried only the preregistered deltas `{0,0.2,2}` K; no adaptive target or refinement trajectory was authorized.

Every protocol/observation/noise condition at `delta_T_sw_K=0` has abstention rate `1.0` and success probability `0`. The locked profile-retention set crosses recoverable and nonrecoverable gamma classes even with zero switching-temperature error. Therefore:

- no discovery bracket exists;
- no held-out lower-success/upper-failure bracket exists;
- `delta_T_sw_star_K=null` for triangle and LTP/LTD;
- solver-refinement consistency is not testable and receives no vote;
- `ceba_configuration_claim_eligible=false`;
- status is `failed_but_informative`.

This is a failure of the preregistered boundary-estimation contract, not evidence that calibration never helps. The ambiguity rule and thresholds were not relaxed after inspection, and no substitute experiment was started.

## Literature Red Team And Innovation Portfolio

The bounded eight-paper audit is recorded in `docs/literature/prompt31_qoi_event_pinn_red_team.md`. PirateNet, DB-PINN, NysNewton-CG/SOAP, XPINN, DeepONet, differentiable event-time models, and DWR/QoI sampling all have prior art and cannot be standalone novelty claims.

Exactly three ideas remain active in `docs/research_strategy/innovation_portfolio.md`: (1) QoI-guided Event-Conditioned complete PINN, (2) evidence-triggered enthalpy/latent heat H1, and (3) evidence-triggered branch/minor-loop history H2. Two-dimensional/interface H3 is inactive until a one-dimensional structural discrepancy survives numerical and parameter uncertainty. No idea was implemented this round and no world-first claim is made.

## Validation And Reproduction

The only full test run after result lock passes `270` tests in `382.12 s`. The single full governance audit has no failed check and reports `pass_with_manual_review`: all eight frozen-GT SHA-256 values pass, while portable mtimes and client-side rule autoloading remain manual semantics. The single strict JSON pass parses `141` tracked JSON files with zero failures. The post-commit clean-clone result is recorded in `outputs/tables/prompt31_final_validation.json` and the final handoff. No historical high-cost experiment is repeated.

## Evidence And Claim Boundary

Allowed manuscript wording:

> In the frozen synthetic benchmark, constrained `gamma_sub` recovery remains calibration-gated and rank-1. A superseding software audit invalidates the CPCF proxy contract as scientific frontier evidence. A direct-solver CEBA implementation reproduces six historical anchors, but its locked ambiguity rule abstains before a calibration-excitation boundary can be bracketed.

Forbidden wording includes: CPCF established or rejected a resource frontier; CEBA estimated `delta_T_sw_star`; one protocol is globally optimal; calibration cost is experimental or device-general; reliable trained full-PINN, sensitivity, SID/EC-OQ, D0/13 V, unique raw-parameter, independent external, or experimental validation succeeded.

## Distance To Definition Of Done

The resource-frontier branch no longer blocks manuscript closure: CPCF has no scientific vote and CEBA has a reproducible fail-closed endpoint. The safe paper line remains identifiability audit -> target reduction to `gamma_sub` -> `T_sw` calibration gate -> constrained inversion -> recoverability/failure/abstention boundary, with full-PINN, SID/EC-OQ, D0, and proxy failures retained as explicit limitations.

## New Blocker

The CEBA profile-ambiguity contract is too conservative to certify recovery even at zero `T_sw` error. Resolving that question would require a new scientific contract and authorization; it must not be repaired post hoc in this round.

## Next Single Priority And Disposition

Complete calibrated `gamma_sub` manuscript, submission, and reviewer-defense assembly. After manuscript lock, the highest-value research candidate is a bounded QoI-guided Event-Conditioned complete-PINN MVE with independent solver, field, event-ledger, interface, and conservation gates. It is a candidate only, not authorized execution.
