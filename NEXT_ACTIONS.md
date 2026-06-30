# Next actions

## Immediate next step

Use the F-SPS-PINN v2 phase-transition stress preflight as the current engineering checkpoint. The goal is to test whether the white-box `vo2_sigma(T, c_v, m)` closure remains finite and trainable under sharper, near-threshold, and high-contrast synthetic phase-transition parameters. This is not a large ablation or formal performance claim.

Primary evidence already completed:

- `docs\codex_reports\f_sps_pinn_architecture_mvp_report.md`
- `configs\pinn_inverse_v2_f_sps_smoke.yaml`
- `scripts\train_pinn_inverse_v2_smoke.py`
- `outputs\tables\pinn_inverse_v2_f_sps_smoke_summary.json`
- `configs\pinn_inverse_v2_f_sps_baseline.yaml`
- `scripts\run_pinn_inverse_v2_baseline.py`
- `outputs\tables\pinn_inverse_v2_f_sps_baseline_summary.json`
- `outputs\tables\pinn_inverse_v2_f_sps_baseline_runs.csv`

Current preflight evidence:

- `configs\pinn_inverse_v2_phase_transition_stress.yaml`
- `scripts\run_pinn_inverse_v2_phase_transition_stress.py`
- `tests\test_pinn_inverse_v2_phase_transition_stress.py`
- `outputs\tables\pinn_inverse_v2_phase_transition_stress_summary.json`
- `outputs\tables\pinn_inverse_v2_phase_transition_stress_cases.csv`

The constrained `gamma_sub` inversion remains the most stable paper claim. The F-SPS-PINN path is method development that must remain bounded as synthetic numerical digital-twin evidence until proper baselines and stress tests are run.

## Recommended tasks

1. Keep phase-transition stress claims limited to numerical stability and small-scale response.
2. If the stress preflight remains stable, run a Fourier on/off ablation or dynamic gate smoke test next.
3. Preserve the constrained `gamma_sub` storyline as the defensible paper core.
4. Keep frequency losses and STL disabled until each has a separate smoke test in the v2 training path.
5. Keep all generated datasets and figures reproducible through scripts rather than committing large binary artifacts.

## Do not do next

- Do not modify frozen Ground Truth v1.1 acceptance configs, data, metrics, manifest, equations, or default parameters.
- Do not describe synthetic numerical benchmark outputs as experimental data.
- Do not claim full 3D device simulation or sparse-port full hidden-field recovery.
- Do not claim F-SPS-PINN performance superiority from the stress preflight.
- Do not start STL continuation, observability-augmented sparse temperature/state recovery, VO2-NbO2 oscillator work, NeuroSPICE/NeuroPINN, or system-level mapping unless explicitly authorized.

## Deferred Method Enhancements

Record these as future options, not current work:

- implement gamma_sub-PINN;
- add stiff transfer learning continuation;
- add observability-augmented sparse `T/m` extension.
