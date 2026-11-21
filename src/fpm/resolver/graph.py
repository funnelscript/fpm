"""Deterministic dependency graph resolution, cycle detection, and conflict analysis."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from fpm.errors import (
    CircularDependencyError,
    EngineIncompatibleError,
    PackageNotFoundError,
    VersionConflictError,
)
from fpm.models.manifest import GitDependency, Manifest, PathDependency
from fpm.resolver.semver import matches_constraint, select_best_version


@dataclass
class ResolvedNode:
    name: str
    version: str
    resolved: str
    integrity: str
    entry: str = "index.fnl"
    dependencies: dict[str, str] = field(default_factory=dict)
    modules: dict[str, str] = field(default_factory=dict)
    local_dir: str | None = None


class PackageProvider(Protocol):
    def get_available_versions(self, package_name: str) -> list[str]: ...

    def get_package_manifest(self, package_name: str, version: str) -> Manifest: ...

    def get_package_tarball_info(self, package_name: str, version: str) -> tuple[str, str]: ...


class DependencyResolver:
    """Deterministic, acyclic package dependency resolver."""

    def __init__(
        self,
        provider: PackageProvider,
        funnelscript_version: str = "0.4.0",
    ) -> None:
        self.provider = provider
        self.funnelscript_version = funnelscript_version

    def resolve(self, root_manifest: Manifest) -> dict[str, ResolvedNode]:
        resolved: dict[str, ResolvedNode] = {}
        constraints_by_package: dict[str, dict[str, str]] = {}

        # Detect cycles and build resolution plan using DFS
        active_stack: list[str] = [root_manifest.name]
        self._resolve_dependencies(
            parent_name=root_manifest.name,
            dependencies=root_manifest.dependencies,
            active_stack=active_stack,
            resolved=resolved,
            constraints_by_package=constraints_by_package,
        )

        return resolved

    def _resolve_dependencies(
        self,
        parent_name: str,
        dependencies: dict[str, Any],
        active_stack: list[str],
        resolved: dict[str, ResolvedNode],
        constraints_by_package: dict[str, dict[str, str]],
    ) -> None:
        for pkg_name, dep_spec in sorted(dependencies.items()):
            # Cycle detection
            if pkg_name in active_stack:
                cycle = active_stack[active_stack.index(pkg_name) :] + [pkg_name]
                raise CircularDependencyError(cycle)

            # Record constraint
            req_constraint = self._extract_constraint(dep_spec)
            if pkg_name not in constraints_by_package:
                constraints_by_package[pkg_name] = {}
            constraints_by_package[pkg_name][parent_name] = req_constraint

            # Handle Path Dependency
            if isinstance(dep_spec, PathDependency) or (isinstance(dep_spec, dict) and "path" in dep_spec):
                path_str = dep_spec.path if isinstance(dep_spec, PathDependency) else dep_spec["path"]
                # Resolve via local manifest
                node = self._resolve_path_dependency(pkg_name, path_str)
                resolved[pkg_name] = node
                continue

            # Handle Registry / SemVer Dependency
            available_versions = self.provider.get_available_versions(pkg_name)
            if not available_versions:
                raise PackageNotFoundError(pkg_name)

            # Check if all collected constraints for this package are satisfiable
            all_reqs = list(constraints_by_package[pkg_name].values())
            candidate_versions: list[str] = []
            for v_str in available_versions:
                if all(matches_constraint(v_str, req) for req in all_reqs):
                    candidate_versions.append(v_str)

            if not candidate_versions:
                raise VersionConflictError(pkg_name, constraints_by_package[pkg_name])

            # Deterministic selection: highest version satisfying all constraints
            best_ver = select_best_version(candidate_versions, req_constraint)
            if not best_ver:
                raise VersionConflictError(pkg_name, constraints_by_package[pkg_name])

            best_ver_str = str(best_ver)

            # Fetch manifest for engine & transitive deps check
            pkg_manifest = self.provider.get_package_manifest(pkg_name, best_ver_str)

            # FunnelScript Engine compatibility check (FPM-E203)
            engine_req = pkg_manifest.package.funnelscript_version
            if not matches_constraint(self.funnelscript_version, engine_req):
                raise EngineIncompatibleError(pkg_name, engine_req, self.funnelscript_version)

            resolved_url, integrity = self.provider.get_package_tarball_info(pkg_name, best_ver_str)

            direct_deps = {}
            for d_name, d_val in pkg_manifest.dependencies.items():
                direct_deps[d_name] = self._extract_constraint(d_val)

            resolved[pkg_name] = ResolvedNode(
                name=pkg_name,
                version=best_ver_str,
                resolved=resolved_url,
                integrity=integrity,
                entry=pkg_manifest.entry,
                dependencies=direct_deps,
                modules=pkg_manifest.modules,
            )

            # Recurse on transitive dependencies
            active_stack.append(pkg_name)
            self._resolve_dependencies(
                parent_name=pkg_name,
                dependencies=pkg_manifest.dependencies,
                active_stack=active_stack,
                resolved=resolved,
                constraints_by_package=constraints_by_package,
            )
            active_stack.pop()

    def _extract_constraint(self, dep_spec: Any) -> str:
        if isinstance(dep_spec, str):
            return dep_spec
        if isinstance(dep_spec, (PathDependency, GitDependency)):
            return dep_spec.version or "*"
        if isinstance(dep_spec, dict):
            return dep_spec.get("version", "*")
        return "*"

    def _resolve_path_dependency(self, name: str, rel_path: str) -> ResolvedNode:
        import hashlib
        from pathlib import Path

        p = Path(rel_path).resolve()
        manifest_file = p / "fpm.toml"
        if not manifest_file.exists():
            raise PackageNotFoundError(name, details={"path": str(p)})
        m = Manifest.load_from_file(manifest_file)

        # Hash files in directory deterministically
        hasher = hashlib.sha256()
        for f in sorted(p.rglob("*.fnl")):
            hasher.update(f.relative_to(p).as_posix().encode("utf-8"))
            hasher.update(f.read_bytes())
        digest = f"sha256-{hasher.hexdigest()}"

        return ResolvedNode(
            name=name,
            version=m.version,
            resolved=f"file://{p.as_posix()}",
            integrity=digest,
            entry=m.entry,
            dependencies={k: self._extract_constraint(v) for k, v in m.dependencies.items()},
            modules=m.modules,
            local_dir=str(p),
        )
