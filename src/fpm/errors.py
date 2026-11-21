"""Structured error hierarchy and diagnostic codes for fpm."""

from __future__ import annotations

from typing import Any


class FpmError(Exception):
    """Base exception for all Funnel Package Manager diagnostic errors."""

    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(f"[{code}] {message}")
        self.code = code
        self.message = message
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "details": self.details,
        }


# Manifest & Schema Errors (FPM-E1xx)
class ManifestSyntaxError(FpmError):
    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__("FPM-E101", message, details)


class InvalidPackageNameError(FpmError):
    def __init__(self, name: str, details: dict[str, Any] | None = None) -> None:
        msg = (
            f"Invalid package name '{name}'. Must match scoped pattern "
            f"'^[a-z0-9-]+/[a-z0-9_]+$' (e.g. 'ecommerce/d2c_scale')."
        )
        super().__init__("FPM-E102", msg, details)


class InvalidSemVerError(FpmError):
    def __init__(self, version: str, details: dict[str, Any] | None = None) -> None:
        super().__init__("FPM-E103", f"Invalid SemVer 2.0 version string: '{version}'", details)


class MissingManifestFieldError(FpmError):
    def __init__(self, field: str, details: dict[str, Any] | None = None) -> None:
        super().__init__("FPM-E104", f"Missing required manifest field: '{field}'", details)


class InvalidParameterBoundsError(FpmError):
    def __init__(self, param_name: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__("FPM-E105", f"Parameter '{param_name}' bounds error: {message}", details)


# Resolver & Graph Errors (FPM-E2xx)
class CircularDependencyError(FpmError):
    def __init__(self, cycle_path: list[str], details: dict[str, Any] | None = None) -> None:
        chain = " -> ".join(cycle_path)
        det = details or {}
        det["cycle"] = cycle_path
        super().__init__("FPM-E201", f"Circular dependency detected: {chain}", det)


class VersionConflictError(FpmError):
    def __init__(
        self,
        package: str,
        conflicting_constraints: dict[str, str],
        details: dict[str, Any] | None = None,
    ) -> None:
        det = details or {}
        det["package"] = package
        det["conflicts"] = conflicting_constraints
        lines = [f"  - from '{parent}': requires '{req}'" for parent, req in conflicting_constraints.items()]
        msg = f"Unsatisfiable version conflict for '{package}':\n" + "\n".join(lines)
        super().__init__("FPM-E202", msg, det)


class EngineIncompatibleError(FpmError):
    def __init__(
        self,
        package: str,
        required_engine: str,
        current_engine: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        det = details or {}
        det.update({"package": package, "required": required_engine, "current": current_engine})
        msg = (
            f"Package '{package}' requires FunnelScript engine '{required_engine}', "
            f"which is incompatible with current version '{current_engine}'"
        )
        super().__init__("FPM-E203", msg, det)


# Fetcher & Registry Errors (FPM-E3xx)
class PackageNotFoundError(FpmError):
    def __init__(self, package: str, version: str | None = None, details: dict[str, Any] | None = None) -> None:
        ver_str = f" version '{version}'" if version else ""
        super().__init__("FPM-E301", f"Package '{package}'{ver_str} not found in registry", details)


class FetchError(FpmError):
    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__("FPM-E302", f"Failed to fetch package archive: {message}", details)


# Integrity & Lockfile Errors (FPM-E4xx)
class IntegrityVerificationError(FpmError):
    def __init__(
        self,
        package: str,
        expected_hash: str,
        actual_hash: str,
        file_path: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        det = details or {}
        det.update(
            {
                "package": package,
                "expected_hash": expected_hash,
                "actual_hash": actual_hash,
                "file_path": file_path,
            }
        )
        msg = (
            f"Integrity check failed for '{package}'. Expected hash '{expected_hash}', "
            f"got '{actual_hash}'. File may be corrupt or tampered."
        )
        super().__init__("FPM-E401", msg, det)


class FrozenLockfileOutOfSyncError(FpmError):
    def __init__(self, details: dict[str, Any] | None = None) -> None:
        msg = (
            "Lockfile 'fpm.lock' is out of sync with 'fpm.toml'. "
            "Cannot install with --frozen. Run 'fpm install' to regenerate lockfile."
        )
        super().__init__("FPM-E402", msg, details)


# Packaging & Pre-flight Errors (FPM-E5xx)
class MissingRequiredFileError(FpmError):
    def __init__(self, filename: str, details: dict[str, Any] | None = None) -> None:
        super().__init__("FPM-E501", f"Missing required file for packaging: '{filename}'", details)


class MissingExportError(FpmError):
    def __init__(self, export_name: str, target_file: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            "FPM-E502",
            f"Export '{export_name}' points to non-existent file: '{target_file}'",
            details,
        )


class CompilerLintError(FpmError):
    def __init__(self, output: str, details: dict[str, Any] | None = None) -> None:
        super().__init__("FPM-E503", f"FunnelScript compiler check failed:\n{output}", details)
