# Phase-Change PINN SCI Sprint Blueprint

## Purpose

This document integrates four strategic outputs into one compact project-level guide:

1. project panorama and long-term vision;
2. current engineering state and theoretical bottlenecks;
3. core R&D roadmap for stiffness-aware phase-transition modeling;
4. SCI paper outline and experiment evidence matrix.

It is a planning and handoff document, not an experimental result report. It should be used to guide future Codex tasks, paper drafting, and method refactoring while preserving the current evidence boundary of the repository.

## Current Repository Reality

The repository currently supports a synthetic numerical digital-twin benchmark for oxide optoelectronic memristive devices. The frozen benchmark is still Nb/NbOx/V2O5/Ni-inspired, and all current data/results are synthetic numerical benchmark evidence, not measured experimental data.

The active completed evidence chain shows:

- Ground Truth v1.1 is frozen and must not be modified unless an explicit new GT revision is opened.
- v0/v1/v1.1 inverse PINN workflows are runnable and audited.
- Identifiability audit shows that sparse terminal observations constrain conductance-level response but cannot uniquely recover full hidden fields.
- Reduced `gamma_sub` inversion is stable under fixed micro-kinetic priors, but confounding parameters, especially `T_sw`, can bias the inverse result.
- Continuous off-grid refinement improves reduced `gamma_sub` recovery but remains a conditional synthetic benchmark result.

Therefore, the next research direction should not claim unconstrained full hidden-field recovery. The defensible route is an identifiability-aware, physics-constrained, reduced inverse digital twin.

## 1. Core Scientific Narrative

### 1.1 Problem Discovery

Traditional PINNs encounter two coupled failures in phase-transition memristive systems.

First, sparse terminal observations create an identifiability paradox. Measured or synthetic terminal signals such as

```math
V(t),\quad I(t),\quad G(t)
```

mainly constrain an integrated conductance response:

```math
G(t) \approx \int_{\Omega} \sigma(x,t)\,dx.
```

They do not uniquely determine the hidden fields:

```math
T(x,t),\quad c_v(x,t),\quad m(x,t),\quad \sigma(x,t).
```

Second, strong phase-transition materials such as VO2/NbO2 exhibit stiffness near the switching regime:

```math
T \approx T_c,
```

where the phase fraction and conductivity can change abruptly across several orders of magnitude. Standard MLP/PINN architectures suffer from spectral bias, residual-scale imbalance, and physically invalid shortcut learning through a free `log_sigma` head.

### 1.2 Proposed Theory

The long-term method target is F-SPS-PINN:

```math
\text{F-SPS-PINN}
=
\text{Fourier Pyramid}
+
\text{Spiking Phase-transition Surrogate}
+
\text{Stiffness-aware Physics-informed Learning}.
```

The method should use two coupled constraint domains:

| Domain | Constraint target | Purpose |
|---|---|---|
| Spatio-temporal physics domain | heat diffusion, Joule heating, phase dynamics, current continuity | prevent black-box curve fitting |
| Frequency/event domain | oscillation frequency, pulse width, switching time | improve identifiability of thermal dynamics |

The central technical shift is to replace a free surrogate conductivity head with a differentiable constitutive closure:

```math
\sigma = \sigma(T,c_v,m,E).
```

### 1.3 Experiment Breakthrough Logic

The paper should turn previous failure modes into evidence:

1. vanilla PINN and `log_sigma` surrogate can fit terminal traces but fail to recover hidden fields robustly;
2. identifiability audit proves why this failure is structural rather than a simple tuning issue;
3. target-space reduction to `gamma_sub` yields a defensible inverse problem under fixed priors;
4. a future VO2/NbO2-oriented white-box constitutive PINN can attack stiffness without overclaiming full-field recovery.

## 2. Engineering Assets Ready For Reuse

