# Q2 CurrentClamp-HysGeo-PINN v1

## Batch 1 contract

This is a new research contract after the valid negative Stage A result in PR
#30. It is not PR #30 Stage B, an old C01 retry, or a revival of the retired
voltage-driven dynamic solver. Batch 1 contains only CC-0 and the bounded CC-A
zero-dimensional admission gate.

Batch 1 executed on code anchor `230f1e37fbefd88d554d54009db626d175a00444`
and terminated with `PASS_CC_A_CURRENT_CLAMP_ADMISSION`. The lifecycle state is
`executed` and the claim status is `qualified_supported`; the global science
vote remains false and the formal execution count remains zero. CC-B remains
unauthorized and unexecuted.

The unresolved reviewer question is whether ideal current control, under the
audited Qiu S1 major-branch source law, admits a non-degenerate set of locally
stable, continuation-connected heating and cooling equilibria. A positive
answer only makes a separately authorized two-dimensional CC-B pilot eligible.

## Source and branch semantics

For externally conditioned branch metadata (b\in\{\uparrow,\downarrow\}),

\[
F_b(T)=\frac12\left[1+\tanh\left(\beta
\left(T_c+\delta_b\frac{w}{2}-T\right)\right)\right],
\qquad s_b(T)=1-F_b(T),
\]

\[
R_b^{QS}(T)=R_0\exp(E_a/T)F_b(T)+R_m.
\]

Only S1 is used. The S7 factor (k=4.90) remains a dynamic filament-effective
comparator and is not a local material parameter. The cooling high-state
endpoint is externally preconditioned. Continuation connectivity within a
fixed branch law does not establish branch-switching dynamics, minor loops, or
physical dynamic reachability.

## CC-A equations and frozen cases

The ideal-current-clamp fixed point satisfies

\[
S_{th}(T-T_0)-I_{set}^2R_b^{QS}(T)=0,
\qquad V_d=I_{set}R_b^{QS}(T),
\]

with local lumped thermal eigenvalue

\[
\lambda=\frac{I_{set}^2\,dR_b^{QS}/dT-S_{th}}{C_{th}}.
\]

Formal currents are (0.1,\ldots,0.7\) mA. (I=0) is a non-voting heating
anchor. Roots are resolved on fixed nested temperature partitions over
300--380 K, and the voltage envelope is frozen at (V_d\le17\) V. This voltage
bound is an operating envelope, not proof of source-model voltage calibration.

The cooling trace starts from a unique certified (0.7\) mA root with
(s_{down}\ge0.9). Heating starts from the unique certified (I=0) root with
(s_{up}\le0.1). Subsequent points must be reached by predictor/corrector and
matched to the independently enumerated root. Independently initialized roots
cannot restore a terminated trace.

## Admission gate

`PASS_CC_A_CURRENT_CLAMP_ADMISSION` requires, simultaneously:

- one certified algebraic root for every branch/current case;
- at least five continuation-connected stable points per branch;
- conductive-state span at least 0.5 per branch;
- at least two (0.1\le s\le0.9) points per branch;
- at least five common currents with branch-state separation at least 0.1;
- valid heating and cooling endpoints, source temperature range, positive
  resistance, and the frozen voltage envelope.

A valid miss is `STOP_CC_CURRENT_CLAMP_ADMISSION` and permanently stops this
route within Batch 1. An invalid run is `INVALID_CC_A_EXECUTION`. None of these
dispositions casts a Phase-1 scientific vote or increments a formal execution
counter.

## Later mapping boundary

Batch 1 records only the algebraic mapping

\[
g_{geom}=Wt_v/L=5\times10^{-7}\,\mathrm m,
\qquad \sigma_b^{eff}(T)=\frac{1}{g_{geom}R_b^{QS}(T)}.
\]

This is a device-effective distributed proxy that exactly recovers the S1
port resistance in a uniform conductor. It is not an intrinsic local VO2
conductivity or a reconstruction of contact current crowding. No two-dimensional
field solve is performed in Batch 1.

## Evidence and stop boundary

All results use the identity `literature-guided synthetic numerical
digital-twin evidence`. Even a PASS only supports a request for CC-B; it does
not support 2.5-D forward physics, CurrentClamp-HysGeo-PINN, CC01, CC06,
experimental validation, or Qiu quantitative reproduction. Execution must stop
after CC-A and return to the user for a new decision.
