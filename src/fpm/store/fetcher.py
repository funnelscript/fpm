"""Package fetching from local paths, static registries, and git sources."""

from __future__ import annotations

import json
import shutil
import urllib.parse
import urllib.request
from pathlib import Path

from fpm.errors import FetchError, PackageNotFoundError
from fpm.models.manifest import Manifest
from fpm.models.registry import RegistryPackageIndex
from fpm.resolver.graph import PackageProvider
from fpm.store.cache import GlobalCache


class StaticRegistryProvider(PackageProvider):
    """Provides package metadata and fetches artifacts from a static or local file registry."""

    def __init__(
        self,
        registry_url_or_path: str | Path,
        cache: GlobalCache | None = None,
    ) -> None:
        self.raw_source = str(registry_url_or_path)
        self.is_local = not (self.raw_source.startswith("http://") or self.raw_source.startswith("https://"))
        self.base_path = Path(registry_url_or_path).resolve() if self.is_local else None
        self.cache = cache or GlobalCache()
        self._indices: dict[str, RegistryPackageIndex] = {}

    def _get_index_url(self, package_name: str) -> str:
        # Static registry index structure: index/<scope>/<name>.json
        if self.is_local and self.base_path:
            return str((self.base_path / "index" / f"{package_name}.json").resolve())
        return f"{self.raw_source.rstrip('/')}/index/{package_name}.json"

    def _get_tarball_url(self, relative_or_absolute: str) -> str:
        if relative_or_absolute.startswith("http://") or relative_or_absolute.startswith("https://"):
            return relative_or_absolute
        if self.is_local and self.base_path:
            return str((self.base_path / relative_or_absolute).resolve())
        return f"{self.raw_source.rstrip('/')}/{relative_or_absolute.lstrip('/')}"

    def load_package_index(self, package_name: str) -> RegistryPackageIndex:
        if package_name in self._indices:
            return self._indices[package_name]

        index_loc = self._get_index_url(package_name)
        if self.is_local:
            p = Path(index_loc)
            if not p.exists():
                raise PackageNotFoundError(package_name, details={"location": index_loc})
            try:
                index = RegistryPackageIndex.load_from_file(p)
            except Exception as err:
                raise FetchError(f"Failed to read index for '{package_name}': {err}") from err
        else:
            try:
                req = urllib.request.Request(index_loc, headers={"User-Agent": "fpm/0.1.0"})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    index = RegistryPackageIndex(**data)
            except Exception as err:
                raise PackageNotFoundError(package_name, details={"url": index_loc, "error": str(err)}) from err

        self._indices[package_name] = index
        return index

    def get_available_versions(self, package_name: str) -> list[str]:
        try:
            index = self.load_package_index(package_name)
            return sorted(index.versions.keys())
        except PackageNotFoundError:
            return []

    def get_package_tarball_info(self, package_name: str, version: str) -> tuple[str, str]:
        index = self.load_package_index(package_name)
        ver_info = index.versions.get(version)
        if not ver_info:
            raise PackageNotFoundError(package_name, version=version)
        tarball_url = self._get_tarball_url(ver_info.tarball_url)
        return tarball_url, ver_info.integrity

    def get_package_manifest(self, package_name: str, version: str) -> Manifest:
        # Check cache or fetch tarball and inspect manifest
        tarball_url, integrity = self.get_package_tarball_info(package_name, version)
        local_tarball = self.fetch_tarball(tarball_url, integrity)

        # Extract to temporary inspection location or cache
        inspect_dir = self.cache.root / "inspect" / f"{package_name}@{version}"
        if not (inspect_dir / "fpm.toml").exists():
            self.cache.extract_tarball(local_tarball, inspect_dir, expected_integrity=integrity)

        return Manifest.load_from_file(inspect_dir / "fpm.toml")

    def fetch_tarball(self, tarball_url: str, expected_integrity: str) -> Path:
        cached = self.cache.get_tarball(expected_integrity)
        if cached:
            return cached

        # Download or copy to temp
        temp_dl = self.cache.root / "temp_download.tar.gz"
        temp_dl.parent.mkdir(parents=True, exist_ok=True)

        if not (tarball_url.startswith("http://") or tarball_url.startswith("https://")):
            # Local file path
            src_file = Path(tarball_url)
            if not src_file.exists():
                raise FetchError(f"Local tarball not found at {src_file}")
            shutil.copy2(src_file, temp_dl)
        else:
            try:
                req = urllib.request.Request(tarball_url, headers={"User-Agent": "fpm/0.1.0"})
                with urllib.request.urlopen(req, timeout=15) as resp, temp_dl.open("wb") as out:
                    shutil.copyfileobj(resp, out)
            except Exception as err:
                raise FetchError(f"Network error downloading {tarball_url}: {err}") from err

        stored = self.cache.store_tarball(temp_dl, expected_integrity)
        temp_dl.unlink(missing_ok=True)
        return stored

    def install_package(self, package_name: str, version: str, destination: Path) -> Path:
        tarball_url, integrity = self.get_package_tarball_info(package_name, version)
        tarball_path = self.fetch_tarball(tarball_url, integrity)
        return self.cache.extract_tarball(tarball_path, destination, expected_integrity=integrity)
