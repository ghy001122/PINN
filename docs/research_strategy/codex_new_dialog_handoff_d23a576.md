# PINN 相变材料项目：Codex 新对话完整交接说明

> Governance overlay: current authority and low-token routing are defined by `AGENTS.md`, `PROJECT_GOAL.md`, `CODEX_CONTEXT.md`, `docs/research_strategy/active_phase.md`, and `docs/research_strategy/context_loading_policy.md`. This document remains the single complete historical handoff; its embedded HEAD is the v10 handoff anchor, not a live status field.
> **建议放置路径**：`docs/research_strategy/codex_new_dialog_handoff_d23a576.md`  
> **本地工作区**：`E:\Python demo\PINN`  
> **GitHub 仓库**：`ghy001122/PINN`  
> **分支**：`main`  
> **交接锚点提交**：`d23a576b2d8bb17a1d1f72a0cf81cc457d42e048`  
> **锚点提交信息**：`Build control-volume OASIS and repair inverse v10`  
> **目标模式**：`Q2_SCI_DELIVERY_MODE`  
> **唯一最终交付目标**：形成一篇证据充分、逻辑闭合、可复现、符合学术伦理的二区 SCI 论文初稿、投稿包与审稿防御材料。该目标是项目管理目标，不代表预先保证期刊录用。

---

## 0. 新对话启动时必须先做什么

新 Codex 对话不得直接开始改代码或开新实验。先在工作区完成以下启动检查：

```powershell
cd "E:\Python demo\PINN"
git status --short
git branch --show-current
git rev-parse HEAD
git log -1 --oneline
```

预期：

- 当前分支为 `main`；
- 当前 HEAD 至少包含交接锚点 `d23a576b2d8bb17a1d1f72a0cf81cc457d42e048`；
- 工作树应干净，或必须先说明未提交更改的来源；
- 不得使用 `git reset --hard`、强制覆盖或删除用户本地未提交文件来“恢复一致”。

随后按顺序阅读：

1. 本交接文档；
2. `AGENTS.md`；
3. `CODEX_CONTEXT.md`；
4. `docs/research_strategy/active_phase.md`；
5. `docs/project_prompts/critical_research_mode.md`；
6. `docs/research_strategy/context_loading_policy.md`；
7. 只有任务需要时，再按本文后续索引加载 `PROJECT_STATE.md`、`NEXT_ACTIONS.md`、注册表、报告、代码和文献。

首次回复用户前，必须用不超过一页的内容确认：

- 当前 HEAD；
- 工作树状态；
- 当前论文主线；
- v10 的 P0–P4 gate 状态；
- 下一步最值得做的一个任务；
- 当前绝对不能写入论文的过度主张。

---

## 1. 用户背景与项目现实约束

用户是光电学院电子信息方向博士生，约一年后毕业，导师直接指导有限，需要尽快完成一篇质量较好的 SCI 论文。用户具备 Python、PyTorch、神经网络和软件算法基础，但微纳加工、流片、实体器件和探针台测量能力薄弱。因此项目自始至终优先采用：

\[
\text{纯软件数值数字孪生}
+\text{物理约束神经网络}
+\text{稀疏观测反演}
+\text{可辨识性审计}
\]

而不是把成功依赖于短期内无法获得的器件加工或实验数据。

用户反复强调：

- 时间紧，研究必须高效率、面向论文交付；
- 可以组合、重构和改进已有方法，但不得抄袭、捏造或伪造创新；
- 工作量、创新性、应用性和进度必须平衡；
- 不得为了“稳妥”而停止一切高风险探索；
- 也不得为了“看起来高级”而堆叠没有证据价值的模块；
- 所有算法、物理结构、方程、参数和文献必须有真实依据；
- 负面结果可以保留，但必须转化为可辨识性边界、适用范围或审稿防御；
- 目标是二区 SCI，而不是完成一个代码玩具或无休止的研究分支。

### 1.1 Goal 模式

整个项目以 `Q2_SCI_DELIVERY_MODE` 运行。任何任务必须至少服务于以下一项：

1. 论文核心 claim；
2. 主图或主表；
3. 关键方法方程；
4. 高质量消融或 baseline；
5. 泛化、鲁棒性或不确定性证据；
6. 审稿人可能提出的尖锐问题；
7. 明确且可发表的 negative result；
8. 可复现性、证据链或投稿包。

不能说明服务对象的任务，应缩减、延后或删除。

---

## 2. 项目研究对象与当前论文定位

### 2.1 总体研究对象

研究对象为氧化物相变/忆阻器数字孪生，涉及：

- \(VO_2\)、\(NbO_2\) 等强电热相变材料；
- \(V_2O_5\)、\(Nb_2O_5\)、NbO\(_x\) 等氧化物电阻开关/缺陷体系；
- 电—热—相态—缺陷耦合；
- 多层三明治器件、电极、热势垒、衬底和外部 RC 电路；
- 稀疏端口观测下的参数反演和可辨识性；
- 相变阈值附近的 stiffness cliff 与 spectral bias；
- reduced 2D、多端口观测和跨结构泛化。

### 2.2 当前最稳的论文主线

当前最成熟、最可防御的主线不是“完整隐场恢复”，也不是“F-SPS-PINN 全面优越”，而是：

\[
\boxed{
\text{synthetic numerical digital-twin benchmark}
+\text{sparse-port identifiability audit}
+\text{identifiability-guided target-space reduction}
+\text{calibration-gated constrained }\gamma_{\mathrm{sub}}\text{ inversion}
}
\]

