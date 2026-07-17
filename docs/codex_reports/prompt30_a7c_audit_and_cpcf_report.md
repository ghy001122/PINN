---
task_name: prompt30_a7c_audit_ci_split_and_bounded_cpcf
base_sha: a7c108e3980953ced24d2de86ce7afc340e65a88
preregistration_sha: 3cd714cb91bd2c700881584391f3b9ab66027b3c
final_sha: reported_in_final_handoff_because_a_commit_cannot_contain_its_own_hash
branch: main
tests:
  - focused CPCF/a7c/schema tests before final validation
reproduction_commands:
  - .\.venv\Scripts\python.exe scripts\audit_a7c_prompt30_evidence.py
  - .\.venv\Scripts\python.exe scripts\audit_gamma_sub_calibration_protocol_cost_frontier.py --config configs\gamma_sub_calibration_protocol_cost_frontier.yaml --mode pilot --resume --max-workers 2
  - .\.venv\Scripts\python.exe scripts\validate_tracked_json.py
frozen_gt_modified: false
evidence_type: synthetic_numerical_digital_twin_decision_audit
claim_status: failed_but_informative
supported_claims:
  - a7c machine evidence classification is internally consistent
  - CPCF valid pilot executed within the preregistered scope
forbidden_claims:
  - stable or optimal CPCF frontier
  - monetary or laboratory cost optimality
  - experimental or device-general resource prescription
  - trained full-PINN fidelity or inverse success
goal_distance_change: CI is cheaper and the CPCF decision boundary is closed without changing the safe gamma_sub mainline
claim_changes:
  - CPCF downgraded to supplementary failed_but_informative evidence
  - current SID implementation rejection separated from the broader hypothesis
new_blockers:
  - fresh CPCF anchors violate the locked historical response-surface tolerance
next_single_priority: calibrated gamma_sub manuscript and reviewer-defense assembly
disposition: stop_cpcf_full_sweep_and_return_to_manuscript
---

# Prompt-30 a7c Audit And Bounded CPCF Final Report

## Scope And Manuscript Use

This round audited commit `a7c108e3980953ced24d2de86ce7afc340e65a88`, split continuous integration into fast and full evidence tiers, and executed exactly one new scientific MVE: the bounded Calibration-Protocol Cost Frontier (CPCF) pilot. It did not rerun N0 training, SID/EC-OQ, D0, 13 V, or unrestricted seeds/optimizers. The complete multidomain PINN architecture remains the mandatory scaffold, but no trained full-PINN claim is upgraded.

The only possible manuscript use of CPCF is a supplementary decision/rejection table. The calibration-gated rank-1 `gamma_sub` result remains the safe `qualified_supported` inverse mainline.

## a7c Machine Audit

`outputs/tables/prompt30_a7c_audit_summary.json` checks Git blobs, current hashes, row counts, gate logic, and report-to-JSON consistency without recomputing historical expensive outputs.

| Evidence class | Audited result |
| --- | --- |
| Actually executed | v3r completed 1200 Adam steps and produced a scoreable post-Adam trajectory; same-checkpoint diagnostic reproduced strong-Wolfe non-finiteness at closure 3; solver-first SID/EC-OQ ran 36 cases and 189/420 allowed forwards. |
| Gates passed | N0 port NRMSE95 `0.0955475 <= 0.10` and finite/bounds implementation checks; isolated SID rank/information votes are explicitly non-voting after prerequisite failure. |
| `failed_but_informative` | v3r fails residual, field, flux, and ledger gates, with five metrics above `20x`; SID derivative agreement is `3/9`, maximum discrepancy `0.648429`, and event-window/stability/dual-geometry prerequisites fail. |
| Current implementation rejected | The locked N0 optimizer route and prompt-29 SID/EC-OQ numerical/event-window implementation. |
| Still unvalidated | Reliable full-PINN forward/sensitivity/inverse fidelity, protocol-dependent quotients, the broader SID hypothesis under a new contract, D0b-D0d, 13 V, and independent external validation. |

The corrected SID wording is: **the current preregistered implementation failed and is inactive**. It is forbidden to claim that the broader scientific hypothesis has been permanently falsified.

