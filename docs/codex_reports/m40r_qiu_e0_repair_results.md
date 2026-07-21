# M40R Qiu E0 Mesh and Active-Transient Repair Results

- Task: `Q2_M40R_QIU_E0_MESH_AND_ACTIVE_TRANSIENT_REPAIR`
- Base snapshot: `5e68d3bf25bcbe30bdce4840f9130c096a0177e1`
- Preregistration commit: `b935631c13ca288961e1bf72ed37782418693e54`
- Formal attempt: `1` of `1`
- Status: `failed_but_informative`
- Original numerical E0 gates pass: `True`
- New active-transient gates pass: `False`
- M41 authorized: `False`
- Frozen GT unchanged: `True`

## Non-voting forensic conclusion

The old field estimator did not reconstruct conservative face fluxes, but the old p99 failure was dominated by changing discrete quantiles around the ideal top-contact sharp-corner field and first-order coplanar-contact current crowding. The repair uses face-current J/sigma on one fixed physical grid; the unwindowed sharp-corner maximum remains non-convergent and non-voting.

The old M40 formal result and protected files remain byte-for-byte locked.
The old sharp-corner failure remains a valid diagnostic; no rounding,
exclusion-window enlargement, percentile reduction, fitting, or threshold
relaxation was used.

## Repaired original E0 gates

| Gate | Value | Pass |
| --- | ---: | :---: |
| current_conservation | 2.393913407e-07 | True |
| electrical_contact_jump | 1.526556659e-16 | True |
| layered_electrical | 1.678764654e-15 | True |
| layered_thermal | 1.698532068e-14 | True |
| main_qoi_mesh_convergence | 5.925864994e-03 | True |
| manufactured_electrical | 1.427939177e-15 | True |
| nominal_qiu_startup_finite_diagnostic | 7.009568215e-18 | True |
| peak_field_mesh_convergence | 8.474185043e-03 | True |
| smooth_window_energy_conservation | 1.426259682e-08 | True |
| substrate_electrical_invariance | 0.000000000e+00 | True |
| substrate_leak_tamper_detection | 6.788970969e-03 | True |
| switching_window_energy_conservation | 2.324412915e-12 | True |
| thermal_interface_jump | 1.172879975e-14 | True |
| uniform_2d_to_reduced | 2.349104707e-15 | True |

## New active-transient gates

| Gate | Value | Pass |
| --- | ---: | :---: |
| nominal_duration | 9.203389123e-02 | False |
| nominal_history_active | 6.455417746e-01 | True |
| nominal_reaches_Tc | 3.602249398e+02 | True |
| nominal_smooth_energy_conservation | 4.543253997e-13 | True |
| nominal_switching_energy_conservation | 1.233904201e-12 | True |
| nominal_transient_finite | True | True |
| nominal_within_source_R_T_domain | 3.602249398e+02 | False |
| transient_Tmax_fine_pair | 4.838089611e-03 | True |
| transient_Tmean_fine_pair | 1.552068839e-03 | True |
| transient_current_fine_pair | 3.421267915e-02 | False |
| transient_outward_heat_fine_pair | 6.377782522e-03 | True |

## Preserved old M40 boundary

- Status: `failed_but_informative`
- Old main-current mesh change: `2.478775649e-02`
- Old fixed-window field-p99 mesh change: `1.106638225e-01`
- Old M41 authorization: `False`

## Nominal transient interpretation

- The fine trajectory is a source-domain-limited truncated run: it stops at
  `1.601989950e-7 s` (`0.0920684 R_load C`) rather than the locked
  `5.22e-6 s` target when `Tmax=360.224940 K` exceeds the 360 K source limit.
- Activity class: `active_nonoscillatory_or_latched`
- Event count: `0`
- Median period: `None` s
- Local 2D sensible heat capacity: `7.804699999999999e-14` J/K
- Local bottom-conductance time constant: `7.8047e-08` s

The active run is solver-generated under a source-composed illustrative
protocol. It is not a measured trace, calibration, exact Qiu source-model
reproduction, or experimental validation. The energy ledger covers sensible
heat, Joule input, and bottom outflow only; it is not a latent-heat or full
phase-change enthalpy balance.

The `nominal_final_voltage_V`/`nominal_final_current_A` legacy keys in
the summary belong to the preserved 5 ns startup diagnostic, not to this
domain-limited active trajectory. The active JSON is authoritative for the
new coarse/fine traces.

## Repository validation

- Command: `.\.venv\Scripts\python.exe -m pytest -q`
- Passed: `387`
- Failed: `1`
- Skipped: `0`
- Validation complete: `True`

The sole failure is the historical `test_train_pinn_inverse_v1_smoke`
subprocess, which raised `_ArrayMemoryError` while allocating a 561 x 721
float32 plotting array after completing its two training epochs. This is not
an M40R gate failure, but the repository-wide validation is recorded as
failed and was not rerun.

## Claim decision

Repository validation failed; no positive M40R claim or M41 authorization.

Forbidden: Qiu real-device calibrated; exact Qiu source-model reproduction; experimental validation; measured active-transient reproduction; complete phase-change enthalpy conservation; converged ideal sharp-corner maximum field; inverse identification; PINN training or sensitivity fidelity; gamma_eff relation; full 2D hidden-field recovery

Return to manuscript fallback: `True`.
