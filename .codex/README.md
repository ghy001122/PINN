# Project-Local Codex Policy

`config.toml` supplies repository-scoped runtime defaults and GitHub network access. `rules/project_safety.rules` contains command-safety policy only. Scientific claims and research behavior remain in `AGENTS.md`; the reusable research workflow is `docs/research_strategy/sci_delivery_pipeline.md`.

Codex scans `rules/` under every active config layer at startup. Project-local config and rules load only for a trusted project; `E:\Python demo\PINN` is explicitly trusted in the current user configuration. Restart Codex after changing these files.

The policy permits routine staging/commits, fast-forward synchronization, `git push origin main`, and read-only GitHub PR/Actions/issue inspection without repeated prompts. It deliberately does not auto-authorize PR merges, workflow dispatches, issue edits, releases, remote deletion, or history rewriting. Those cloud writes still use the GitHub connector's confirmation flow or the normal approval policy.

Prefer the authenticated GitHub connector for repository metadata, reviews, checks, issues, and pull requests. Git push authentication remains with Git Credential Manager. Execpolicy rules never store or grant credentials; the optional `gh` CLI requires its own valid login.

The rule file uses the `prefix_rule(...)` syntax accepted by the installed Codex CLI and is tested directly with `codex execpolicy check`.

Safe alternatives for forbidden commands:

- replace `git reset --hard` with `git status`, `git diff`, and a user-approved targeted restore;
- replace `git clean -fd[x]` with a dry-run inventory and explicit path removal after approval;
- replace force-push with a normal push, new branch, or user-approved history repair.

Rules that cannot be reliably encoded by a command prefix, such as detecting every path outside the repository, remain governed by sandbox permissions and `AGENTS.md`.
