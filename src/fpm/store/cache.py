"""Content-addressed global cache and package extraction."""

from __future__ import annotations

import os
import shutil
import tarfile
from pathlib import Path

from fpm.errors import IntegrityVerificationError
from fpm.store.packager import compute_file_sha256


class GlobalCache:
    """Manages content-addressed tarball storage and extracted package assets."""

    def __init__(self, cache_dir: Path | None = None) -> None:
        if cache_dir:
            self.root = cache_dir.resolve()
        else:
            env_dir = os.environ.get("FPM_CACHE_DIR")
            if env_dir:
                self.root = Path(env_dir).resolve()
            else:
                self.root = Path.home() / ".cache" / "fpm"

        self.tarballs_dir = self.root / "tarballs"
        self.tarballs_dir.mkdir(parents=True, exist_ok=True)

    def _hash_to_filename(self, integrity: str) -> str:
        # integrity is "sha256-<hex>"
        clean = integrity.replace("sha256-", "")
        return f"{clean}.tar.gz"

    def get_tarball(self, integrity: str) -> Path | None:
        candidate = self.tarballs_dir / self._hash_to_filename(integrity)
        if candidate.exists():
            # Verify integrity
            computed = compute_file_sha256(candidate)
            if computed == integrity:
                return candidate
            candidate.unlink(missing_ok=True)
        return None

    def store_tarball(self, source_path: Path, integrity: str) -> Path:
        computed = compute_file_sha256(source_path)
        if computed != integrity:
            raise IntegrityVerificationError(
                package=source_path.name,
                expected_hash=integrity,
                actual_hash=computed,
                file_path=str(source_path),
            )
        dest = self.tarballs_dir / self._hash_to_filename(integrity)
        if not dest.exists():
            shutil.copy2(source_path, dest)
        return dest

    def extract_tarball(
        self,
        tarball_path: Path,
        destination_dir: Path,
        expected_integrity: str | None = None,
    ) -> Path:
        if expected_integrity:
            computed = compute_file_sha256(tarball_path)
            if computed != expected_integrity:
                raise IntegrityVerificationError(
                    package=tarball_path.name,
                    expected_hash=expected_integrity,
                    actual_hash=computed,
                    file_path=str(tarball_path),
                )

        destination_dir.mkdir(parents=True, exist_ok=True)
        with tarfile.open(tarball_path, "r:gz") as tar:
            tar.extractall(destination_dir)

        return destination_dir
