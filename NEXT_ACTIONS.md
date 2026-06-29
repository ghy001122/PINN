# Next actions

## Immediate next step

Use the F-SPS-PINN v2 smoke training pipeline as the next engineering checkpoint. The goal is forward/backward/train smoke validation with the white-box `vo2_sigma(T, c_v, m)` closure, not a large ablation or performance claim.

Primary evidence:

- `docs\codex_reports\f_sps_pinn_architecture_mvp_report.md`
- `configs\pinn_inverse_v2_f_sps_smoke.yaml`
- `scripts\train_pinn_inverse_v2_smoke.py`
- `tests\test_pinn_inverse_v2_smoke.py`
- `outputs\tables\pinn_inverse_v2_f_sps_smoke_summary.json`

The constrained `gamma_sub` inversion remains the most stable paper claim. The F-SPS-PINN path is method development that must remain bounded as synthetic numerical digital-twin smoke evidence until proper baselines are run.

## Recommended tasks

1. Keep v2 smoke claims limited to finite forward/backward/train closure with `vo2_sigma`.
2. Add a small-run baseline comparing free `log_sigma` versus white-box `vo2_sigma` only after the smoke path is stable.
3. Preserve the constrained `gamma_sub` storyline as the defensible paper core.
4. Keep dynamic gate and frequency losses disabled until each has a separate smoke test in the v2 training path.
5. Keep all generated datasets and figures reproducible through scripts rather than committing large binary artifacts.

## Do not do next

- Do not modify frozen Ground Truth v1.1 acceptance configs, data, metrics,
  manifest, equations, or default parameters.
- Do not describe synthetic numerical benchmark outputs as experimental data.
- Do not claim full 3D device simulation or sparse-port full hidden-field
  recovery.
- Do not start F-Pyramid, STL continuation, observability-augmented sparse
  temperature/state recovery, VO2-NbO2 oscillator work, NeuroSPICE/NeuroPINN,
  or system-level mapping unless explicitly authorized.

## Deferred Method Enhancements

Record these as future options, not current work:

- replace free `log_sigma` with physics-constrained sigma closure;
- implement gamma_sub-PINN;
- add F-Pyramid or multi-resolution Fourier features;
- add stiff transfer learning continuation;
- add observability-augmented sparse `T/m` extension.