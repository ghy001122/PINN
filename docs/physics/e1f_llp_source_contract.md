# Layered E1F / LLP source contract

This record separates four responsibilities that were previously conflated.

| Contract ID | Supported responsibility | Explicit boundary |
|---|---|---|
| `qiu_2024_si_printed_s3_transcription` | Literal transcription of Qiu Supporting Information Eqs. S3–S4 | Not unpublished Qiu author code |
| `tanh_llp_atanh_anchor_inverse_identity` | Analytic inverse of the configured tanh limiting branch | Not a universal LLP identity |
| `sena_de_almeida_2026_explicit_event_comparator` | Later explicit state-machine comparator | Cannot establish what Qiu used in 2024 |
| `repository_e1f_historical_atanh_like_implementation` | Repository implementation lineage | Qiu-author equivalence remains unverified |

## Primary-source locator

Qiu et al., *Reconfigurable Cascaded Thermal Neuristors for Neuromorphic Computing*, DOI `10.1002/adma.202306818`. The local Supporting Information file has SHA-256 `D47ED95CD5782C3E632BBC440C1FCC681870E0FF303F0B05F8CD8F30CEC70BFD`. PDF page 4 (printed page 3) contains S3 and S4. A 300-dpi internal crop used for visual verification has SHA-256 `27A2E5CA875993CE1D73E25A128FD5F6E526AF270F7B87A5AB2CFD36557C4C0C`; the crop and third-party PDF are not redistributed.

The printed S3 is

\[
T_{pr}=\delta\frac{w}{2}+T_c-\frac{2F(T_r)-1}{\beta}-T_r,
\]

whereas the separately audited tanh-anchor inverse is

\[
T_{pr}=\delta\frac{w}{2}+T_c-\frac{\operatorname{atanh}(2F_r-1)}{\beta}-T_r.
\]

The latter has model-lineage support from de Almeida et al. (DOIs `10.1117/1.1501095` and `10.1109/TMAG.2002.806344`) and is compared with the later Sena–de Almeida implementation (DOI `10.1038/s41598-026-49919-9`). These metadata do not establish page-level formula provenance unless a full text was directly checked.

## Kernel and gates

The printed kernel has

\[
P(0)=\tfrac12[1+\tanh(\pi^2)]<1.
\]

The deficit is analytic, not floating-point rounding, and the implementation does not force normalization. G1 independently checks vectorized and scalar literal/atanh evaluations over 2001 reversal fractions on each branch. G2 checks realized reversal continuity only for the tanh-anchor inverse. Manufactured return-point and wiping-out protocols are G3 diagnostics, non-blocking because the fallback manuscript makes neither property claim.

## Historical interpretation

E1F carries no scientific vote. Its atanh term is no longer described as an unreferenced insertion, but full Qiu-author algorithm equivalence remains unverified. E1F-R remains a literal-S3 sensitivity with solver parity passing and the clean S1 source-curve match failing. That failure is `failed_but_informative`; it neither validates an external mapping nor refutes general LLP.
