# Quasi-2D Phase-Transition Device Model

This document defines a literature-anchored laterally resolved quasi-2D thin-film phase-transition device model for synthetic numerical preflight only.

## Assumptions

- The model resolves the in-plane \((x,y)\) fields and averages through thickness.
- Substrate heat loss is represented by an effective sink \(\gamma_{\mathrm{sub}}(T-T_0)\).
- Sparse terminal current remains the only port observable.
- The module is forward/preflight only and does not solve two-dimensional inverse diagnosis.

## Equations

Electric potential:

\[
\nabla_{xy}\cdot\left(\sigma(T,c_v,m)\nabla_{xy}\phi\right)=0.
\]

Joule heating:

\[
q_J=\sigma(T,c_v,m)|\nabla_{xy}\phi|^2.
\]

Heat equation with substrate sink:

\[
\rho C_p\frac{\partial T}{\partial t}=\nabla_{xy}\cdot(k_{xy}\nabla_{xy}T)+q_J-\gamma_{\mathrm{sub}}(T-T_0).
\]

Phase/order parameter:

\[
\frac{\partial m}{\partial t}=\frac{m_{\mathrm{eq}}(T,c_v)-m}{\tau_m}.
\]

Optional vacancy drift-diffusion:

\[
\frac{\partial c_v}{\partial t}=-\nabla_{xy}\cdot\mathbf{J}_v-k_r(c_v-c_{v0}),\quad
\mathbf{J}_v=-D_v\nabla_{xy}c_v+\mu_v c_v(1-c_v)\mathbf{E}.
\]

Terminal current:

\[
I(t)=\int_{\Gamma_{\mathrm{left}}}\sigma\left(-\nabla\phi\cdot\mathbf{n}\right)\,d\Gamma.
\]

## Boundary

The two-dimensional unknown field dimension sharply increases relative to the one-dimensional benchmark. Sparse terminal current alone cannot identify full 2D hidden fields. This module only provides controlled extension feasibility.
