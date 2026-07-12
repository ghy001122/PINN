from __future__ import annotations

import json
from pathlib import Path

import numpy as np

import scripts.audit_active_protocol_identifiability_v2 as audit


def test_trace_features_use_terminal_traces_only() -> None:
    result = {"current": np.arange(4.0), "conductance": np.arange(4.0) + 1.0, "voltage_device": np.linspace(0.0, 1.0, 4)}
    feat = audit._trace_features(result)
    assert feat.shape == (16,)
    assert np.isfinite(feat).all()


def test_active_protocol_v2_existing_summary_schema() -> None:
    path = Path("outputs/tables/active_protocol_identifiability_v2_summary.json")
    if path.exists():
        summary = json.loads(path.read_text(encoding="utf-8"))
        assert summary["uses_only_terminal_traces"] is True
        assert "protocol_metrics" in summary
        assert "combined_d_optimal" in summary["protocol_metrics"]
