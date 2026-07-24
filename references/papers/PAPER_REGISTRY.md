# Paper Registry

This is a compact routing index for the active GeoPhase route. It does not
assert that literature validates repository outputs as experimental data.
Exact values require verification in the primary source, including units and
whether each value is measured, fitted, digitized, or assumed.

## Active Device And Material Sources

| Topic | Primary source | Permitted use | Forbidden transfer |
| --- | --- | --- | --- |
| Qiu VO2 coplanar thermal neuristor | Qiu et al., *Advanced Materials* (2024), DOI `10.1002/adma.202306818` | primary x-y geometry, circuit topology, hysteresis/mechanism motivation, literature-fitted device-level quantities | exact author-code reproduction, calibrated local fields, treating fitted lumped thermal values as local material constants |
| SnSe/NbO2 thermal engineering | Chen et al., *Advanced Functional Materials* 35, 2423800 (2025), DOI `10.1002/adfm.202423800` | auxiliary Poole--Frenkel/electrothermal-runaway kernel and thermal-barrier trend validation | importing VO2 state laws/thresholds or claiming zero-shot material transfer |
| Coplanar NbOx topology | Liu et al., *IEEE Electron Device Letters* 45, 708--711 (2024), DOI `10.1109/LED.2024.3362829` | geometry/multi-terminal motivation and future holdout | arbitrary full-field recovery or direct VO2 hysteresis reuse |
| Public VO2 source/data route | Zhang, Sipling, Qiu et al., *Nature Communications* 15, 6986 (2024), DOI `10.1038/s41467-024-51254-4` | provenance, source-model comparison, and historical public-data boundary | validation of the new 2.5D local model or independent project experiment |
| NbO2 mechanism | Slesazeck et al., *RSC Advances* (2015), DOI `10.1039/C5RA19300A` | Poole--Frenkel plus Joule-heating mechanism context | VO2 parameter or state-law transfer |

## Active PINN And Scientific-ML Sources

| Topic | Source | Project boundary |
| --- | --- | --- |
| Stiff transfer | Seiler, Lei, Protopapas, *Stiff Transfer Learning for Physics-Informed Neural Networks* (2025), arXiv `2501.17281` | joint phase/Joule homotopy may use the continuation idea; full STL requires the actual multi-head/head-transfer comparison |
| Phase-field inverse PINN | Zhao et al., *Neural Networks* 190, 107665 (2025), DOI `10.1016/j.neunet.2025.107665` | supports inverse PINNs with field/multiphysics data; does not support terminal-only raw recovery |
| Memristor PINN | Lee et al., *Micromachines* 15, 253 (2024), DOI `10.3390/mi15020253` | compact-model/PINN prior art; not novelty for using a PINN on a memristor |
| Physics-regularized memristor surrogate | Jurj, *IEEE Access* (2026), DOI `10.1109/ACCESS.2026.3658220` | surrogate/noise/cross-curve baseline context; literature-calibrated synthetic evidence remains synthetic |
| Composable emulator | Li et al., *Nature* 652, 643--650 (2026) | motivates material-specific replaceable kernels and pure-surrogate baselines | zero-shot material truth or proof that PINN is automatically preferable |

## Candidate Sources Requiring Task-Specific Primary Read

- PINNacle for task-dependent benchmark conclusions;
- RoPINN for region-optimized residual prior art;
- phase-change heat-conduction PINNs for transition/interface weighting;
- scalable semiconductor-device PINNs for geometry-conditioned device models.

Do not cite a title-level registry entry for a quantitative claim. Open the
primary paper and record its exact method/result boundary in the literature
decision log before using it in equations, novelty wording, or a manuscript
comparison.

## Reading Rule

Use this registry before opening full papers. Secondary reviews and the revised
brainstorm are hypothesis/design sources, not authority for a physical number
or novelty claim. Google Drive source documents should be read only when a
task requires the corresponding source contract.
