# Source-contract amendment and fallback submission-lock results

## Disposition

- Branch: `main`
- Baseline: `76970488118612f6ccf9c3cbf6cb17946ca0d999`
- C1: `09fc546c35486e5fb093492abdaba8f8d0a1707f`
- C2 validated content: `689a7a6b218d4263bdc92f04ae52231e7439e752`
- C3: reported in the user handoff because a commit cannot contain its own hash
- Overall status: `NO_GO`
- Disposition: `CONTENT_NO_GO`
- Frozen Ground Truth modified: **No**
- New formal scientific experiments: **0**
- New claim-bearing device forward runs: **0**
- External data fabricated: **No**
- Qiu author intent inferred: **No**
- Qiu author code verified: **No**

## Work completed

### C1 — source-contract amendment

The LLP audit separates the literal printed Qiu SI contract, the analytic
inverse of the configured tanh limiting branch, the later Sena--de Almeida
comparator, and the historical repository implementation. Across 4002
branch/grid evaluations, the anchor-inverse identity and realized reversal-
continuity gates pass. The configured proximity kernel has
`P(0)=0.999999997324712`; its deficit is analytic, not a rounding artifact.
The allowed statement is limited to the analytic identity. Author-code
equivalence, general LLP refutation, return-point memory, and wiping-out remain
forbidden.

### C2 — technical manuscript package

The package adds manuscript v2, Supplementary Information, six-source BibTeX,
failure evidence, data/reproducibility statements, a generic cover letter,
submission checklist, journal shortlist, six main figures as their existing
original bytes, a figure/source hash manifest, and a fail-closed readiness
audit. Five core manuscript sentences map exactly to hash-locked evidence, and
all six citation keys resolve. Pandoc is unavailable, so no journal-format or
rendered-PDF readiness is claimed.

## Single detached C2 validation

Validation used one detached worktree at C2. Eight declared local assets were
copied only after path, byte-size, SHA-256, and reparse-point checks and were
made read-only. `pinnpcm` imported from the detached worktree. Pytest and
matplotlib caches were outside the worktree.

| Gate | Result |
|---|---|
| Full pytest, executed once | **Fail:** 412 passed, 16 failed in 254.80 s |
| Non-writing governance audit | **Pass:** exit code 0 |
| Readiness audit | **Fail:** exit code 1 |
| Normalized Git content diff against C2 | **Pass:** exit code 0 |
| Worktree status / hermeticity | **Fail:** 14 tracked paths rewritten; 6 unexpected figures generated |

The committed logs are UTF-8-normalized copies of the mixed-encoding
PowerShell capture. NUL padding was removed; no test, traceback, command, or
exit-code line was omitted.

## Failure analysis

### 1. Non-portable working-tree byte locks — 10 test failures

The repository has no `.gitattributes` and uses `core.autocrlf=input`. Several
historical preregistrations store SHA-256 values or byte sizes from an active
CRLF working tree, while the detached checkout materializes the canonical Git
blob with LF. For example,
`outputs/tables/m40_qiu_mesh_convergence.csv` is 447 bytes in the active
workspace but 443 bytes in the detached checkout. Git reports no normalized
content diff, yet byte-based tests fail. The same mechanism affects E1F/E1F-R,
CPCF/SCIS, M35--M37R, and M40R locks.

This is a reproducibility-contract failure, not evidence that the underlying
scientific values changed. It nevertheless blocks release because the current
tests claim byte portability that the repository does not provide.

### 2. Incomplete local asset closure — 6 test failures

The eight-file copy manifest omits required local inputs. SCIS/prompt-32 tests
need CEBA trajectory cache files, while M35/M37/M37R tests need provenance-
locked Zhang raw 9 V and 11 V source-data CSVs. Solver fallback is correctly
forbidden, so those tests fail closed. These files must be enumerated with
license/provenance, exact hashes, and redistribution status before a new clean
replay can be attempted.

### 3. Non-hermetic full-suite behavior

The full test run rewrites 14 tracked evidence files (Git-normalized content is
unchanged but working-tree bytes/status change) and generates six untracked
figures. A release test suite must write only to temporary directories or use
explicit `write_output=False` controls. The present suite therefore cannot
serve as a clean submission-lock validator.

### 4. Readiness-audit serialization defect

YAML parses `retrieved_at: 2026-07-22` as a `datetime.date`. The C2 readiness
script passes that object directly to `json.dumps`, raising
`TypeError: Object of type date is not JSON serializable`. The script had
already computed the static citation, claim, figure, source, and protected-
evidence checks, but produced no final JSON. The committed readiness JSON is a
fail-closed C3 reconstruction from the preserved logs and pre-C2 static audit;
it does not pretend that the C2 script succeeded.

## Claim changes

| Claim | Final status | Change |
|---|---|---|
| `atanh` as analytic inverse of the configured tanh anchor | `supported` | Corrected from the stale “unreferenced insertion” wording |
| Qiu author-code or author-intent equivalence | `forbidden` | Unchanged and explicit |
| Calibration-gated reduced `gamma_sub` recovery | `qualified_supported` scientifically; release `manual_unverified_high_risk` | Scientific evidence unchanged; release replay failed |
| Calibration dominates protocol in the tested bundle | `qualified_supported` | Mapped into manuscript v2 |
| Submission technical content ready | `failed_but_informative` | Downgraded to `CONTENT_NO_GO` by the clean replay |

## Distance to delivery goal

The source-semantics ambiguity and manuscript assembly bottlenecks are closed.
The remaining highest-value blocker is now concrete and engineering-bounded:
the clean-clone replay contract is not portable or hermetic. No additional
device/PINN experiment should start before this release gate is repaired.

## Next single priority

Open one bounded **clean-replay portability and asset-closure repair** round:

1. replace working-tree text-byte locks with transparent dual provenance
   (historical workspace SHA plus canonical Git blob/OID or canonical-LF hash),
   without altering protected historical scientific content;
2. enumerate every required CEBA cache and Zhang raw source file in a complete
   local-asset manifest with provenance, hash, size, license, and redistribution
   policy;
3. make output-producing tests use temporary paths or `write_output=False`;
4. serialize YAML dates deterministically (quoted string or ISO conversion);
5. create a new content commit and validate it once in a fresh detached
   worktree. Do not reuse or cosmetically relabel the failed C2 validation.

Only after that gate reaches content `GO` should the authors select a journal,
verify current Q2 status, complete metadata/declarations, render the selected
template, and perform visual PDF QA.
