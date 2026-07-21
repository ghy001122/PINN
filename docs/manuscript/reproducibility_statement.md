# Reproducibility statement

## Versioned components

- Python source, YAML configurations, tests, and audit scripts;
- lightweight JSON/CSV evidence and source/protected-evidence manifests;
- manuscript text, claim mappings, and six main-figure original PNG bytes;
- frozen-input hashes and a fail-closed project-governance audit.

## Local replay

Validation uses Python 3.11 in the project virtual environment and a detached
clean worktree at the validated content commit. Before execution, each required
local-only asset is copied by its declared relative path, checked for exact
SHA-256 and byte size, checked not to be a symbolic link/reparse point, and
marked read-only. The detached worktree must import `pinnpcm` from its own
`src/` tree. Pytest cache and matplotlib cache are redirected outside the
worktree.

The content commit is validated once with the complete test suite, the
non-writing governance audit, and the submission-readiness audit. Any failure
produces `NO_GO`; the content commit is not silently repaired after validation.

## Public reproduction boundary

The repository does not redistribute frozen NPZ arrays or publisher PDFs.
Consequently, a public clean clone without the local asset pack is not claimed
to reproduce every test. The manuscript and data statement disclose this
boundary, and the readiness record distinguishes local clean-worktree replay
from public-clone reproducibility.
