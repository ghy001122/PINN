# Next Actions

## Authoritative Current Queue

`Q2_M43_FINITE_WIDTH_THERMAL_SPREADING_CLOSURE` is the only research task.
M42 decision B allows a final thermal-only closure audit; it does not authorize
formal Qiu dynamics, inverse identification, or PINN training.
The constrained `gamma_sub` mainline stays locked and is not rerun.

### Bounded M43 package (one day maximum)

1. Preregister an isoflux finite-source thermal-spreading benchmark, domain and
   mesh ladder, evidence roles, fixed gates, and a strict CPU-call budget.
2. Compare the conservative finite-width FVM with an independent analytical or
   converged series reference for a finite source on a finite/half-space body.
3. Separate spreading resistance, one-dimensional resistance, finite-domain
   truncation, and transient storage; do not use Qiu lumped `Cth/Sth` locally.
4. Test only geometry/material ranges already source-registered. No curve fit,
   latent-heat insertion, hysteretic dynamic, inverse, or neural model.
5. If domain, mesh, and independent-reference gates pass, retain a 2.5D thermal
   impedance/kernel as a later model component. Otherwise choose C and stop 2D.

The relevant physical basis is finite-source thermal spreading, not another
network architecture. Jain (2024, DOI `10.1016/j.ijheatmasstransfer.2023.124946`)
provides a finite-thickness spreading-resistance reference and explicitly
separates total and one-dimensional resistance. Its steady/isothermal scope is
only a benchmark boundary, not a Qiu transient validation.

## Submission queue after M43

Select the target journal/article type from official sources; add author and
funding/conflict/AI-use declarations; render and visually inspect manuscript
and SI; publish redistributable assets and document restricted third-party
asset acquisition. Do not reopen science to fix formatting or scope concerns.

## Locked prohibitions

No M40/M40R/E1F rescue, Qiu refit, Zhang 13 V, M41, `gamma_eff` claim, device
dynamic GT, inverse/PINN, STL/Fourier/F-SPS expansion, threshold relaxation,
or transfer of NbO2/NbOx parameters into VO2. Exact Qiu reproduction,
experimental validation, arbitrary 2D field recovery, and successful trained
full-PINN wording remain `forbidden`.
