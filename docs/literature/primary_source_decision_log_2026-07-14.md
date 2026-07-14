# Primary-Source Decision Log — 2026-07-14

## Evidence Boundary

This review used the two user-provided Google Drive folders and primary publisher/preprint records. No paper parameter is treated as a measurement made by this project, and no external curve has yet been ingested into the repository.

## Device And Phase-Transition Sources

| Source | Directly supports | Does not support |
| --- | --- | --- |
| Chen et al., *Advanced Functional Materials* 35, 2423800 (2025), DOI `10.1002/adfm.202423800`, main paper and SI in the user Drive | NbO2 threshold switching as field-assisted Poole–Frenkel/electrothermal runaway; effective thermal resistance/capacitance as device controls; SnSe thermal engineering; core PF plus shell leakage compact modeling | importing fitted values into VO2 or the frozen Nb/NbOx/V2O5/Ni-inspired benchmark; claiming the repository reproduced SnSe/NbO2 |
| Qiu et al., *Advanced Materials* (2024), DOI `10.1002/adma.202306818`, main paper and SI in the user Drive | VO2 branch-dependent hysteresis, lumped electrothermal oscillator equations, experimental/model comparison, and fitted thermal/circuit parameters | treating uniform-temperature and fitted metallic-channel assumptions as device-resolved truth |
| Liu et al., *IEEE Electron Device Letters* 45, 708–711 (2024), DOI `10.1109/LED.2024.3362829`, user Drive | coplanar NbOx topology, passivation relevance, and a defensible motivation for multi-terminal structures | arbitrary segmented-terminal field recovery or direct reuse of a VO2 hysteresis state law |
| Zhang, Sipling, Qiu et al., *Nature Communications* 15, 6986 (2024), DOI `10.1038/s41467-024-51254-4` | a public VO2 RC/electrothermal model, source data, code provenance, distinct voltage protocols, and CC BY 4.0 reuse terms | validation of the frozen mainline material stack or universal thermal parameters |

The [Nature Communications article](https://www.nature.com/articles/s41467-024-51254-4) explicitly provides source data and a two-equation electrical/thermal model. The associated code is archived at [Zenodo 10.5281/zenodo.13119587](https://zenodo.org/records/13119587). It is therefore the safest Priority D provenance candidate. The allowed result is a **VO2 literature-family external curve anchor**, not experimental validation of the frozen mainline.

## PINN And Surrogate Sources

| Source | Decision for this project |
| --- | --- |
| Seiler, Lei, Protopapas, “Stiff Transfer Learning for Physics-Informed Neural Networks” (2025), [arXiv:2501.17281](https://arxiv.org/abs/2501.17281) | Full STL requires a shared representation, multiple low-stiffness heads, and evaluated high-stiffness transfer. The current mini/proxy audits do not reproduce it. |
| Zhao et al., *Neural Networks* 190, 107665 (2025), DOI `10.1016/j.neunet.2025.107665` | Supports inverse PINNs for phase-field equations with numerical/full-field data; it does not justify sparse-terminal phase-field recovery. |
| Lee et al., *Micromachines* 15, 253 (2024), DOI `10.3390/mi15020253` | Supports a later PINN-to-Verilog-A compact-model path; export is an engineering extension, not current validation. |
| Jurj, *IEEE Access* (2026), DOI `10.1109/ACCESS.2026.3658220` | Supports physics-regularized surrogate comparisons, variability/noise tests, and digitized external curves; its literature-calibrated synthetic evidence must not be relabeled experimental. |
| Li et al., *Nature* 652, 643–650 (2026), user Drive | Supports material-specific composable emulators when only device outputs are needed; also warns that a PINN is not automatically the best surrogate when terminal outputs suffice. |

## Consequences For Planning

1. Separate VO2 hysteretic and NbO2 Poole–Frenkel kernels.
2. Keep numerical solvers as the trusted forward reference.
3. Require a measurable neural advantage—amortized inverse speed, uncertainty, assimilation, or within-family OOD—before making a neural architecture a main claim.
4. Treat full STL, universal Fourier/F-SPS superiority, and arbitrary 2D field recovery as `forbidden` until their exact gates pass.
5. Use the Nature source-data package for the first external fit/holdout audit; use Chen/Qiu/Liu primarily for mechanism, topology, and reviewer-defense positioning.
