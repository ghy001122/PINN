# Data Provenance

This file must be updated whenever new raw, external, or processed data is added.

## `data/raw/`

Reserved for user-provided or lab raw data. No project-generated experimental data are present.

## `data/external/`

Contains public external literature artifacts only when source, version, license, hash and transformation semantics are recorded. These are not measurements performed by this project.

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
