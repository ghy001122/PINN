# Paper Registry

This registry is a compact routing index for literature relevant to the current
synthetic digital-twin benchmark. It does not assert that these papers validate
the repository outputs as experimental data.

## Directly Useful For Current gamma_sub Route

| Topic | Paper or note | Current use |
| --- | --- | --- |
| External VO2 anchor | Zhang, Sipling, Qiu et al. 2024, Nature Communications 15, 6986, DOI `10.1038/s41467-024-51254-4` | Primary Priority D candidate; publisher source data/SI support a provenance-backed R-T or spiking fit/holdout audit. |
| NbO2 mechanism anchor | Slesazeck et al. 2015, RSC Advances, DOI `10.1039/C5RA19300A` | Primary Frenkel-Poole plus Joule-heating mechanism source and fallback curve candidate. || Stiff PINNs | Seiler et al. 2025, "Stiff Transfer Learning for Physics-Informed Neural Networks" | Deferred training strategy for stiff multi-physics residuals and continuation. |
| Memristor PINN | Lee et al. 2024, "A Compact Memristor Model Implemented Using Physics-Informed Neural Networks" | Supports PINN-style compact memristor modeling. |
| Physics-regularized memristor surrogate | Jurj 2026, "physics-regularized neural surrogate framework for printed memristors" | Supports physics-regularized surrogate framing. |
| Phase-field inverse PINN | Zhao et al. 2025, "Physics-informed neural networks for inverse problems in phase field models" | Supports inverse-PINN and parameter-field inversion framing. |
| Thermal/electrical neural emulator | Li et al. 2026, "Composable neural emulators for thermoelectric generator design and system-level optimization" | Background for differentiable thermal/electrical surrogate design. |

## Secondary Or Deferred

| Topic | Use boundary |
| --- | --- |
| Electromagnetic PINNs | Background only; not part of the active reduced `gamma_sub` task. |
| Scalable device PINNs for GaN HEMT | Background for future device-scale extensions. |
| Lumped kinetic PINN | Possible support for reduced kinetics and parameter inference. |
| Optical inverse design PINNs | Not central to the current memristor thermal-dissipation route. |
| NeuroPINN, NeuroSPICE, VSN, or system mapping | Deferred extension only. |

## Reading Rule

Use this registry before opening full papers. Exact values quoted by secondary reviews must not be copied until the primary table, figure, units, fitted/measured status, and reuse terms are verified. Read Google Drive source documents
only when the local digest is insufficient or the user explicitly asks for
literature verification.
