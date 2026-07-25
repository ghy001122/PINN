任务 ID：
Q2_REPOSITORY_REALIGNMENT_AND_PHASE0_GOVERNANCE

任务目标：全面浏览、审计并调整当前 PINN × 氧化物相变器件项目的本地工作区和 GitHub 云端仓库，使其适配最新PINN-based_Phase_Change_Materials_Research_Executive_Guide.md文档，同时完整保留历史证据、冻结资产、长期约束和有参考价值的失败结果。

本轮不是科学实验轮。不要训练 PINN，不要租 GPU，不要运行新的参数拟合、逆问题、文献曲线数字化、2.5D 正式求解或新结果实验。本轮只完成：

1. 全仓库只读审计；
2. 文件与目录职责重构；
3. 当前/历史内容隔离；
4. 重复和失效文档清理；
5. 权威状态链同步；
6. Phase 0 治理与复现基线闭环；
7. 云端提交和推送；
8. 生成下一阶段唯一执行入口。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
一、权威来源与解释优先级
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

将随本任务提供的文件：

PINN-based_Phase_Change_Materials_Research_Executive_Guide.md

视为最新研究战略、实验路由、止损规则和论文路线总指南。

若仓库中已经存在内容相同或近似的执行总指南：

- 先比较文件哈希和内容；
- 只保留一个当前权威版本；
- 建议规范路径：

  docs/research_strategy/pinn_phase_change_q2_sci_execution_guide.md

- 不得因文件名不同而保存多个内容重复副本；
- 其他入口文件只链接该权威指南，不重复粘贴全文。

解决信息冲突时按以下顺序裁决：

1. 当前配置、代码、测试和机器可读 JSON/CSV；
2. 当前冻结证据、manifest、claim matrix 和 evidence index；
3. 当前 PROJECT_STATE、active_phase 和权威执行合同；
4. 最新执行总指南；
5. 历史报告、历史 handoff 和旧规划文档。

执行总指南是“下一步战略”，不能把规划内容伪写成已经取得的科学结果。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
二、启动检查与安全边界
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

首先进入实际仓库根目录并执行：

git status --short
git branch --show-current
git rev-parse HEAD
git log -1 --oneline
git remote -v
git fetch origin
git rev-parse origin/main

要求：

- 确认当前分支；确认 HEAD 与 origin/main 的关系；
- 记录 base SHA；

禁止：

- git reset --hard；
- git clean -fd；
- force push；
- rebase 或改写已发布历史；
- 删除未提交文件；
- 修改 frozen Ground Truth；
- 为整理目录而修改历史结果数值；
- 把旧失败结论改写成新路线正面结果。

若工作区干净且 HEAD 与远端一致，创建一个迁移前安全锚点；已有等价锚点则不重复创建：

pre-workspace-realignment-20260725-<short_sha>

使用 annotated tag，并在最终验证通过后推送该 tag。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
三、必须阅读的最小权威集合
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

先读以下文件，不要一开始遍历所有长报告：

1. PINN-based_Phase_Change_Materials_Research_Executive_Guide.md；
2. AGENTS.md；
3. CODEX_CONTEXT.md；
4. PROJECT_GOAL.md；
5. PROJECT_STATE.md；
6. NEXT_ACTIONS.md；
7. README.md；
8. docs/research_strategy/active_phase.md；
9. docs/project_prompts/critical_research_mode.md；
10. docs/research_strategy/context_loading_policy.md；
11. docs/research_strategy/context_index.md；
12. docs/project_state/current_evidence_index.md；
13. docs/method_equations.md；
14. EXPERIMENT_REGISTRY.md；
15. DATASET_REGISTRY.md（若存在）；
16. FIGURE_REGISTRY.md（若存在）；
17. docs/paper 和 docs/manuscript 中的当前 claim、figure、table 和 go/no-go 入口。

随后再按需读取历史报告、旧 handoff、旧稿件和旧路线代码。

不要把所有文档全文一次性加载进上下文。先用文件名、标题、git grep、引用关系和内容摘要完成分层审计，再打开需要处理的文件。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
四、建立全仓库文件清单和引用图
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

对所有 tracked files 建立机器可读清单，至少记录：

- path；
- file type；
- size；
- SHA256；
- last Git commit；
- 当前是否被其他文件引用；
- 所属路线；
- 当前/历史属性；
- 是否是冻结证据；
- 是否含唯一信息；
- 建议 disposition；
- disposition 理由；
- replacement 或新入口。

分类只能使用：

KEEP_CURRENT
KEEP_EVERGREEN
UPDATE
MERGE
ARCHIVE
DELETE_DUPLICATE
DELETE_GENERATED
LEAVE_IN_PLACE_FROZEN
REVIEW_BLOCKED

