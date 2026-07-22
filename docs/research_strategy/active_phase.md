# Active Phase

Active phase ID: `Q2_M44_THERMAL_REDUCTION_VALIDITY_AND_REFUSAL`

## Objective and manuscript use

Run one bounded component-level reduction audit against the locked M43
finite-source thermal-spreading evidence. Compare one-RC, two-RC, and causal
thermal-kernel descriptions under matched data, physical-admissibility, and
complexity rules. Determine the region in which a scalar thermal coordinate is
sufficient, the region in which additional memory is required, and the region
in which inference or prediction must be refused.

A pass may support a qualified reduced-component validity/refusal map. A
failure is a useful model-reduction boundary. Neither outcome validates Qiu
dynamics, a real device, an inverse method, or a PINN. The constrained `gamma_sub` mainline remains frozen and unchanged.

## Upstream decisions

M42 remains `failed_but_informative`, decision B:

- source/local resistance error `1.33023`;
- domain sensitivity `0.84235`;
- mesh fine-pair sensitivity `0.13813`;
- time fine-pair sensitivity `0.00886`;
- finite-width/x-z closure error `0.67058`;
- smooth discrete enthalpy ledger `2.58e-14`;
- switching enthalpy unassessed because latent heat is not source-locked.

M43 is `qualified_supported`, decision
`M43_THERMAL_CLOSURE_GO_COMPONENT_ONLY`: `15` unique thermal PDE forwards and
all `21/21` preregistered gates passed for a manufactured finite rectangular
isoflux source on a homogeneous isotropic half-space. This does not supersede
any M42 failure or provide device/external evidence.

## Allowed M44 scope

- one-RC and positive two-RC thermal-impedance reductions;
- a causal, passive thermal-kernel comparator based only on the locked M43
  component evidence;
- preregistered fit/calibration versus held-out time/Fourier-number regimes;
- matched waveform, energy, asymptotic, stability, complexity, and runtime
  metrics;
- an explicit component-level sufficient/extra-memory/refusal map.

Before execution, lock the data hashes, split, fitting budget, physical
constraints, thresholds, decision logic, and exact allowed/forbidden wording.
No post-result threshold or regime change is permitted.

## Stop rule

M44 is one bounded comparison, not a model-search campaign. If the preferred
reduction is unstable across held-out regimes, violates causality/passivity, or
cannot meet its preregistered accuracy/complexity gates, preserve the failure
and define the refusal region. Then freeze the scientific results and return to
submission; no second reduction-repair round is authorized.

## Forbidden

Qiu parameter fitting, device coupling, author-code equivalence, M40/M40R rerun,
M41, local use of lumped `Cth/Sth`, unsourced latent heat, active hysteretic
device forward, `gamma_eff` or new `gamma_sub` claim, inverse or PINN, Zhang
13 V, external-validation, experimental, arbitrary-field, or successful-neural
claims.
