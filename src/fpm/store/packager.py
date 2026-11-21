"""Deterministic tarball creation for reproducible fpm packages."""

from __future__ import annotations

import gzip
import hashlib
import io
import os
import tarfile
from pathlib import Path
from typing import Callable

DEFAULT_MTIME = 1700000000  # Fixed deterministic timestamp
EXCLUDED_PATTERNS = {
    ".git",
    ".DS_Store",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    ".fpm",
    "dist",
    "build",
}


def compute_file_sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return f"sha256-{hasher.hexdigest()}"


def compute_bytes_sha256(data: bytes) -> str:
    return f"sha256-{hashlib.sha256(data).hexdigest()}"


def build_package_tarball(
    package_dir: Path,
    output_path: Path,
    mtime: int = DEFAULT_MTIME,
    filter_func: Callable[[Path], bool] | None = None,
) -> tuple[Path, str]:
    package_dir = package_dir.resolve()
    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Collect and sort all files deterministically
    all_files: list[Path] = []
    for root, dirs, files in os.walk(package_dir):
        dirs[:] = sorted([d for d in dirs if d not in EXCLUDED_PATTERNS and not d.startswith(".")])
        for f in sorted(files):
            if f in EXCLUDED_PATTERNS or f.endswith(".pyc") or f.startswith("."):
                continue
            p = Path(root) / f
            if filter_func and not filter_func(p):
                continue
            all_files.append(p)

    all_files.sort(key=lambda p: p.relative_to(package_dir).as_posix())

    # Write tar with normalized tarinfo into a deterministic gzip stream
    tar_buffer = io.BytesIO()
    with tarfile.open(fileobj=tar_buffer, mode="w:") as tar:
        for file_path in all_files:
            rel_name = file_path.relative_to(package_dir).as_posix()
            data = file_path.read_bytes()
            ti = tarfile.TarInfo(name=rel_name)
            ti.size = len(data)
            ti.mtime = mtime
            ti.mode = 0o644
            ti.uid = 0
            ti.gid = 0
            ti.uname = ""
            ti.gname = ""
            tar.addfile(ti, io.BytesIO(data))

    uncompressed_tar = tar_buffer.getvalue()

    # Compress with fixed gzip mtime
    gz_buffer = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=gz_buffer, mtime=float(mtime)) as gz:
        gz.write(uncompressed_tar)

    tar_bytes = gz_buffer.getvalue()
    output_path.write_bytes(tar_bytes)
    digest = compute_bytes_sha256(tar_bytes)

    return output_path, digest
