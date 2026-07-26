# PINN × 氧化物相变器件二区 SCI 研究执行总指南

> **版本**：v1.0（2026-07-25）  
> **项目模式**：`Q2_SCI_DELIVERY_MODE`  
> **时间约束**：以一个自然月完成核心研究与论文初稿为默认预算；若时间增加，只扩展已通过证据门的路线。  
> **研究边界**：项目自身结果均为 **literature-guided synthetic numerical digital-twin evidence**；文献曲线数字化不等于自有实验，作者模型复现不等于独立实验验证。  
> **主材料**：Qiu 等 VO₂ 共面 thermal neuristor。  
> **辅助材料**：Chen 等 SnSe/NbO₂ 垂直阈值开关器件。  
> **核心目标**：以真实 2.5D 器件物理为底座，使 PINN 在正向场预测、跨工况泛化或受限逆问题中承担不可替代的正面方法角色，并形成一篇逻辑闭合、证据可复现、边界诚实的二区 SCI 论文。

---

# 0. 本指南的使用规则

本指南不是愿望清单，而是项目的**研究路由器、实验预注册表、失败止损协议和论文写作合同**。后续每一个 Codex 任务、代码分支、实验和论文 claim 都必须能映射到本文中的一个明确条目。

每项工作在启动前必须回答：

1. 它解决哪个已确认的物理、算法或可辨识性问题？
2. 它对应论文哪一条 claim、哪一张主图或哪一个审稿问题？
3. 输入数据从哪里来？参考求解器是什么？
4. 成功指标和阈值是什么？
5. 失败后是可发表负结果，还是纯浪费？
6. 是否会破坏冻结 Ground Truth、历史证据链或材料机理边界？

所有结论统一使用四级状态：

- `supported`：直接证据充分，可以进入正文正面结论；
- `qualified_supported`：有证据，但必须限定模型、参数、协议或 synthetic 边界；
- `failed_but_informative`：失败，但能界定适用域或形成审稿防御；
- `forbidden`：证据不足，禁止写入摘要、标题和结论。

---

# 1. 总体审稿裁决

当前项目不能继续以“增加网络复杂度，从稀疏端口恢复全部隐藏场”为主线。历史结果已经表明：

\[
\text{表示能力}\neq\text{观测信息增益}.
\]

更宽的 MLP、Fourier 特征、B-PINN 或更复杂的多头网络，都不能从相同的端口积分观测中创造缺失信息。真正值得推进的闭环是：

\[
\boxed{
\text{真实二维几何}
\rightarrow
\text{守恒 2.5D 降阶}
\rightarrow
\text{白盒材料核}
\rightarrow
\text{相变局域表示}
\rightarrow
\text{刚性同伦}
\rightarrow
\text{灵敏度保真}
\rightarrow
\text{可观测子空间反演与拒判}
}
\]

这里的“排列组合＋魔改”只有在以下条件同时满足时，才构成可论证的原创增量：

1. 修改由 VO₂/NbO₂ 的特有物理困难强制产生，而非仅改名或调参；
2. 组合产生单模块不具备的新能力；
3. 逐模块消融能证明协同增益；
4. 来源、修改、代码许可和贡献边界清楚；
5. 组合带来新的科学认识，而不只是更低的训练损失。

---

# 2. 三条最推荐的论文主体框架

三条路线是**逐级嵌套、可随证据降级**的，不是三个同时铺开的独立大项目。

## 2.1 路线 R1：HysGeo-Hybrid-PINN——最低风险、必须完成

### 定义

\[
\boxed{
\text{HysGeo-Hybrid-PINN}
=
\text{真实 2.5D 几何}
+
\text{VO₂ 白盒迟滞核}
+
\text{K-state 垂向热记忆}
+
\text{端口/RC/能量闭环}
+
\text{少量独立场锚点}
}
\]

### 论文身份

> A geometry-aware 2.5D hybrid physics-informed digital twin for electrothermal hysteretic neuristors.

### 为什么强力推荐

- 修复旧一维结构物理意义弱的问题；
- 不依赖 data-free PINN 必须成功；
- PINN 可在连续场、守恒、几何 OOD 和多查询预测中承担正面角色；
- 少量 FVM 场锚点显著提高一个月内获得正结果的概率；
- 即使高阶 inverse 失败，仍可形成 forward/generalization 论文。

### 最低投稿门

- 端口量中位相对误差不高于 5%；
- 事件时间中位相对误差不高于 5%；
- 能量账本误差不高于 1%；
- 至少一个 geometry/protocol OOD 任务优于纯 MLP；
- 多 seed 结果稳定；
- 明确标注 hybrid PINN 和 synthetic evidence。

### 目标题目

> **HysGeo-PINN: A geometry-aware 2.5D hybrid physics-informed digital twin for electrothermal phase-transition neuristors**

---

## 2.2 路线 R2：GeoPhase-HomoMoE-PINN——二区主方法优先路线

### 定义

\[
\boxed{
\text{GeoPhase-HomoMoE-PINN}
=
\text{R1}
+
\text{Transition-localized spectral experts}
+
\text{phase-sharpness × Joule-feedback homotopy}
}
\]

### 论文身份

> A transition-localized spectral mixture-of-experts with physics-based dual-axis homotopy for stiff electrothermal phase transitions.

### 为什么推荐

R1 解决物理真实性，但方法创新仍可能被评为“合理的 hybrid PINN 应用”。R2 直接针对两个相变 PINN 公认瓶颈：

- 临界相变区的高频尖锐前沿与谱偏差；
- 相变窄化和焦耳热正反馈共同造成的刚性悬崖。

### 核心证据门

- 相变窗口加权误差较 vanilla PINN 至少下降 20%；
- sharp regime 中成功率至少提升 30 个百分点；
- 非相变区误差不劣于 global Fourier；
- 高频专家的激活位置与 \(T\approx T_c\)、高残差区或切换事件一致；
- `local expert only`、`homotopy only` 和二者组合均有独立消融。

### 目标题目

> **GeoPhase-HomoMoE-PINN: Transition-localized spectral learning and dual-axis homotopy for stiff phase-transition neuristors**

---

## 2.3 路线 R3：GeoPhase-OQ-PINN——高上限、条件式冲刺

### 定义

\[
\boxed{
\text{GeoPhase-OQ-PINN}
=
\text{R2}
+
\text{event-aligned local observable subspace}
+
\text{sensitivity-fidelity gate}
+
\text{refusal/abstention}
}
\]

### 初期名称限制

在全局等价类未被证明前，不直接使用 “Observation Quotient” 作为既成事实。研究阶段使用：

> **Event-Aligned Local Observable-Subspace Inversion**

只有在多锚点、有限幅度零空间扰动和 nonlinear profile 实验均表明稳定等价类后，才升级为 `Observation-Quotient`。

### 科学假设

滞回相变器件的可辨识对象不是固定原始参数列表，而是随协议、分支和几何变化的低维参数组合：

