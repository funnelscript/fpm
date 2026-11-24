"""Tests for deterministic package archiving, layout checks, and publish validation."""

from pathlib import Path

import pytest

from fpm.errors import MissingExportError, MissingRequiredFileError
from fpm.store.packager import build_package_tarball
from fpm.validator.package_check import run_preflight_audit, validate_package_layout


def test_deterministic_tarball_hash(tmp_path: Path):
    pkg_dir = tmp_path / "deterministic_pkg"
    pkg_dir.mkdir()
    (pkg_dir / "index.fnls").write_text("strategy Main {}", encoding="utf-8")
    (pkg_dir / "README.md").write_text("# Readme", encoding="utf-8")
    (pkg_dir / "fpm.toml").write_text(
        '[package]\nname = "test/det"\nversion = "0.1.0"\ndescription = "desc"\n',
        encoding="utf-8",
    )

    tar_out_1 = tmp_path / "out1.tar.gz"
    tar_out_2 = tmp_path / "out2.tar.gz"

    _, digest1 = build_package_tarball(pkg_dir, tar_out_1)
    _, digest2 = build_package_tarball(pkg_dir, tar_out_2)

    assert digest1 == digest2
    assert tar_out_1.read_bytes() == tar_out_2.read_bytes()


def test_preflight_audit_missing_readme(tmp_path: Path):
    pkg_dir = tmp_path / "pkg_no_readme"
    pkg_dir.mkdir()
    (pkg_dir / "index.fnls").write_text("strategy A {}", encoding="utf-8")
    (pkg_dir / "fpm.toml").write_text(
        '[package]\nname = "test/noreadme"\nversion = "0.1.0"\ndescription = "desc"\n',
        encoding="utf-8",
    )
    with pytest.raises(MissingRequiredFileError) as exc_info:
        validate_package_layout(pkg_dir)
    assert exc_info.value.code == "FPM-E501"


def test_preflight_audit_missing_entry(tmp_path: Path):
    pkg_dir = tmp_path / "pkg_no_entry"
    pkg_dir.mkdir()
    (pkg_dir / "README.md").write_text("# Readme", encoding="utf-8")
    (pkg_dir / "fpm.toml").write_text(
        '[package]\nname = "test/noentry"\nversion = "0.1.0"\ndescription = "desc"\nmain = "missing.fnls"\n',
        encoding="utf-8",
    )
    with pytest.raises(MissingRequiredFileError) as exc_info:
        validate_package_layout(pkg_dir)
    assert exc_info.value.code == "FPM-E501"


def test_preflight_audit_missing_export(tmp_path: Path):
    pkg_dir = tmp_path / "pkg_bad_export"
    pkg_dir.mkdir()
    (pkg_dir / "index.fnls").write_text("strategy A {}", encoding="utf-8")
    (pkg_dir / "README.md").write_text("# Readme", encoding="utf-8")
    (pkg_dir / "fpm.toml").write_text(
        '[package]\nname = "test/badexport"\nversion = "0.1.0"\ndescription = "desc"\n\n'
        '[modules]\nmissing_mod = "does_not_exist.fnls"\n',
        encoding="utf-8",
    )
    with pytest.raises(MissingExportError) as exc_info:
        validate_package_layout(pkg_dir)
    assert exc_info.value.code == "FPM-E502"


def test_preflight_audit_success(tmp_path: Path):
    pkg_dir = tmp_path / "valid_pkg"
    pkg_dir.mkdir()
    (pkg_dir / "index.fnls").write_text("strategy A {}", encoding="utf-8")
    (pkg_dir / "utils.fnls").write_text("entity B {}", encoding="utf-8")
    (pkg_dir / "README.md").write_text("# Readme", encoding="utf-8")
    (pkg_dir / "fpm.toml").write_text(
        '[package]\nname = "test/valid"\nversion = "0.1.0"\ndescription = "desc"\n\n[modules]\nutils = "utils.fnls"\n',
        encoding="utf-8",
    )
    report = run_preflight_audit(pkg_dir)
    assert report["status"] == "passed"
    assert report["name"] == "test/valid"
    assert report["modules_count"] == 1
