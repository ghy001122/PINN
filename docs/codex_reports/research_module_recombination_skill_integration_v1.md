# Research Module Recombination Skill Integration V1

## 1. Correction Objective

This governance-only task makes attributed literature-module adaptation and bounded recombination an explicit project research method. It separates module provenance/contribution type from evidence claim status, replaces blanket novelty rejection with precise diagnoses, and adds a reusable route from source decomposition to a minimum-evidence execution contract.

No physics solve, continuation, stability spectrum, dataset generation, PINN/surrogate training, OOD, inverse run, or scientific-state update was executed.

## 2. Created Skill

- Name: research-module-recombination
- Path: .agents/skills/research-module-recombination/SKILL.md
- Explicit invocation: $research-module-recombination
- Implicit invocation: enabled in agents/openai.yaml
- Invocation modes: FAST_SCAN, FULL_DESIGN, and CLOSEOUT_SALVAGE
- Utility scale: ordinal 1–5 with raw time/run estimates
- Pragmatic metrics: time_to_first_figure, time_to_manuscript_claim, and new_data_or_solver_runs_required
- References: workflow.md, templates.md, and pinn_pcm_worked_example.md

The UI short description uses the 60-character “Decompose, adapt, recombine, rank, and validate SCI modules.” form because the project Skill generator enforces a 25–64 character field; the task's 67-character wording was shortened without changing scope.

## 3. Trigger Scope

| Prompt | Expected routing | Reason |
| --- | --- | --- |
| 把三篇文献的方法拆成模块并排列组合。 | Trigger | Literature decomposition and recombination. |
| 构思 PINN 与二维相变材料的创新点。 | Trigger | SCI innovation design. |
| 审查当前 A'+C'+D' 方法组合。 | Trigger | Contribution and interface review. |
| 负结果后哪些模块还能回收重组？ | Trigger | Negative-result salvage. |
| 给出下一篇 SCI 的最低成本方法组合。 | Trigger | Utility ranking and minimum evidence. |
| 修复 CSV 解析 bug。 | Do not trigger | Routine bug fix. |
| 把一个变量重命名。 | Do not trigger | Mechanical edit. |
| 运行已冻结 config。 | Do not trigger | Direct execution of a fixed contract. |
| 格式化 markdown。 | Do not trigger | Formatting only. |
| 读取某个日志并报告错误行。 | Do not trigger | Log triage only. |

## 4. Contribution Axis Versus Claim Gate

The Skill records module roles independently as directly_transferred_module, adapted_module, interface_contribution, workflow_contribution, functional_composition, validation_contribution, composability_contribution, or supporting_module.

The evidence gate remains supported, qualified_supported, failed_but_informative, or forbidden. A known or directly transferred component is not automatically forbidden; an unmeasured combination remains unable to support a headline claim.

## 5. Authoritative Workflow Updates

- AGENTS.md: formal recombination method, attribution, orthogonal axes, frozen-NO-GO scope, and mandatory Skill routing.
- docs/AGENTS.md: local documentation rule aligned with direct transfers, supporting roles, and minimum discriminative evidence.
- docs/project_prompts/critical_research_mode.md: precise misconduct/contribution gate and compliant recombination section.
- docs/research_strategy/sci_delivery_pipeline.md: source → adaptation → bounded pool → ranking → evidence → claim → contract lane.
- docs/research_strategy/context_loading_policy.md: explicit trigger and non-trigger routing.
- docs/research_strategy/pinn_phase_change_q2_sci_execution_guide.md: less rigid module-adaptation methodology without changing scientific gates.
- .codex/README.md: project Skill location, explicit/implicit invocation, reload behavior, and command-policy separation.

PR #44 was synchronized by a normal merge with post-PR43 `origin/main`. The overlapping PR #43 communication, efficiency, stop-discipline, and scientific-state rules remain authoritative; the Skill-specific routing and contribution-axis additions are layered once without a second authority surface.

