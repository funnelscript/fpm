"""Tests for fpm.toml manifest parsing, validation, and error reporting."""

from pathlib import Path

import pytest

from fpm.errors import (
    InvalidPackageNameError,
    InvalidParameterBoundsError,
    InvalidSemVerError,
    MissingManifestFieldError,
)
from fpm.models.manifest import (
    GitDependency,
    Manifest,
    PackageMetadata,
    ParameterSpec,
    PathDependency,
)


def test_valid_package_metadata():
    pkg = PackageMetadata(
        name="ecommerce/d2c_scale",
        version="1.2.3",
        description="D2C scale model",
        license="MIT",
        funnelscript_version=">=0.4.0",
        entry="index.fnl",
    )
    assert pkg.name == "ecommerce/d2c_scale"
    assert pkg.version == "1.2.3"
    assert pkg.entry == "index.fnl"


def test_invalid_package_name():
    for bad_name in ["InvalidScope/pkg", "pkg_only", "scope/UPPER", "scope/with space"]:
        with pytest.raises(InvalidPackageNameError) as exc_info:
            PackageMetadata(
                name=bad_name,
                version="1.0.0",
                description="desc",
            )
        assert exc_info.value.code == "FPM-E102"


def test_invalid_semver():
    for bad_ver in ["1.0", "v1.0.0", "1.0.0.0", "1.0.beta", "latest"]:
        with pytest.raises(InvalidSemVerError) as exc_info:
            PackageMetadata(
                name="valid/pkg",
                version=bad_ver,
                description="desc",
            )
        assert exc_info.value.code == "FPM-E103"


def test_parameter_bounds_validation():
    # Valid
    p = ParameterSpec(
        type="float",
        dimension="Currency",
        unit="USD",
        default=50.0,
        min=10.0,
        max=100.0,
        description="Daily budget",
    )
    assert p.default == 50.0

    # Default < min
    with pytest.raises(InvalidParameterBoundsError) as exc_info:
        ParameterSpec(
            type="float",
            dimension="Currency",
            default=5.0,
            min=10.0,
            max=100.0,
            description="desc",
        )
    assert exc_info.value.code == "FPM-E105"

    # Default > max
    with pytest.raises(InvalidParameterBoundsError) as exc_info:
        ParameterSpec(
            type="int",
            dimension="Count",
            default=150,
            min=10,
            max=100,
            description="desc",
        )
    assert exc_info.value.code == "FPM-E105"

    # min > max
    with pytest.raises(InvalidParameterBoundsError) as exc_info:
        ParameterSpec(
            type="float",
            dimension="Scalar",
            default=50.0,
            min=100.0,
            max=10.0,
            description="desc",
        )
    assert exc_info.value.code == "FPM-E105"


def test_manifest_roundtrip_file(tmp_path: Path):
    manifest_file = tmp_path / "fpm.toml"
    meta = PackageMetadata(
        name="test/sample",
        version="0.1.0",
        description="Sample package",
        license="Apache-2.0",
        funnelscript_version=">=0.4.0",
        entry="main.fnl",
    )
    manifest = Manifest(
        package=meta,
        modules={"main": "main.fnl", "utils": "utils.fnl"},
        parameters={
            "spend": ParameterSpec(
                type="float",
                dimension="Currency",
                unit="USD",
                default=100.0,
                min=10.0,
                max=500.0,
                description="Spend parameter",
            )
        },
        dependencies={
            "dep/one": "^1.0.0",
            "dep/local": PathDependency(path="../other_pkg"),
            "dep/git": GitDependency(git="https://github.com/org/repo.git", rev="v1.0"),
        },
    )
    manifest.save_to_file(manifest_file)
    assert manifest_file.exists()

    loaded = Manifest.load_from_file(manifest_file)
    assert loaded.name == "test/sample"
    assert loaded.version == "0.1.0"
    assert loaded.entry == "main.fnl"
    assert loaded.modules["utils"] == "utils.fnl"
    assert "spend" in loaded.parameters
    assert isinstance(loaded.dependencies["dep/local"], PathDependency)
    assert loaded.dependencies["dep/local"].path == "../other_pkg"
    assert isinstance(loaded.dependencies["dep/git"], GitDependency)


def test_missing_manifest_file(tmp_path: Path):
    with pytest.raises(MissingManifestFieldError) as exc_info:
        Manifest.load_from_file(tmp_path / "non_existent.toml")
    assert exc_info.value.code == "FPM-E104"