| Asset | Repository role | Research value |
|---|---|---|
| frozen GT v1.1 | synthetic benchmark standard | controlled forward world |
| triangle / ltp_ltd protocols | benchmark datasets | terminal and synaptic-like response tests |
| v0 inverse PINN | baseline inverse workflow | anchor-dependence and port-only limitations |
| v1/v1.1 physics runs | approximate physics regularization | shows loss balancing is insufficient |
| identifiability audit | observability boundary analysis | proves full hidden-field recovery is ill-posed |
| `gamma_sub` audit | reduced inverse target | defensible low-dimensional inverse route |
| confounding audit | prior-sensitivity analysis | identifies `T_sw` as dangerous confounder |
| continuous off-grid refinement | simulator-backed parameter refinement | moves beyond discrete candidate-grid inversion |

These assets should be preserved as the first half of the SCI story: problem discovery, boundary proof, and reduced inverse target justification.

## 3. Current Fatal Limitation

The current inverse PINN path still contains a fundamental physical weakness: the conductivity field can be represented by a positive network-predicted surrogate closure, often conceptually equivalent to a free `log_sigma` regression path.

This is useful for engineering proof-of-concept, but it is not a true phase-transition constitutive law. A real VO2/NbO2 model should not let the network arbitrarily output conductivity. It should compute conductivity from thermal, phase, defect, and electric-field variables:

```math
\sigma(x,t)=\sigma(T(x,t),c_v(x,t),m(x,t),E(x,t)).
```

The current architecture can therefore learn a terminally correct but physically ambiguous solution. This is acceptable as a baseline, not as the final paper method.

## 4. Future Core R&D Roadmap

### 4.1 Stage A: White-Box Physical Kernel

Goal: add a VO2/NbO2-oriented constitutive physics layer under `src/pinnpcm/physics/` and move the main path away from the free `log_sigma` surrogate.

Recommended files:

```text
src/pinnpcm/physics/vo2_constitutive.py
src/pinnpcm/physics/phase_field.py
src/pinnpcm/physics/effective_medium.py
src/pinnpcm/physics/thermal_residuals.py
```

Core equations:

```math
C_{\mathrm{th}}\frac{\partial T}{\partial t}
=
\nabla\cdot(k_{\mathrm{th}}\nabla T)
+
\sigma(T,c_v,m,E)|E|^2
-
\gamma_{\mathrm{sub}}(T-T_0).
```

A Landau-style phase variable can be represented through

```math
\mathcal{F}(m,T,c_v)
=
\frac{a}{2}(T-T_c(c_v))m^2
+
\frac{b}{4}m^4
+
\frac{c}{6}m^6,
```

with phase dynamics

```math
\tau_m\frac{\partial m}{\partial t}
=
-\frac{\partial \mathcal{F}}{\partial m}
+D_m\nabla^2 m.
```

Conductivity should be computed through an effective-medium or phase-mixture closure:

```math
\sigma(T,c_v,m)
=
(1-m)\sigma_{\mathrm{ins}}(T,c_v)
+m\sigma_{\mathrm{met}}(T).
```

The old `log_sigma` path should remain only as an ablation baseline.

### 4.2 Stage B: Stiffness-Resistant Network Upgrade

Goal: add multiscale representation and dynamic residual balancing under `src/pinnpcm/pinn/`.

Recommended files:

```text
src/pinnpcm/pinn/network.py
src/pinnpcm/pinn/loss_balancer.py
```

Fourier feature pyramid:

```math
\Gamma(z)
=
[z,\sin(2\pi B_1z),\cos(2\pi B_1z),...,\sin(2\pi B_Kz),\cos(2\pi B_Kz)].
```

Here `z` may include normalized space, time, and protocol information:

```math
z=[x,t,V(t)].
```

The main network should predict physical state variables such as

```math
\hat{T},\quad \hat{c}_v,\quad \hat{m},
```

while conductivity is computed by the white-box constitutive layer.

