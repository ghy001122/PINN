# Calibration Tolerance, Protocol Disentanglement, And Submission Lock Report

## Repository

- Repo: https://github.com/ghy001122/PINN
- Branch: main
- Commit hash: see final Codex response and GitHub commit history; a commit cannot embed its own final hash without changing that hash.
- Scope: synthetic numerical digital-twin manuscript-defense pack, not experimental validation.

## Key Results

### T_sw Calibration Tolerance Sweep

- Cases: `1350`.
- Maximum tolerable calibration error for <=15% median error: `0.1` K.
- Maximum tolerable prior width for <=15% median error: `0.05`.
- Calibrated protocol advantage in this sweep: `0.0565437907077283`.
- Manuscript sentence: In the synthetic tolerance sweep, gamma_sub recovery stays reliable only when residual T_sw error is about 0.1 K or the post-calibration prior width is about 0.05 or narrower under the configured <=15% error criterion.

### Calibration-vs-Protocol Disentanglement

- Total gain: `1.1381068369066785`.
- Calibration gain: `1.1216748794829614`.
- Protocol gain: `0.014955665059772812`.
- Interaction gain: `0.0014762923639442468`.
- Best protocol under equal-prior control: `multi_pulse_to_ltp_ltd`.
- Protocol advantage survives equal-prior control: `True`.
- Previous protocol claim needs qualification: `True`.
- Claim update: Protocol advantage survives equal-prior control but most improvement is still driven by T_sw calibration.

### Calibrated Protocol Robustness Final

- ODE-backed cases: `2400`.
- Best protocol: `calibrated_short_pulse_to_ltp_ltd`.
- Success rate by best protocol: `0.9604166666666667`.
- Median error by best protocol: `0.1111111111111111`.
- Worst-case error by best protocol: `0.4444444444444444`.
- Ready as main figure without qualification: `False`.
- Required qualification: Use as a synthetic ODE-backed main-figure candidate only under calibrated or tightly bounded T_sw priors; not an experimental protocol claim.

### External Curve Extraction Result

- Sources scanned: `15`.
- Valid digitized curve tables: `0`.
- Accepted points: `0`.
- Manual digitization queue items: `6`.
- Blocked reason: `no_provenance_backed_digitized_curve_tables_found`.

### Final Figure/Table/Claim Lock

- Figures locked: `7`.
- Tables locked: `7`.
- Claim matrix locked: `True`.
- External curve status: `no_provenance_backed_digitized_curve_tables_found`.

## Supported SCI Claims

- Sparse-port terminal data do not uniquely recover full hidden fields in the current benchmark.
- Calibration-gated reduced `gamma_sub` inversion is defensible under fixed or tightly bounded priors.
- `T_sw` calibration is the main requirement and must be close to about `0.1` K residual error in the configured synthetic tolerance audit.
- Protocol design may help, but the gain is smaller than the calibration gain and needs qualification.

## Forbidden Claims

- No experimental validation claim.
- No literature curve fitting success claim without provenance-backed digitized data.
- No sparse-port full hidden-field recovery claim.
- No unconditional `gamma_sub` identifiability claim.
- No F-SPS-PINN superiority claim.

## Remaining Gaps

- External curves remain blocked until manually digitized with provenance.
- Final ODE robustness makes the protocol result more qualified than the earlier response-surface preflight: `calibrated_short_pulse_to_ltp_ltd` is best, while multi-pulse is not robust across the broader grid.
- The manuscript should now be drafted, not expanded indefinitely with new experiments.

## Validation

Dedicated new tests: 9 passed. Related previous-pack tests: 9 passed. Full test suite: 119 passed in 181.09 s.

## Boundaries

- Frozen GT modified: No.
- External data fabricated: No.
- Large figures/checkpoints submitted: No.