输出：

outputs/tables/repository_file_disposition.csv
outputs/tables/repository_realign_phase0_summary.json

在移动或删除任何文件前，必须完成：

- git grep 引用检查；
- Markdown 链接检查；
- Python import 检查；
- 配置、脚本、测试、manifest 和报告中的路径检查；
- 同内容文件的 SHA256 去重；
- 对近似重复文档检查是否含唯一结论、指标或历史语义。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
五、文件处置判定规则
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

A. 必须保留的内容

以下内容不得因与新主线不直接相关而删除：

1. AGENTS.md 中长期使命、工程纪律和学术边界；
2. Critical Research Mode；
3. 时间约束和纯软件路线等长期背景；
4. frozen Ground Truth v1.1 及其 hash、manifest、验收报告；
5. 已锁定的 gamma_sub 条件性结果；
6. 完整 PINN 失败证据和稀疏端口不可辨识性证据；
8. M40/M40R、M44、OASIS、SID/EC-OQ 等失败或无效合同的历史记录；
9. 所有机器可读实验结果和支持历史 claim 的表格；
10. 来源合同、数据 provenance、文献参数语义和材料族边界；
11. 真实引用关系、许可证和第三方代码来源；
12. 可复用的 FVM、端口积分、RC、能量账本、SVD、principal-angle、接口和白盒材料核组件。

这些内容即使不再是新论文主线，也应作为：

- historical baseline；
- negative evidence；
- reviewer defense；
- reusable implementation pattern；
- provenance record。

B. 应更新的内容

重点检查并同步：

- README.md；
- PROJECT_GOAL.md；
- CODEX_CONTEXT.md；
- PROJECT_STATE.md；
- NEXT_ACTIONS.md；
- docs/research_strategy/active_phase.md；
- docs/research_strategy/current_research_handoff.md；
- docs/research_strategy/context_index.md；
- docs/project_state/current_evidence_index.md；
- docs/project_state/repo_tree.md；
- docs/project_state/file_inventory.md；
- docs/project_state/reproducibility.md；
- docs/method_equations.md；
- 当前 claim matrix；
- manuscript README；
- submission_go_no_go.md；
- EXPERIMENT_REGISTRY.md；
- DATASET_REGISTRY.md；
- FIGURE_REGISTRY.md；
- pyproject.toml 的项目描述。

C. 应归档的内容

归档而不是删除：

- 已被新指南替代、但含独特研究判断的旧路线规划；
- 历史 handoff；
- 历史 manuscript v1/v2；
- 已结束阶段的 next_task 文档；
- 旧主线的 submission-lock 文档；
- 旧的完整论文框架和 figure/table 规划；
- 失效但具有审计价值的研究构想；
- 带有历史指标或失败原因的 Codex 报告。

建议按实际情况建立：

docs/archive/
├─ handoffs/
├─ legacy_1d_route/
├─ retired_real_device_bridges/
├─ historical_manuscripts/
├─ superseded_strategy/
└─ README.md

归档目录 README 必须说明：

- 为什么归档；
- 其历史阶段；
- 当前是否有科学投票权；
- 当前替代入口；
- 哪些负面结论仍然有效。

优先使用 git mv，以保留文件历史。

D. 可删除的内容

只允许删除：

- SHA256 完全一致的重复副本；
- 空文件或无内容占位符；
- 明确生成的临时文件、缓存、日志碎片；
- 已被完整合并、无任何独特内容、无引用、无证据用途的重复说明文档；
- 已确认不属于复现包且可由脚本重新生成的误提交产物；
- 失效且没有任何历史、来源、指标或审稿防御价值的纯工作草稿。

每个删除项必须在 disposition CSV 中记录：

- 原路径；
- 删除原因；
- 检查过的引用；
- 替代文件；
- 是否可通过 Git 历史恢复。

“与新路线无关”本身不构成删除理由。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
六、建立清晰的当前权威状态链
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

完成整理后，当前状态必须形成以下单向入口：

README.md
  -> CODEX_CONTEXT.md
  -> PROJECT_GOAL.md
  -> PROJECT_STATE.md
  -> docs/research_strategy/active_phase.md
  -> NEXT_ACTIONS.md
  -> current_evidence_index.md
  -> 执行总指南 / 当前技术合同

具体要求：

1. AGENTS.md
   - 保留长期使命、伦理、工程和执行纪律；
   - 不塞入大量阶段性指标；
   - 不重复整份执行指南。

