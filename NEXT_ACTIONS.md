# Next actions

## Immediate next step

Use the F-SPS-PINN v2 Fourier on/off ablation under stress as the current engineering checkpoint. The goal is to compare `vo2_sigma_fourier_off` and `vo2_sigma_fourier_on` under the same sharp-transition synthetic stress condition, seed, epochs, field-anchor count, and loss weights. This is not a large ablation or formal performance claim.

Primary evidence already completed:

- `docs\codex_reports\f_sps_pinn_architecture_mvp_report.md`
- `configs\pinn_inverse_v2_f_sps_smoke.yaml`
- `scripts\train_pinn_inverse_v2_smoke.py`
- `outputs\tables\pinn_inverse_v2_f_sps_smoke_summary.json`
- `configs\pinn_inverse_v2_f_sps_baseline.yaml`
- `scripts\run_pinn_inverse_v2_baseline.py`
- `outputs\tables\pinn_inverse_v2_f_sps_baseline_summary.json`
- `outputs\tables\pinn_inverse_v2_f_sps_baseline_runs.csv`
- `configs\pinn_inverse_v2_phase_transition_stress.yaml`
- `scripts\run_pinn_inverse_v2_phase_transition_stress.py`
- `outputs\tables\pinn_inverse_v2_phase_transition_stress_summary.json`
- `outputs\tables\pinn_inverse_v2_phase_transition_stress_cases.csv`

Current ablation evidence:

- `configs\pinn_inverse_v2_fourier_ablation.yaml`
- `scripts\run_pinn_inverse_v2_fourier_ablation.py`
- `tests\test_pinn_inverse_v2_fourier_ablation.py`
- `outputs\tables\pinn_inverse_v2_fourier_ablation_summary.json`
- `outputs\tables\pinn_inverse_v2_fourier_ablation_runs.csv`

The constrained `gamma_sub` inversion remains the most stable paper claim. The F-SPS-PINN path is method development that must remain bounded as synthetic numerical digital-twin evidence until stronger baselines and stress tests support a narrower claim.

## Recommended tasks

1. Keep Fourier-ablation claims limited to small-run numerical comparison under one stress condition.
2. If Fourier on clearly helps, run a slightly longer small-run or prepare a figure-ready summary.
3. If Fourier on does not clearly help, return to the constrained `gamma_sub` paper mainline and keep F-SPS-PINN in appendix or future work.
4. Keep frequency losses, dynamic gate training, and STL disabled until each has a separate smoke test in the v2 training path.
5. Keep all generated datasets and figures reproducible through scripts rather than committing large binary artifacts.

## Do not do next

- Do not modify frozen Ground Truth v1.1 acceptance configs, data, metrics, manifest, equations, or default parameters.
- Do not describe synthetic numerical benchmark outputs as experimental data.
- Do not claim full 3D device simulation or sparse-port full hidden-field recovery.
- Do not claim F-SPS-PINN performance superiority from the Fourier ablation.
- Do not claim stress preflight or Fourier ablation has solved phase-transition stiffness.
- Do not start STL continuation, observability-augmented sparse temperature/state recovery, VO2-NbO2 oscillator work, NeuroSPICE/NeuroPINN, or system-level mapping unless explicitly authorized.

## Deferred Method Enhancements

Record these as future options, not current work:

- implement gamma_sub-PINN;
- add stiff transfer learning continuation;
- add observability-augmented sparse `T/m` extension.
