# Literature-Anchored Gamma_Sub Calibration And Simulator-Backed Protocol Validation Report

## Scope

Repository: `https://github.com/ghy001122/PINN`

Base commit before this task: `8f160a9c4c23256b5f978710bb63dcb739c78447`

All results are synthetic numerical digital-twin benchmark evidence. They are not experimental measurements, not full 3D device validation, and not sparse-port full hidden-field recovery.

## What Changed

Added literature/engineering-prior sanity checks, an external-curve fitting template with no-fabrication behavior, T_sw calibration-necessity evidence, simulator-backed sequential protocol validation, manuscript-style figure generation, and caption/style scaffolding.

## Literature Findings

Google Drive literature review found usable text-level anchors from:

- Lee et al. (2024), compact memristor PINN: GMMS threshold/time-constant anchors such as `VON=0.2 V`, `VOFF=0.1 V`, `tau=1e-4`, and resistance contrast `ROFF/RON=20`.
- Jurj (2026), physics-regularized printed memristor surrogate: supports literature-calibrated synthetic benchmark framing, explicit non-fabrication boundaries, and activation/contrast examples such as `Ea=0.379 eV` and high reported switching ratios.

No provenance-backed digitized numerical curve CSV was available in the repository. Therefore curve fitting is blocked/template-only and no external curve data were fabricated.

## Key Results

- Literature sanity: `8` checked parameters, `7` plausible under literature/engineering-prior framing, `1` boundary-sensitive item.
- Curve fitting: `0` curves fit; blocked because `No provenance-backed digitized numerical literature curve was available in the repository, so curve fitting is blocked and only a template registry is emitted.`
- T_sw calibration necessity: minimum reliable tested T_sw prior width `0.02`; wide-prior relative error `0.8309764722472351`; wrong-calibration relative error `0.3021732626353582`.
- Simulator-backed sequential validation: `150` ODE-backed finite cases; best mean-error candidate `multi_pulse_to_ltp_ltd`; supports response-surface best ranking `True`; frozen GT unchanged `True`.

## Claim Boundary

The strongest manuscript claim is still identifiability-guided target-space reduction: `gamma_sub` can be a reduced inverse target only when T_sw and related micro-kinetic priors are fixed or tightly bounded. T_sw remains the dominant limitation and must be handled as a calibration/prior requirement.

## Outputs

- `data/literature/literature_parameter_sanity_table.csv`
- `data/literature/literature_curve_registry.csv`
- `outputs/tables/literature_phase_change_parameter_sanity_summary.json`
- `outputs/tables/literature_curve_fit_external_anchor_summary.json`
- `outputs/tables/gamma_sub_tsw_calibration_necessity_summary.json`
- `outputs/tables/gamma_sub_simulator_backed_sequential_protocol_validation_summary.json`
- `docs/literature/literature_parameter_sanity_notes.md`
- `docs/literature/literature_curve_fit_notes.md`
- `docs/paper/main_figure_captions_v1.md`
- `docs/paper/supplementary_figure_captions_v1.md`
- `docs/paper/table_captions_v1.md`
- `docs/paper/visual_style_guide.md`

Ignored figure outputs generated under `outputs/figures/manuscript_style_gamma_sub/`.

## Validation

Validation commands requested by the task were run after implementation. Final pass/fail status is recorded in the final Codex response for the pushed commit.

## Next Step

Draft the manuscript around the constrained `gamma_sub` line, with T_sw calibration as a stated boundary. Do not expand F-SPS-PINN unless a separate method-paper task is opened.
