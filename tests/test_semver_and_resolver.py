"""Tests for SemVer 2.0 evaluation, range matching, and dependency graph resolution."""

import pytest

from fpm.errors import (
    CircularDependencyError,
    EngineIncompatibleError,
    VersionConflictError,
)
from fpm.models.manifest import Manifest, PackageMetadata
from fpm.resolver.graph import DependencyResolver, PackageProvider
from fpm.resolver.semver import Version, matches_constraint, select_best_version


def test_semver_comparisons():
    v1 = Version.parse("1.0.0")
    v2 = Version.parse("1.2.0")
    v3 = Version.parse("2.0.0")
    v_pre = Version.parse("1.0.0-alpha.1")

    assert v1 < v2 < v3
    assert v_pre < v1
    assert v1 == Version.parse("1.0.0")
    assert str(v1) == "1.0.0"


def test_semver_constraints():
    # Caret
    assert matches_constraint("1.2.3", "^1.2.0")
    assert matches_constraint("1.9.9", "^1.2.0")
    assert not matches_constraint("2.0.0", "^1.2.0")
    assert not matches_constraint("1.1.0", "^1.2.0")

    # Caret on 0.x
    assert matches_constraint("0.2.5", "^0.2.0")
    assert not matches_constraint("0.3.0", "^0.2.0")

    # Tilde
    assert matches_constraint("1.2.5", "~1.2.0")
    assert not matches_constraint("1.3.0", "~1.2.0")

    # Inequalities
    assert matches_constraint("0.5.0", ">=0.4.0,<1.0.0")
    assert not matches_constraint("1.0.0", ">=0.4.0,<1.0.0")
    assert not matches_constraint("0.3.9", ">=0.4.0,<1.0.0")

    # Best version selection
    versions = ["0.1.0", "0.2.0", "0.2.5", "1.0.0", "1.1.0"]
    assert str(select_best_version(versions, "^0.2.0")) == "0.2.5"
    assert str(select_best_version(versions, "^1.0.0")) == "1.1.0"
    assert select_best_version(versions, "^2.0.0") is None


class DummyProvider(PackageProvider):
    def __init__(self, packages_data: dict[str, dict[str, dict]]):
        # packages_data: { pkg_name: { version: { "deps": {...}, "engine": ">=0.4.0" } } }
        self.data = packages_data

    def get_available_versions(self, package_name: str) -> list[str]:
        return sorted(self.data.get(package_name, {}).keys())

    def get_package_manifest(self, package_name: str, version: str) -> Manifest:
        info = self.data[package_name][version]
        meta = PackageMetadata(
            name=package_name,
            version=version,
            description="desc",
            funnelscript_version=info.get("engine", ">=0.4.0"),
        )
        return Manifest(
            package=meta,
            dependencies=info.get("deps", {}),
        )

    def get_package_tarball_info(self, package_name: str, version: str) -> tuple[str, str]:
        return f"https://registry.funnelscript.org/{package_name}-{version}.tar.gz", "sha256-mock"


def test_resolver_clean_chain():
    provider = DummyProvider(
        {
            "pkg/b": {
                "1.0.0": {"deps": {"pkg/c": "^1.0.0"}},
            },
            "pkg/c": {
                "1.1.0": {"deps": {}},
            },
        }
    )
    resolver = DependencyResolver(provider, funnelscript_version="0.4.0")
    root_manifest = Manifest(
        package=PackageMetadata(name="root/app", version="0.1.0", description="root"),
        dependencies={"pkg/b": "^1.0.0"},
    )
    resolved = resolver.resolve(root_manifest)
    assert "pkg/b" in resolved
    assert "pkg/c" in resolved
    assert resolved["pkg/b"].version == "1.0.0"
    assert resolved["pkg/c"].version == "1.1.0"


def test_resolver_cycle_detection():
    # A -> B -> C -> A (cycle)
    provider = DummyProvider(
        {
            "pkg/b": {"1.0.0": {"deps": {"pkg/c": "^1.0.0"}}},
            "pkg/c": {"1.0.0": {"deps": {"pkg/b": "^1.0.0"}}},
        }
    )
    resolver = DependencyResolver(provider, funnelscript_version="0.4.0")
    root_manifest = Manifest(
        package=PackageMetadata(name="root/app", version="0.1.0", description="root"),
        dependencies={"pkg/b": "^1.0.0"},
    )
    with pytest.raises(CircularDependencyError) as exc_info:
        resolver.resolve(root_manifest)
    assert exc_info.value.code == "FPM-E201"
    assert "pkg/b" in exc_info.value.details["cycle"]


def test_resolver_version_conflict():
    # Root needs A and B
    # A needs C@^1.0.0
    # B needs C@^2.0.0
    provider = DummyProvider(
        {
            "pkg/a": {"1.0.0": {"deps": {"pkg/c": "^1.0.0"}}},
            "pkg/b": {"1.0.0": {"deps": {"pkg/c": "^2.0.0"}}},
            "pkg/c": {
                "1.0.0": {"deps": {}},
                "2.0.0": {"deps": {}},
            },
        }
    )
    resolver = DependencyResolver(provider, funnelscript_version="0.4.0")
    root_manifest = Manifest(
        package=PackageMetadata(name="root/app", version="0.1.0", description="root"),
        dependencies={"pkg/a": "^1.0.0", "pkg/b": "^1.0.0"},
    )
    with pytest.raises(VersionConflictError) as exc_info:
        resolver.resolve(root_manifest)
    assert exc_info.value.code == "FPM-E202"
    assert exc_info.value.details["package"] == "pkg/c"


def test_resolver_engine_incompatible():
    provider = DummyProvider(
        {
            "pkg/a": {"1.0.0": {"deps": {}, "engine": ">=1.0.0"}},
        }
    )
    resolver = DependencyResolver(provider, funnelscript_version="0.4.0")
    root_manifest = Manifest(
        package=PackageMetadata(name="root/app", version="0.1.0", description="root"),
        dependencies={"pkg/a": "^1.0.0"},
    )
    with pytest.raises(EngineIncompatibleError) as exc_info:
        resolver.resolve(root_manifest)
    assert exc_info.value.code == "FPM-E203"
    assert exc_info.value.details["required"] == ">=1.0.0"
    assert exc_info.value.details["current"] == "0.4.0"
