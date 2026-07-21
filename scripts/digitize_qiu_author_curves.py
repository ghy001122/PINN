"""Digitize the two E1F-locked Qiu 2024 panels without persisting crops."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

try:
    import yaml
except ImportError:  # bundled PDF runtime intentionally has no PyYAML
    yaml = None


SCHEMA_VERSION = "e1f_qiu_digitization_v1"


PANEL_SPECS: dict[str, dict[str, Any]] = {
    "qiu_2024_si_fig_s1_12v_current": {
        "pdf_role": "supporting_information",
        "page_index_zero_based": 6,
        "page_number_one_based": 7,
        "panel": "Figure S1 upper current trace",
        "crop_box_px_600dpi": [1050, 850, 4250, 3400],
        "x_range_px_600dpi": [1187, 4162],
        "y_range_px_600dpi": [942, 2135],
        "x_ticks": [[1187.0, 0.0], [1931.0, 5.0], [2675.0, 10.0], [3419.0, 15.0], [4162.0, 20.0]],
        "y_ticks": [[2094.0, 0.0], [1323.0, 5.0]],
        "mask": "red",
        "value_name": "current_mA",
        "value_unit": "mA",
        "semantics": "caption_does_not_identify_experiment_or_simulation",
    },
    "qiu_2024_si_fig_s1_12v_device_voltage": {
        "pdf_role": "supporting_information",
        "page_index_zero_based": 6,
        "page_number_one_based": 7,
        "panel": "Figure S1 lower VO2-voltage trace",
        "crop_box_px_600dpi": [1050, 850, 4250, 3400],
        "x_range_px_600dpi": [1187, 4162],
        "y_range_px_600dpi": [2145, 3339],
        "x_ticks": [[1187.0, 0.0], [1931.0, 5.0], [2675.0, 10.0], [3419.0, 15.0], [4162.0, 20.0]],
        "y_ticks": [[3296.0, 0.0], [2525.0, 5.0]],
        "mask": "red",
        "value_name": "device_voltage_V",
        "value_unit": "V",
        "semantics": "caption_does_not_identify_experiment_or_simulation",
    },
    "qiu_2024_main_fig2b_12p5v_experimental_current": {
        "pdf_role": "main",
        "page_index_zero_based": 2,
        "page_number_one_based": 3,
        "panel": "Figure 2B solid blue experimental current",
        "crop_box_px_600dpi": [2100, 650, 3050, 1300],
        "x_range_px_600dpi": [2203, 2975],
        "y_range_px_600dpi": [712, 1215],
        "x_ticks": [[2203.0, 0.0], [2396.0, 5.0], [2589.0, 10.0], [2782.0, 15.0], [2975.0, 20.0]],
        "y_ticks": [[1193.0, 0.0], [1059.0, 2.5], [924.0, 5.0], [790.0, 7.5]],
        "mask": "blue",
        "value_name": "current_mA",
        "value_unit": "mA",
        "semantics": "digitized_literature_curve_not_raw_data_same_paper_development_contamination_risk",
    },
    "qiu_2024_main_fig2b_12p5v_author_simulation_current": {
        "pdf_role": "main",
        "page_index_zero_based": 2,
        "page_number_one_based": 3,
        "panel": "Figure 2B dashed black author-simulation current",
        "crop_box_px_600dpi": [2100, 650, 3050, 1300],
        "x_range_px_600dpi": [2203, 2975],
        "y_range_px_600dpi": [712, 1215],
        "x_ticks": [[2203.0, 0.0], [2396.0, 5.0], [2589.0, 10.0], [2782.0, 15.0], [2975.0, 20.0]],
        "y_ticks": [[1193.0, 0.0], [1059.0, 2.5], [924.0, 5.0], [790.0, 7.5]],
        "mask": "black_dashed",
        "mask_exclusion_boxes_px_600dpi": [
            [2195, 700, 2210, 1225],
            [2968, 700, 2983, 1225],
            [2600, 715, 2960, 880],
        ],
        "minimum_separable_column_fraction": 0.75,
        "value_name": "current_mA",
        "value_unit": "mA",
        "semantics": "author_simulation_trace_digitized_from_same_panel",
    },
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def _load_config(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if yaml is not None:
        return yaml.safe_load(text)

    def scalar(key: str) -> str:
        match = re.search(rf"^\s*{re.escape(key)}:\s*(.+?)\s*$", text, re.MULTILINE)
        if match is None:
            raise RuntimeError(f"missing locked config key {key!r}")
        return match.group(1).strip().strip("\"'")

    return {
        "stage_id": scalar("stage_id"),
        "source": {
            "main_pdf": scalar("main_pdf"),
            "supporting_information_pdf": scalar("supporting_information_pdf"),
            "manifest": scalar("manifest"),
        },
        "digitization": {
            "render_dpi": int(scalar("render_dpi")),
            "curve_sampling": scalar("curve_sampling"),
            "axis_calibration": scalar("axis_calibration"),
            "uncertainty": {
                "calibration_pixel_half_width": float(scalar("calibration_pixel_half_width")),
                "trace_pixel_half_width_rule": scalar("trace_pixel_half_width_rule"),
                "monte_carlo_draws": int(scalar("monte_carlo_draws")),
                "seed": int(scalar("seed")),
            },
        },
    }


def _canonical_crop_hash(image: np.ndarray, crop_box: list[int]) -> str:
    left, top, right, bottom = crop_box
    crop = Image.fromarray(image[top:bottom, left:right], mode="RGB")
    payload = io.BytesIO()
    crop.save(payload, format="PNG", optimize=False, compress_level=9)
    return hashlib.sha256(payload.getvalue()).hexdigest().upper()


def _render_pdf_page(path: Path, page_index: int, dpi: int) -> np.ndarray:
    try:
        import pypdfium2 as pdfium
    except ImportError as exc:  # pragma: no cover - environment-specific guard
        raise RuntimeError(
            "pypdfium2 is required unless a pre-rendered page image is supplied"
        ) from exc
    document = pdfium.PdfDocument(str(path))
    page = document[page_index]
    rendered = page.render(scale=dpi / 72.0).to_pil().convert("RGB")
    return np.asarray(rendered)


def _load_page(path: Path | None, pdf_path: Path, page_index: int, dpi: int) -> np.ndarray:
    if path is None:
        return _render_pdf_page(pdf_path, page_index, dpi)
    return np.asarray(Image.open(path).convert("RGB"))


def _mask(image: np.ndarray, name: str) -> np.ndarray:
    work = image.astype(np.int16)
    red = work[:, :, 0]
    green = work[:, :, 1]
    blue = work[:, :, 2]
    if name == "red":
        return (red > 200) & ((red - green) > 50) & ((red - blue) > 50)
    if name == "blue":
        return ((blue - red) > 55) & ((blue - green) > 20) & (red < 190)
    if name == "black_dashed":
        return np.max(work, axis=2) < 105
    raise ValueError(f"unknown mask {name!r}")


def _fit_axis(ticks: list[list[float]]) -> tuple[float, float]:
    pixels = np.asarray([pair[0] for pair in ticks], dtype=float)
    values = np.asarray([pair[1] for pair in ticks], dtype=float)
    slope, intercept = np.polyfit(pixels, values, 1)
    return float(slope), float(intercept)


def _maximum_false_run(values: np.ndarray) -> int:
    maximum = current = 0
    for value in values:
        if value:
            current = 0
        else:
            current += 1
            maximum = max(maximum, current)
    return maximum


def _extract_centerline(image: np.ndarray, spec: dict[str, Any]) -> dict[str, np.ndarray | float | int]:
    mask = _mask(image, spec["mask"])
    for left, top, right, bottom in spec.get("mask_exclusion_boxes_px_600dpi", []):
        mask[top:bottom, left:right] = False

    x_start, x_stop = spec["x_range_px_600dpi"]
    y_start, y_stop = spec["y_range_px_600dpi"]
    x_pixels = np.arange(x_start, x_stop + 1, dtype=int)
    centers = np.full(x_pixels.size, np.nan, dtype=float)
    y_min = np.full(x_pixels.size, np.nan, dtype=float)
    y_max = np.full(x_pixels.size, np.nan, dtype=float)
    counts = np.zeros(x_pixels.size, dtype=int)

    for index, x_pixel in enumerate(x_pixels):
        candidates = np.flatnonzero(mask[y_start:y_stop, x_pixel]) + y_start
        if candidates.size:
            counts[index] = int(candidates.size)
            centers[index] = float(np.median(candidates))
            y_min[index] = float(candidates.min())
            y_max[index] = float(candidates.max())

    observed = np.isfinite(centers)
    if observed.sum() < 2:
        raise RuntimeError(f"insufficient trace pixels for {spec['panel']}")
    interpolated_centers = np.interp(x_pixels, x_pixels[observed], centers[observed])
    observed_width = y_max - y_min + 1.0
    typical_width = float(np.nanmedian(observed_width))
    filled_width = np.where(np.isfinite(observed_width), observed_width, typical_width)
    return {
        "x_pixels": x_pixels,
        "y_pixels": interpolated_centers,
        "observed": observed,
        "counts": counts,
        "y_min": y_min,
        "y_max": y_max,
        "line_width": filled_width,
        "observed_fraction": float(observed.mean()),
        "maximum_missing_run_pixels": int(_maximum_false_run(observed)),
        "typical_line_width_pixels": typical_width,
    }


def _monte_carlo_coordinates(
    trace: dict[str, Any],
    spec: dict[str, Any],
    *,
    draws: int,
    seed: int,
    calibration_half_width: float,
) -> dict[str, np.ndarray]:
    rng = np.random.default_rng(seed)
    x_pixels = np.asarray(trace["x_pixels"], dtype=float)
    y_pixels = np.asarray(trace["y_pixels"], dtype=float)
    line_width = np.asarray(trace["line_width"], dtype=float)
    trace_y_half_width = 0.5 * line_width + 1.0

    x_tick_pixels = np.asarray([pair[0] for pair in spec["x_ticks"]], dtype=float)
    x_tick_values = np.asarray([pair[1] for pair in spec["x_ticks"]], dtype=float)
    y_tick_pixels = np.asarray([pair[0] for pair in spec["y_ticks"]], dtype=float)
    y_tick_values = np.asarray([pair[1] for pair in spec["y_ticks"]], dtype=float)

    time_draws = np.empty((draws, x_pixels.size), dtype=float)
    value_draws = np.empty((draws, y_pixels.size), dtype=float)
    for draw in range(draws):
        x_jittered_ticks = x_tick_pixels + rng.uniform(
            -calibration_half_width, calibration_half_width, x_tick_pixels.size
        )
        y_jittered_ticks = y_tick_pixels + rng.uniform(
            -calibration_half_width, calibration_half_width, y_tick_pixels.size
        )
        x_slope, x_intercept = np.polyfit(x_jittered_ticks, x_tick_values, 1)
        y_slope, y_intercept = np.polyfit(y_jittered_ticks, y_tick_values, 1)
        time_draws[draw] = x_slope * (
            x_pixels + rng.uniform(-1.0, 1.0, x_pixels.size)
        ) + x_intercept
        value_draws[draw] = y_slope * (
            y_pixels + rng.uniform(-trace_y_half_width, trace_y_half_width)
        ) + y_intercept

    x_slope, x_intercept = _fit_axis(spec["x_ticks"])
    y_slope, y_intercept = _fit_axis(spec["y_ticks"])
    return {
        "time_us": x_slope * x_pixels + x_intercept,
        "value": y_slope * y_pixels + y_intercept,
        "time_std_us": time_draws.std(axis=0, ddof=1),
        "time_p025_us": np.quantile(time_draws, 0.025, axis=0),
        "time_p975_us": np.quantile(time_draws, 0.975, axis=0),
        "value_std": value_draws.std(axis=0, ddof=1),
        "value_p025": np.quantile(value_draws, 0.025, axis=0),
        "value_p975": np.quantile(value_draws, 0.975, axis=0),
        "trace_y_half_width_pixels": trace_y_half_width,
    }


def _write_csv(path: Path, curve_id: str, spec: dict[str, Any], trace: dict[str, Any], coords: dict[str, np.ndarray]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    value_name = spec["value_name"]
    fieldnames = [
        "curve_id", "point_index", "x_pixel_page_600dpi", "y_pixel_page_600dpi",
        "trace_observed", "observed_pixel_count", "observed_y_min_pixel",
        "observed_y_max_pixel", "observed_line_width_pixel", "trace_y_half_width_pixel",
        "time_us", "time_std_us", "time_p025_us", "time_p975_us", value_name,
        f"{value_name}_std", f"{value_name}_p025", f"{value_name}_p975",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for index in range(len(trace["x_pixels"])):
            observed = bool(trace["observed"][index])
            writer.writerow({
                "curve_id": curve_id,
                "point_index": index,
                "x_pixel_page_600dpi": int(trace["x_pixels"][index]),
                "y_pixel_page_600dpi": f"{float(trace['y_pixels'][index]):.6f}",
                "trace_observed": str(observed).lower(),
                "observed_pixel_count": int(trace["counts"][index]),
                "observed_y_min_pixel": "" if not observed else int(trace["y_min"][index]),
                "observed_y_max_pixel": "" if not observed else int(trace["y_max"][index]),
                "observed_line_width_pixel": f"{float(trace['line_width'][index]):.6f}",
                "trace_y_half_width_pixel": f"{float(coords['trace_y_half_width_pixels'][index]):.6f}",
                "time_us": f"{float(coords['time_us'][index]):.12g}",
                "time_std_us": f"{float(coords['time_std_us'][index]):.12g}",
                "time_p025_us": f"{float(coords['time_p025_us'][index]):.12g}",
                "time_p975_us": f"{float(coords['time_p975_us'][index]):.12g}",
                value_name: f"{float(coords['value'][index]):.12g}",
                f"{value_name}_std": f"{float(coords['value_std'][index]):.12g}",
                f"{value_name}_p025": f"{float(coords['value_p025'][index]):.12g}",
                f"{value_name}_p975": f"{float(coords['value_p975'][index]):.12g}",
            })


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/e1f_qiu_author_external_anchor.yaml"))
    parser.add_argument("--main-page-image", type=Path, default=None)
    parser.add_argument("--si-page-image", type=Path, default=None)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    root = args.repo_root.resolve()
    config = _load_config(root / args.config)
    dpi = int(config["digitization"]["render_dpi"])
    if dpi != 600:
        raise RuntimeError("locked pixel calibration is valid only at 600 dpi")
    draws = int(config["digitization"]["uncertainty"]["monte_carlo_draws"])
    seed = int(config["digitization"]["uncertainty"]["seed"])
    calibration_half_width = float(
        config["digitization"]["uncertainty"]["calibration_pixel_half_width"]
    )

    source_manifest_path = root / config["source"]["manifest"]
    source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))
    main_pdf = root / config["source"]["main_pdf"]
    si_pdf = root / config["source"]["supporting_information_pdf"]
    source_hashes = {entry["role"]: entry["sha256"] for entry in source_manifest["sources"] if entry.get("sha256")}
    actual_hashes = {
        "publisher_version_main_article": _sha256(main_pdf),
        "official_supporting_information": _sha256(si_pdf),
    }
    for role, actual in actual_hashes.items():
        if actual.upper() != source_hashes[role].upper():
            raise RuntimeError(f"source hash mismatch for {role}")

    main_page = _load_page(
        None if args.main_page_image is None else root / args.main_page_image,
        main_pdf,
        2,
        dpi,
    )
    si_page = _load_page(
        None if args.si_page_image is None else root / args.si_page_image,
        si_pdf,
        6,
        dpi,
    )
    pages = {"main": main_page, "supporting_information": si_page}

    derived_dir = root / "data/external/qiu_2024_thermal_neuristor/derived"
    curve_records: list[dict[str, Any]] = []
    output_files: list[Path] = []
    for curve_index, (curve_id, spec) in enumerate(PANEL_SPECS.items()):
        image = pages[spec["pdf_role"]]
        trace = _extract_centerline(image, spec)
        minimum_fraction = spec.get("minimum_separable_column_fraction")
        separable = minimum_fraction is None or trace["observed_fraction"] >= minimum_fraction
        if not separable:
            curve_records.append({
                "curve_id": curve_id,
                "digitized": False,
                "reason": "trace_not_reliably_separable_under_locked_color_mask",
                "observed_column_fraction": trace["observed_fraction"],
            })
            continue
        coords = _monte_carlo_coordinates(
            trace,
            spec,
            draws=draws,
            seed=seed + curve_index,
            calibration_half_width=calibration_half_width,
        )
        csv_path = derived_dir / f"{curve_id}.csv"
        _write_csv(csv_path, curve_id, spec, trace, coords)
        output_files.append(csv_path)
        curve_records.append({
            "curve_id": curve_id,
            "digitized": True,
            "panel": spec["panel"],
            "source_pdf_role": spec["pdf_role"],
            "source_pdf_page_one_based": spec["page_number_one_based"],
            "semantics": spec["semantics"],
            "csv_path": csv_path.relative_to(root).as_posix(),
            "point_count": int(len(trace["x_pixels"])),
            "observed_point_count": int(np.asarray(trace["observed"]).sum()),
            "observed_column_fraction": trace["observed_fraction"],
            "maximum_interpolated_gap_pixels": trace["maximum_missing_run_pixels"],
            "typical_observed_line_width_pixels": trace["typical_line_width_pixels"],
            "crop_box_px_600dpi": spec["crop_box_px_600dpi"],
            "crop_png_sha256_not_committed": _canonical_crop_hash(image, spec["crop_box_px_600dpi"]),
            "axis_calibration": {"x_tick_pixel_value_pairs": spec["x_ticks"], "y_tick_pixel_value_pairs": spec["y_ticks"]},
            "mask": spec["mask"],
            "mask_exclusion_boxes_px_600dpi": spec.get("mask_exclusion_boxes_px_600dpi", []),
            "value_name": spec["value_name"],
            "value_unit": spec["value_unit"],
        })

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "stage_id": config["stage_id"],
        "evidence_kind": "derived_digitized_literature_curve",
        "raw_experimental_data": False,
        "independent_external_holdout": False,
        "source_author_parameter_development_independence_known": False,
        "same_paper_development_contamination_risk": True,
        "si_figure_s1_semantics_ambiguous": True,
        "copyright_crop_images_committed": False,
        "render": {"dpi": dpi, "renderer": "pypdfium2_or_explicit_prerendered_page", "in_memory_crop_only": True},
        "source_files": {
            "main_pdf": {"path": main_pdf.relative_to(root).as_posix(), "sha256": actual_hashes["publisher_version_main_article"]},
            "supporting_information_pdf": {"path": si_pdf.relative_to(root).as_posix(), "sha256": actual_hashes["official_supporting_information"]},
        },
        "method": {
            "curve_sampling": config["digitization"]["curve_sampling"],
            "raw_pixel_coordinates_preserved": True,
            "axis_calibration": config["digitization"]["axis_calibration"],
            "calibration_pixel_half_width": calibration_half_width,
            "trace_pixel_half_width_rule": config["digitization"]["uncertainty"]["trace_pixel_half_width_rule"],
            "monte_carlo_draws": draws,
            "monte_carlo_seed": seed,
            "uncertainty_distribution": "independent_uniform_pixel_jitter_then_linear_axis_refit",
            "missing_columns": "linear_interpolation_with_trace_observed_flag_retained",
        },
        "curves": curve_records,
    }
    manifest_path = root / "data/external/qiu_2024_thermal_neuristor/digitized_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    output_files.append(manifest_path)
    print(json.dumps({
        "status": "digitization_complete_no_scientific_vote",
        "files": [path.relative_to(root).as_posix() for path in output_files],
        "curves": [{"curve_id": item["curve_id"], "digitized": item["digitized"], "point_count": item.get("point_count", 0)} for item in curve_records],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