可概括为：

> 面向相变/忆阻器数字孪生的可辨识性引导稀疏端口反演；当完整隐场在端口积分观测下不可唯一恢复时，通过先验标定和目标空间收缩，恢复更稳定的有效热耗散参数，并用混杂、协议、噪声、先验宽度和 off-grid 审计界定可解区域。

### 2.3 OASIS 分支的正确定位

OASIS 多层、多域、二维、多端口分支的作用是：

- 提升物理器件结构真实性；
- 回答“1D synthetic 是否过于简单”；
- 验证多层界面、横向耦合和多端口 observability；
- 探索真正 PDE/CV 约束神经求解器；
- 为未来更高档次方法论文或扩展章节提供基础。

截至交接锚点，OASIS 仍是**补充方法开发与负面边界证据**，不能替代 \(\gamma_{\mathrm{sub}}\) 主线。

---

## 3. 交接锚点 `d23a576...` 的真实状态

该提交完成 control-volume multidomain OASIS and inverse repair v10。所有结果均为 synthetic numerical digital-twin evidence，frozen Ground Truth v1.1 未修改。

### 3.1 P0：物理语义与器件拓扑

状态：`qualified_supported`

已完成：

- 电学域和热学域分离；
- 电流在 BE 终止，substrate 仅进入热学域；
- 删除此前通过超高 substrate 电导绕过电学拓扑的错误；
- VO\(_2\) normalized-activated profile 与 literature-anchored profile 分离；
- NbO\(_2\) 主路径采用 field-dependent Poole–Frenkel + electrothermal feedback，不再依赖无依据的主路径 phase-fraction multiplier；
- 外部 RC excitation 使用电路 ODE 积分，而不是把外加正弦波伪称为自治振荡；
- threshold 与 holding voltage 分支提取，零/零结果不能通过 activation gate；
- SnSe 的 \(k\)、\(\sigma\)、厚度和存在性只作为 engineering-prior sensitivity，不是测得参数。

v9 激活审计的参考结果：

- VO\(_2\) activation rate：`0.8888888888888888`；
- NbO\(_2\) activation rate：`0.8888888888888888`；
- median max \(\Delta T\)：`15.140535460408756 K`；
- median \(\Delta m\)：`0.7834880687603829`；
- median conductance ratio：`2.561625048607053`。

这些结果证明 reduced forward 不再退化，但不等于真实器件定量校准。

### 3.2 P1：Control-volume multidomain neural training

状态：`failed_but_informative`

严格结果：

- median \(E_T=0.37563055753707886\)；
- median \(E_m=0.06811526417732239\)；
- median interface residual `106.15460205078125`；
- success rate `0.0`；
- gate：失败。

核心含义：

- v9 中“loss 下降即成功”的 smoke gate 已被否定；
- 真实 CV/mortar 路径暴露了残差量纲、尺度失衡、边界面处理和优化路径问题；
- ordered anchor-driven surrogate 更容易拟合，但不能冒充严格 PINN 求解成功；
- 当前 P1 仍依赖 simulator field anchors，正确名称应是 field-anchored CV physics-regularized neural surrogate/audit，而不是 data-free PDE solver。

### 3.3 P2：主动协议与 noisy inverse

状态：`failed_but_informative`

已修复此前“加噪后没有重新反演”的逻辑错误。v10 对每个 noisy target 重新生成和反演，并按材料族拆分参数块。

当前结果：

- NbO\(_2\)：\(R_c/E_a\) 块较稳定；热块 \(R_{\mathrm{th,eff}}/\tau_{\mathrm{th}}\) 失败；
- VO\(_2\)：局部 \(T_c^\uparrow/T_c^\downarrow/w\) 块误差低；热块 success rate 低于 `0.70`；
- 被选协议对完整材料参数向量仍 rank-deficient；
- interval coverage 未过 gate；
- 当前主要是 nominal prior 附近的局部线性化可恢复性，不是全先验域 nonlinear inverse。

不能把“总体 median error 较低”用于掩盖失败参数块。

### 3.4 P3：Segmented-electrode \(y-z\) forward

状态：`qualified_supported`

已实现有限体积电势求解：

\[
\nabla\cdot(\sigma\nabla\phi)=0,
\]

配合 segmented top/side electrode Dirichlet faces、bottom ground、未分配边界绝缘，以及边界通量积分端口电流。

结果：

- uniform-series limit relative error：`7.666968074108158e-12`；
- current-balance error：报告案例中低于 `1e-12`；
- synthetic local observability rank：single terminal `1`，segmented terminals `3`。

这只支持多端口 forward/observability implementation；没有运行完整 PDE-constrained field inverse，不能声称 full 2D hidden-field recovery。

### 3.5 P4：STL/Fourier/F-SPS

状态：`not_run_blocked`

原因：P1 基础求解器未过 gate，不能在失败底座上声称算法优越。当前仍不支持：

- canonical full STL-PINN reproduction；
- Seiler-style multi-head STL positive claim；
- LoRA-STL positive claim；
- universal F-SPS/Fourier superiority。

### 3.6 泛化

状态：`preflight_only`

当前 reduced ridge/OOD preflight 显示：

- geometry interpolation 相对较好；
- stack、interface、pulse holdout 较差；
- cross-material transfer 极差；
- 结论支持“共享结构框架 + 材料专属本构专家”，不支持 VO\(_2\)/NbO\(_2\) 无条件共用单一本构网络。

