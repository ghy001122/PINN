# Literature-Anchored Quasi-2D Structures

This registry is literature-guided motivation for a synthetic numerical digital-twin preflight. It is not experimental validation.

| ID | Source | Role | Allowed use | Forbidden use |
| --- | --- | --- | --- | --- |
| `vo2_phase_field_slab` | Shi & Chen, Phase-field model of IMT in VO2 under electric field | phase-field/domain evolution reference | slab/domain-front physics | experimental validation |
| `vo2_localized_heater_strip` | Bohaichuk et al., localized triggering of VO2 using CNT | localized heater/hotspot/electrothermal structure reference | lateral hotspot and local Joule heating motivation | claiming identical geometry or dimensions without explicit provenance |
| `vo2_sin_threshold_switch` | Brown et al., electro-thermal characterization of dynamical VO2 memristors | local activity and electrothermal device-modeling reference | electrothermal threshold-switch motivation | direct parameter copying without provenance |
| `nbo2_threshold_closure` | Slesazeck et al., physical model of NbO2 threshold switching | Frenkel-Poole + Joule-heating conduction closure | conduction model motivation | 2D geometry evidence |
| `generic_2d_pinn_phase_change` | 2025 CPC 2D phase-change PINN | diffuse-interface/enthalpy PINN method reference | numerical method inspiration | VO2/NbO2 device validation |