\[
J_{p,b}=\frac{\partial \mathbf y_{p,b}}{\partial\theta}
=U_{p,b}\Sigma_{p,b}V_{p,b}^{\top},
\qquad
\mathbf q_{p,b}=V_{p,b,r}^{\top}\theta.
\]

### 进入路线 R3 的硬条件

- solver-first Jacobian 对步长、噪声和参数锚点稳定；
- 不同协议或迟滞分支出现稳定秩变化或主子空间旋转；
- PINN 与 solver 的主子空间最大 principal angle 不高于 \(15^\circ\)；
- 可观测坐标反演优于 raw-parameter inverse；
- refusal 对不可辨识 case 的 AUPRC 不低于 0.8。

### 失败降级

- 无稳定旋转但存在固定低秩方向：降级为 identifiability-gated reduced inverse；
- Jacobian 不稳定：PINN 只用于 forward，逆问题回到 solver/profile；
- terminal-only 完整场仍不可恢复：保留为 `failed_but_informative`。

### 目标题目

> **GeoPhase-OQ-PINN: Event-aligned observable-subspace learning for identifiable inversion of hysteretic phase-transition neuristors**

---

# 3. 物理模型总合同

## 3.1 主器件：Qiu VO₂ 共面 thermal neuristor

使用文献给出的真实结构锚点：

- VO₂ 膜厚约 100 nm；
- 器件面内尺寸约 \(100\times500\,\mathrm{nm^2}\)；
- 相邻器件间距约 500 nm；
- Ti/Au 电极约 15/40 nm；
- Al₂O₃ 衬底；
- 外部负载电阻与约 0.15 nF 寄生电容；
- R–T 主/次回线、静息、振荡和金属态锁定工况。

文献拟合的热导和热容是包含 VO₂、电极和周围衬底的**器件级等效量**，不能写成 VO₂ 本征热参数。其拟合热容远大于仅按 VO₂ 体积估算的热容，正好支持建立垂向热记忆模型。

## 3.2 2.5D 电学方程

\[
\nabla_{\parallel}\cdot
\left[t_{\mathrm{VO_2}}\sigma(T,s,\mathcal H)
\nabla_{\parallel}\phi\right]=0,
\]

\[
\mathbf J_{\parallel}
=-t_{\mathrm{VO_2}}\sigma\nabla_{\parallel}\phi.
\]

边界条件：

- 激励电极：\(\phi=V_d(t)\)；
- 接地电极：\(\phi=0\)；
- 其余外边界：\(\mathbf J\cdot\mathbf n=0\)；
- 若显式建接触层，采用接触电阻对应的 Robin/jump 条件。

## 3.3 2.5D 热方程

\[
\rho c_pt_{\mathrm{VO_2}}\frac{\partial T}{\partial t}
=
\nabla_{\parallel}\cdot
\left(k_{\parallel}t_{\mathrm{VO_2}}\nabla_{\parallel}T\right)
+t_{\mathrm{VO_2}}\sigma|\nabla_{\parallel}\phi|^2
-Q_z+Q_{\mathrm{couple}}.
\]

## 3.4 K-state 垂向热记忆

从 \(K=2\) 起步：

\[
C_1\dot z_1=G_0(T-z_1)-G_1(z_1-z_2),
\]

\[
C_2\dot z_2=G_1(z_1-z_2)-G_2(z_2-T_0),
\]

\[
Q_z=G_0(T-z_1).
\]

K-state 必须通过高阶热核、细化 3D/2.5D 参考模型或文献 ODE 响应进行阶数选择。不能只因为 K=2 看起来复杂就采用。

## 3.5 VO₂ 白盒迟滞闭包

最低可行闭包：

\[
\tau_s\dot s=s_{\mathrm{eq}}(T,b)-s,
\]

\[
s_{\mathrm{eq}}=
\operatorname{sigmoid}
\left(\frac{T-T_c(b)}{w_T}\right),
\]

\[
T_c(b)=\frac{1+b}{2}T_c^\uparrow+
\frac{1-b}{2}T_c^\downarrow,
\]

\[
\sigma=
\exp\left[(1-s)\log\sigma_{\mathrm{ins}}(T)
+s\log\sigma_{\mathrm{met}}(T)\right].
\]

变量 \(s\) 的论文名称只能是：

> effective conductive-state coordinate

没有显微相分数证据时，禁止称为真实金属相体积分数。

## 3.6 外部 RC 电路

\[
C_p\dot V_d=
\frac{V_{\mathrm{in}}-V_d}{R_L}-I_{\mathrm{dev}},
\]

\[
I_{\mathrm{dev}}=
\int_{\Gamma_e}-t_{\mathrm{VO_2}}\sigma\nabla\phi\cdot\mathbf n\,ds.
\]

## 3.7 全局能量账本

至少检查：

\[
P_{\mathrm{in}}
=
\frac{dE_{\mathrm{stored}}}{dt}
+P_{\mathrm{lateral}}
+P_{\mathrm{vertical}}
+P_{\mathrm{contact}}
+\varepsilon_E.
\]

\(\varepsilon_E\) 是数值闭合误差。只看温度场 NRMSE 而不看能量账本，不足以证明热模型正确。

## 3.8 NbO₂ 辅助材料核

NbO₂ 必须使用热辅助 Poole–Frenkel/thermal-runaway 核，不与 VO₂ 共享 IMT 迟滞公式：

\[
R_{\mathrm{PF}}=
R_0\exp\left[
\frac{E_a-\Delta E_{\mathrm{PF}}(E)}{k_BT}
\right],
\]

并保留 core PF＋shell ohmic、有效热阻和热容。共享的是框架接口，不是参数和本构。

---

# 4. 魔改单模块库：保留全部候选项

以下模块均需保留在项目方法资产库中。`强力推荐` 表示进入当前主线；`可以尝试` 表示通过前置 gate 后启动；`低价值/高风险` 表示保留为基线、负例或未来路线；`红线` 表示禁止作为正面方法。

## A′：2.5D Geometry + K-state Thermal Memory

- **来源思想**：薄膜降阶、多层热 RC、器件级等效热参数；
- **魔改**：真实面内连续场＋垂向低阶动态热记忆；
- **解决问题**：一维 `gamma_sub` 物理语义悬空、完整 3D 成本过高；
- **判定**：**强力推荐**；
- **论文角色**：主物理贡献。

## B′：VO₂ White-box Hysteretic Conductivity Kernel

- **来源思想**：Qiu 的 R–T 迟滞和 RC–热模型；
- **魔改**：从 0D 均匀温度阻值模型扩展为局部 \(T,s,E\) 依赖的可微电导闭包；
- **解决问题**：自由 `log_sigma` 走非物理捷径；
- **判定**：**强力推荐**；
- **论文角色**：必要物理底座，不单独冒充算法创新。

## C′：Differentiable Port + RC + Energy Ledger

- **来源思想**：端口通量积分、电路 ODE、守恒审计；
- **魔改**：将连续场、器件电流、外部电路和全局能量账本放入同一可微图；
- **判定**：**强力推荐**；
- **论文角色**：可信度基础设施。

