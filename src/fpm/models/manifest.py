"""Pydantic v2 schemas and validation for fpm.toml package manifests."""

from __future__ import annotations

import hashlib
import re
import tomllib
from pathlib import Path
from typing import Annotated, Any, Literal

import tomli_w
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from fpm.errors import (
    InvalidPackageNameError,
    InvalidParameterBoundsError,
    InvalidSemVerError,
    ManifestSyntaxError,
    MissingManifestFieldError,
)

NAME_PATTERN = re.compile(r"^[a-z0-9-]+/[a-z0-9_]+$")
SEMVER_PATTERN = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
)


class PackageMetadata(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    name: str = Field(..., description="Scoped package identifier (e.g. 'ecommerce/d2c_scale')")
    version: str = Field(..., description="Strict SemVer 2.0 version")
    description: str = Field(..., description="Package summary")
    license: str = Field(default="MIT", description="SPDX license identifier")
    author: str | None = Field(default=None, description="Author / Organization details")
    funnelscript_version: str = Field(
        default=">=0.1.0",
        description="Target FunnelScript compiler engine constraint",
    )
    entry: str = Field(
        default="index.fnls",
        description="Path to primary FunnelScript entry file",
        alias="main",
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not NAME_PATTERN.match(v):
            raise InvalidPackageNameError(v)
        return v

    @field_validator("version")
    @classmethod
    def validate_version(cls, v: str) -> str:
        if not SEMVER_PATTERN.match(v):
            raise InvalidSemVerError(v)
        return v


class ParameterSpec(BaseModel):
    model_config = ConfigDict(extra="ignore")

    type: Literal["float", "int", "str", "bool"] = Field(..., description="Parameter primitive type")
    dimension: str = Field(..., description="FunnelScript dimensional quantity or Scalar")
    unit: str | None = Field(default=None, description="Physical / financial unit")
    default: Any = Field(..., description="Default value")
    min: float | int | None = Field(default=None, description="Lower bound")
    max: float | int | None = Field(default=None, description="Upper bound")
    description: str = Field(..., description="Human-readable parameter documentation")

    @model_validator(mode="after")
    def validate_bounds(self) -> ParameterSpec:
        if self.type in ("float", "int") and isinstance(self.default, (int, float)):
            if self.min is not None and self.default < self.min:
                raise InvalidParameterBoundsError(
                    "self",
                    f"default ({self.default}) is strictly less than min ({self.min})",
                )
            if self.max is not None and self.default > self.max:
                raise InvalidParameterBoundsError(
                    "self",
                    f"default ({self.default}) is strictly greater than max ({self.max})",
                )
            if self.min is not None and self.max is not None and self.min > self.max:
                raise InvalidParameterBoundsError(
                    "self",
                    f"min ({self.min}) cannot be greater than max ({self.max})",
                )
        return self


class MetricSpec(BaseModel):
    model_config = ConfigDict(extra="ignore")

    dimension: str = Field(..., description="Dimensional type of simulation output")
    unit: str | None = Field(default=None, description="Unit of measurement")
    description: str = Field(..., description="Metric summary")


class PathDependency(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str = Field(..., description="Relative filesystem path to package directory")
    version: str | None = Field(default=None, description="Optional SemVer constraint")


class GitDependency(BaseModel):
    model_config = ConfigDict(extra="forbid")
    git: str = Field(..., description="Git repository URL")
    rev: str | None = Field(default=None, description="Commit hash, tag, or branch")
    version: str | None = Field(default=None, description="Optional SemVer constraint")


DependencySpec = Annotated[str | PathDependency | GitDependency, Field(description="Dependency specifier")]


class Manifest(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    package: PackageMetadata
    modules: dict[str, str] = Field(default_factory=dict, alias="exports")
    parameters: dict[str, ParameterSpec] = Field(default_factory=dict)
    metrics: dict[str, MetricSpec] = Field(default_factory=dict)
    dependencies: dict[str, DependencySpec] = Field(default_factory=dict)

    @property
    def name(self) -> str:
        return self.package.name

    @property
    def version(self) -> str:
        return self.package.version

    @property
    def entry(self) -> str:
        return self.package.entry

    def compute_hash(self) -> str:
        data = self.to_toml_dict()
        canonical_toml = tomli_w.dumps(data)
        return f"sha256-{hashlib.sha256(canonical_toml.encode('utf-8')).hexdigest()}"

    def to_toml_dict(self) -> dict[str, Any]:
        pkg = {
            "name": self.package.name,
            "version": self.package.version,
            "description": self.package.description,
            "license": self.package.license,
            "funnelscript_version": self.package.funnelscript_version,
            "main": self.package.entry,
        }
        if self.package.author:
            pkg["author"] = self.package.author

        out: dict[str, Any] = {"package": pkg}
        if self.modules:
            out["modules"] = dict(sorted(self.modules.items()))

        if self.parameters:
            params_dict = {}
            for k, p in sorted(self.parameters.items()):
                p_item: dict[str, Any] = {
                    "type": p.type,
                    "dimension": p.dimension,
                    "default": p.default,
                    "description": p.description,
                }
                if p.unit:
                    p_item["unit"] = p.unit
                if p.min is not None:
                    p_item["min"] = p.min
                if p.max is not None:
                    p_item["max"] = p.max
                params_dict[k] = p_item
            out["parameters"] = params_dict

        if self.metrics:
            metrics_dict = {}
            for k, m in sorted(self.metrics.items()):
                m_item: dict[str, Any] = {
                    "dimension": m.dimension,
                    "description": m.description,
                }
                if m.unit:
                    m_item["unit"] = m.unit
                metrics_dict[k] = m_item
            out["metrics"] = metrics_dict

        if self.dependencies:
            deps_dict = {}
            for k, d in sorted(self.dependencies.items()):
                if isinstance(d, str):
                    deps_dict[k] = d
                elif isinstance(d, PathDependency):
                    deps_dict[k] = {"path": d.path}
                    if d.version:
                        deps_dict[k]["version"] = d.version
                elif isinstance(d, GitDependency):
                    deps_dict[k] = {"git": d.git}
                    if d.rev:
                        deps_dict[k]["rev"] = d.rev
                    if d.version:
                        deps_dict[k]["version"] = d.version
                elif isinstance(d, dict):
                    deps_dict[k] = d
            out["dependencies"] = deps_dict

        return out

    def save_to_file(self, path: Path) -> None:
        data = self.to_toml_dict()
        toml_str = tomli_w.dumps(data)
        path.write_text(toml_str, encoding="utf-8")

    @classmethod
    def load_from_file(cls, path: Path) -> Manifest:
        if not path.exists():
            raise MissingManifestFieldError("fpm.toml", {"path": str(path)})
        try:
            raw = tomllib.loads(path.read_text(encoding="utf-8"))
        except Exception as err:
            raise ManifestSyntaxError(str(err), {"path": str(path)}) from err

        if "package" not in raw:
            raise MissingManifestFieldError("package", {"path": str(path)})

        # Normalize modules vs exports
        if "exports" in raw and "modules" not in raw:
            raw["modules"] = raw["exports"]

        # Parse dependencies
        deps = {}
        if "dependencies" in raw and isinstance(raw["dependencies"], dict):
            for k, v in raw["dependencies"].items():
                if isinstance(v, str):
                    deps[k] = v
                elif isinstance(v, dict):
                    if "path" in v:
                        deps[k] = PathDependency(**v)
                    elif "git" in v:
                        deps[k] = GitDependency(**v)
                    else:
                        deps[k] = v
            raw["dependencies"] = deps

        try:
            return cls(**raw)
        except (InvalidPackageNameError, InvalidSemVerError, InvalidParameterBoundsError):
            raise
        except Exception as err:
            raise ManifestSyntaxError(f"Manifest validation failed: {err}") from err