## CI And Reproducibility Changes

- Push/PR fast validation uses path filters, pip caching, concurrency cancellation, a 20-minute timeout, focused CPCF/a7c/evidence/claim tests, strict tracked-JSON parsing, and a fast-checkout governance mode.
- Manual and Monday-scheduled full validation reconstructs ignored frozen GT fixtures, runs the complete suite and full governance audit, parses all tracked JSON, and checks for tracked mutation under a 60-minute timeout.
- The CPCF runner locks config/input/script hashes, fixed seeds and case IDs; supports case-level cache, `--resume`, atomic file replacement, strict finite JSON values, and bounded two-worker parallelism.
- The full sweep is a fail-closed branch: it cannot run unless all four pilot expansion gates pass.

Lower CI frequency does not lower the evidence standard; it moves the expensive claim-bearing suite to explicit full validation while keeping focused push checks read-only.

## CPCF Pre-registration

The preregistration is bound to commit `3cd714cb91bd2c700881584391f3b9ab66027b3c`, config SHA-256 `03ebcf1c94c3c6c626d85e5267666bfaff22c51ac63d9c15d1cf03ed854c2624`, and preregistration SHA-256 `846a96603948d5aafd956fcb06007db8aa885908e40e6ecbbc9c7d27b1905560`.

It compares four strategies: calibration-only, protocol-only, sequential calibration-to-protocol, and joint calibration-protocol design. Decision axes are `T_sw` prior width, locked protocol family, observation count, and the existing noise levels `0/0.01/0.02/0.05`. The transparent balanced resource weights are calibration/protocol/observations `0.40/0.35/0.25`; the index is normalized and non-monetary. Risk includes `gamma_sub` relative error, success rate at the locked `0.15` threshold, profile/bootstrap width, and abstention.

Expansion required all of:

1. fresh solver-anchor consistency within the existing historical tolerance;
2. at least two bootstrap-stable nondominated operating points;
3. at least `20%` lower cost at matched risk or `20%` lower risk at matched cost;
4. bootstrap 95% CI excluding zero in the improvement direction.

No threshold was relaxed after observation.

## Invalid Attempt Preserved Without Scientific Vote

The first implementation attempt completed `48` cases in `43.176 s` (`48` solver forwards, cache hits `0`, misses `48`) but aggregated them into only `4`, rather than `12`, operating points because the replicate `id` overwrote the operating-point `id`. Its definition commit was `30785f22dd1e0122b1cf0799bdea92c7c2142b85`; raw-summary SHA-256 is `16d327f58c8828c66e359f42a8ba56b0b5ea339aa016849e9ac87bcbf6754da1`.

The raw summary and provenance are retained at `outputs/tables/gamma_sub_cpcf_attempt1_invalid_summary.json` and `outputs/tables/gamma_sub_cpcf_attempt1_invalid_provenance.json`. This attempt has `scientific_vote=false`. Only the ID aggregation defect was fixed; the unpushed preregistration commit was amended, all scientific thresholds remained unchanged, and the valid pilot was rerun from an empty task cache.

## Valid CPCF Pilot Results

The valid run completed in `116.445 s` (`48` cases, `12` operating points, `8` fresh anchors, `48` solver forwards, two workers). Because it was the first valid run after the corrected definition, cache hits were `0` and misses were `48`.

| Preregistered gate | Result | Evidence |
| --- | --- | --- |
| a. Solver-anchor consistency | **FAIL** | Mean absolute discrepancy `0.299600 > 0.0537361`; classification agreement `0.625 < 0.883333`; disagreements `3 > 0`; maximum discrepancy `1.12998`. |
| b. At least two stable nondominated points | **PASS** | `5` sample-nondominated operating points have bootstrap frequency at least `0.90`. This gate alone cannot vote for a frontier claim. |
| c. At least 20% cost/risk improvement | **FAIL** | No candidate reaches the locked improvement threshold. |
| d. Bootstrap direction excludes zero | **FAIL** | No selected qualifying improvement exists, so no direction interval can pass. |

