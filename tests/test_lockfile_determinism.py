"""Tests verifying byte-for-byte reproducibility and canonical serialization of fpm.lock."""

import json
from pathlib import Path

from fpm.models.lockfile import LockedPackage, Lockfile


def test_lockfile_canonical_determinism():
    pkg1 = LockedPackage(
        name="leadgen/sales_capacity",
        version="0.1.0",
        resolved="https://registry.funnelscript.org/leadgen-sales_capacity-0.1.0.tar.gz",
        integrity="sha256-abcdef1234567890",
        entry="index.fnls",
        dependencies={"ecommerce/d2c_scale": "^0.1.0"},
    )
    pkg2 = LockedPackage(
        name="ecommerce/d2c_scale",
        version="0.1.0",
        resolved="https://registry.funnelscript.org/ecommerce-d2c_scale-0.1.0.tar.gz",
        integrity="sha256-1234567890abcdef",
        entry="index.fnls",
        dependencies={},
    )

    # Insert in unsorted order
    lockfile = Lockfile(
        lockfile_version=1,
        manifest_hash="sha256-manifest-hash-value",
        packages={
            "leadgen/sales_capacity@0.1.0": pkg1,
            "ecommerce/d2c_scale@0.1.0": pkg2,
        },
    )

    json_str_1 = lockfile.to_canonical_json()
    json_str_2 = lockfile.to_canonical_json()

    # Exact byte-for-byte equality
    assert json_str_1 == json_str_2
    assert json_str_1.endswith("\n")

    # Verify keys are sorted: 'ecommerce/d2c_scale@0.1.0' should precede 'leadgen/sales_capacity@0.1.0'
    parsed = json.loads(json_str_1)
    keys = list(parsed["packages"].keys())
    assert keys == ["ecommerce/d2c_scale@0.1.0", "leadgen/sales_capacity@0.1.0"]


def test_lockfile_save_and_load(tmp_path: Path):
    lock_file = tmp_path / "fpm.lock"
    pkg = LockedPackage(
        name="test/pkg",
        version="1.0.0",
        resolved="file://local",
        integrity="sha256-test",
        entry="index.fnls",
    )
    lock = Lockfile(
        lockfile_version=1,
        manifest_hash="sha256-sample",
        packages={"test/pkg@1.0.0": pkg},
    )
    lock.save_to_file(lock_file)
    assert lock_file.exists()

    loaded = Lockfile.load_from_file(lock_file)
    assert loaded.lockfile_version == 1
    assert loaded.manifest_hash == "sha256-sample"
    assert "test/pkg@1.0.0" in loaded.packages
    assert loaded.packages["test/pkg@1.0.0"].version == "1.0.0"
    assert loaded.to_canonical_json() == lock.to_canonical_json()
