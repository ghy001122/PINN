# Current Evidence Index

This is the compact routing surface. Current status is authoritative in
`PROJECT_STATE.md`; authorization is authoritative in
`docs/research_strategy/active_phase.md`. Cumulative history remains in the
registries and Git.

## Active GeoPhase Route

| Item | Status | Primary artifact |
| --- | --- | --- |
| Revised research contract | planning/governance fact `supported`; no scientific vote | `docs/research_strategy/geophase_oq_pinn_execution_contract.md` |
| Active 2.5D equations | preregistered method contract `supported`; implementation/result `forbidden` | `docs/method_equations.md` |
| G0/E0 configuration | preregistration fact `supported`; formal result `forbidden` | `configs/geophase_e0_2p5d_reference.yaml` |
| G0 x-y/K-state reference | unimplemented; positive result `forbidden` | planned `src/pinnpcm/physics/geophase_2p5d.py`, `src/pinnpcm/solvers/geophase_2p5d_fvm.py`, and E0 outputs |
| G1-G3 forward/architecture/generalization | unimplemented/unrun; `forbidden` | unlock only after every E0 gate passes |
| G4 quotient/sensitivity/refusal | unrun; `forbidden` | unlock only after solver derivatives converge and the forward PINN passes |
| G5 SnSe/NbO2 cross-model | unrun; `forbidden` | auxiliary material-specific validation after VO2 route disposition |

No K-state thermal-memory implementation or transition-localized GeoPhase
network exists in live `main` at route activation. Related historical modules
are reusable patterns or baselines only.

## Retained Safe Historical Mainline

- Frozen GT: `docs/gt_v1_acceptance_report.md` and
  `data/processed/gt_v1_acceptance/manifest.json`.
- Sparse-port hidden-field boundary: `outputs/tables/pinn_identifiability_summary.json`
  and `outputs/tables/pinn_inverse_v0_ablation_summary.json` (`supported` only
  in the configured frozen synthetic benchmark).
- Constrained `gamma_sub`: `docs/paper/gamma_sub_evidence_lock.md` and
  `outputs/tables/gamma_sub_evidence_lock_summary.json`
  (`qualified_supported` under its locked 1D priors and calibration).
- Historical claim matrix: `docs/paper/final_claim_matrix.md`; GeoPhase rows are
  candidate claims and remain `forbidden` until direct evidence exists.

## Reusable Components Without Claim Transfer

| Component | Current use boundary |
| --- | --- |
| `configs/m40_qiu_vo2_real_device_2d.yaml`, `src/pinnpcm/physics/qiu_vo2_device.py` | Qiu source/provenance and geometry facts; x-z fields/results do not validate x-y E0. |
| `src/pinnpcm/solvers/qiu_vo2_2d_fvm.py`, `src/pinnpcm/solvers/m40r_qiu_e0_repair.py` | face-flux, RC, ledger, and comparison patterns only. |
| `src/pinnpcm/physics/vo2_constitutive.py`, `vo2_thermal_neuristor.py` | candidate VO2 components subject to the new state/unit contract; no exact-Qiu status. |
| `src/pinnpcm/physics/multilayer_sandwich.py`, `src/pinnpcm/pinn/oasis_components.py` | material/interface/CV patterns and baselines; historical P1/P2 failures remain. |
| `src/pinnpcm/pinn/network.py`, `mixed_flux_pinn.py` | Fourier/mixed-form baselines; no localized-expert or success claim. |
| `src/pinnpcm/identifiability.py` | SVD/principal-angle utilities after derivative convergence; historical SID/EC-OQ remains negative. |

## Closed Historical Boundaries

| Block | Status | Primary evidence |
| --- | --- | --- |
| Complete 1D PINN | contracts `supported`; trained routes `failed_but_informative` | `outputs/tables/full_pinn_contract_v1.json`; `outputs/tables/n0_cv_e_v3r_forensic_resolution.json`; `outputs/tables/m33_mixed_flux_final_summary.json` |
| M40/M40R Qiu x-z bridge | `failed_but_informative`; no M41 | `outputs/tables/m40_qiu_e0_summary.json`; `outputs/tables/m40r_qiu_e0_summary.json`; associated reports |
| E1F/E1F-R Qiu compact source | formula subfacts plus `failed_but_informative` setting checks | `outputs/tables/e1f_llp_source_contract_summary.json`; `outputs/tables/e1fr_qiu_source_equation_correction.json` |
| Zhang D0/M35-M37R | provenance/parity subfacts; quotient/fit/13 V unavailable | `data/external/vo2_zhang_2024/manifest.json`; M35-M37R summaries |
| P1/P2/P4 and SID/EC-OQ | negative or `forbidden` | historical OASIS, active-protocol, algorithm, and SID summaries |
| M44 3D bridge | retired historical `failed_but_informative`, non-voting | absent from live implementation after rollback; do not repair or cite as current capability |

## Evidence Taxonomy

- `synthetic_gt`: frozen benchmark arrays; not measured data.
- `solver_generated`: independent numerical trajectories and audits.
- `pinn_predicted`: neural outputs only; never relabel solver output.
- `public_external_raw`: publisher-supplied numeric data with provenance.
- `external_literature_source_document`: source paper/SI; not project data.
- `derived` / `interpolated`: transformations retaining parent identity.

## Manuscript And Submission Routing

- `docs/manuscript/main_submission_v1.md` and `main_submission_v2.md` are
  historical snapshots for the old route.
- Current go/no-go: `docs/manuscript/submission_go_no_go.md`.
- Current research contract: `docs/research_strategy/geophase_oq_pinn_execution_contract.md`.
- Current single priority: pass G0/E0. No new manuscript result, figure roster,
  GPU training, or inverse/cross-model claim is authorized before that gate.
