# Methods V1

This manuscript package describes a synthetic numerical digital-twin benchmark. It does not use measured device data.

## Benchmark

The frozen one-dimensional Ground Truth v1.1 benchmark supplies terminal voltage/current/conductance observations and hidden thermal, defect, switching-state, and conductivity fields. It is used to test inverse identifiability and constrained reduced-target inversion.

## Literature And Engineering Priors

Literature and engineering priors are used to bound plausible parameter ranges. They are not measured material parameters for the simulated device. Provenance-backed digitized curves must be stored as CSV files under `data/literature/curves/` before any external curve-fit claim is made.

## Reduced Inverse Target

The primary inverse target is the effective substrate heat-dissipation parameter `gamma_sub`. Micro-defect transport and switching/conductivity parameters are fixed or tightly bounded. The method claim is conditional reduced inversion, not full hidden-field recovery.

## Calibration-Before-Inversion Workflow

The proposed workflow is: first constrain or probe `T_sw`, then estimate `gamma_sub` from sparse port observations using the frozen simulator and a port-objective plus heat-residual term. Wrong or wide `T_sw` priors remain the main failure mode.

## Sequential Protocol Validation

Sequential protocol validation is performed by re-running the ODE simulator with configured pulse protocols, candidate `gamma_sub` values, noise levels, seeds, and bounded `T_sw` scenarios. These are synthetic preflight cases, not experimental protocols.