## D′：Dual-Discretization Hybrid PINN

- **来源思想**：hybrid PINN、少量数值标签辅助物理训练；
- **魔改**：GT 用 FVM/隐式求解，PINN 用自动微分残差；只给极少量场锚点；
- **判定**：**强力推荐**；
- **关键边界**：必须称 hybrid PINN，不称 data-free。

## E′：Interface-Jump Domain Heads + Hard Constraints

- **来源思想**：XPINN/cPINN、材料域分解、Robin/interface 条件、硬约束 PINN；
- **魔改**：材料邻接图只表示真实电极/VO₂/衬底界面；局部 head 与界面残差分离；
- **判定**：**强力推荐**，但不是 headline innovation。

## F′：Transition-Localized Spectral Mixture of Experts

- **来源思想**：Fourier/SIREN、mixture-of-experts、区域优化；
- **魔改**：高频专家只在相变流形和界面邻域激活，平滑区由低频专家负责；
- **判定**：**可以尝试**，主网络创新候选；
- **风险**：专家塌缩、门控自证循环、非相变区振荡。

## G′：Phase-Sharpness × Joule-Feedback Homotopy

- **来源思想**：continuation、STL 的低刚性到高刚性思路；
- **魔改**：同时沿 \(w_T\) 和焦耳反馈系数 \(\lambda_J\) 两个物理轴推进；
- **判定**：**可以尝试**，高性价比训练算法；
- **边界**：未实现 multi-head transfer 时禁止称完整 STL。

## H′：Phase-Manifold Adaptive Sampling

- **来源思想**：RAR、RoPINN、非均匀过渡区采样；
- **魔改**：概率密度同时依赖残差、\(T\approx T_c\)、电流拥挤、材料界面和切换事件窗；
- **判定**：**可以使用，但低创新**；
- **论文角色**：训练组件，不能单独当贡献。

## I′：Controlled Adaptive Loss Balancing

- **来源思想**：ReLoBRaLo、GradNorm、动态残差权重；
- **魔改**：守恒项设置权重下限，transition/observation 组分阶段调节，记录全部权重轨迹；
- **判定**：**可以使用，但高审计要求**；
- **风险**：模型通过降低困难物理项权重逃避约束。

## J′：Event-Aligned Local Observable-Subspace Inverse

- **来源思想**：Jacobian/SVD、局部可辨识性、事件特征；
- **魔改**：保留事件时间作为显式特征，同时将波形按切换事件对齐，比较协议/分支子空间；
- **判定**：**可以尝试，论文上限最高**；
- **风险**：局部子空间被误写成全局 quotient。

## K′：Sensitivity-Fidelity Regularization/Gate

- **来源思想**：灵敏度学习、Jacobian matching；
- **魔改**：匹配 PINN 与 solver 的 Jacobian 或主投影矩阵；
- **判定**：**强力推荐**，所有 inverse/协议设计的硬 gate；
- **边界**：forward 准确不代表 sensitivity 正确。

## L′：Counterfactual Ambiguity Loss

- **来源思想**：反事实训练、零空间扰动、不确定性拒判；
- **魔改**：沿 solver 验证的近零空间构造参数对，只约束可观测坐标一致；
- **判定**：**可以尝试**，仅在 J′ 成立后；
- **风险**：有限幅度扰动离开局部零空间。

## M′：Ambiguity-Annihilating Protocol Design

- **来源思想**：A/D/E-optimal design、Fisher 信息；
- **魔改**：直接最小化多协议零空间交集，加入温度、能量和锁定态安全约束；
- **判定**：**可以尝试**，次贡献候选。

## N′：Transition-Localized Discrepancy

- **来源思想**：gray-box correction、model discrepancy；
- **魔改**：修正项只在相变事件窗激活，并受耗散、幅度和总变差约束；
- **判定**：**可以尝试**，必须有独立 holdout 证明白盒失配；
- **风险**：任意神经补丁吸收所有物理误差。

## O′：Material-Specific Composable Physics Kernels

- **来源思想**：可组合 emulator、材料专属专家；
- **魔改**：共享几何、热记忆、端口和可辨识性接口，分离 VO₂/NbO₂ 本构；
- **判定**：**可以尝试**，辅助框架贡献；
- **禁止主张**：zero-shot cross-material transfer。

## P′：Full STL-PINN Reproduction

- **来源思想**：Seiler 等 multi-head low-stiff pretraining＋high-stiff head transfer；
- **判定**：**低价值/高风险**；
- **用途**：时间充足且 R2 已成功后，做附录 MVE；
- **禁止**：把普通 continuation 写成 STL。

## Q′：Bayesian PINN

- **作用**：表达参数后验和预测不确定性；
- **缺陷**：不能消除结构不可辨识，只会得到宽或多峰后验；
- **判定**：**低价值/高风险**；
- **用途**：小规模 UQ 基线。

## R′：fPINN

- **作用**：分数阶输运；
- **缺陷**：当前 VO₂/NbO₂ 没有明确分数阶物理依据；
- **判定**：**低价值/高风险**。

## S′：Explicit Moving-Boundary Dual Network

- **来源思想**：Stefan 界面网络；
- **缺陷**：VO₂ 导电通道不一定是可观测、单值几何界面；
- **判定**：**低价值/高风险**；
- **可保留改法**：第二网络预测事件时间或分支状态，而非伪造几何相界。

## T′：Enthalpy/Effective-Heat-Capacity Inspired State Closure

- **来源思想**：固定网格焓法、等效热容法；
- **可借鉴部分**：温度驱动平滑状态变量、transition-window weighting；
- **禁止部分**：把 VO₂ 电子相变直接称固液潜热焓法；
- **判定**：**低价值/高风险**，仅保留数学启发。

## U′：Full Landau/Allen–Cahn/Cahn–Hilliard Phase Field

- **优势**：可表示形核、界面和拓扑变化；
- **缺陷**：缺少器件一致的自由能、界面能和迁移率；时间成本过高；
- **判定**：**低价值/高风险**，当前停止。

## V′：NeuroPINN/VSN

- **优势**：神经形态部署与事件稀疏计算；
- **缺陷**：不解决当前几何、刚性和可辨识性核心问题；
- **判定**：**低价值/高风险**。

## W′：QGAN/Quantum PINN

- **缺陷**：问题同构度低、验证困难、概念堆砌；
- **判定**：**低价值/高风险**。

## X′：Anisotropic/Nano-enhanced Thermal-Storage PCM Route

- **优势**：可做焓—多孔介质、各向异性、翅片和自然对流；
- **缺陷**：赛道拥挤，无法复用现有 neuristor 资产；
- **判定**：**低价值/高风险**，作为完全换题后路。

## Y′：GST Multi-phase-field PINN Route

- **优势**：材料和相变机理丰富；
- **缺陷**：晶化、熔化、淬火、成核和纳秒热过程参数过多；
- **判定**：**低价值/高风险**，当前停止。

