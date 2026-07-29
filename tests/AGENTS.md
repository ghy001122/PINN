# Tests Subtree Rules

These rules extend the root `AGENTS.md` for `tests/`.

- Test physical behavior, conservation, gradients, boundary/interface semantics, ranks, gates, and failure paths; file-existence and finite-only tests are insufficient for scientific claims.
- For noisy inverse tests, verify each noisy target is actually re-inverted.
- Test frozen GT hash integrity and, in the active workspace, confirm mtimes did not change.
- Test absence of target leakage, holdout leakage, and algebraic residual stubs when relevant.
- Test that failed gates cannot upgrade a claim and that aggregation cannot hide failing blocks or seeds.
- Do not repair tests by weakening scientific thresholds after observing results. Change a threshold only through an explicit, evidence-backed protocol revision.
- Every defect repair adds a regression that reproduces the old failure and reruns the smallest affected valid experiment or audit. A one-case pass without that regression is not closure.
- Formal scale-up tests enforce the declared progression from analytic/limit cases through short single-device, one-seed, multi-condition, multi-seed, and full-scale runs; debug artifacts remain non-voting and isolated.
- Keep CPU smoke coverage, but label it as smoke rather than performance evidence.