2. CODEX_CONTEXT.md
   - 保持 low-token；
   - 只写当前主线、证据边界、当前 gate、单一优先任务和禁止主张；
   - 链接执行总指南和按需上下文索引；
   - 删除或修正旧 phase、旧唯一主线、旧 submission-lock 冲突。

3. PROJECT_GOAL.md
   - 明确三档可降级路线：
     R1 HysGeo-Hybrid-PINN；
     R2 GeoPhase-HomoMoE-PINN；
     R3 条件式 observable-subspace/OQ；
   - 明确 R1 是最低必须完成路线；
   - 明确项目结果仍为 literature-guided synthetic numerical digital-twin evidence。

4. PROJECT_STATE.md
   - 开头必须是当前事实，不是历史愿景；
   - 清楚区分：
     current evidence；
     historical retained evidence；
     unimplemented candidates；
     forbidden claims；
   - 不得把执行指南中的计划写成已完成结果。

5. active_phase.md
   - 根据审计后的真实证据，设置“最早尚未通过的阶段”；
   - 本任务完成后：若 Phase 0 所有 gate 通过，则当前下一阶段应为 Phase 1 独立 2.5D 参考求解器；若 Phase 0 未通过，则继续保持 Phase 0，并明确唯一阻塞；
   - 不得仅因旧文档写了 E0/G0 就假定治理已经通过。
   
6. NEXT_ACTIONS.md
   - 顶部只保留当前唯一执行队列；
   - 历史 next actions 移入 archive 或历史区；
   - 不允许多个互相冲突的“下一步”同时存在；
   - 若 Phase 0 通过，下一步唯一任务为：独立 2.5D FVM/implicit reference solver。
   
7. current_research_handoff.md
   - 只保留一个当前 handoff；
   - 内容应短于完整执行指南；
   - 链接 PROJECT_STATE、active_phase、执行总指南和 evidence index；
   - 旧 handoff 统一归档。

8. current_evidence_index.md
   - 按 current / historical / candidate / forbidden 四区组织；
   - 历史证据可定位，但不会被误认为新路线结果。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
七、代码和目录结构调整原则
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

执行总指南推荐 responsibility-based 结构：

src/pinnpcm/
  physics/
  solvers/
  pinn/
  inverse/
  evaluation/

但不得为了目录美观而大规模搬迁仍被历史证据调用的代码。

原则：

1. 现有可运行历史代码默认留在原路径；
2. 对新路线使用清晰的 geophase / hysgeo 命名；
3. 新代码按职责进入 physics、solvers、pinn、inverse、evaluation；
4. 不创建没有实现的空模块或占位脚本；
5. 不把旧模块简单改名后声称为新方法；
6. 历史模块可通过 registry、README 或 docstring 标记 legacy/baseline；
7. frozen evidence 使用的路径尽量不移动；
8. 必须移动时，完整更新所有引用、测试和 manifest，并验证 hash/结果身份；
9. 新输出必须与历史输出隔离，例如：

   outputs/tables/geophase_*/
   outputs/figures/geophase_*/
   data/processed/geophase_*/

10. 不移动或重写冻结 GT 目录。

本轮只调整结构、入口和文档，不实现以下候选模块：

- transition-localized MoE；
- homotopy training；
- observable-subspace inverse；
- refusal head；
- NbO2 cross-model；
- 新 2.5D 正式求解器。

允许保留或整理现有配置合同，但禁止生成伪结果。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
八、历史稿件和 claim 处理
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. 旧 manuscript v1/v2 必须保留为历史快照；
2. 不得修改历史稿件使其看起来属于新路线；
3. 可移动到 historical_manuscripts 或增加明确 legacy banner；
4. 当前 manuscript 入口必须说明：
   - 新稿尚未由 R1/R2/R3 证据生成；
   - 旧稿只是 fallback/history；
5. 当前 claim matrix 中分别建立：
   - R1 candidate claims；
   - R2 candidate claims；
   - R3 candidate claims；
6. 所有新候选 claim 当前状态必须为 forbidden 或pending_direct_evidence；
7. 保留历史 supported / qualified_supported / failed_but_informative 状态；
8. 不允许因路线改变而升级历史科学结论。

持续使用四级 claim：

supported
qualified_supported
failed_but_informative
forbidden

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
九、Phase 0 基线验证
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

本轮只运行治理和复现验证。

为了效率，只运行：

A. 修改前一次完整基线：
- 全 pytest；
- governance audit；
- frozen GT hash audit；
- 当前可用的 evidence integrity/readiness 检查；
- 记录通过数、失败数和耗时。

B. 修改中：
- 只运行受影响的 targeted tests；
- Markdown/link/reference/import 检查；
- 不反复运行完整科学回归。

