"""Resolver package providing SemVer evaluation, dependency DAG resolution, and runtime bridge."""

from fpm.resolver.bridge import generate_resolution_map, write_resolution_map
from fpm.resolver.graph import DependencyResolver, PackageProvider, ResolvedNode
from fpm.resolver.semver import Version, VersionRange, matches_constraint, select_best_version

__all__ = [
    "DependencyResolver",
    "PackageProvider",
    "ResolvedNode",
    "Version",
    "VersionRange",
    "generate_resolution_map",
    "matches_constraint",
    "select_best_version",
    "write_resolution_map",
]
