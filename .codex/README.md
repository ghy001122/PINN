# Project-Local Codex Policy

`rules/project_safety.rules` contains command-safety policy only. Scientific claims and research behavior remain in `AGENTS.md`; the reusable research workflow is `docs/research_strategy/sci_delivery_pipeline.md`.

The file uses the `prefix_rule(...)` syntax accepted by the installed Codex CLI and is tested directly with `codex execpolicy check`. Direct checks prove syntax and match behavior; they do not prove that every Codex client automatically trusts and loads project-local `.codex` policy. Automatic loading is therefore `manual_review_required` unless the client explicitly reports it.

Safe alternatives for forbidden commands:

- replace `git reset --hard` with `git status`, `git diff`, and a user-approved targeted restore;
- replace `git clean -fd[x]` with a dry-run inventory and explicit path removal after approval;
- replace force-push with a normal push, new branch, or user-approved history repair.

Rules that cannot be reliably encoded by a command prefix, such as detecting every path outside the repository, remain governed by sandbox permissions and `AGENTS.md`.
