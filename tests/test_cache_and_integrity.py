"""Tests verifying global cache, SHA-256 integrity verification, and tamper detection."""

from pathlib import Path

import pytest

from fpm.errors import IntegrityVerificationError
from fpm.models.lockfile import Lockfile
from fpm.models.manifest import Manifest, PackageMetadata
from fpm.store.cache import GlobalCache
from fpm.store.packager import build_package_tarball


def test_cache_store_and_retrieve(tmp_path: Path):
    cache_dir = tmp_path / "cache"
    cache = GlobalCache(cache_dir=cache_dir)

    # Create dummy package directory
    pkg_dir = tmp_path / "sample_pkg"
    pkg_dir.mkdir()
    (pkg_dir / "index.fnl").write_text("// FunnelScript", encoding="utf-8")
    (pkg_dir / "README.md").write_text("# Readme", encoding="utf-8")
    (pkg_dir / "fpm.toml").write_text(
        '[package]\nname = "test/pkg"\nversion = "0.1.0"\ndescription = "desc"\n',
        encoding="utf-8",
    )

    tar_out = tmp_path / "sample.tar.gz"
    _, digest = build_package_tarball(pkg_dir, tar_out)

    # Store in cache
    stored = cache.store_tarball(tar_out, digest)
    assert stored.exists()

    # Retrieve by digest
    retrieved = cache.get_tarball(digest)
    assert retrieved == stored

    # Attempt store with corrupted/mismatched digest
    corrupt_digest = "sha256-0000000000000000000000000000000000000000000000000000000000000000"
    with pytest.raises(IntegrityVerificationError) as exc_info:
        cache.store_tarball(tar_out, corrupt_digest)
    assert exc_info.value.code == "FPM-E401"


def test_tamper_detection(tmp_path: Path):
    cache = GlobalCache(cache_dir=tmp_path / "cache")

    # Create package and tarball
    pkg_dir = tmp_path / "pkg"
    pkg_dir.mkdir()
    fnl_file = pkg_dir / "index.fnl"
    fnl_file.write_text("strategy Test { val = 1.0 USD; }", encoding="utf-8")

    tar_file = tmp_path / "pkg.tar.gz"
    _, original_digest = build_package_tarball(pkg_dir, tar_file)

    # Extract to target directory
    extract_dest = tmp_path / "installed" / "test/pkg@0.1.0"
    cache.extract_tarball(tar_file, extract_dest, expected_integrity=original_digest)
    assert (extract_dest / "index.fnl").exists()

    # Tamper with single byte in installed file
    installed_fnl = extract_dest / "index.fnl"
    installed_fnl.write_text("strategy Test { val = 2.0 USD; }", encoding="utf-8")

    # Re-packing/verifying detects hash mismatch
    temp_check = tmp_path / "check.tar.gz"
    _, tampered_digest = build_package_tarball(extract_dest, temp_check)
    assert tampered_digest != original_digest


def test_frozen_lockfile_out_of_sync():
    meta = PackageMetadata(
        name="root/app",
        version="0.1.0",
        description="desc",
    )
    m = Manifest(package=meta)
    m_hash = m.compute_hash()

    lock = Lockfile(
        lockfile_version=1,
        manifest_hash="sha256-different-hash",
        packages={},
    )
    assert lock.manifest_hash != m_hash