## Z′：Free `log_sigma` Output Head

- **价值**：容易拟合端口，可作为非物理捷径反例；
- **判定**：**只能作为负面基线**；
- **禁止**：作为最终材料本构。

## AA′：Terminal-only Full 2D Hidden-field Recovery

- **问题**：与已有可辨识性证据冲突；
- **判定**：**forbidden**；
- **用途**：作为审稿防御中的失败边界，不再投入主预算。

---

# 5. 核心模块的完整排列组合库

为满足“保留 A′、B′、C′，也保留 A′+B′、A′+C′、B′+C′、A′+B′+C′”的要求，定义四个核心模块：

- \(A'\)：HysGeo 物理底座，即 2.5D＋白盒核＋端口/RC/账本＋hybrid PINN；
- \(B'\)：Transition-localized spectral experts；
- \(C'\)：Dual-axis stiffness homotopy；
- \(D'\)：Local observable-subspace＋sensitivity fidelity＋refusal。

以下保留四模块全部 15 个非空组合。

| 编号 | 组合 | 可形成的研究身份 | 当前裁决 |
|---|---|---|---|
| C01 | \(A'\) | HysGeo-Hybrid-PINN | **强力推荐，最低主线** |
| C02 | \(B'\) | Transition-localized representation benchmark | 可做经典 PDE/简化相变基准，不足以单独投稿 |
| C03 | \(C'\) | Dual-axis continuation benchmark | 训练算法小论文潜力低，作为消融 |
| C04 | \(D'\) | Solver/PINN observable-subspace audit | 可形成逆问题方法短文，但缺真实场底座时物理性不足 |
| C05 | \(A'+B'\) | Geometry-aware transition-localized PINN | **可以尝试**，网络贡献明确 |
| C06 | \(A'+C'\) | Geometry-aware stiffness-homotopic PINN | **可以尝试**，实施成本最低 |
| C07 | \(A'+D'\) | Geometry-aware identifiability-gated hybrid PINN | **可以尝试**，稳健 inverse 路线 |
| C08 | \(B'+C'\) | Transition-localized homotopy PINN | 适合简化模型预检，缺器件物理时不够完整 |
| C09 | \(B'+D'\) | Spectral inverse with observable coordinates | 风险高，forward 未稳前不做 |
| C10 | \(C'+D'\) | Homotopy-trained observable-subspace inverse | 可作为 inverse 训练增强，不应独立成主线 |
| C11 | \(A'+B'+C'\) | GeoPhase-HomoMoE-PINN | **强力推荐，二区主方法** |
| C12 | \(A'+B'+D'\) | GeoPhase observable-subspace PINN without homotopy | 可尝试，但 sharp regime 训练风险高 |
| C13 | \(A'+C'+D'\) | Homotopy-based identifiability-gated PINN | **可以尝试**，若 MoE 不稳定的替代路线 |
| C14 | \(B'+C'+D'\) | Abstract stiffness-aware inverse PINN | 不推荐脱离真实器件单独投稿 |
| C15 | \(A'+B'+C'+D'\) | GeoPhase-OQ-PINN | **高上限条件式冲刺** |

## 5.1 附加插件组合库

以下组合保留为通过相应 gate 后的扩展：

| 组合 | 目的 | 启动条件 |
|---|---|---|
| \(A'+E'\) | 多材料域接口守恒 | 2.5D solver 接口误差成为主瓶颈 |
| \(A'+F'+G'\) | R2 主方法 | R1 已稳定，sharp regime 仍失败 |
| \(A'+J'+K'\) | 受限 inverse 主线 | solver Jacobian 稳定 |
| \(J'+K'+L'\) | 反事实歧义训练 | 已验证近零空间有限扰动仍近等价 |
| \(J'+K'+M'\) | 歧义消除协议设计 | 多协议子空间互补成立 |
| \(B'+N'\) | 局域频谱＋局域模型误差 | 外部 holdout 表明白盒只在事件窗失配 |
| \(A'+O'\) | VO₂/NbO₂ 材料核可替换框架 | VO₂ 主线完成后 |
| \(A'+P'\) | 完整 STL 扩展 | 有充足预算且 R2 已通过 |
| \(A'+Q'\) | Bayesian UQ | 需要后验展示且计算预算允许 |
| \(A'+H'+I'\) | 自适应采样与损失控制 | 仅作为训练组件组合 |
| \(A'+S'\) | 事件网络替代几何界面网络 | 事件定义稳定且可观测 |
| \(X'+H'+D'\) | 各向异性 PCM 新载体路线 | 主项目彻底失败并决定换题 |
| \(Y'+C'+H'\) | GST 多相场刚性 PINN | 仅长期新项目，不进入当前月度计划 |

---

# 6. 推荐代码架构

以下为推荐路径，实施时需与仓库现有结构对齐，不得破坏冻结资产。

```text
src/pinnpcm/
├─ physics/
│  ├─ geometry_vo2_coplanar.py
│  ├─ vo2_hysteresis_kernel.py
│  ├─ nbo2_pf_kernel.py
│  ├─ vertical_thermal_memory.py
│  ├─ electrothermal_2p5d.py
│  ├─ circuit_rc.py
│  ├─ port_operator.py
│  ├─ energy_ledger.py
│  └─ interface_conditions.py
├─ solvers/
│  ├─ fvm_electric_2d.py
│  ├─ fvm_thermal_2p5d.py
│  ├─ implicit_time_integrator.py
│  └─ convergence_audit.py
├─ pinn/
│  ├─ hysgeo_network.py
│  ├─ transition_local_moe.py
│  ├─ hard_output_transforms.py
│  ├─ hybrid_losses.py
│  ├─ homotopy_scheduler.py
│  ├─ phase_manifold_sampler.py
│  └─ controlled_loss_balancer.py
├─ inverse/
│  ├─ observable_subspace.py
│  ├─ sensitivity_fidelity.py
│  ├─ refusal_head.py
│  ├─ ambiguity_loss.py
│  └─ protocol_design.py
└─ evaluation/
   ├─ field_metrics.py
   ├─ event_metrics.py
   ├─ conservation_metrics.py
   ├─ inverse_metrics.py
   └─ claim_gate.py
```

每个新模块必须同时包含：

- 单元测试；
- 物理极限测试；
- 数值稳定性测试；
- 配置文件；
- 机器可读 JSON/CSV；
- 对应 Codex 报告；
- claim 状态更新。

---

# 7. 分阶段执行路线

# Phase 0：治理冻结与复现基线

## 目标

确保所有新实验建立在干净、可复现、不会污染历史证据的仓库上。

## 操作

1. 核验 `HEAD == origin/main`、分支和工作区；
2. 运行全测试并记录通过数、失败数和耗时；
3. 校验 frozen GT v1.1 哈希、mtime 和文件清单；
4. 创建独立新阶段配置，不修改历史 benchmark；
5. 建立新 claim matrix：R1、R2、R3 分开；
6. 固定随机种子集合，例如 2026、2027、2028、2029、2030；
7. 预注册成功门和止损门。

## 交付

- `docs/research_strategy/active_phase.md`；
- `configs/geo2p5d_stage.yaml`；
- baseline replay 报告；
- 新旧证据隔离清单。

## Gate 0A

任何 frozen asset 被非预期修改，则停止全部科学实验，先修复治理。

---

# Phase 1：独立 2.5D FVM 参考求解器

## 目标

建立所有 PINN 实验的可信判卷器。没有参考求解器通过，禁止训练正式 PINN。

## 实施顺序

### 1.1 电学子问题

- 规则或结构化有限体积网格；
- 面电导使用调和平均；
- 电极 Dirichlet、外边界绝缘；
- 稀疏线性求解；
- 端口电流由边界通量积分。

验证：

- 均匀矩形导体解析极限；
- 电流平衡；
- 网格细化；
- 有限 Dirichlet 接触边界和均匀导体极限；Phase 1 不实现接触电阻，因此不得声称完整接触/接口模型。

### 1.2 热子问题

- 面内扩散＋焦耳热；
- 裸露 VO₂ 区与电极覆盖 VO₂ 区分别采用 K-state 垂向热记忆，禁止重复计入 active-plane VO₂ 储能；
- 自适应隐式 backward Euler 推进，并进行独立时间步细化；
- Phase 1 正式基线只解析单 neuristor；双器件仅用两个独立副本验证零耦合与标签对称性。

非零双器件热耦合不属于 Phase 1。若后续论文需要该主张，必须先增加显式衬底表面热场，或增加经高阶独立模型验证的非局部被动耦合核，并单独通过网格/时间收敛、互易性、守恒和能量账本 gate；标量经验耦合项本身不能替代这些证据。

验证：

- 无焦耳热冷却解析极限；
- 稳态热阻极限；
- K-state 阶跃响应；
- 时间步细化；
- 能量账本。

### 1.3 迟滞和电路耦合

- 先做平滑、无迟滞闭包；
- 再加入 major-loop；
- 最后加入 branch/minor-loop 简化状态；
- RC 电路使用一致隐式或分裂迭代。

### 1.4 文献趋势对齐

主验证不是逐点复刻实验，而是检查：

- 9 V 附近静息；
- 12.5 V 附近振荡；
- 更高偏压下金属态锁定/抑制趋势；
- 频率随偏压变化方向仅作描述性、非投票诊断，除非另有源可追踪阈值；
- 单器件 9 V、12.5 V 和更高偏压趋势；双器件非零热耦合方向延后到具备显式衬底场或经验证非局部核之后。

## Gate 1

- 电流守恒误差达到数值容差；
- 能量账本相对残差 \(\le1\%\)；
- 网格和时间步细化表现单调；
- 相变事件对细化不出现非物理漂移；
- 端口趋势与文献一致。

不通过时禁止进入 Phase 2。

---

# Phase 2：数据集与 inverse-crime 防护

## 数据生成

构造参数化数据集：

- 几何：长度、宽度、电极搭接、相邻间距；
- 物理：\(G_k,C_k,T_c^\uparrow,T_c^\downarrow,w_T,\tau_s,R_c\)；
- 协议：偏压、脉冲、\(R_L,C_p\)；
- 工况：静息、振荡、锁定、双器件耦合。

## 划分

必须按实体维度划分，不得随机打散相邻时空点：

- interpolation split；
- unseen voltage/protocol split；
- unseen geometry split；
- unseen thermal-memory split；
- noisy/jitter split；
- model-mismatch split。

## 防 inverse crime

1. GT 用 FVM＋隐式积分，PINN 用自动微分连续残差；
2. 测试加入温变热导、双时间尺度热损失、接触漂移等训练缺失项；
3. 加入 0%、1%、3%、5% 噪声；
4. 加入采样时间 jitter、偏置 offset 和分辨率下降；
5. 文献数字化 fit 和 holdout 分离；
6. 不使用测试 case 的真实参数计算部署时不可获得的 OQ basis。

## 交付

- 数据 manifest；
- 参数范围与来源表；
- train/val/test case ID；
- solver convergence metadata；
- 数据哈希。

---

# Phase 3：基线系统

## 必须实现的基线

1. FVM/implicit solver；
2. vanilla PINN；
3. global Fourier PINN；
4. domain-decomposed PINN 或 FBPINN-lite；
5. pure MLP/TCN port surrogate；
6. hybrid PINN without proposed modules；
7. old 1D `gamma_sub` reduced inverse；
8. direct solver＋LM/CMA-ES/profile inverse。

## 公平性合同

- 相同训练数据；
- 相同 collocation 总数；
- 匹配参数量或报告差异；
- 匹配 wall-clock/GPU budget；
- 至少 5 seeds；
- 超参数搜索预算相同；
- 报告 median、IQR、95 分位和失败率。

## Gate 3

若 vanilla PINN 连平滑工况都不能通过，先修无量纲化、边界和损失，不得直接上 MoE。

---

# Phase 4：R1 HysGeo-Hybrid-PINN

## 网络输入

\[
[x,y,t,\mathrm{SDF},\mathrm{material\ mask},
V_{\mathrm{in}},R_L,C_p,\theta_g,\theta_p].
\]

## 网络输出

\[
[\phi,T,s,z_1,z_2].
\]

## 架构

- 共享几何/协议编码器；
- 电势 head 与热/状态 head 分离；
- 电导由白盒层计算；
- 端口电流由积分层计算；
- 边界和变量范围使用硬输出变换；
- 少量场 anchor 只覆盖低比例时空点。

## 损失

\[
\mathcal L=
\mathcal L_{\mathrm{current}}
+\mathcal L_{\mathrm{energy}}
+\mathcal L_s
+\mathcal L_{\mathrm{RC}}
+\mathcal L_{\mathrm{interface}}
+\lambda_p\mathcal L_{\mathrm{port}}
+\lambda_a\mathcal L_{\mathrm{anchor}}.
\]

## 必须消融

- anchor 比例 0、极少量、较多；
- free `log_sigma` vs white-box；
- 单 `gamma_eff` vs K-state；
- 直接回归电流 vs 可微端口积分；
- 软边界 vs 硬边界。

## Gate 4

R1 至少在一个 geometry OOD 和一个 protocol OOD 上形成正面结果，否则不能进入正式论文主线。

---

# Phase 5：R2 Transition-localized MoE 与双轴同伦

## 5.1 最小 MoE

起步仅使用两个专家：

\[
u=u_{\mathrm{smooth}}+g_{\mathrm{tr}}u_{\mathrm{spectral}}.
\]

门控优先使用：

- solver/coarse network 温度；
- 停止梯度的 coarse prediction；
- SDF 与局部电场；
- 事件窗口。

禁止让高频专家通过自己输出的温度控制自身门控而形成闭环自证。

## 5.2 同伦阶段

建议三阶段：

\[
(w_T,\lambda_J):
(w_{\mathrm{wide}},0.2)
\rightarrow
(w_{\mathrm{mid}},0.5)
\rightarrow
(w_{\mathrm{real}},1.0).
\]

阶段切换条件不能只用 epoch，至少同时考虑：

- 物理残差下降；
- 事件误差；
- 梯度范数比；
- 稳定训练窗口。

## 5.3 对比矩阵

- vanilla；
- global Fourier；
- local expert only；
- homotopy only；
- local expert＋homotopy；
- local expert＋homotopy＋adaptive sampling。

## Gate 5

只有组合相对单模块出现协同增益，才能将 R2 写成新方法，而非两个已有 trick 的并列堆叠。

---

# Phase 6：R3 Solver-first Observable-Subspace MVE

## 6.1 参数维数先缩小

第一轮只选 3–4 个参数，例如：

\[
\theta=[\log G_{\mathrm{th}}^{\mathrm{eff}},T_c,w_T,R_c].
\]

不要直接对十维参数做高调商空间分析。

## 6.2 观测特征

同时保留事件时间和事件对齐波形：

\[
\Phi=[t_{\mathrm{on}},t_{\mathrm{off}},w_{\mathrm{pulse}},
f_{\mathrm{osc}},\widetilde I(\tau)].
\]

事件对齐不能删除 \(t_{\mathrm{on}}\)，否则人为丢掉最有信息的切换延迟。

## 6.3 Jacobian 审计

- 自动微分与有限差分交叉；
- 多个差分步长；
- 多参数锚点；
- 多噪声 realization；
- whitened Jacobian；
- SVD、effective rank、principal angle；
- profile likelihood 和有限幅度 null perturbation。

## 6.4 PINN sensitivity gate

比较：

\[
J_{\mathrm{PINN}}
\quad\text{vs.}\quad
J_{\mathrm{solver}}.
\]

如果 forward 很准但主子空间不一致，PINN 不得进入 inverse 与协议设计。

## 6.5 Inverse head

- 只预测可观测坐标 \(q\)；
- 对零空间保留先验、输出集合或拒判；
- basis 必须由训练/校准流程获得，不得从测试真值偷算；
- 和 raw parameter inverse、固定 reduced inverse 比较。

## Gate 6

R3 失败不影响 R1/R2 投稿。任何时候都不得为了保住 “OQ” 名称而修改秩阈值或隐藏负结果。

---

# Phase 7：协议设计、反事实与 discrepancy 的条件扩展

## 7.1 AA 协议设计

仅从有限协议库选择，不做无边界任意波形：

- 三角扫描；
- 阶跃；
- 短/长脉冲；
- 多组 \(R_L,C_p\)；
- 邻近器件热扰动。

目标：

\[
\max_{\mathcal P}
\sigma_{\min}^{+}
\left(\sum_{p\in\mathcal P}J_p^T\Sigma_p^{-1}J_p\right),
\]

并惩罚峰值温度、能量、持续时间和锁定态风险。

## 7.2 Counterfactual ambiguity

只有经过 finite-amplitude solver 验证的近零空间扰动才能用于训练。否则是伪反事实。

## 7.3 Transition-localized discrepancy

启动条件：外部文献 holdout 或 model-mismatch GT 明确显示白盒模型只在相变事件窗系统失配。

---

# Phase 8：NbO₂ 跨模型数值验证

## 目标

证明共享框架能够替换材料专属物理核，而不是证明 VO₂ 网络零样本迁移到 NbO₂。

## 验证内容

- 增大有效热阻时，阈值电压和阈值电流的趋势；
- hysteresis window 的方向性；
- \(R_{\mathrm{th}},E_a,d,R_0\) 的混杂结构；
- 统一端口、RC、能量和可辨识性工作流；
- 与 Chen 文献模型趋势一致。

正确名称：

> cross-model numerical validation

禁止名称：

- experimental validation；
- zero-shot transfer；
- universal constitutive law。

---

# Phase 9：最终实验矩阵与主图

## 主实验

| ID | 实验 | 主要输出 |
|---|---|---|
| E0 | 2.5D solver 验证 | 细化、守恒、能量账本 |
| E1 | R1 forward | 场、端口、事件、OOD |
| E2 | R2 刚性消融 | 多 seed 成功率、相变区误差 |
| E3 | geometry/protocol generalization | OOD gap、数据效率 |
| E4 | solver-first observable subspace | rank、奇异值、principal angle |
| E5 | PINN sensitivity fidelity | Jacobian/subspace 误差 |
| E6 | quotient/reduced inverse | 坐标误差、coverage、refusal |
| E7 | AA 协议设计 | fresh nonlinear inverse 收益 |
| E8 | NbO₂ cross-model | 热工程趋势和混杂地图 |

## 推荐六张主图

1. **Fig. 1**：真实器件、2.5D 物理图和网络总框架；
2. **Fig. 2**：FVM 验证、K-state 热记忆和能量账本；
3. **Fig. 3**：R1 场与端口预测、未见协议泛化；
4. **Fig. 4**：MoE＋homotopy 的刚性相图和消融；
5. **Fig. 5**：observable-subspace、sensitivity fidelity 和 refusal；
6. **Fig. 6**：NbO₂ cross-model 趋势或 geometry OOD 设计图谱。

若 R3 未过 gate，Fig. 5 改为 identifiability boundary 和 fixed reduced inverse，不保留 OQ 叙事。

## 主表

- Table 1：方程、变量、参数语义和来源；
- Table 2：基线与预算公平性；
- Table 3：forward/事件/守恒结果；
- Table 4：模块消融和多 seed 成功率；
- Table 5：inverse、coverage 和 refusal；
- Table 6：claim gate 与证据状态。

---

# 8. 指标和预注册门

## Forward

- 端口 NRMSE/MAE；
- \(V_{\mathrm{th}},t_{\mathrm{on}},t_{\mathrm{off}}\)；
- spike frequency、pulse width；
- hysteresis area；
- 温度和状态场 NRMSE；
- transition-window weighted error；
- current balance；
- interface flux mismatch；
- energy ledger residual；
- OOD generalization gap；
- 训练和推理成本。

## Inverse

- observable-coordinate relative error；
- raw parameter coverage；
- profile width；
- principal angle；
- refusal AUROC/AUPRC；
- false-confidence rate；
- protocol information gain；
- noise/anchor robustness。

## 推荐成功阈值

这些是目标，不是已有结果：

- 主端口量中位误差 \(\le5\%\)，95 分位 \(\le10\%\)；
- 事件时间中位误差 \(\le5\%\)；
- 能量账本残差 \(\le1\%\)；
- sharp regime 成功率相对 vanilla 提升至少 30 个百分点；
- geometry OOD 相对纯 MLP 改善至少 20%；
- 可辨识区坐标反演中位误差 \(\le10\%\)；
- refusal AUPRC \(\ge0.8\)；
- PINN–solver 最大 principal angle \(\le15^\circ\)。

门失败时降级 claim，不得临时换指标。

---

# 9. 论文写作指南

## 9.1 引言逻辑

第一段：相变 neuristor 的工程和物理价值。  
第二段：现有相变 PINN 主要面向 Stefan/焓法/相场，现有忆阻器 PINN 主要是紧凑 ODE 或端口代理。  
第三段：指出三重缺口：真实几何、临界刚性、端口非唯一。  
第四段：说明为何 2.5D 守恒降阶、局域频谱分配和可辨识性门控必须联合设计。  
第五段：列出贡献，且每条贡献对应一组实验。

禁止使用泛滥叙事：

> PINN 是无网格方法，FEM 很慢，因此我们将 Fourier 和 XPINN 用于 VO₂。

这会被视为普通应用拼接。

## 9.2 摘要创新钉法

### R1 摘要核心句

> We develop a geometry-aware 2.5D hybrid physics-informed digital twin that couples in-plane electrothermal fields with reduced vertical thermal memory, a white-box hysteretic conductivity closure, differentiable terminal fluxes, and an external RC circuit.

### R2 追加句

> A transition-localized spectral mixture-of-experts and a phase-sharpness–electrothermal-feedback homotopy allocate high-frequency capacity only near the switching manifold and improve training reliability in sharp regimes.

### R3 追加句

> The inverse formulation estimates only solver-verified locally observable coordinates and abstains when the requested parameters are unsupported by terminal observations.

任何句子只有实验过 gate 后才能写为结果。

## 9.3 三条贡献的推荐表述

### Contribution 1：真实结构与守恒降阶

提出面向共面 VO₂ thermal neuristor 的守恒 2.5D 物理信息数字孪生，将真实面内电热场、垂向多状态热记忆、端口积分和外部 RC 电路统一到同一计算图中。

### Contribution 2：相变局域表示与双轴刚性同伦

提出相变流形门控的局域频谱专家架构，并沿相变尖锐度和电热反馈强度进行联合同伦，以降低临界区谱平滑化和直接高刚性训练失败。

### Contribution 3：局部可观测子空间与灵敏度保真

提出事件对齐的局部可观测子空间反演，并通过 PINN–solver 灵敏度保真和拒判机制避免从端口数据返回虚假唯一材料参数。

若 R3 失败，Contribution 3 改为：

> 系统刻画稀疏端口下的 recoverability boundary，并证明目标空间缩减和校准门控的必要性。

## 9.4 Discussion 必须主动承认

- synthetic-only；
- 文献参数和数字化数据边界；
- \(s\) 是有效状态坐标；
- 热参数是器件级等效量；
- 2.5D 是守恒降阶而非完整 3D；
- terminal-only 不支持完整隐场；
- VO₂ 与 NbO₂ 使用不同本构；
- PINN 在单次高精度求解上不必优于 FVM。

---

# 10. 选刊路由

投稿前必须重新核验最新分区、范围和近期论文。

## 优先 1：International Journal of Heat and Mass Transfer

适用条件：

- 2.5D 热传递、垂向热记忆、能量守恒和相变临界区误差是主线；
- 能给出新的传热认识，而非只展示网络性能。

## 优先 2：Engineering Applications of Artificial Intelligence

适用条件：

- 网络创新、benchmark、公开代码和可复现性强；
- 有明确工程任务和外部文献锚点。

## 优先 3：Applied Thermal Engineering

适用条件：

- 器件热管理、阈值、能耗和 SnSe/NbO₂ 热工程设计突出。

## 冲刺：Journal of Computational Physics

只有 R3 完整通过、算法一般性、鲁棒性和复杂度分析充分时考虑。

## 不推荐当前直接投稿

- `Energy`：当前是器件级 neuristor，不是系统能源研究；
- `Journal of Energy Storage`：VO₂/NbO₂ 易失性神经元不属于储能主线。

---

# 11. 功利化止损规则

## 11.1 必须立即停止的情况

- 参考求解器守恒或细化不通过；
- MoE 在平滑区造成明显伪振荡且无法用简单门控修复；
- OQ 子空间对锚点和差分步长不稳定；
- PINN sensitivity 与 solver 明显不一致；
- 为获得正结果需要改变冻结 GT 或测试分布；
- 需要引入完整 3D、完整相场或大量未知材料参数才能继续。

## 11.2 失败后的论文降级路由

| 失败点 | 降级方案 |
|---|---|
| data-free PINN 失败 | 使用 dual-discretization hybrid PINN |
| MoE 失败 | 保留 homotopy，回到 A′+C′ |
| homotopy 失败 | 保留局域专家，回到 A′+B′ |
| 二者均无增益 | 仅投稿 R1，算法模块进 SI/负结果 |
| OQ 无旋转 | 固定低秩 observable coordinate |
| Jacobian 不稳定 | inverse 由 solver 完成，PINN 仅 forward |
| NbO₂ 验证失败 | 删除跨模型主张，不影响 VO₂ 主线 |
| 外部曲线定量误差较大 | 降级为趋势一致和 model-mismatch 讨论 |

---

# 12. “灌水”边界和学术道德合同

## 合规借鉴

- 正确引用原方法；
- 独立实现或遵守开源许可证；
- 明确原模块、修改内容和新增物理意义；
- 用消融证明修改有效；
- 将已有方法用于新载体，但不夸大为方法首创；
- 使用 literature-calibrated synthetic data，并明确来源和边界；
- 保留失败 seed、失败区域和负结果。

## 只会被判 trivial、但未必构成不端

- 只改层数、激活函数或损失权重；
- 将 vanilla PINN 换材料名称；
- 将 Fourier＋RAR＋XPINN 并列堆叠；
- 只与弱 MLP 比，不与 FVM/FEM 比；
- 用总体 L2 掩盖事件、守恒和最坏 case 失败。

## 学术道德红线

- 复制代码后只改变量名且不遵守许可证；
- 复用他人文字、图或公式推导而不引用；
- 把 synthetic/FVM 数据写成实验；
- 把数字化文献曲线写成自己的测量；
- 修改 frozen GT、测试范围或成功门制造结果；
- 使用测试真值计算 inverse basis，造成数据泄漏；
- 隐藏失败 seed 或只展示最优运行；
- 将 Qiu 的器件级等效热容写成 VO₂ 本征热容；
- 将 VO₂ 与 NbO₂ 本构和参数混用；
- 重复发表相同数据、图和结论。

## 每个模块的来源审计模板

```text
模块名称：
原始来源与引用：
原始应用问题：
本项目复用的思想：
实质性修改：
为何由 VO2/NbO2 问题强制产生：
新增能力：
消融实验：
代码来源/许可证：
允许 claim：
禁止 claim：
```

---

# 13. 论文完成清单

## 科学内容

- [ ] 参考求解器全部过 gate；
- [ ] R1 至少一项 OOD 正面结果；
- [ ] R2 模块逐项消融；
- [ ] 至少 5 seeds；
- [ ] 传统数值和纯监督基线；
- [ ] 最坏 case 与失败区域；
- [ ] 能量和电流守恒；
- [ ] inverse crime 防护；
- [ ] claim matrix 更新；
- [ ] NbO₂ 验证或明确删除。

## 稿件

- [ ] 标题不包含未通过的方法名；
- [ ] 摘要每个结果均有图表支撑；
- [ ] 引言完成文献排重；
- [ ] 方程与代码变量一致；
- [ ] 参数表含单位、来源、范围和语义；
- [ ] 图中区分 solver、PINN、literature data；
- [ ] Discussion 主动写限制；
- [ ] Data/Code availability 清楚；
- [ ] 参考文献充足且真实；
- [ ] Supplementary 包含完整消融与失败表。

## 复现包

- [ ] 环境锁定；
- [ ] 一键生成主表和主图；
- [ ] case manifest；
- [ ] 随机种子；
- [ ] checkpoint 或可重训脚本；
- [ ] JSON/CSV 原始指标；
- [ ] clean-worktree replay；
- [ ] 最终 commit hash；
- [ ] README 执行说明。

## 投稿

- [ ] 期刊范围和最新分区复核；
- [ ] 图分辨率、格式和单位统一；
- [ ] cover letter 聚焦真实科学缺口；
- [ ] highlights 不使用 “first” 和 “absolute stability”；
- [ ] authorship、利益冲突、基金和数据声明完整；
- [ ] 预写审稿答辩：synthetic、FVM 对比、PINN 必要性、参数可辨识性、2.5D 合理性。

---

# 14. 审稿人高概率问题及防御要点

## Q1：为什么不用 FVM/FEM？

回答重点：PINN 不宣称替代单次高精度求解；价值在于连续参数化、多查询摊销、可微端口—电路闭环、少量场数据融合和受限 inverse。必须给出 break-even 分析。

## Q2：为什么需要 PINN，而不是纯 MLP？

回答重点：比较 OOD、守恒、内部场、数据效率和 sensitivity；若只比较端口拟合，则 PINN 没有存在必要。

## Q3：2.5D 是否过度简化？

回答重点：由完整 3D 成本和历史失败推动的守恒降阶；K-state 通过高阶热核拟合和能量账本验证；明确适用范围。

## Q4：参数是否真的可辨识？

回答重点：不返回虚假唯一值；先做 solver Jacobian、profile 和 finite perturbation；只反演可观测坐标并拒判。

## Q5：为何使用少量 FVM 标签？

回答重点：方法准确命名为 hybrid PINN；不同离散体系、低标签比例、数据效率曲线和未见工况验证避免把 solver 蒸馏冒充 data-free。

## Q6：VO₂ 状态变量是否是真实相分数？

回答重点：不是；它是器件级有效导电状态坐标，论文不会作显微相分数主张。

## Q7：没有自有实验为何有工程价值？

回答重点：真实文献器件锚定、独立 solver、文献 holdout、严格失配与噪声测试；结论限定为 numerical digital twin，不写实验验证。

---

# 15. 最终推荐决策

## 当前立即执行

\[
\boxed{
\text{Phase 0}
\rightarrow
\text{Phase 1 参考求解器}
\rightarrow
\text{R1 HysGeo-Hybrid-PINN}
}
\]

## R1 成功后优先升级

\[
\boxed{
\text{Transition-localized spectral experts}
+
\text{dual-axis homotopy}
}
\]

## 只有 solver-first MVE 通过后启动

\[
\boxed{
\text{observable-subspace inverse}
+
\text{sensitivity fidelity}
+
\text{refusal}
}
\]

## 论文最终可接受的三档身份

1. **强方法档**：R1＋R2＋R3；
2. **二区稳健档**：R1＋R2，inverse 只报告边界或固定低秩；
3. **保底档**：R1 成功，data-free PINN 失败但 hybrid PINN 正面，完整可辨识性边界进入 Discussion/Results。

最不应做的事情是同时启动 full STL、B-PINN、相场、NeuroPINN、QGAN、完整 3D 和多材料统一本构。那不是提高创新密度，而是把一个月项目变成无法闭环的模块坟场。

---

# 16. 主要来源与文献入口

## 项目战略文件

- `Critical Research Mode for PINN Phase-Transition Project.md`
- `PINN_Codex_New_Dialog_Handoff_d23a576(1).md`
- `PINN_project_research_audit_and_idea_portfolio_2026-07-15(1).md`
- `PINN_phase_change_integrated_deep_research_and_roadmap_2026-07-16(1).md`
- `PINN_deep_research_GDrive_integrated_revised_2026-07-20(1).md`
- `PINN_phase_change_Deep_Research_brainstorm_revised_2026-07-24(4).md`

## 相变器件

1. Qiu et al., *Reconfigurable Cascaded Thermal Neuristors for Neuromorphic Computing*, Advanced Materials 2024.  
   https://doi.org/10.1002/adma.202306818

2. Chen et al., *Thermal Engineering of NbO₂-Based Memristor for Low-Power and High-Capacity Oscillatory Neural Networks*, Advanced Functional Materials 2025.  
   https://doi.org/10.1002/adfm.202423800

3. Liu et al., *Experimental Demonstration of Coplanar NbOₓ Mott Memristors for Spiking Neurons*, IEEE Electron Device Letters 2024.  
   https://doi.org/10.1109/LED.2024.3362829

## PINN 与科学机器学习

4. Seiler et al., *Stiff Transfer Learning for Physics-Informed Neural Networks*, 2025.  
   https://arxiv.org/abs/2501.17281

5. Zhao et al., *Physics-informed neural networks for solving inverse problems in phase field models*, Neural Networks 2025.  
   https://doi.org/10.1016/j.neunet.2025.107665

6. Tang et al., *Physics-informed neural networks to solve lumped kinetic model for chromatography process*, Journal of Chromatography A 2023.  
   https://doi.org/10.1016/j.chroma.2023.464346

7. Lee et al., *A Compact Memristor Model Based on Physics-Informed Neural Networks*, Micromachines 2024.  
   https://doi.org/10.3390/mi15020253

8. Jurj, *A Physics-Regularized Neural Surrogate Framework for Printed Memristors*, IEEE Access 2026.  
   https://doi.org/10.1109/ACCESS.2026.3658220

9. Li et al., *Composable neural emulators accelerate thermoelectric generator design*, Nature 2026.  
   https://doi.org/10.1038/s41586-026-10223-1

10. Luo et al., *A Physics-Informed Neural Network-Based Scalable Model for GaN HEMTs*, IEEE TMTT 2026.  
    https://doi.org/10.1109/TMTT.2026.3666090

---

# 17. 一句话项目合同

> **先用独立求解器证明真实 2.5D 器件物理正确，再用 hybrid PINN 获得可复现的正向与泛化收益；只在 solver 验证的灵敏度子空间内做逆问题，任何高阶模块都必须接受单模块消融、失败止损和 claim 降级。**