To handle residual stiffness, use MMoE-inspired dynamic residual gating:

```math
\mathcal{L}_{\mathrm{dyn}}
=
\sum_i w_i(z)\mathcal{R}_i(z)^2,
\quad
w_i(z)=\mathrm{softmax}(g_\psi(z)).
```

This is intended to balance heat, phase, electrical, port, and frequency residuals without relying on brittle fixed scalar weights.

### 4.3 Stage C: Frequency/Event Constraints

Goal: add VO2/NbO2 oscillator-aware constraints to `losses.py` and related physics utilities.

Recommended file:

```text
src/pinnpcm/physics/oscillation_metrics.py
```

Additional losses:

```math
\mathcal{L}_{f}
=
\left(\frac{\hat{f}_{\mathrm{osc}}-f_{\mathrm{osc}}}{f_{\mathrm{osc}}}\right)^2,
```

```math
\mathcal{L}_{w}
=
\left(\frac{\hat{w}_{\mathrm{pulse}}-w_{\mathrm{pulse}}}{w_{\mathrm{pulse}}}\right)^2.
```

These constraints should not be presented as universal for all memristors. They are specifically useful for threshold-switching or self-oscillatory VO2/NbO2-like regimes, where frequency and pulse width encode thermal charging/discharging dynamics.

## 5. SCI Paper Outline

### 5.1 Proposed Title

Stiffness-aware physics-informed neural digital twin for identifiable thermal parameter inference in phase-transition neuromorphic oxide memristors

### 5.2 Paper Structure

1. Introduction
   - phase-transition neuromorphic memristors;
   - sparse terminal sensing;
   - identifiability paradox;
   - stiffness collapse of vanilla PINN.

2. Physical Model
   - electro-thermal-defect-state coupling;
   - reduced thermal dissipation target `gamma_sub`;
   - VO2/NbO2 constitutive extension.

3. Method
   - identifiability-aware inverse formulation;
   - F-SPS-PINN architecture;
   - white-box conductivity layer;
   - Fourier pyramid;
   - dynamic residual gating;
   - frequency/event residuals.

4. Experiments
   - frozen synthetic benchmark;
   - baseline comparison;
   - identifiability audit;
   - `gamma_sub` constrained inversion;
   - constitutive and stiffness-aware ablations.

5. Discussion and Limitations
   - synthetic benchmark boundary;
   - reduced-order geometry;
   - fixed priors;
   - no claim of unconstrained full hidden-field recovery.

## 6. Experiment Evidence Matrix

| ID | Method | Purpose | Expected evidence |
|---|---|---|---|
| E0 | frozen GT solver | standard synthetic world | reproducible terminal and field data |
| E1 | black-box MLP/LSTM/TCN | data-driven baseline | terminal fit without physical interpretability |
| E2 | vanilla PINN + free `log_sigma` | traditional PINN baseline | terminal fit but hidden-field ambiguity |
| E3 | prior-constrained PINN | partial physical prior | improved stability but unresolved stiffness |
| E4 | v1.1 balanced PINN | existing repository baseline | loss balancing alone cannot solve `delta_T` error |
| E5 | constrained `gamma_sub` inversion | reduced inverse proof | stable conditional parameter recovery |
| E6 | white-box constitutive PINN | remove conductivity shortcut | improved physical consistency |
| E7 | Fourier-pyramid PINN | anti-spectral-bias test | lower error near transition fronts |
| E8 | dynamic-gated F-SPS-PINN | stiffness-aware loss balancing | more stable PDE residual trajectories |
| E9 | full F-SPS-PINN + frequency loss | dual-domain final model | better `gamma_sub`, frequency, pulse-width consistency |

Key metrics:

- terminal current error;
- conductance error;
- temperature-field error;
- phase-field error;
- conductivity-field error;
- stiffness-region weighted error near `T_sw` or `T_c`;
- oscillation-frequency error;
- pulse-width error;
- `gamma_sub` relative error;
- residual balance and training success rate.

