from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import numpy as np
import pytest
import yaml

from pinnpcm.external_data.vo2_zhang import require_fit_lock_for_sealed_access
from pinnpcm.physics.vo2_thermal_neuristor import (
    VO2ThermalNeuristorParameters,
    resistance_path_ohm,
    simulate_source_compat_si,
)
from scripts.prepare_vo2_d0_sources import prepare_sources


def _write_zip(path: Path, members: dict[str, bytes]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as bundle:
        for name, payload in members.items():
            bundle.writestr(name, payload)


def test_prelock_quarantine_does_not_extract_or_hash_13v(tmp_path: Path) -> None:
    source_zip = tmp_path / "raw" / "nature.zip"
    code_zip = tmp_path / "raw" / "code.zip"
    _write_zip(
        source_zip,
        {
            "Source Data/Fig1b.csv": b"T,R\n300,1\n",
            "Source Data/Experiment_11V.csv": b"t,I\n0,0\n",
            "Source Data/Experiment_13V.csv": b"t,I\n0,13\n",
        },
    )
    _write_zip(
        code_zip,
        {
            "repo-v1.0.0/model.py": b"# model",
            "repo-v1.0.0/README.md": b"# readme",
            "repo-v1.0.0/LICENSE": b"MIT",
            "repo-v1.0.0/data.zip": b"sealed nested data",
        },
    )
    cfg = yaml.safe_load(
        Path("configs/vo2_d0a_exact_source_v2.yaml").read_text(encoding="utf-8")
    )
    cfg["sources"]["nature_source_data"].update(
        {"url": source_zip.as_uri(), "filename": "nature.zip"}
    )
    cfg["sources"]["github_tag"].update(
        {"url": code_zip.as_uri(), "filename": "code.zip"}
    )
    cfg["sources"]["zenodo_record"]["download_record_files"] = False
    cfg["paths"] = {
        key: str(tmp_path / Path(value).name)
        for key, value in cfg["paths"].items()
    }
    cfg["paths"]["raw_dir"] = str(tmp_path / "raw")
    cfg["paths"]["allowed_extract_dir"] = str(tmp_path / "allowed")
    cfg["paths"]["sealed_dir"] = str(tmp_path / "sealed")
    cfg["paths"]["author_code_dir"] = str(tmp_path / "author_code")
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")

    manifest = prepare_sources(path, allow_network=False)
    members = manifest["archive_members"]["nature_source_data"]
    withheld = [item for item in members if "13V" in item["member_name"]]
    assert len(withheld) == 1
    assert withheld[0]["content_read_prelock"] is False
    assert withheld[0]["extracted_path"] is None
    assert withheld[0]["sha256"] is None
    assert not list((tmp_path / "allowed").rglob("*13V*"))
    assert not (tmp_path / "author_code" / "data.zip").exists()


def test_sealed_access_requires_valid_canonical_fit_lock(tmp_path: Path) -> None:
    fit_lock = tmp_path / "fit_lock.json"
    with pytest.raises(PermissionError):
        require_fit_lock_for_sealed_access(fit_lock)

    payload = {
        "git_commit": "abc",
        "config_sha256": "def",
        "fit_data_sha256": "ghi",
        "preprocessing": {},
        "metrics": {},
        "thresholds": {},
        "all_start_results": [],
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    payload["fit_lock_sha256"] = hashlib.sha256(canonical).hexdigest().upper()
    fit_lock.write_text(json.dumps(payload), encoding="utf-8")
    loaded = require_fit_lock_for_sealed_access(fit_lock)
    assert loaded["fit_lock_sha256"] == payload["fit_lock_sha256"]


def test_si_source_model_preserves_parameter_product_and_finite_dynamics() -> None:
    cfg = yaml.safe_load(
        Path("configs/vo2_d0a_exact_source_v2.yaml").read_text(encoding="utf-8")
    )
    params = VO2ThermalNeuristorParameters.from_config(cfg)
    assert params.R_metal_ohm == pytest.approx(
        params.Rm0_ohm * params.Rm_factor
    )
    temperatures = np.array([325.0, 340.0, 350.0, 330.0])
    resistance, branch, events = resistance_path_ohm(temperatures, params)
    assert resistance.shape == temperatures.shape
    assert branch.shape == temperatures.shape
    assert events.ndim == 1
    assert np.all(np.isfinite(resistance))
    assert np.all(resistance > 0.0)

    trace = simulate_source_compat_si(
        params,
        input_voltage_V=11.0,
        t_max_s=2.0e-7,
        dt_s=1.0e-8,
        noise_strength=0.0,
        seed=20260715,
    )
    assert trace.time_s.size == 20
    assert np.all(np.isfinite(trace.current_A))
    assert np.all(trace.resistance_ohm > 0.0)
