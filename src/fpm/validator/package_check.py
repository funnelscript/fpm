"""Pre-flight packaging and publishing verification."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fpm.errors import (
    MissingExportError,
    MissingManifestFieldError,
    MissingRequiredFileError,
)
from fpm.models.manifest import Manifest


def validate_package_layout(package_dir: Path) -> tuple[Manifest, list[str]]:
    package_dir = package_dir.resolve()
    manifest_file = package_dir / "fpm.toml"
    if not manifest_file.exists():
        raise MissingManifestFieldError("fpm.toml", {"package_dir": str(package_dir)})

    manifest = Manifest.load_from_file(manifest_file)
    warnings: list[str] = []

    # Check README.md
    readme_file = package_dir / "README.md"
    if not readme_file.exists() or readme_file.stat().st_size == 0:
        raise MissingRequiredFileError("README.md", {"package_dir": str(package_dir)})

    # Check entry point
    entry_file = package_dir / manifest.entry
    if not entry_file.exists():
        raise MissingRequiredFileError(manifest.entry, {"package_dir": str(package_dir)})

    # Check exported modules
    for mod_name, mod_file in manifest.modules.items():
        target = package_dir / mod_file
        if not target.exists():
            raise MissingExportError(mod_name, mod_file, {"package_dir": str(package_dir)})

    # Check for broken symlinks or escape paths
    for root, _, files in os.walk(package_dir):
        for f in files:
            p = Path(root) / f
            if p.is_symlink():
                resolved = p.resolve()
                if not str(resolved).startswith(str(package_dir)):
                    warnings.append(f"Symlink '{p.relative_to(package_dir)}' escapes package boundary.")

    return manifest, warnings


def run_preflight_audit(package_dir: Path) -> dict[str, Any]:
    manifest, warnings = validate_package_layout(package_dir)
    return {
        "status": "passed",
        "name": manifest.name,
        "version": manifest.version,
        "entry": manifest.entry,
        "modules_count": len(manifest.modules),
        "parameters_count": len(manifest.parameters),
        "metrics_count": len(manifest.metrics),
        "warnings": warnings,
    }