C. 修改后一次完整回归：
- 全 pytest；
- governance audit；
- frozen hash audit；
- git diff --check；
- 检查工作区副作用；
- 检查已删除或移动路径无悬空引用。

Phase 0 通过条件：

- HEAD/远端状态明确；
- 所有未知未提交更改已处理；
- frozen GT hash 与 manifest 不变；
- 当前权威文档无路线冲突；
- 旧稿和旧路线不会被误认为当前主线；
- 只有一个当前 handoff；
- 只有一个当前 active phase；
- 只有一个当前 next action；
- 重要历史证据可定位；
- 重复文件已处理；
- 删除项均有审计记录；
- 测试结果不低于修改前基线，或任何差异均有明确原因；
- git diff --check 通过；
- 工作区最终干净。

任一 frozen asset 非预期变化：
立即停止，不进入后续提交。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
十、必须生成或更新的交付物
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

至少生成：

1. 规范化执行总指南：
   docs/research_strategy/pinn_phase_change_q2_sci_execution_guide.md

2. 当前 handoff：
   docs/research_strategy/current_research_handoff.md

3. 最新目录树：
   docs/project_state/repo_tree.md

4. 文件职责与处置清单：
   docs/project_state/file_inventory.md
   outputs/tables/repository_file_disposition.csv

5. 历史归档索引：
   docs/archive/README.md
   或更新现有 legacy_document_index.md

6. 机器可读总结：
   outputs/tables/repository_realign_phase0_summary.json

7. 本轮 Codex 报告：
   docs/codex_reports/repository_realign_phase0_2026-07-25.md

报告头部必须包含机器可检查字段：

task_id
base_sha
final_sha
branch
changed_files
moved_files
deleted_files
tests
frozen_gt_modified
evidence_type
claim_status
current_phase
next_single_priority
push_status

报告正文至少包含：

- 实际审计范围；
- 当前仓库问题；
- 文件分类统计；
- 具体移动、更新、合并和删除；
- 保留了哪些历史资产及原因；
- 哪些旧结论仍有效；
- 哪些新候选仍 forbidden；
- 修改前后测试；
- 云端同步状态；
- 距离论文交付目标还有什么；
- 下一唯一任务。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
十一、Phase 1 下一任务准备
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

本轮不要实现 Phase 1 求解器。

若 Phase 0 通过：

- 将 active phase 或 NEXT_ACTIONS 正确指向 Phase 1；
- 确保仓库中只有一个 Phase 1 执行合同；
- 若已有 geophase E0/2.5D reference contract，审计并与新指南对齐，不重复创建；
- 若没有，创建一个简洁的 next-task 合同，但不创建空代码；
- 下一任务必须是：

  独立、守恒、与 PINN residual 实现分离的Qiu-inspired VO2 真实 x-y + K-state vertical memory 2.5D FVM/implicit reference solver。

其 gate 至少包括：

- manufactured electrical/thermal solution；
- terminal current conservation；
- full energy ledger；
- mesh refinement；
- time-step refinement；
- K-state passivity 与高阶参考对齐；
- zero-drive/uniform/single-dual-device limits；
- 文献趋势 sanity；
- 所有 required gate 全部通过后才允许 PINN。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
十二、提交与云端同步
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

不要产生大量零碎提交。

最多使用两个逻辑提交：

1. Archive legacy routes and realign workspace
2. Align governance with Q2 2.5D PINN execution guide

若文件移动和权威文档更新高度耦合，也可使用一个原子提交。

提交前执行：

git diff --check
git status --short
完整最终测试
frozen GT hash audit
悬空链接和引用检查

提交信息必须准确，不得写“完成 GeoPhase 方法”或“完成 2.5D solver”。

推送：

- 正常 push 当前授权分支；
- 不 force push；
- 推送迁移前安全 tag；
- 推送最终提交；
- 再次 fetch；
- 核验 HEAD == origin/<branch>；
- 核验工作区干净。

若 GitHub Actions 存在，记录 workflow 状态。若不存在，明确写“未配置或无可见云端 CI”，不得把本地测试称为 GitHub CI。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
十三、最终回复格式
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

最终回复控制在一页左右，只报告：

1. base SHA；
2. final SHA；
3. branch；
4. archived / merged / deleted / updated 文件数量；
5. 最关键的目录和权威入口变化；
6. 修改前后测试结果；
8. 当前 claim 是否有变化；
9. 云端是否同步；
10. 工作区是否干净；
11. 当前 active phase；
12. 下一唯一任务。

不要复述整个研究指南。不要声称取得任何新科学结果。不要在本轮启动 Phase 1、PINN 训练或 inverse。