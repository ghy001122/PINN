# Reviewer Defense Notes

## Why 1D?

The first paper version targets a stable, interpretable inverse-identification benchmark. A 1D model captures the dominant through-thickness coupling among voltage drop, Joule heating, effective defect redistribution, and conductive-state evolution while keeping the inverse problem tractable for sparse port observations. Full 3D Maxwell or complete phase-field modeling is reserved for later work.

## Why synthetic data?

The first version evaluates whether a physics-informed inverse-identification workflow can recover hidden fields and parameters under controlled conditions. Synthetic Ground Truth enables exact knowledge of latent states, reproducible noise studies, and clean ablations. The manuscript must label these results as synthetic benchmarks, not measured experiments.

## Is `c_v` truly oxygen vacancy concentration?

No direct microscopic claim is made in the first version. `c_v` is an effective defect / oxygen-vacancy state variable. It is motivated by oxide memristor physics but should not be described as a directly measured vacancy concentration.

## Is `m` a real crystallographic phase fraction?

No. `m` is an effective conductive-state fraction. It compresses unresolved microscopic changes into a bounded state variable used for benchmark modeling. It should not be described as a measured crystallographic phase fraction.

## Does using the same physics in GT and PINN create inverse crime?

It can, if presented carelessly. The first version should acknowledge that a PINN trained against a synthetic solver with matching physics is a controlled benchmark rather than proof of real-device predictive validity.

## How to mitigate inverse crime?

- Add noisy sparse observations.
- Hold out voltage protocols for generalization tests.
- Use parameter mismatch and missing-term ablations.
- Compare against black-box and non-physics baselines.
- Later validate against documented literature curves or lab data with separate provenance.

## Why not use black-box MLP/LSTM?

Black-box models are useful baselines but do not enforce electro-thermal-defect consistency and generally require more data. The PINN route is motivated by sparse observations, hidden-state reconstruction, and extrapolation across voltage protocols. The project still keeps black-box baselines for fair comparison.
