# Phase 1-v2 Equivalence-v2 One-shot Audit Contract

Task: `Q2_PHASE1_V2_EQUIVALENCE_V2_ONE_SHOT_AUDIT`
State: `preregistered_not_authorized_not_executed`

## Purpose and manuscript destination

This contract defines one future implementation-equivalence audit between the
frozen optimized S2 candidate and the frozen PR #8 oracle. Its only manuscript
use is reviewer defense for the independent Phase 1 reference implementation.
It cannot validate S2 physics, Qiu reproduction, runtime readiness, or Phase 1.

Strict-equivalence-v1 remains an immutable valid `12/57` fail-fast result with
disposition `NO_GO_EQUIVALENT_PERFORMANCE_REPAIR`. The solver-free parent audit
remains `GO_VERSIONED_EQUIVALENCE_V2_AUDIT` within its qualified metric scope;
the coverage correction mechanically maps 638 parameterized templates to all
57 rows and passes 21/21 raw-record controls. None of those facts is an
equivalence-v2 result.

## Frozen inputs

- Candidate commit/tree/identity:
  `1ae2704f6d84a3733d9de58aa23d992aa0c471a5` /
  `d3833a4a5dd067dab72c84f15fe2f8e726bd9512` /
  `39044f37c983060df48e9915c594f69fbfbeacc60eef9a32bc352bdb5ec25b10`.
- Oracle commit/tree/source SHA-256:
  `85e4257fc01af2e0bf706ef9001f263b1420ecaa` /
  `50ef2214b19f98c6cada0f5f40c682de9eb16bee` /
  `e1a349ca0275021508cd07da02576adafbbcdae81e122659274769f329016a37`.
- Original plan source and comparator SHA-256:
  `src/pinnpcm/solvers/geophase_phase1_v2_performance_equivalence.py` /
  `05868658ca199737600d796fbdcd4eb2661d222cc749e95a3530c1ea7078ebdc`.
- Original performance contract SHA-256:
  `84e1ecb298cfa6264646cc5e74df602b3e9e790e3eecfdc1abea62c087e87db4`.
- Canonical ordered 57-row plan SHA-256:
  `d88b88f04f1a5fe6bafd80702eebb29e8f48656b456879e092dafd1d01f1bce2`.

The future audit is machine-bound to the Python, NumPy, SciPy, PyYAML, OS,
architecture, dependency hashes, and single-process/single-thread environment
recorded in the YAML. Any mismatch is `INVALID_INFRA`, not a valid vote.

## Locked plan and data separation

The production `build_equivalence_plan` order is immutable:

- indices 0--11: `metric-development`; these rows were observed by v1 and are
  not v2 results;
- indices 12--56: `held-out`; these 45 rows must remain unexecuted until a
  fresh explicit authorization starts the one allowed v2 attempt.

The future attempt, if separately authorized, must evaluate indices 0--56 in
that order. No row may be inserted, deleted, reordered, skipped, retried, or
used for rule selection.

## Comparison rules

### A. Primary physical quantities

`T`, `s`, `b`, `V_d`, `phi`, terminal current, field/device Joule power, the
four ledgers, and embedded temporal error retain the v1 normalized relative
threshold `1e-12`. Missing, extra, non-finite, or invalid fields fail closed.

### B. Topology and state machine

Nonlinear method, convergence/fallback disposition, accepted/rejected
sequence, failure classification, event count/direction/order, and reversal
count/direction/order must match exactly. Missing, extra, or validation-error
states fail closed.

### C. Lateral conservation and flux

Physical x/y face fluxes and net-cell outflow remain voting. They use the
pre-result analytic bounds

\[
B_x=2g_{x,\max}\|\Delta T\|_\infty+
64\epsilon\max(g_{x,\max}T_{\rm scale},q_{\rm scale}),
\]

\[
B_y=2g_{y,\max}\|\Delta T\|_\infty+
64\epsilon\max(g_{y,\max}T_{\rm scale},q_{\rm scale}),
\]

\[
B_{\rm net}=\|L\|_\infty\|\Delta T\|_\infty+
64\epsilon\max(\|L\|_\infty T_{\rm scale},q_{\rm scale}).
\]

The candidate and oracle must each pass the original lateral hard gate, and
their hard-gate dispositions must match. Signed cancellation residues remain
voting under

\[
B_{\rm cancel}=64\epsilon\,2
(n_xq_{x,\rm scale}+n_yq_{y,\rm scale}).
\]

No empirical multiplier or result-derived threshold is permitted.

## Execution control

This contract creates no runner and authorizes no row. A later explicit user
authorization is required before an immutable registry can atomically change
`equivalence_v2_execution_count` from 0 to 1 and schedule plan index 0.

The future audit must use a single-writer append-only JSONL hash chain and
per-row temporary write, flush, hash verification, and atomic rename. A partial
row is not completed evidence. The audit fails fast on the first valid A/B/C
failure and permits no automatic or manual retry under this contract.

The only terminal states are:

- `PASS`: 57/57 completed and every A/B/C vote passed;
- `VALID_FAIL`: the first valid A/B/C vote failed;
- `INVALID_INFRA`: authority, environment, hash, I/O, schema, or execution
  integrity failed; this casts no equivalence or scientific vote.

## Current claim and stop boundary

At preregistration close:

- `equivalence_v2_execution_count=0`;
- `equivalence_v2_completed_rows=0`;
- equivalence-v2 result artifacts = 0;
- `formal_execution_count=0` and formal artifacts = 0;
- optimized equivalence and Phase 1/S2 science remain `forbidden`/unassessed.

No C1/C2/C3, runtime preflight, formal runner, PINN, Phase 2, inverse, S1,
FEM/3D, NbO2, or alternative-route experiment is authorized by this contract.
