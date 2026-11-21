"""Compiler bridge generating .fpm/resolution-map.json for FunnelScript import resolution."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fpm.resolver.graph import ResolvedNode


def generate_resolution_map(
    resolved_nodes: dict[str, ResolvedNode],
    packages_dir: Path,
    use_absolute_paths: bool = True,
) -> dict[str, Any]:
    packages_data: dict[str, Any] = {}

    for name, node in sorted(resolved_nodes.items()):
        if node.local_dir:
            pkg_root = Path(node.local_dir)
        else:
            pkg_root = packages_dir / f"{name}@{node.version}"

        entry_path = pkg_root / node.entry
        modules_map: dict[str, str] = {}
        for mod_name, mod_file in sorted(node.modules.items()):
            m_path = pkg_root / mod_file
            modules_map[mod_name] = str(m_path.resolve()) if use_absolute_paths else str(m_path)

        packages_data[name] = {
            "version": node.version,
            "entry": str(entry_path.resolve()) if use_absolute_paths else str(entry_path),
            "integrity": node.integrity,
            "modules": modules_map,
        }

    return {
        "schema_version": "1.0.0",
        "packages": packages_data,
    }


def write_resolution_map(
    project_root: Path,
    resolved_nodes: dict[str, ResolvedNode],
    packages_dir: Path,
) -> Path:
    fpm_dir = project_root / ".fpm"
    fpm_dir.mkdir(parents=True, exist_ok=True)
    out_file = fpm_dir / "resolution-map.json"

    data = generate_resolution_map(resolved_nodes, packages_dir, use_absolute_paths=True)
    out_file.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return out_file
