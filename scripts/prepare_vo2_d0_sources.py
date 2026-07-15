"""Acquire and quarantine the D0a VO2 primary-source package.

Only ZIP central-directory metadata are inspected for repository-withheld 13 V
members before the fit lock. Such members are not decompressed or hashed.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pinnpcm.external_data.vo2_zhang import compute_sha256

DEFAULT_CONFIG = Path("configs/vo2_d0a_exact_source_v2.yaml")
USER_AGENT = "PINN-VO2-D0a/2.0 (research reproducibility audit)"


def _resolve(path: str | Path) -> Path:
    value = Path(path)
    return value if value.is_absolute() else ROOT / value


def _display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _load_config(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(_resolve(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("D0a config must be a mapping.")
    return payload


def _download(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".part")
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=120) as response, temporary.open("wb") as out:
        shutil.copyfileobj(response, out)
    temporary.replace(destination)


def _download_if_needed(url: str, destination: Path) -> bool:
    if destination.exists() and destination.stat().st_size > 0:
        return False
    _download(url, destination)
    return True


def _is_sealed_member(name: str, patterns: list[str]) -> bool:
    normalized = name.replace("\\", "/").casefold()
    return any(pattern.casefold() in normalized for pattern in patterns)


def _safe_destination(root: Path, member_name: str) -> Path:
    pure = PurePosixPath(member_name.replace("\\", "/"))
    if pure.is_absolute() or ".." in pure.parts:
        raise ValueError(f"Unsafe ZIP member path: {member_name}")
    destination = (root / Path(*pure.parts)).resolve()
    if root.resolve() not in destination.parents and destination != root.resolve():
        raise ValueError(f"ZIP member escapes extraction root: {member_name}")
    return destination


def _extract_allowed_source_members(
    archive: Path,
    destination: Path,
    sealed_patterns: list[str],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with zipfile.ZipFile(archive) as bundle:
        for info in bundle.infolist():
            if info.is_dir():
                continue
            sealed = _is_sealed_member(info.filename, sealed_patterns)
            record: dict[str, Any] = {
                "member_name": info.filename,
                "crc32": f"{info.CRC:08X}",
                "compressed_size": info.compress_size,
                "uncompressed_size": info.file_size,
                "sealed_repository_withheld": sealed,
                "content_read_prelock": False,
                "extracted_path": None,
                "sha256": None,
            }
            if not sealed:
                target = _safe_destination(destination, info.filename)
                target.parent.mkdir(parents=True, exist_ok=True)
                with bundle.open(info, "r") as source, target.open("wb") as out:
                    shutil.copyfileobj(source, out)
                record["content_read_prelock"] = True
                record["extracted_path"] = _display(target)
                record["sha256"] = compute_sha256(target)
            records.append(record)
    return records


def _extract_author_code(
    archive: Path,
    destination: Path,
    allowed_extensions: set[str],
    allowed_names: set[str],
    forbidden_names: set[str],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with zipfile.ZipFile(archive) as bundle:
        for info in bundle.infolist():
            if info.is_dir():
                continue
            basename = PurePosixPath(info.filename).name
            suffix = PurePosixPath(info.filename).suffix.casefold()
            allowed = (
                basename in allowed_names or suffix in allowed_extensions
            ) and basename not in forbidden_names
            record: dict[str, Any] = {
                "member_name": info.filename,
                "crc32": f"{info.CRC:08X}",
                "compressed_size": info.compress_size,
                "uncompressed_size": info.file_size,
                "code_member_extracted": allowed,
                "content_read_prelock": allowed,
                "extracted_path": None,
                "sha256": None,
            }
            if allowed:
                relative_parts = PurePosixPath(info.filename).parts[1:]
                relative = "/".join(relative_parts) if relative_parts else basename
                target = _safe_destination(destination, relative)
                target.parent.mkdir(parents=True, exist_ok=True)
                with bundle.open(info, "r") as source, target.open("wb") as out:
                    shutil.copyfileobj(source, out)
                record["extracted_path"] = _display(target)
                record["sha256"] = compute_sha256(target)
            records.append(record)
    return records


def _fetch_zenodo_record(record_url: str) -> dict[str, Any]:
    request = urllib.request.Request(record_url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.loads(response.read().decode("utf-8"))


def _source_artifact(
    *,
    artifact_id: str,
    source_role: str,
    source_url: str,
    source_version: str,
    path: Path | None,
    license_id: str,
    acquired_at: str,
    downloaded: bool,
    sealed_until_fit_lock: bool = False,
) -> dict[str, Any]:
    return {
        "artifact_id": artifact_id,
        "source_role": source_role,
        "source_url": source_url,
        "source_version_or_tag": source_version,
        "source_commit_or_blob_sha": "",
        "path": _display(path) if path else None,
        "sha256": compute_sha256(path) if path else None,
        "size_bytes": path.stat().st_size if path else None,
        "license_id": license_id,
        "acquired_at_utc": acquired_at,
        "data_kind": "public_external_raw",
        "use_role": "source_reproduction",
        "derived_from_artifact_ids": [],
        "curve_id": None,
        "protocol_id": None,
        "voltage_V": None,
        "branch_id": None,
        "raw_units": None,
        "si_units": None,
        "conversion_formula": None,
        "sealed_until_fit_lock": sealed_until_fit_lock,
        "downloaded_this_run": downloaded,
    }


def prepare_sources(
    config_path: Path = DEFAULT_CONFIG,
    *,
    allow_network: bool = True,
) -> dict[str, Any]:
    cfg = _load_config(config_path)
    paths = cfg["paths"]
    raw_dir = _resolve(paths["raw_dir"])
    extract_dir = _resolve(paths["allowed_extract_dir"])
    code_dir = _resolve(paths["author_code_dir"])
    sealed_dir = _resolve(paths["sealed_dir"])
    for directory in (raw_dir, extract_dir, code_dir, sealed_dir):
        directory.mkdir(parents=True, exist_ok=True)

    acquired_at = datetime.now(timezone.utc).isoformat()
    artifacts: list[dict[str, Any]] = []
    source_members: list[dict[str, Any]] = []
    code_members: list[dict[str, Any]] = []

    paper = cfg["sources"]["nature_article"]
    artifacts.append(
        _source_artifact(
            artifact_id="zhang_2024_nature_article",
            source_role=paper["source_role"],
            source_url=paper["url"],
            source_version=paper["version"],
            path=None,
            license_id=paper["license_id"],
            acquired_at=acquired_at,
            downloaded=False,
        )
    )

    for key in ("nature_source_data", "github_tag"):
        source = cfg["sources"][key]
        destination = raw_dir / source["filename"]
        if not destination.exists() and not allow_network:
            raise FileNotFoundError(destination)
        downloaded = _download_if_needed(source["url"], destination) if allow_network else False
        artifacts.append(
            _source_artifact(
                artifact_id=f"zhang_2024_{key}",
                source_role=source["source_role"],
                source_url=source["url"],
                source_version=str(source.get("version", "publisher_file")),
                path=destination,
                license_id=source["license_id"],
                acquired_at=acquired_at,
                downloaded=downloaded,
                sealed_until_fit_lock=key == "nature_source_data",
            )
        )
        if key == "nature_source_data":
            source_members = _extract_allowed_source_members(
                destination,
                extract_dir,
                list(cfg["quarantine"]["sealed_member_patterns"]),
            )
        else:
            code_members = _extract_author_code(
                destination,
                code_dir,
                {str(x).casefold() for x in cfg["quarantine"]["author_code_extensions"]},
                set(cfg["quarantine"]["author_code_names"]),
                set(cfg["quarantine"]["never_extract_prelock"]),
            )

    zenodo = cfg["sources"]["zenodo_record"]
    if allow_network:
        zenodo_metadata = _fetch_zenodo_record(zenodo["record_url"])
        metadata_path = raw_dir / "zenodo_record_13119587.json"
        metadata_path.write_text(
            json.dumps(zenodo_metadata, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        artifacts.append(
            _source_artifact(
                artifact_id="zhang_2024_zenodo_record_metadata",
                source_role=zenodo["source_role"],
                source_url=zenodo["record_url"],
                source_version=zenodo["record_id"],
                path=metadata_path,
                license_id=zenodo["license_id"],
                acquired_at=acquired_at,
                downloaded=True,
            )
        )
        if zenodo.get("download_record_files", False):
            for item in zenodo_metadata.get("files", []):
                file_url = item.get("links", {}).get("self")
                filename = Path(str(item.get("key", "zenodo_file"))).name
                if not file_url:
                    continue
                destination = raw_dir / f"zenodo_{filename}"
                downloaded = _download_if_needed(file_url, destination)
                artifacts.append(
                    _source_artifact(
                        artifact_id=f"zhang_2024_zenodo_{filename}",
                        source_role=zenodo["source_role"],
                        source_url=file_url,
                        source_version=zenodo["record_id"],
                        path=destination,
                        license_id=zenodo["license_id"],
                        acquired_at=acquired_at,
                        downloaded=downloaded,
                        sealed_until_fit_lock=True,
                    )
                )

    sealed_records = [item for item in source_members if item["sealed_repository_withheld"]]
    if any(item["content_read_prelock"] for item in sealed_records):
        raise RuntimeError("A repository-withheld 13 V member was read before fit lock.")

    manifest = {
        "schema_version": "vo2_d0_provenance_v2",
        "benchmark": cfg["benchmark"],
        "stage_id": cfg["stage_id"],
        "created_at_utc": acquired_at,
        "fit_lock_path": cfg["quarantine"]["fit_lock_path"],
        "artifacts": artifacts,
        "archive_members": {
            "nature_source_data": source_members,
            "github_tag_code_only": code_members,
        },
        "sealed_member_count": len(sealed_records),
        "sealed_member_content_read_prelock": False,
        "zenodo_record_id": zenodo["record_id"],
        "evidence_semantics": {
            "source_paper_model_reproduction": True,
            "repository_side_refit": False,
            "repository_withheld_preregistered_cross_voltage_evaluation": False,
            "independent_external_validation": False,
        },
    }
    manifest_path = _resolve(paths["manifest_json"])
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    provenance = _resolve(paths["provenance_md"])
    provenance.write_text(
        "# Zhang et al. VO2 Public-Data Provenance\n\n"
        "This directory contains provenance metadata for public external literature "
        "artifacts. It is not project-generated experimental data.\n\n"
        "- Nature article: DOI 10.1038/s41467-024-51254-4.\n"
        "- Zenodo record: DOI 10.5281/zenodo.13119587.\n"
        "- Author code: GitHub tag v1.0.0.\n"
        "- The 13 V member is repository-withheld before fit_lock.json; pre-lock "
        "processing records ZIP directory metadata only and does not decompress it.\n"
        "- Source-paper model reproduction, repository refit, cross-voltage evaluation, "
        "and genuinely independent external validation are distinct evidence classes.\n",
        encoding="utf-8",
    )
    licenses = _resolve(paths["licenses_md"])
    licenses.write_text(
        "# License Separation\n\n"
        "| Artifact | License | Boundary |\n"
        "| --- | --- | --- |\n"
        "| Nature article and publisher Source Data | CC BY 4.0 | Paper/source-data reuse |\n"
        "| Zenodo record 13119587 | CC BY 4.0 | Archived record/files |\n"
        "| GitHub tag v1.0.0 code | MIT | Author source code only |\n\n"
        "These licenses are recorded separately and are not treated as interchangeable.\n",
        encoding="utf-8",
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument(
        "--quarantine-13v",
        action="store_true",
        help="Required acknowledgement that 13 V members remain unextracted.",
    )
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    if not args.quarantine_13v:
        raise SystemExit("--quarantine-13v is required for D0a.")
    payload = prepare_sources(args.config, allow_network=not args.offline)
    print(
        json.dumps(
            {
                "schema_version": payload["schema_version"],
                "stage_id": payload["stage_id"],
                "artifact_count": len(payload["artifacts"]),
                "sealed_member_count": payload["sealed_member_count"],
                "sealed_member_content_read_prelock": payload[
                    "sealed_member_content_read_prelock"
                ],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