`all_pilot_expansion_gates_pass=false`, `full_sweep_triggered=false`, `full_sweep_executed=false`, and `cpcf_main_claim_eligible=false`. The valid summary is `outputs/tables/gamma_sub_cpcf_pilot_summary.json`; the operating-point table and source-backed figure are versioned alongside it.

## Literature Red Team And Idea Disposition

Eight primary papers were checked across PINN loss pathology/preconditioning, inverse identifiability, Bayesian OED, PINN experimental-point design, enthalpy phase change, VO2 transition non-congruence, and thermal-neuristor compact modeling. The audit is in `docs/literature/prompt30_cpcf_idea_red_team.md`.

- **Added as conditional hypotheses:** H1 residual-triggered enthalpy/latent heat; H2 branch/minor-loop history state. Both require provenance-backed external discrepancy before any implementation.
- **Rejected as main innovation:** generic PINN preconditioning/conditioning diagnosis, because direct primary precedents exist and the current N0 route is closed. A read-only diagnostic could at most support reviewer defense under new authorization.
- **Downgraded:** CPCF, from candidate resource-frontier claim to supplementary `failed_but_informative` decision evidence.
- **Still forbidden:** H3 two-dimensional/interface innovation without demonstrated 1D structural error; any novelty claim based on standard profile likelihood, Bayesian OED, NTK point selection, enthalpy PINNs, or hysteresis components alone.

## Claim And Manuscript Boundary

Allowed wording:

> In the configured one-dimensional synthetic benchmark, calibration-gated rank-1 `gamma_sub` inversion is conditionally supported. A bounded CPCF pilot did not establish a stable resource frontier because fresh-anchor consistency and preregistered improvement gates failed; its decision table is retained as supplementary negative evidence.

Forbidden wording includes stable/optimal CPCF frontier, monetary or laboratory cost, device-general resource requirement, global protocol optimality, unconditional `gamma_sub` identifiability, experimental validation, reliable trained full-PINN fidelity, protocol-dependent quotient geometry, and successful 13 V evaluation.

## Frozen GT And Attribution

Frozen GT v1.1 equations, configs, report, manifest, and arrays were not modified. CPCF inputs remain `synthetic_gt`, historical solver-backed tables, and fresh `solver_generated` anchors. Nothing is labeled public-external measurement or `pinn_predicted`. The figure legend and report keep solver/PINN attribution separate.

## Validation And Reproduction

Focused implementation tests passed before the pilot (`6 passed`; the earlier combined focused run was `9 passed, 2 failed` only because an audit test matched a literal port-number string, then `2 passed` after the semantic assertion correction); the final focused set passed `8` tests in `3.20 s`. The single final full-suite run passed `253` tests in `259.15 s`. The single explicit read-only governance audit returned `pass_with_manual_review`, with no failed checks, frozen-GT hashes unchanged, and the five-file context surface at `19,820/24,576` bytes. Strict-JSON validation and the post-commit clean-clone result are recorded in `outputs/tables/prompt30_cpcf_final_validation.json` and the final handoff.

Primary reproduction commands:

```powershell
.\.venv\Scripts\python.exe scripts\audit_a7c_prompt30_evidence.py
.\.venv\Scripts\python.exe -m pytest tests\test_gamma_sub_calibration_protocol_cost_frontier.py tests\test_gamma_sub_cpcf_evidence_schema.py tests\test_prompt30_a7c_evidence_audit.py -q
.\.venv\Scripts\python.exe scripts\validate_tracked_json.py
```

The pilot command is preserved for provenance but must not be rerun merely to reconstruct the already-versioned result. `--mode full` is prohibited by the failed gate.

## Distance To Goal, Blocker, And Next Decision

The round closes a tempting resource-frontier branch without increasing the paper's positive-claim surface. It improves reproducibility and reviewer defense by proving that the old response-surface tolerance does not transfer to these fresh CPCF anchors.

The single project priority is calibrated `gamma_sub` manuscript/submission/reviewer-defense assembly. The highest-value feasible research after that, and only under new authorization, is a provenance-backed branch-resolved thermal/minor-loop data feasibility audit before choosing H1 or H2. No new physics term or training run should precede that evidence trigger.

Disposition: **stop CPCF expansion; retain the complete PINN scaffold; return to manuscript assembly.**