---

## 4. 项目历史研究进程与关键决策

### 阶段 A：项目骨架与 Ground Truth

建立 Python 3.11、PyTorch、SciPy、pytest 的可复现工程；构建 1D finite-volume + Radau Ground Truth，输出：

\[
x,t,V,I,G,c_v,T,m,E,\phi,\sigma.
\]

Ground Truth v1.1 通过验收后冻结，作为后续所有逆问题和算法比较的统一判卷器。

### 阶段 B：PINN inverse v0/v1/v1.1

- v0：建立可运行训练闭环，包含 full/weak/port-only field-anchor ablation；
- v1：加入近似热、状态、缺陷和 conductivity residual；
- v1.1：加入 residual balancing、warmup 等；
- 结果：\(\Delta T\) 长期为主要误差，free \(\log\sigma\) 容易走非物理捷径，端口数据不能唯一恢复完整隐藏场。

关键决策：停止把“从稀疏端口唯一恢复 \(T,c_v,m,\sigma\)”作为当前主线。

### 阶段 C：可辨识性审计与 \(\gamma_{\mathrm{sub}}\) 目标收缩

发现 \(G(t)\) 与 mean conductivity 近乎完全相关，但对内部场的约束主要是积分层面的。项目转向只估计有效衬底热耗散参数：

\[
\gamma_{\mathrm{sub}},
\]

并冻结或约束微观动力学参数。

完成：

- scalar identifiability；
- confounding audit；
- constrained inversion；
- off-grid continuous refinement；
- observation-count/noise robustness；
- prior-width sweep；
- profile likelihood；
- joint nuisance release；
- protocol observability；
- auxiliary observation sweep。

### 阶段 D：\(T_{\mathrm{sw}}\) calibration gate 与 protocol 证据链

关键发现：\(T_{\mathrm{sw}}\) 是 \(\gamma_{\mathrm{sub}}\) 可辨识性的主要 confounder。宽先验或 mismatch 可造成超过 100% 的系统偏差；独立标定或窄先验可以显著降低误差。

重要结论：

- calibration gain 远大于 protocol gain；
- protocol 是 secondary robustness enhancer，不是主要可辨识性来源；
- response-surface dense points 由有限 simulator-backed source points 插值得到，必须明确限定；
- 已增加 ODE-backed spot-check/robustness，但不得把 synthetic tolerance 当作真实实验仪器要求。

### 阶段 E：F-SPS、Fourier 与 stiffness

实现或审计：

- white-box VO\(_2\) conductivity closure；
- Fourier feature/pyramid 接口；
- dynamic residual gate；
- differentiable oscillation metrics；
- phase-transition stress preflight；
- Fourier on/off；
- continuation/scale-aware stiffness handling；
- mini-STL-style transfer。

真实结论：

- white-box closure 数值可训练，但 near-threshold 仍困难；
- Fourier on/off 未证明普遍改善；
- stiffness-aware continuation/scale-aware 在 reduced benchmark 上可缓解 stiffness cliff；
- mini-STL 是 lightweight transfer audit，不是 full STL-PINN reproduction；
- F-SPS 不得作为当前论文主创新。

### 阶段 F：Reduced 2D 与 OASIS 多层器件

逐步从 quasi-2D proxy 推进至：

- literature-backed multilayer sandwich；
- TE/PCM/SnSe barrier/BE/substrate；
- 独立 interface \(R_c/R_{\mathrm{th}}\)；
- 横向导热和耦合；
- material-family-specific kernels；
- segmented-electrode finite-volume forward；
- control-volume neural residual；
- active protocol inverse。

关键经验：真实结构复杂度增加不会自动解决可辨识性，也不会自动证明神经网络优于数值求解器。

---

## 5. 物理模型与方程边界

### 5.1 冻结 1D GT 主体

主 benchmark 是 Nb/NbO\(_x\)/V\(_2\)O\(_5\)/Ni-inspired reduced device，不是 fabricated device replication。典型约束包含：

电流连续性：

\[
\nabla\cdot\left(\sigma\nabla\phi\right)=0,
\qquad
\mathbf J=-\sigma\nabla\phi.
\]

热方程：

\[
\rho c_p\frac{\partial T}{\partial t}
=\nabla\cdot(k\nabla T)+\mathbf J\cdot\mathbf E-Q_{\mathrm{loss}}.
\]

相态/内部状态动力学采用 reduced kinetic closure，具体实现和默认参数必须以 `docs/method_equations.md`、配置和现有代码为准，不得凭记忆改写。

### 5.2 多层 OASIS 结构

电学域：

\[
\Omega_e=\Omega_{\mathrm{TE}}\cup\Omega_{\mathrm{PCM}}
\cup\Omega_{\mathrm{barrier}}\cup\Omega_{\mathrm{BE}}.
\]

热学域：

\[
\Omega_T=\Omega_e\cup\Omega_{\mathrm{substrate}}.
\]

界面电学条件：

\[
J_{n,i}+J_{n,j}=0,
\qquad
\phi_i-\phi_j-R_{c,ij}J_{n,i}=0.
\]

界面热学条件：

\[
q_{n,i}+q_{n,j}=0,
\qquad
T_i-T_j-R_{\mathrm{th},ij}q_{n,i}=0.
\]

外部 RC 电路：

\[
C\frac{dV_{\mathrm{dev}}}{dt}
=\frac{V_{\mathrm{in}}-V_{\mathrm{dev}}}{R_L}
-I_{\mathrm{dev}}(V_{\mathrm{dev}},T,\text{state}).
\]

