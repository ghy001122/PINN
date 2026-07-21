"""The E1F bridge table must be derived only from locked M40/M40R artifacts."""

from __future__ import annotations

import math

from scripts.audit_e1f_source_to_pde_bridge import bridge_rows


def test_e1f_bridge_values_and_semantics() -> None:
    rows = {row["quantity"]: row for row in bridge_rows()}
    assert set(rows) == {
        "electrical_resistance",
        "thermal_capacitance",
        "thermal_conductance",
        "thermal_time_constant",
    }
    assert math.isclose(
        float(rows["electrical_resistance"]["ratio_local_over_source"]),
        2.3302332075455143,
        rel_tol=1.0e-12,
    )
    assert math.isclose(
        float(rows["thermal_capacitance"]["ratio_source_over_local"]),
        635.514497674478,
        rel_tol=1.0e-12,
    )
    assert math.isclose(
        float(rows["thermal_conductance"]["ratio_source_over_local"]),
        206.0,
        rel_tol=1.0e-12,
    )
    assert math.isclose(
        float(rows["thermal_time_constant"]["ratio_source_over_local"]),
        3.085021833371254,
        rel_tol=1.0e-12,
    )
    assert all(row["scientific_vote"] is False for row in rows.values())
    assert all(row["m40_or_m40r_solver_called"] is False for row in rows.values())
