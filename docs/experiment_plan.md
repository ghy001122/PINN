# Experiment Plan

## Stage 1: Ground Truth Generation and Visualization

- Implement the one-dimensional electro-thermal-defect-conductive-state Ground Truth solver.
- Generate synthetic benchmark data for triangle and LTP/LTD voltage protocols.
- Plot I-V, G(t), temperature, defect state, conductive-state fraction, conductivity, and voltage/current traces.
- Verify shapes, finite values, and CPU smoke-test runtime.

## Stage 2: PINN Inverse Identification

- Train a PINN on sparse synthetic port observations and physics residuals.
- Estimate selected multiphysics parameters under documented priors.
- Compare field reconstruction and port-level observables against the synthetic Ground Truth.
- Report uncertainty and sensitivity where possible.

## Stage 3: Ablation, Robustness, Baseline Comparison, and Paper Figures

- Add noise robustness tests.
- Add protocol generalization tests across voltage waveforms.
- Compare against black-box MLP/LSTM and least-squares parameter fitting baselines.
- Add ablations for data-only, physics-only, missing physics terms, and reduced observations.
- Produce paper-quality figures with explicit synthetic-data labeling.
