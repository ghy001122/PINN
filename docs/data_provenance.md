# Data Provenance

This file must be updated whenever new raw, external, or processed data is added.

## `data/raw/`

Reserved for user-provided or lab raw data. No project-generated experimental data are present.

## `data/external/`

Contains public external literature artifacts only when source, version, license, hash and transformation semantics are recorded. These are not measurements performed by this project.

### Qiu et al. VO2 publication-curve audit (2026-07-21)

- Paper: Qiu et al., *Advanced Materials* (2024), DOI
  `10.1002/adma.202306818`. The local publisher main/SI PDFs have SHA-256
  `D842E8BF1B5AC609AB504D8BF6104CFD3EFEA59697A5C7AC21664A99EB7D3C67`
  and `D47ED95CD5782C3E632BBC440C1FCC681870E0FF303F0B05F8CD8F30CEC70BFD`.
  They are hash-locked source documents; redistribution permission is not
  assumed. The publisher states that data are available on reasonable request,
  so the repository does not describe digitized pixels as public raw arrays.
- SI Fig. S1 current and voltage traces were digitized at 600 dpi with explicit
  tick calibration, retained raw pixel coordinates, observed/interpolated
  flags, crop hashes, and conditional pixel-jitter sensitivity envelopes.
  Their CSV hashes are recorded in
  `data/external/qiu_2024_thermal_neuristor/digitized_manifest.json`. These are
  `derived_digitized_literature_curve`, not raw or project-generated data; the
  caption does not establish whether the panel is experiment or simulation.
- Main Fig. 2b extraction is `implementation_contract_invalid/unassessed`
  because legend pixels contaminated both traces. It has no holdout vote and
  was not read, simulated, or scored by the corrective E1F-R run.
- The original E1F run also mistranscribed SI Eq. S3 and therefore has no
  scientific curve vote. E1F-R used literal printed Eq. S3 and only clean SI
  Fig. S1. No parameter fit, phase/time alignment, or replacement curve was
  used. Its trajectories are `solver_generated`.
- Neither audit is independent experimental validation, an exact author-code
  reproduction, or evidence that author-fitted lumped quantities are local
  PDE material/boundary parameters.

### Zhang et al. VO2 source package (2026-07-15)

- Paper: Zhang, Sipling, Qiu et al., *Nature Communications* 15, 6986 (2024), DOI `10.1038/s41467-024-51254-4`.
- Publisher Source Data archive SHA-256: `E8916E1B0861C7947119C3F175CEB2E625B197BC32B6B5602F1016823222FFE3`; license `CC BY 4.0`.
- Zenodo 13119587 archive SHA-256: `B7E767169405FBC23BE4CF6E790CDEF42270DD9F44B64F6C54F432A608AF958B`; license `CC BY 4.0`.
- GitHub tag `v1.0.0` archive SHA-256: `7159525F88A5AEA925AAA6247FD2BCC4286A7130AAF47F0002959FC0049A210D`; code license `MIT`.
- Full provenance records: `data/external/vo2_zhang_2024/manifest.json`; license separation: `data/external/vo2_zhang_2024/LICENSES.md`.
- Large raw archives and extracted numerical payloads are local/ignored. Lightweight immutable metadata are tracked.
- The exact 13 V ZIP members were recorded from archive-directory metadata only. Their content was not decompressed or hashed before a fit lock. D0a failed, no fit lock was created, and those numerical contents remain sealed.
- Publisher traces are `public_external_raw`, SI/author simulations are `solver_generated`, and network results are `pinn_predicted`. Interpolated arrays must retain their raw parent hash.

Evidence roles are distinct: `source_paper_model_reproduction`, `repository_side_refit`, `repository_withheld_preregistered_cross_voltage_evaluation`, and `independent_external_validation`. Only the first role was attempted; it failed the full D0a time-step gate while retaining a qualified source/SI semantic-parity sub-result.

## `data/processed/`

Files produced by `scripts/run_gt_v1.py` are literature-guided synthetic data for algorithm validation and must not be described as measured experimental data.

The frozen `gt_v1_acceptance` arrays used to score N0 remain `synthetic_gt`. They were accessed only after training in the N0 data-free forward run; no hidden field or port label was used as a training target. Derived D0a parity arrays remain `solver_generated` and preserve parent artifact hashes through the manifest.
