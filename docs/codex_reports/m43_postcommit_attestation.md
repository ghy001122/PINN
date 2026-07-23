# M43 post-commit attestation

This additive attestation binds the frozen M43 evidence to the remote result
commit `e433fe900cb4376b5e1d5cfe81333e527f5454a5`. It does not rewrite any M43
result, figure, case table, threshold, or scientific status.

## Verified record

- Remote branch: `research/m43-finite-width-thermal-closure`.
- Preregistration ancestor: `a1f229a25b4392422af3ced7e354ada0b5605365`.
- M42 result ancestor: `0dc103f391d1206fe02c100987ecab68ed1d741d`.
- Execution: 15 unique thermal-only PDE forwards.
- Gates: 19 scientific/contract gates plus 2 budget gates, all passed.
- Targeted validation before finalization: 52 passed, 0 failed.
- One complete-suite invocation: 497 passed, 2 failed. Both failures were
  pre-commit historical-identity failures; the suite was not rerun on the
  final amended commit.
- Post-commit identity/result closure: 6 passed, 0 failed. The stored log is
  authoritative; it must not be described as 7/7.
- Formal 3D/Green comparison range: \(Fo_A\in[0.1,1218]\). The earlier
  \(\sqrt{t}\) check validates the independent Green reference, not a direct
  FVM limit as \(t\rightarrow0\).
- Governance: `pass_with_manual_review`, zero failed checks.

The exact SHA-256 values are stored in
`outputs/tables/m43_postcommit_attestation.json`. The two CSVs were written
with CRLF line endings at runtime but are stored by Git with LF line endings;
the attestation records both byte identities and verifies that their canonical
LF text is identical. This portability fact does not alter scientific data.
M43 remains
`qualified_supported` only for the manufactured homogeneous isotropic
half-space thermal-spreading component. It does not validate a Qiu device,
phase-change enthalpy, inverse identification, PINN training, or experiment.
