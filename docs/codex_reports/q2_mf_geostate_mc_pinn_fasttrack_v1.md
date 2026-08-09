# Q2 MF GeoState MC-PINN Fast-Track V1

## Actual execution

Executed the six fixed M0/M1/M2 x C0/C1 reference runs, selected `M1`, generated twelve complete-case fields with two one-level sentinel refinements, and trained the recorded sparse-anchor baselines/PINN models at seed `20260809`. Evidence type: `literature-guided synthetic numerical digital-twin evidence`.

The first downstream attempt is immutable `invalid/INVALID_MODEL_SELECTION_HOTSPOT_METRIC` because the hotspot distance used device length rather than width and allowed a uniform-field argmax to vote. The six physical MVE solves were reused; Stage B was not rerun.

## Six-run MVE

| Case | Model | residual | current imbalance | port-field | field-sink | Tmax K | chi_2d |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| C0 | M0 | 9.003e-08 | 1.649e-16 | 5.735e-16 | 9.003e-08 | 326.836 | 0.000 |
| C0 | M1 | 7.981e-08 | 1.901e-15 | 2.587e-15 | 6.734e-08 | 326.861 | 0.000 |
| C0 | M2 | 7.023e-08 | 1.736e-15 | 3.019e-15 | 1.120e-08 | 326.862 | 0.000 |
| C1 | M0 | 8.188e-08 | 4.972e-16 | 7.205e-16 | 1.438e-08 | 326.836 | 0.188 |
| C1 | M1 | 8.178e-08 | 1.662e-16 | 2.891e-16 | 1.363e-08 | 326.892 | 0.186 |
| C1 | M2 | 7.059e-08 | 9.138e-16 | 1.156e-15 | 5.195e-09 | 326.893 | 0.156 |

Reference conclusion: `M1` is the simplest model satisfying the fixed ledger and M2-spread thresholds.

## Dataset and actual training

The pilot contains 12 full cases split only by complete case; training exposes 1% of each train-case field (minimum three points), while continuous collocation points are generated independently. No geometry-OOD claim is made.

| Model | steps | T rel L2 | phi rel L2 | current error | energy error | interface mismatch | passing test cases |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| B0 | 1000 | 0.4937 | 0.0099 | 0.0467 | 0.1172 | 1.4443 | 0 |
| B1 | 1000 | 0.2109 | 0.0179 | 0.0172 | 0.1458 | 1.2452 | 0 |
| M0 | 1000 | 0.2119 | 0.0128 | 0.0336 | 0.1417 | 0.7401 | 0 |

Gate disposition: `NO_GO_GEOSTATE_PINN_IDEA_SCREEN`; idea-level GO = `false`. The sole M1 homotopy rescue was not eligible and not executed.

Evidence status: software/method implementation `supported`; selected M1 reduced reference `qualified_supported`; single-seed PINN screen `failed_but_informative` and non-voting; formal PINN superiority `forbidden`.

## Figures

- `outputs/figures/q2_mf_geostate_mc_pinn_fasttrack_v1/Q2-MF-GEOSTATE-MC-PINN-FASTTRACK-20260809-V1-R1/model_form_spread.png`
- `outputs/figures/q2_mf_geostate_mc_pinn_fasttrack_v1/Q2-MF-GEOSTATE-MC-PINN-FASTTRACK-20260809-V1-R1/model_form_C0_fields.png`
- `outputs/figures/q2_mf_geostate_mc_pinn_fasttrack_v1/Q2-MF-GEOSTATE-MC-PINN-FASTTRACK-20260809-V1-R1/model_form_C1_fields.png`
- `outputs/figures/q2_mf_geostate_mc_pinn_fasttrack_v1/Q2-MF-GEOSTATE-MC-PINN-FASTTRACK-20260809-V1-R1/pilot_reference_fields.png`
- `outputs/figures/q2_mf_geostate_mc_pinn_fasttrack_v1/Q2-MF-GEOSTATE-MC-PINN-FASTTRACK-20260809-V1-R1/pinn_field_comparison.png`
- `outputs/figures/q2_mf_geostate_mc_pinn_fasttrack_v1/Q2-MF-GEOSTATE-MC-PINN-FASTTRACK-20260809-V1-R1/training_group_losses.png`
- `outputs/figures/q2_mf_geostate_mc_pinn_fasttrack_v1/Q2-MF-GEOSTATE-MC-PINN-FASTTRACK-20260809-V1-R1/port_and_energy_ledger.png`

## Claim boundary

Allowed manuscript sentence: "On a literature-guided synthetic Qiu-inspired 2.5D benchmark, contact-aware M1 was the simplest ledger-closed reference, while the single-seed mixed-conservative sparse-anchor PINN did not pass the preregistered field, energy-ledger, and interface-flux screen."

Forbidden: formal PINN superiority, experimental validation, stable-branch recovery, inverse recovery, Qiu quantitative reproduction, or geometry OOD.

## Single next priority

Stop architecture expansion and preserve this bounded screen as a physics-optimization or surrogate limitation.

Base SHA: `9ef452b2d0b8444e7aecc7593ab6c1ce22115ae3`. Final task SHA is reported in the delivery handoff after the evidence commit.