## 7. Claim Boundary

Allowed claims:

- The repository provides synthetic numerical digital-twin benchmark evidence.
- Sparse terminal observations do not uniquely identify all hidden fields.
- Under fixed or literature-constrained priors, `gamma_sub` is a more defensible reduced inverse target than full hidden-field recovery.
- White-box phase-transition constitutive modeling is the necessary next step for a stronger VO2/NbO2 paper claim.

Disallowed claims:

- Current results are measured experimental validation.
- Port-only data uniquely recover `T`, `c_v`, `m`, and `sigma`.
- The present Nb/NbOx/V2O5/Ni-inspired benchmark already proves a full VO2/NbO2 physical device model.
- Free `log_sigma` regression is a real material constitutive law.

Acceptable simplifications for the paper:

| Simplification | Defensible explanation |
|---|---|
| 1D or quasi-1D geometry | focus on effective electro-thermal-phase dynamics; substrate loss is absorbed into `gamma_sub` |
| synthetic benchmark | controlled inverse-problem testbed, not fabricated experimental evidence |
| fixed micro-kinetic priors | required by identifiability audit; avoids unsupported joint inversion |
| phenomenological Landau/EMA model | appropriate for differentiable device-level digital twin, not first-principles material prediction |
| simplified defect dynamics | `c_v` is an auxiliary modulation field, not the main inverse target |
| frequency/event constraints only for oscillator regimes | valid for VO2/NbO2 threshold-switching modes, not universal to all memristors |

## 8. Placement In Repository

This file should remain in:

```text
docs/research_strategy/phase_change_pinn_sci_sprint_blueprint.md
```

Do not place it in `docs/codex_reports/`, because it is not a one-run Codex report. Do not place it at repository root, because the root already contains compact operational state files such as `CODEX_CONTEXT.md`, `PROJECT_STATE.md`, and registries.

Suggested future references:

- Add a short pointer in `CODEX_CONTEXT.md` only after the user explicitly opens the VO2/F-SPS-PINN method-expansion phase.
- Keep `docs/research_strategy/active_phase.md` as the phase gate. This blueprint should not override the active phase by itself.
- Create task-specific next-step files such as `docs/research_strategy/next_task_vo2_constitutive_v2.md` when implementation begins.

## 9. Codex Workflow Usage

For low-token Codex work, do not load this file by default. Use it only for phase changes, paper planning, or F-SPS-PINN refactoring tasks.

Recommended prompt pattern:

```text
Read only:
1. CODEX_CONTEXT.md
2. docs/research_strategy/active_phase.md
3. docs/research_strategy/phase_change_pinn_sci_sprint_blueprint.md

Task: implement the next narrowly scoped step from the blueprint: <specific step>.
Do not modify frozen Ground Truth v1.1. Keep all claims synthetic numerical benchmark only. Add/update tests. Write a concise Codex report under docs/codex_reports/ with commit hash, changed files, validation commands, and remaining risks. Push to GitHub.
```

Recommended implementation order:

1. create `next_task_vo2_constitutive_v2.md`;
2. implement `src/pinnpcm/physics/vo2_constitutive.py` with tests;
3. keep old `log_sigma` model as ablation baseline;
4. add Fourier pyramid only after the white-box constitutive layer is tested;
5. add dynamic residual gating only after baseline residuals are reproducible;
6. add frequency/event losses only after oscillator protocol generation is available.

## 10. Immediate Next Recommendation

The safest next Codex task is not full F-SPS-PINN implementation. It is a narrow preparatory task:

```text
Create docs/research_strategy/next_task_vo2_constitutive_v2.md and design the minimal API/test plan for a differentiable VO2 constitutive layer, without modifying frozen GT data or existing inverse results.
```

This keeps the project aligned with the current evidence chain while opening the path toward the stronger phase-transition paper architecture.
