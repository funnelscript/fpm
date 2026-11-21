"""Registry metadata and package index models."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class RegistryVersionEntry(BaseModel):
    model_config = ConfigDict(extra="ignore")

    version: str = Field(..., description="Package version")
    tarball_url: str = Field(..., description="Relative or absolute URL to tarball")
    integrity: str = Field(..., description="SHA-256 digest prefixed with sha256-")
    funnelscript_version: str = Field(default=">=0.1.0", description="Compatible engine constraint")
    dependencies: dict[str, str] = Field(default_factory=dict, description="Package dependencies")
    entry: str = Field(default="index.fnl", description="Entry file")
    published_at: str | None = Field(default=None, description="ISO timestamp")


class RegistryPackageIndex(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str = Field(..., description="Scoped package name")
    description: str = Field(default="", description="Package description")
    latest: str = Field(..., description="Latest stable version")
    versions: dict[str, RegistryVersionEntry] = Field(
        default_factory=dict,
        description="Available published versions",
    )

    def to_json(self) -> str:
        return json.dumps(self.model_dump(), indent=2, sort_keys=True) + "\n"

    def save_to_file(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_json(), encoding="utf-8")

    @classmethod
    def load_from_file(cls, path: Path) -> RegistryPackageIndex:
        return cls(**json.loads(path.read_text(encoding="utf-8")))