### 5.3 材料机理不得混用

- VO\(_2\)：允许 branch-memory hysteretic thermal transition、metallic phase fraction 和对应 conductivity closure；
- NbO\(_2\)：主路径为 field-dependent Poole–Frenkel + electrothermal feedback；若引入 effective conductive fraction，必须明确它不是未经证实的真实相分数；
- SnSe：当前只作为低热导、较高电导的 thermal-barrier trend/engineering prior；
- V\(_2\)O\(_5\)/Nb\(_2\)O\(_5\)：更适合按氧化物电阻开关、缺陷/氧空位迁移体系描述，不得无依据地等同于主流光子 PCM。

任何物理方程改变必须同步更新 `docs/method_equations.md`。

---

## 6. 工作区结构与各类文件作用

### 6.1 顶层治理与状态文件

| 文件 | 作用 | 权威级别 |
|---|---|---|
| `AGENTS.md` | 全局使命、学术伦理、工程规则、Critical Research Mode、Codex 行为约束 | 最高 |
| `CODEX_CONTEXT.md` | 非平凡任务的低 token 第一读；当前阶段、主线、claim boundary | 最高且应精简 |
| `PROJECT_STATE.md` | 项目累计状态、历史证据和当前结论 | 状态总账 |
| `NEXT_ACTIONS.md` | 当前和历次阶段的下一步；最新章节优先 | 执行队列 |
| `RESEARCH_LOG.md` | 按时间记录研究变更与结论 | 历史日志 |
| `EXPERIMENT_REGISTRY.md` | 实验配置、脚本、状态和结果索引 | 实验证据链 |
| `DATASET_REGISTRY.md` | 数据、表格、来源、synthetic/external 属性 | 数据证据链 |
| `FIGURE_REGISTRY.md` | 图、来源表、论文位置和 claim 关系 | 图表证据链 |
| `README.md` | 项目入口、环境、运行方式和高层目录 | 用户入口 |

### 6.2 `docs/research_strategy/`

- `active_phase.md`：当前授权研究阶段和 P0–P4 gate；
- `context_loading_policy.md`：Tier 0–4 的按需读取规则；
- `context_index.md`：上下文和报告快速索引；
- `codex_workflow_rules.md`：Codex 执行、验证和 Windows 规则；
- `current_research_handoff.md`：旧交接，内容停留在早期 \(\gamma_{\mathrm{sub}}\) 阶段，已明显过时；本文件应替代或重写它；
- `phase_change_pinn_sci_sprint_blueprint.md`：长期架构和论文规划，不是结果报告；
- `next_task_*.md`：具体任务脚手架，只有当前任务相关时才读。

### 6.3 `docs/project_prompts/` 和 `docs/templates/`

- `critical_research_mode.md`：全局批判性、探索优先、claim-gated 规则；
- `docs/templates/codex_critical_preamble.md`：设计新 Codex 任务时的标准前言；
- 任何新高风险分支必须先定义成功阈值、失败解释、allowed claim 和 forbidden overclaim。

### 6.4 `docs/project_state/`

- `repo_tree.md`：工作区目录树和阶段性新增文件；
- `file_inventory.md`：核心代码、脚本、配置、测试和证据文件的职责；
- `latest_changes.md`：各阶段 scope、changed、result；
- `reproducibility.md`：复现命令、环境和输出约定。

### 6.5 `docs/paper/` 与 `docs/manuscript/`

包含：

- manuscript outline；
- method/results/limitations 草稿；
- claim stress-test matrix；
- claim gate resolution matrix；
- figure/table mapping；
- reviewer-defense matrix；
- allowed/forbidden wording。

这些文件是“论文逻辑链”，不能把未通过 gate 的结果写成主结果。

### 6.6 `docs/codex_reports/`

每次非平凡 Codex 任务的最终审计报告。报告至少应包含：

- 实际 final commit SHA；
- base commit；
- changed files；
- 运行和验证命令；
- 关键结果；
- frozen GT 是否修改；
- synthetic/external/experimental 属性；
- supported/qualified/failed/forbidden claims；
- 剩余问题。

禁止再写 `this squashed commit; see git log` 代替实际 SHA。

### 6.7 `configs/`

所有实验参数、物理先验、扫描范围、seed、epoch、noise、gate 均放 YAML。不得在脚本中散落 opaque magic numbers。

### 6.8 `src/pinnpcm/`

- `physics/`：GT、参数、本构、导电、热学、电静力、多层结构、多端口 \(y-z\) 求解器；
- `pinn/`：网络、输出变换、物理 residual、loss、F-SPS/OASIS components；
- `experiments/`：2D claim-resolution 等实验逻辑；
- `baselines/`：非 PINN 或简化 baseline；
- `utils/`：YAML、JSON、路径、随机种子；
- `visualization/`：matplotlib 绘图。

当前重点文件：

- `src/pinnpcm/physics/multilayer_sandwich.py`；
- `src/pinnpcm/physics/multiterminal_yz.py`；
- `src/pinnpcm/pinn/oasis_components.py`；
- `src/pinnpcm/pinn/physics_residuals.py`；
- `src/pinnpcm/pinn/network.py`；
- `src/pinnpcm/physics/params.py`。

### 6.9 `scripts/`

CLI 入口和审计流程。命名通常为：

