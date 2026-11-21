"""Deterministic lockfile schema and serialization for fpm.lock."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class LockedPackage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str = Field(..., description="Scoped package identifier")
    version: str = Field(..., description="Exact resolved SemVer version")
    resolved: str = Field(..., description="Source location (tarball URL, local path, or git URI)")
    integrity: str = Field(..., description="Cryptographic SHA-256 digest prefixed with 'sha256-'")
    entry: str = Field(default="index.fnl", description="Relative path to package entry point")
    dependencies: dict[str, str] = Field(
        default_factory=dict,
        description="Direct dependency names mapped to exact resolved versions",
    )

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "dependencies": dict(sorted(self.dependencies.items())),
            "entry": self.entry,
            "integrity": self.integrity,
            "name": self.name,
            "resolved": self.resolved,
            "version": self.version,
        }


class Lockfile(BaseModel):
    model_config = ConfigDict(extra="ignore")

    lockfile_version: int = Field(default=1, description="Lockfile format version")
    manifest_hash: str = Field(..., description="SHA-256 digest of fpm.toml when lockfile was generated")
    packages: dict[str, LockedPackage] = Field(
        default_factory=dict,
        description="Resolved package entries indexed by scoped name or name@version",
    )

    def to_canonical_dict(self) -> dict[str, Any]:
        sorted_pkgs = {pkg_key: self.packages[pkg_key].to_canonical_dict() for pkg_key in sorted(self.packages.keys())}
        return {
            "lockfile_version": self.lockfile_version,
            "manifest_hash": self.manifest_hash,
            "packages": sorted_pkgs,
        }

    def to_canonical_json(self) -> str:
        data = self.to_canonical_dict()
        return json.dumps(data, indent=2, sort_keys=True) + "\n"

    def save_to_file(self, path: Path) -> None:
        content = self.to_canonical_json()
        path.write_text(content, encoding="utf-8")

    @classmethod
    def load_from_file(cls, path: Path) -> Lockfile:
        if not path.exists():
            raise FileNotFoundError(f"Lockfile not found: {path}")
        raw = json.loads(path.read_text(encoding="utf-8"))
        pkgs = {}
        for k, v in raw.get("packages", {}).items():
            pkgs[k] = LockedPackage(**v)
        return cls(
            lockfile_version=raw.get("lockfile_version", 1),
            manifest_hash=raw.get("manifest_hash", ""),
            packages=pkgs,
        )
