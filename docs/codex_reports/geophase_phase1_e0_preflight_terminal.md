# Phase 1 E0 Preflight Terminal Report

## Disposition

`INVALID_E0_EXECUTION / STOP_E0_SECOND_IMPLEMENTATION_DEFECT`

The authorized E0 route did not form a physical or scientific verdict. The
formal 63-item campaign, Phase 2 data generation, and C01 training were not
started.

## Execution identity

- Evidence type: literature-guided synthetic numerical digital-twin execution
  provenance; no experimental evidence.
- Base after PR #18: `5fe7f25d856f66f063d488ef449af816106981d9`.
- Initial runner code anchor: `31c23251d48135308829ed7cd64d631d82acf7e5`.
- Single repair anchor: `4dec78ef7ab691a599bdafcd320958e1e2049321`.
- Repaired current-head CI: run `30693018031`, success.
- Command: `.venv/Scripts/python.exe scripts/run_geophase_phase1_e0.py --execute-preflight`.
- Frozen budget: CPU-only, one thread, 7200 s wall-clock maximum.

## Actual runs and root causes

1. The first invocation returned JSON `null` before creating a registry or
   scheduling a case. Root cause: `run_preflight_worker()` did not dispatch to
   `execute_preflight()` because that call was unreachable. The invocation is
   permanently recorded as invalid, with zero cases and no scientific vote.
2. The only permitted implementation repair moved that dispatch into the
   worker and added a focused regression. The repaired identity was pushed and
   passed clean-checkout CI before execution.
3. The second invocation created an atomic registry and journal, then failed
   while canonicalizing the first `PRE-E0-FOUNDATION` record: a NumPy `bool_`
   was not JSON serializable. It terminated in 0.2643127 s with zero published
   cases.

This is the second implementation defect. The registered repair budget is
exhausted, so no further repair or rerun is allowed in this goal.

## Atomic evidence

- `journal.jsonl`: SHA-256
  `5528beb69f772332621bcb7afc39fc91b73dbde686c6b504f486d537bed4a273`;
  three contiguous hash-chained events.
- `registry.json`: SHA-256
  `44f333e6dacd9b2af97b384e83dfda523ef350a4d6ccbe07c6dcf8a9cec7b5b9`;
  state `INVALID_E0_EXECUTION`, validity `invalid`, no scientific vote.
- `preflight_summary.json`: SHA-256
  `79265d994fe0594a1322a88017df89206213077e14d575f8890df7d4ec285e45`;
  `completed_case_count=0` and `formal_execution_count=0`.
- First invalid invocation record: SHA-256
  `78f8f200c94b43762c9a3ac07b008f7f0fbdead301af053355325cba5291bdff`.

## Claim effect and manuscript use

- E0 physics: `forbidden` / unassessed.
- Phase 1-v2 judge: `forbidden` / unassessed.
- Runtime feasibility: `forbidden` / unassessed.
- C01/R1 and all OOD claims: `forbidden`; no dataset, training, baseline, or
  evaluation was created.
- Historical strict-equivalence-v1 and equivalence-v2/v3 remain immutable.
- Frozen GT remains read-only.

No Methods or Results sentence is eligible from an invalid execution. This
report is reproducibility and reviewer-defense provenance only; it cannot be
used as an S2 physical failure, a Phase 1 result, or evidence against PINNs.