- `run_*`：生成或运行；
- `train_*`：训练；
- `audit_*`：审计、扫描、claim gate；
- `build_*`：生成图、表、矩阵或 manuscript artifact；
- `fit_*`：外部曲线拟合；
- `ingest_*`：带 provenance 的数据导入。

v10 关键脚本：

- `audit_physical_semantics_v10.py`；
- `train_cv_multidomain_oasis_v10.py`；
- `audit_active_protocol_design_v3.py`；
- `audit_multiterminal_yz_forward_v10.py`；
- `audit_oasis_generalization_v10.py`；
- `audit_oasis_algorithms_v10.py`。

### 6.10 `tests/`

每个新增 config/script/core behavior 必须有 pytest。测试不仅检查“文件存在”和“finite”，还应检查：

- 物理守恒；
- gate 逻辑；
- noisy target 是否真的重新反演；
- protocol rank；
- frozen input hash/mtime；
- 输出 schema；
- baseline budget 一致；
- 无 target leakage；
- claim 状态不会被错误升级。

### 6.11 `data/` 与 `outputs/`

- `data/raw/`：未来真实实验原始数据；
- `data/external/` 或 `data/literature/`：公开/文献数字化曲线，必须有 provenance；
- `data/processed/`：合成 benchmark；
- `outputs/tables/`：轻量 JSON/CSV，允许提交并用于云端审查；
- `outputs/figures/`、`logs/`、`checkpoints/`：通常被忽略，不提交大型产物。

### 6.12 `references/`

- `references/project_sources/README.md`：项目来源文件和本地 reference pack 的来源说明；
- `references/papers/PAPER_REGISTRY.md`：论文索引、用途、可支持的方程/参数/claim；
- 完整论文优先从 Google Drive `PINN`、`Phase_change_materials` 文件夹或联网检索获得；不得只凭二次综述写具体事实。

---

## 7. 项目中的四条链必须同步

### 7.1 全局治理链

\[
\texttt{AGENTS.md}
\rightarrow
\texttt{critical\_research\_mode.md}
\rightarrow
\texttt{codex\_workflow\_rules.md}
\rightarrow
\texttt{context\_loading\_policy.md}
\]

### 7.2 状态链

\[
\texttt{CODEX\_CONTEXT.md}
\rightarrow
\texttt{active\_phase.md}
\rightarrow
\texttt{PROJECT\_STATE.md}
\rightarrow
\texttt{NEXT\_ACTIONS.md}
\rightarrow
\texttt{latest\_changes.md}
\rightarrow
\texttt{RESEARCH\_LOG.md}
\]

最新章节优先于文件中保留的旧阶段描述。发现状态冲突时，不得静默选择；必须根据最新 commit、输出表和报告修正。

### 7.3 科学证据链

\[
\texttt{config}
\rightarrow
\texttt{script/core code}
\rightarrow
\texttt{test}
\rightarrow
\texttt{JSON/CSV}
\rightarrow
\texttt{figure/table}
\rightarrow
\texttt{Codex report}
\rightarrow
\texttt{claim matrix}
\rightarrow
\texttt{manuscript sentence}
\]

任何缺少中间环节的 claim 不得升级。

### 7.4 物理依据链

\[
\texttt{primary literature}
\rightarrow
\texttt{literature digest/registry}
\rightarrow
\texttt{parameter prior registry}
\rightarrow
\texttt{method equations}
\rightarrow
\texttt{physics code/config}
\rightarrow
\texttt{sanity/conservation test}
\]

AI 生成的建议、Gemini 报告和综述只能作为检索线索，不能替代原始论文依据。

---

## 8. 完整 Codex 研究工作流

### Step 1：最小上下文读取

先读 Tier 0：

- `CODEX_CONTEXT.md`；
- `docs/research_strategy/active_phase.md`。

规划、审查或论文任务还要读：

- `AGENTS.md`；
- `docs/project_prompts/critical_research_mode.md`。

不要每次读取全部历史报告和完整文献，避免 token 浪费。

### Step 2：定义任务 claim gate

在动代码前写清：

- unresolved problem；
- claim target；
- 为什么值得现在运行；
- 输入数据和物理模型；
- equations/variables/units/BCs；
- baseline；
- metrics；
- success threshold；
- failure interpretation；
- allowed wording；
- forbidden overclaim；
- config/script/test/table/figure/report 输出。

### Step 3：先审计现有实现，再修改

检查：

- 是否已有同功能脚本；
- 是否只是 proxy/stub；
- 是否有 target leakage；
- 是否混用材料机理；
- 是否破坏 frozen GT；
- 是否重复生成同一证据；
- 是否可以复用公共 helper；
- 是否值得新增依赖。

### Step 4：实现和实验

规则：

- 先小规模 smoke；
- smoke 只证明流程可运行，不证明科学性能；
- 正式实验使用预声明 seed、budget 和 gate；
- baseline 必须 matched budget；
- stiffness/2D/full-field 等高风险方向允许探索，但必须 bounded；
- 禁止用增加 epoch 掩盖错误方程、错误尺度或不可辨识性。

### Step 5：验证

Windows 优先：

```powershell
.\.venv\Scripts\python.exe -m pytest <task-specific-tests>
.\.venv\Scripts\python.exe -m pytest
git status --short
git diff --name-only
```

实验必须运行实际 reproduction/audit command，不能只跑测试。

### Step 6：证据和状态更新

至少更新：

