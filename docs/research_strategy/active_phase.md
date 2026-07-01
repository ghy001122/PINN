# Active Phase

## Current Phase

`literature-anchored gamma_sub calibration and simulator-backed protocol validation`

The current phase strengthens the constrained `gamma_sub` manuscript line with literature/engineering-prior sanity checks, explicit no-fabrication handling for missing digitized literature curves, a T_sw calibration-necessity audit, simulator-backed sequential protocol validation, and manuscript-style figure/caption scaffolding.

This phase does not revise frozen Ground Truth v1.1, does not create experimental evidence, does not claim sparse-port full hidden-field recovery, and does not claim F-SPS-PINN performance superiority.

## Evidence Added

- Literature sanity table: `data\literature\literature_parameter_sanity_table.csv`.
- External curve-fit template/blocker: `outputs\tables\literature_curve_fit_external_anchor_summary.json`.
- T_sw calibration necessity: `outputs/tables/gamma_sub_tsw_calibration_necessity_summary.json`.
- Simulator-backed sequential protocol validation: `outputs/tables/gamma_sub_simulator_backed_sequential_protocol_validation_summary.json`.
- Manuscript figure/caption scaffolding under `docs/paper/` and ignored figures under `outputs/figures/manuscript_style_gamma_sub/`.

## Claim Boundary

Allowed: constrained reduced `gamma_sub` inversion is defensible only under fixed or tightly bounded micro-kinetic and switching priors, with T_sw explicitly treated as the dominant calibration boundary.

Forbidden: real experimental validation, direct VO2/NbO2 device replication, unique sparse-port full hidden-field recovery, unconditional joint identifiability, or F-SPS-PINN superiority.