The following workflow-governance files now match post-PR43 main exactly and are absent from the PR #44 diff: `workflow_research_norms_14_item_audit_2026-08-10.md`, `codex_workflow_rules.md`, `durable_project_memory.md`, `codex_final_report.md`, `audit_project_governance.py`, and `test_project_governance.py`.

## 6. PR #36–#43 Worked Example

The non-authoritative worked example preserves every recorded disposition while showing asset reuse: unstable patterned equilibria (#36), failed direct-coordinate PINNs with retained M1/Robin/conservation assets (#37–#38), accurate projected latent fields without neural necessity (#39–#40), multi-fixed-point self-consistent IMT followed by protocol selection (#41–#42), and the merged PR #43 bounded factorial hard-gated surrogate result with retained POD/baseline/refusal assets.

PR #42 remains the independent `GO_PROTOCOL_SELECTED_EQUILIBRIUM_MANIFOLD` node. PR #43 remains `NO_GO_PROTOCOL_MANIFOLD_NEURAL_VALUE`: the 2×2 geometry × thermal context, leakage-free POD, and analytic/ridge/single-head/hard-gated comparisons completed; hard gating did not establish incremental value over the single head; ambiguity recall was 1.0 and certified false-unique was 0, while two-candidate set coverage missed its frozen gate. The example does not override current authority or authorize a new experiment.

## 7. Lightweight Validation

- Skill Creator quick_validate.py: passed.
- SKILL.md frontmatter: valid name and non-empty trigger description.
- agents/openai.yaml: required interface fields and allow_implicit_invocation: true present.
- Three references: present and linked from the Skill.
- FAST_SCAN, FULL_DESIGN, and CLOSEOUT_SALVAGE: defined and routed in the Skill, workflow, templates, metadata, and README.
- Utility ranking: 1–5 only, with the three raw pragmatic estimates and favorable ranking scores present.
- Worked example: PR #42/#43 identities and PR #36–#43 range preserved.
- Root authority and delivery pipeline: both reference $research-module-recombination.
- Current authoritative workflow files: no pseudo-novelty or 伪创新 wording remains.
- Focused standard-library structural/trigger check: passed.
- git diff --check: passed.

## 8. Scientific State Unchanged

The scientific state is the post-PR43 main state, whose frozen disposition is `NO_GO_PROTOCOL_MANIFOLD_NEURAL_VALUE`. PR #44 does not alter that scientific state: relative to post-PR43 main, it does not modify CODEX_CONTEXT.md, PROJECT_STATE.md, NEXT_ACTIONS.md, docs/research_strategy/active_phase.md, docs/paper/final_claim_matrix.md, scientific configs, data, figures, outputs, or historical scientific reports.

Evidence type: governance/software implementation fact. Synchronizing PR #44 incorporates the already merged PR #43 state but creates no new scientific evidence, changes no PR #36–#43 disposition or claim status, and does not constitute a formal Skill research invocation.

## 9. Usage

Explicit examples:

> Use $research-module-recombination FAST_SCAN to screen the next bounded research combination without executing it.

> Use $research-module-recombination FULL_DESIGN to turn an already selected combination into a complete evidence and execution contract.

> Use $research-module-recombination CLOSEOUT_SALVAGE to freeze a result, recover modules, and route stop, paper, fallback, or a possible new MVE.

Codex may invoke the Skill implicitly for innovation design, method decomposition, recombination, rerouting, contribution analysis, or negative-result salvage. Implicit screening defaults to FAST_SCAN; no mode automatically authorizes an experiment. Routine execution and maintenance tasks do not invoke it.

## 10. Future Codex Research Tasks

Read current authority first, then select the smallest mode. Use FAST_SCAN for next-route screening, FULL_DESIGN only for an already selected combination requiring the complete eight-part contract, and CLOSEOUT_SALVAGE after a valid result or NO-GO. Rank with ordinal 1–5 scores and record raw estimates for first-figure time, manuscript-claim time, and new runs. The Skill never supplies execution authority and cannot relax active-phase, provenance, evidence, budget, or ethics constraints.