- 任务 JSON/CSV；
- `EXPERIMENT_REGISTRY.md`；
- `DATASET_REGISTRY.md`；
- 需要时更新 `FIGURE_REGISTRY.md`；
- `PROJECT_STATE.md`；
- `NEXT_ACTIONS.md`；
- `docs/research_strategy/active_phase.md`；
- `docs/project_state/latest_changes.md`；
- `docs/project_state/file_inventory.md`；
- `RESEARCH_LOG.md`；
- claim matrix；
- 最终 Codex report。

不要机械复制同一段到所有文件；保持每个文件职责明确。

### Step 7：提交与汇报

- 尽量一个任务一个合并后的 commit；
- 避免“只增加报告文件”又产生第二个独立提交；
- commit 并 push GitHub；
- 报告实际 final SHA；
- 明确测试、运行、结果、GT 状态、claim 升降级和剩余问题；
- 未获得 GitHub workflow/combined status 时，只能写本地 pytest 记录，不能声称 CI passed。

---

## 9. Claim Gate 统一词汇

- `supported`：直接代码、正式运行、表格、图、测试和报告支持；
- `qualified_supported`：仅在指定先验、观测、噪声、结构、synthetic/reduced 边界下支持；
- `failed_but_informative`：正面目标失败，但定义了边界、负结果或审稿防御；
- `forbidden`：当前无证据或证据矛盾，不能进入论文正面 claim；底层方向仍可通过 bounded audit 探索。

禁止用“promising”“理论上可行”“可以包装”“应该能接受”代替状态判断。

---

## 10. 当前已取得、可为论文服务的成果

### 10.1 强主线成果

1. Frozen GT v1.1：统一、可复现的 synthetic benchmark；
2. port-only full hidden-field non-identifiability；
3. identifiability-guided target-space reduction；
4. fixed/tightly bounded priors 下的 scalar \(\gamma_{\mathrm{sub}}\) recovery；
5. \(T_{\mathrm{sw}}\) confounding、prior width 和 calibration necessity；
6. off-grid continuous simulator-backed refinement；
7. observation count、noise、seed、bootstrap、profile landscape；
8. calibration-vs-protocol disentanglement；
9. ODE-backed calibrated protocol robustness；
10. response-surface 来源和限制的显式审计。

### 10.2 可作为补充或扩展的成果

1. white-box VO\(_2\) closure 的 finite/stress preflight；
2. Fourier on/off 的诚实 negative/neutral result；
3. stiffness-aware continuation + scale-aware weighting 的 reduced benchmark 增益；
4. mini-STL-style lightweight transfer；
5. reduced 2D forward 与几何/横向耦合效应；
6. augmented-observation low-dimensional 2D inverse；
7. terminal-only 2D inverse failure；
8. multilayer sandwich 的文献先验结构；
9. electrical/thermal topology separation；
10. segmented-electrode multi-terminal forward 和 local observability rank 提升。

### 10.3 目前不能作为正面结果的内容

- full hidden-field recovery；
- terminal-only full 2D inverse；
- P1 CV/mortar neural solver success；
- full STL-PINN reproduction；
- F-SPS/Fourier universal superiority；
- experimental validation；
- full FEM/COMSOL/3D device-grade reproduction；
- quantitatively calibrated VO\(_2\)/NbO\(_2\)/SnSe device model。

---

## 11. 当前最严重的未解决问题

### 11.1 P1 训练失败

待解决：

- CV、电、热、state、port、interface residual 非量纲化；
- interface residual \(O(10^2)\) 支配优化；
- hard BC 的 local coordinate 与 global/layer-center coordinate 语义可能不一致；
- cell-center approximation 必须改成 boundary-face evaluation；
- staged optimization：anchor/port pretrain → CV continuation → mortar activation；
- 梯度冲突和 loss-scale diagnostics；
- 区分 field-anchored surrogate 与 data-free PINN。

当前预声明 gate：

\[
E_T,E_m\le 0.25,
\qquad
R_{\mathrm{interface}}\le0.05,
\qquad
\text{success rate}\ge0.70.
\]

### 11.2 P2 协议和反演仍 rank-deficient

待解决：

- 协议先做 rank/full-block gate，再进入 inverse；
- 按材料族和参数块设计组合协议；
- 加强 cooling tail、heating/cooling minor loops、真实 oscillator frequency 等热参数敏感特征；
- 不应继续扩大参数向量；
- 从 local linearized inverse 扩展到 bounded nonlinear profile/optimization；
- coverage 需用可验证方法，不把局部高斯近似冒充严格 posterior。

### 11.3 完整二维场反演尚未闭环

已有 static multi-terminal electrical forward，但缺：

- 动态 electrothermal-state \(y-z-t\) forward；
- PDE-constrained latent field inverse；
- 多端口 + 稀疏温度/状态 anchor 的 observation design；
- train/test target 分离；
- full-field error、conservation、uncertainty、identifiability metrics。

### 11.4 刚性算法尚未在可信底座上转正

待 P1 成立后再做：

- canonical Seiler-style multi-head low-stiff pretraining；
- high-stiff transfer；
- direct-from-scratch baseline；
- continuation baseline；
- trunk/head/adapter ablation；
- sharp/smooth/noise/geometry matched-budget；
- Fourier/F-SPS 仅在预声明 sharp-front subset 上测试 conditional benefit。

### 11.5 外部定量验证不足

目前文献主要支持结构、趋势和参数 plausibility，尚缺至少一条 provenance-backed digitized public curve 的定量拟合/外推。外部数据必须：

