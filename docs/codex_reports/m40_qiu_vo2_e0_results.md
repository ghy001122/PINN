# M40 Qiu VO2 Conservative 2D E0 Results

- Task: `Q2_M40_QIU_VO2_REAL_DEVICE_2D_BRIDGE_E0`
- Base: `e3d47edf7aa4cfc57b0272da20dd1f5654f8c877`
- Preregistration commit: `017260194e42d94633bf64354c922b238dc40c79`
- Evidence status: `failed_but_informative`
- E0 all gates pass: `False`
- Frozen GT unchanged: `True`

## Source boundary

Qiu et al. report the VO2/Ti/Au/Al2O3 geometry, circuit topology,
R-T loops, and lumped fitted compact parameters. Local 2D thermal
properties, substrate thickness, contact resistivity, interface thermal
resistance, and raw numeric curves are unresolved. No fit or digitization
was performed in M40.

Reported/source-fitted quantities include VO2 100 nm, a 100 x 500 nm2
footprint, Ti 15 nm/Au 40 nm, Al2O3, the series-load/parallel-capacitance
topology, the 320-360 K major loop and 330/335 K minor reversals, and the
parameters in the locked manifest. Missing quantities include substrate
thickness, lateral electrode overlap, local Ti/Au/Al2O3 and phase-dependent
VO2 thermal properties, individual contact resistivity, every thermal
boundary resistance, remote heat-loss data, a local history relaxation time,
filament geometry, and raw numeric R-T/I-t arrays.

## Formal gates

| Gate | Value | Threshold | Pass |
| --- | ---: | ---: | :---: |
| manufactured_electrical | 1.427939e-15 | <=1.0e-10 | True |
| layered_electrical | 1.678765e-15 | <=1.0e-10 | True |
| layered_thermal | 1.698532e-14 | <=1.0e-10 | True |
| electrical_contact_jump | 1.526557e-16 | <=1.0e-10 | True |
| thermal_interface_jump | 1.172880e-14 | <=1.0e-10 | True |
| substrate_electrical_invariance | 0.000000e+00 | <=1.0e-12 | True |
| substrate_leak_tamper_detection | 6.788971e-03 | >=1.0e-3 | True |
| current_conservation | 2.454598e-08 | <=1.0e-6 | True |
| smooth_window_energy_conservation | 1.426260e-08 | <=1.0e-4 | True |
| switching_window_energy_conservation | 2.324413e-12 | <=1.0e-3 | True |
| main_qoi_mesh_convergence | 2.478776e-02 | <=1.0e-2 | **False** |
| peak_field_mesh_convergence | 1.106638e-01 | <=2.0e-2 | **False** |
| uniform_2d_to_reduced | 2.349105e-15 | <=1.0e-2 | True |
| nominal_qiu_forward_smoke RC residual | 7.009568e-18 A | <=1.0e-12 A | True |

The nominal smoke's maximum diagnostic energy imbalance was
`1.11796e-4`; it was not the preregistered smooth-window fixture used for the
formal smooth-energy gate and is retained here rather than hidden. This does
not change the overall failure decision.

## Claim decision

No positive M40 solver claim; the failed E0 boundary is retained.

Forbidden: Qiu real-device calibrated; exact Qiu source-model reproduction; experimental validation; inverse identification; PINN training or sensitivity fidelity; gamma_eff relation; full 2D hidden-field recovery

M41 conservative reduction authorized: `False`.
