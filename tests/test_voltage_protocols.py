"""Voltage protocol tests."""

from __future__ import annotations

import numpy as np

from pinnpcm.physics.voltage_protocols import get_voltage_protocol


def test_voltage_protocols_return_finite_values() -> None:
    """Triangle and LTP/LTD protocols should be finite and shaped."""

    t = np.linspace(0.0, 1.0e-3, 50)
    for protocol in ("triangle", "ltp_ltd"):
        voltage_fn = get_voltage_protocol(protocol, t_max=1.0e-3)
        voltage = voltage_fn(t)
        assert voltage.shape == t.shape
        assert np.all(np.isfinite(voltage))