- 来自原始论文或补充材料；
- 记录 DOI、图号、坐标、单位、digitization 方法；
- 存入 `data/external/` 或 `data/literature/`；
- 更新 `docs/data_provenance.md`；
- 区分 curve fitting、shape sanity 和 independent validation。

### 11.6 泛化性不足

优先做同材料族：

- leave-one-geometry-out；
- leave-one-stack-out；
- leave-one-interface-range-out；
- leave-one-pulse-family-out。

跨材料 transfer 只能作为 exploratory negative/control，除非采用 mechanism-routed material experts 后得到稳定证据。

---

## 12. 后续研究优先级

### Priority 1：修复 P1，而不是立即堆新模块

当前最直接的下一任务是：在固定 v10 forward data 和预声明 gate 下，修复 CV/mortar non-dimensionalization、boundary-face BC、staged optimization 和 gradient conflict。未过 gate 前，不开启大规模 STL/F-SPS 优越性实验。

### Priority 2：P2 full-rank active protocol

按 NbO\(_2\) 和 VO\(_2\) 分别设计协议组合；先保证目标参数块 rank 和 condition，再做 noisy nonlinear inverse。优先解决 thermal block，不扩大目标空间。

### Priority 3：动态多端口二维闭环

在 static segmented-electrode solver 上加入电热动态和材料状态，再进行 augmented-observation low-rank/PDE-constrained field inverse。terminal-only 必须作为对照，不预设成功。

### Priority 4：算法提升

P1 通过后，才进行 canonical STL、front-aligned adapter/LoRA、Fourier/F-SPS matched-budget。目的不是必须证明全面优越，而是判断在哪些 stiffness regimes 有条件优势。

### Priority 5：外部曲线和论文实证等级提升

优先寻找可追溯公开 \(I-V\)、\(V_{th}/V_{hold}\)、oscillation frequency、thermal-barrier thickness trend 或 hysteresis curve。至少完成一项真正的 external quantitative anchor。

### Priority 6：论文装配

主论文始终围绕 \(\gamma_{\mathrm{sub}}\) 证据链同步推进，避免等所有高风险分支结束后才写。OASIS、2D、STL、F-SPS 根据 gate 进入 main、supplement、discussion 或 limitation。

---

## 13. 可合法使用的科研 trick

1. **一套实验矩阵服务多个问题**：同一 simulator sweep 同时生成 sensitivity、observability、OOD、uncertainty、protocol 和 phase map；
2. **claim ladder**：single terminal → multi-protocol → segmented terminal → segmented + sparse anchors；
3. **negative result 结构化**：把失败整理为 non-identifiable region、calibration-required region、multi-terminal-required region；
4. **matched-budget ablation**：相同 seed、epoch、collocation、anchor、参数量和 wall-clock；
5. **分层叙事**：主文只放强证据，补充材料保留高风险探索和失败；
6. **有效参数重参数化**：先估 \(R_{\mathrm{th,eff}}\)、\(\tau_{\mathrm{th}}\)，只有可辨识后才拆分界面热阻和衬底散热；
7. **time-window decomposition**：上升沿、电热平台、冷却尾、迟滞分支分别服务不同参数；
8. **mechanism routing**：共享几何/接口编码，VO\(_2\)/NbO\(_2\) 使用独立本构专家；
9. **forward solver 兜底、PINN 服务 inverse/design**：不要强行让 PINN 替代更可靠的 FVM；证明它在 differentiable inverse、amortized inference 或 protocol design 中的额外价值。

这些 trick 不能用于选择性隐藏失败、事后更改成功阈值、把插值说成仿真或把 synthetic 说成实验。

---

## 14. 绝对不能重复踩的坑

1. 用“loss 下降”判定 PINN 成功；
2. 用时间平滑项冒充 PDE residual；
3. 加噪后仍对 noiseless target 反演；
4. 选择 rank-deficient protocol 后仍宣称 inverse solved；
5. 用总体 median 掩盖失败参数块；
6. 把 substrate 放入电流串联路径，或用超高 \(\sigma\) 绕过拓扑；
7. 把外加正弦激励称为自治 RC oscillator；
8. \(V_{th}=V_{hold}=0\) 仍通过 activation；
9. 把 VO\(_2\) 和 NbO\(_2\) 的状态语义和本构混用；
10. 把 normalized-activated \(T_c\) 配置写成 literature-calibrated；
11. 把 SnSe engineering prior 写成测得参数；
12. 把 response-surface 的 2501 dense points 写成 2501 个 ODE solves；
13. 把 anchor verification 写成全量 simulator validation；
14. 把 local Jacobian rank 提升写成 full-field recoverability；
15. 把 lightweight mini-STL 写成 full STL-PINN；
16. 把 Fourier 接入训练图写成解决 spectral bias/stiffness；
17. 在失败的 base solver 上比较高级算法并宣称 superiority；
18. network 输入/硬边界使用的 local/global coordinate 语义不一致；
19. 从 target field 泄漏 non-PCM conductivity 或 hidden-field information；
20. 只测试 finite 和文件存在，不测试物理行为和 gate；
21. 修改 frozen GT 以让新方法看起来更好；
22. 把文献趋势、order-of-magnitude prior 写成器件定量校准；
23. 没有真实数据却写 experimental validation；
24. GitHub 无 CI status 时写“CI passed”；
25. 最终报告不写实际 commit SHA；
26. 同一任务拆成多次无意义提交，尤其报告单独提交；
27. 反复读取全部文献和历史，浪费 token；
28. 因为 claim 当前 `forbidden` 就拒绝开展任何 bounded exploration；
29. 为增加工作量开无边界大实验，最后没有 claim、图或审稿用途；
30. AI 建议、二次综述或 Gemini 输出未经原始文献核查就进入正文。

