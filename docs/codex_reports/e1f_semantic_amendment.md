# E1F semantic amendment

The first E1F formal artifact is retained but has no scientific vote. A
post-run audit found two deterministic implementation-contract defects:

1. Supporting Information Eq. S3 reports
   `T_pr = delta*w/2 + T_c - (2*F(T_r)-1)/beta - T_r`, whereas the repository
   implementation inserted an unreported `atanh` operation.
2. The automatic Fig. 2b extraction associated legend pixels with both the
   experimental and author-simulation traces over part of the plotted interval.

Consequently, solver parity from the first run shows only agreement between two
integrators applied to the same incorrect repository implementation. The
setting and holdout curve errors cannot cast a scientific vote, and the
effective-coordinate preflight remains unauthorized. The original JSON, CSV,
figure, code, and derived curves are preserved for audit.

One corrected E1F-R execution is permitted only after an explicit amendment
lock. It must keep the parameters, curve identities, time intervals, metrics,
and thresholds unchanged; implement Eq. S3 literally; and exclude only the
fixed legend geometry. E1F-R remains a post-lock corrective audit, not an
independent experimental holdout.