---

## 15. 工程与格式硬规则

- Python 3.11；
- 单一 `.venv`；
- 依赖只通过 `requirements.txt` 和 `pyproject.toml`；
- 不添加 Conda/Poetry/Pipenv/setup.py；
- 不创建嵌套 `PINN/PINN`；
- 所有物理量 SI 单位；
- 参数放 `params.py` 或 YAML；
- 路径使用 `pathlib.Path`；
- 源代码不得硬编码 `E:\Python demo\PINN`；
- 绘图只用 matplotlib，不加 seaborn；
- 大型生成文件不提交；
- Markdown/YAML 保持多行可读；
- Windows 工作区避免 `apply_patch`，用小型 Python/PowerShell 脚本编辑；
- 优先 `\.venv\Scripts\python.exe`；
- 已过滤的 matplotlib/pyparsing 第三方 warning 在测试通过时不重复报告；
- 所有带上下标的公式和变量在文档中使用 LaTeX；
- 代码块与说明文字严格分离。

---

## 16. 文献与来源文件读取规则

### 项目来源中的高优先级文件

- `Prompt of PINN.md`：用户背景、纯软件路线、项目目标、文献真实性和工作量要求；
- `Gemini_to_GPT.md`：早期 F-SPS/F-Pyramid/VSN/STL 构想，只能作为候选方案，不是既成事实；
- `PINN × V2O5_Nb2O5.pdf`：早期调研和材料分类警告；
- `SCI 项目级上下文管理与证据链管理`：状态、证据、提交和交接规则；
- `项目交接模式`：新对话需继承的交接要求；
- `Critical Research Mode for PINN Phase-Transition Project.md`：长期批判性和 claim gate；
- PINN 文献文件夹；
- Phase_change_materials 文献和补充材料。

### 已确定的重要原始文献方向

- VO\(_2\) thermal neuristor、迟滞、电热 RC dynamics；
- NbO\(_2\)+SnSe thermal engineering、Poole–Frenkel 和 threshold switching；
- Stiff Transfer Learning for PINNs；
- phase-field inverse PINN；
- compact memristor PINN / physics-regularized surrogate；
- composable neural emulator / geometry-aware operator；
- domain-decomposition、conservative/finite-volume PINN。

文献用途必须明确区分：

- 方程来源；
- 参数范围；
- 结构来源；
- 趋势 sanity；
- 定量拟合；
- independent validation。

不得用一篇论文支持它没有研究的材料或机理。

---

## 17. 推荐的工作区文档调整

新对话可在不破坏历史证据的前提下进行以下整理：

1. 用本文件重写或替代明显过时的 `docs/research_strategy/current_research_handoff.md`；
2. 在 `CODEX_CONTEXT.md` 的 Low-Token First Read 中增加本文件链接，但保持 `CODEX_CONTEXT.md` 简短；
3. 修正 `PROJECT_STATE.md` 中保留的旧“Current phase”冲突，确保文件开头最新状态为权威；
4. 把 `NEXT_ACTIONS.md` 历史段落移入 archive 或加明确“latest section wins”说明，避免新对话误读；
5. 更新 `repo_tree.md`，因为其基础树较旧、主要依靠 addenda 追加；
6. 给所有 final Codex report 增加机器可检查字段：`base_sha`、`final_sha`、`tests`、`frozen_gt_modified`、`claim_status`；
7. 不要创建多个重复 handoff 文件；确定本文件为唯一完整交接，其他入口只链接它。

任何文档重构不得删除历史负面结果或改变原始指标。

---

## 18. 新对话首次执行建议

新 Codex 对话的第一个任务不应直接开大实验。应先完成一个只读启动审计：

```text
请先阅读 docs/research_strategy/codex_new_dialog_handoff_d23a576.md、AGENTS.md、CODEX_CONTEXT.md、docs/research_strategy/active_phase.md 和 docs/project_prompts/critical_research_mode.md。核对 main、HEAD=d23a576b2d8bb17a1d1f72a0cf81cc457d42e048 或其后继提交、工作树、最新 v10 表格/报告和 frozen GT 状态。不要改代码。输出：当前论文主线、P0-P4 gate、状态文件冲突、最优下一任务、所需读取文件、成功阈值和禁止主张。结论先行，控制 token。
```

只读审计确认无误后，下一研究任务优先为：

> `cv_multidomain_p1_scaling_and_boundary_face_repair_v11`

但必须由新对话根据当前 HEAD、现有代码和用户当时指令重新确认，不得把本文建议当作不可变命令。

---

## 19. 最终牢记

这个项目不是为了证明所有大胆设想都成功，而是为了在有限时间内形成一个真实、可复现、能经受审稿质疑的二区 SCI 故事。

当前最强故事是：

\[
\boxed{
\text{端口积分观测导致完整隐场不可辨识}
\rightarrow
\text{目标空间收缩}
\rightarrow
\text{标定门控的有效热参数反演}
\rightarrow
\text{主动协议与多端口观测扩展可解边界}
}
\]

研究策略必须同时满足：

\[
\text{探索要大胆}
\quad+
\text{解释要克制}
\quad+
\text{证据要闭环}
\quad+
\text{任务要服务论文}
\quad+
\text{绝不违反学术伦理}.
\]
