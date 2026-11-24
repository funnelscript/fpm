"""Command-line interface for the Funnel Package Manager (fpm)."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import click

from fpm.errors import (
    FpmError,
    FrozenLockfileOutOfSyncError,
)
from fpm.models.lockfile import LockedPackage, Lockfile
from fpm.models.manifest import GitDependency, Manifest, PackageMetadata, PathDependency
from fpm.resolver.bridge import write_resolution_map
from fpm.resolver.graph import DependencyResolver
from fpm.store.cache import GlobalCache
from fpm.store.fetcher import StaticRegistryProvider
from fpm.store.packager import build_package_tarball, compute_file_sha256
from fpm.validator.compiler_hook import run_compiler_check
from fpm.validator.package_check import run_preflight_audit


def _print_output(data: dict[str, Any], as_json: bool, fallback_msg: str | None = None) -> None:
    if as_json:
        click.echo(json.dumps(data, indent=2))
    elif fallback_msg:
        click.echo(fallback_msg)


@click.group()
@click.option("--json", "as_json", is_flag=True, help="Emit machine-readable JSON output")
@click.pass_context
def cli(ctx: click.Context, as_json: bool) -> None:
    """Funnel Package Manager (fpm) - Package manager for FunnelScript."""
    ctx.ensure_object(dict)
    ctx.obj["json"] = as_json


@cli.command()
@click.argument("name")
@click.option("--dir", "target_dir", default=".", help="Directory to initialize")
@click.pass_context
def init(ctx: click.Context, name: str, target_dir: str) -> None:
    """Scaffold a new FunnelScript package (fpm.toml, index.fnls, README.md, .gitignore)."""
    as_json = ctx.obj.get("json", False)
    root = Path(target_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)

    manifest_file = root / "fpm.toml"
    if manifest_file.exists():
        err = {"status": "error", "message": f"Manifest already exists at {manifest_file}"}
        _print_output(err, as_json, f"Error: {manifest_file} already exists.")
        sys.exit(1)

    try:
        meta = PackageMetadata(
            name=name,
            version="0.1.0",
            description=f"FunnelScript package {name}",
            license="MIT",
            funnelscript_version=">=0.4.0",
            entry="index.fnls",
        )
    except FpmError as e:
        _print_output(e.to_dict(), as_json, f"Error [{e.code}]: {e.message}")
        sys.exit(1)

    manifest = Manifest(package=meta, modules={"index": "index.fnls"})
    manifest.save_to_file(manifest_file)

    # index.fnls
    index_file = root / "index.fnls"
    if not index_file.exists():
        index_file.write_text(
            f'// FunnelScript Package: {name}\n// Entry module\n\nstrategy "{name.replace("/", "_")}" {{\n}}\n',
            encoding="utf-8",
        )

    # README.md
    readme_file = root / "README.md"
    if not readme_file.exists():
        readme_file.write_text(
            f"# {name}\n\nFunnelScript package initialized with `fpm`.\n",
            encoding="utf-8",
        )

    # .gitignore
    gitignore_file = root / ".gitignore"
    if not gitignore_file.exists():
        gitignore_file.write_text(".fpm/\ndist/\n*.tar.gz\n", encoding="utf-8")

    res = {
        "status": "success",
        "action": "init",
        "package": name,
        "files": ["fpm.toml", "index.fnls", "README.md", ".gitignore"],
        "path": str(root),
    }
    _print_output(res, as_json, f"Initialized new package '{name}' in {root}")


@cli.command()
@click.argument("package_spec")
@click.option("--path", "path_dep", default=None, help="Add local filesystem path dependency")
@click.option("--git", "git_url", default=None, help="Add git repository dependency")
@click.option("--rev", default=None, help="Git revision (tag, commit, branch)")
@click.option("--registry", default=None, help="Registry endpoint or local directory")
@click.pass_context
def add(
    ctx: click.Context,
    package_spec: str,
    path_dep: str | None,
    git_url: str | None,
    rev: str | None,
    registry: str | None,
) -> None:
    """Add a dependency to fpm.toml, resolve graph, and update fpm.lock."""
    as_json = ctx.obj.get("json", False)
    cwd = Path.cwd()
    manifest_file = cwd / "fpm.toml"
    if not manifest_file.exists():
        err = {"status": "error", "message": "No fpm.toml found in current directory."}
        _print_output(err, as_json, "Error: No fpm.toml found.")
        sys.exit(1)

    manifest = Manifest.load_from_file(manifest_file)

    # Parse spec
    if "@" in package_spec and not path_dep and not git_url:
        pkg_name, version_req = package_spec.split("@", 1)
        if not version_req.startswith(("^", "~", ">", "<", "=")):
            version_req = f"^{version_req}"
    else:
        pkg_name = package_spec
        version_req = "^0.1.0"

    if path_dep:
        manifest.dependencies[pkg_name] = PathDependency(path=path_dep)
    elif git_url:
        manifest.dependencies[pkg_name] = GitDependency(git=git_url, rev=rev)
    else:
        manifest.dependencies[pkg_name] = version_req

    manifest.save_to_file(manifest_file)

    # Trigger install/resolve
    _do_install(cwd, manifest, registry_url=registry, frozen=False, as_json=as_json)


@cli.command()
@click.argument("package_name")
@click.option("--registry", default=None, help="Registry endpoint or local directory")
@click.pass_context
def remove(ctx: click.Context, package_name: str, registry: str | None) -> None:
    """Remove a dependency from fpm.toml and regenerate lockfile."""
    as_json = ctx.obj.get("json", False)
    cwd = Path.cwd()
    manifest_file = cwd / "fpm.toml"
    if not manifest_file.exists():
        err = {"status": "error", "message": "No fpm.toml found in current directory."}
        _print_output(err, as_json, "Error: No fpm.toml found.")
        sys.exit(1)

    manifest = Manifest.load_from_file(manifest_file)
    if package_name not in manifest.dependencies:
        err = {"status": "error", "message": f"Dependency '{package_name}' not found in fpm.toml."}
        _print_output(err, as_json, f"Error: '{package_name}' is not listed in dependencies.")
        sys.exit(1)

    del manifest.dependencies[package_name]
    manifest.save_to_file(manifest_file)

    _do_install(cwd, manifest, registry_url=registry, frozen=False, as_json=as_json)


@cli.command()
@click.option("--frozen", is_flag=True, help="Enforce that lockfile is strictly up-to-date with manifest")
@click.option("--registry", default=None, help="Registry endpoint or local directory")
@click.pass_context
def install(ctx: click.Context, frozen: bool, registry: str | None) -> None:
    """Install all dependencies declared in fpm.toml and materialize .fpm/."""
    as_json = ctx.obj.get("json", False)
    cwd = Path.cwd()
    manifest_file = cwd / "fpm.toml"
    if not manifest_file.exists():
        err = {"status": "error", "message": "No fpm.toml found in current directory."}
        _print_output(err, as_json, "Error: No fpm.toml found.")
        sys.exit(1)

    manifest = Manifest.load_from_file(manifest_file)
    _do_install(cwd, manifest, registry_url=registry, frozen=frozen, as_json=as_json)


def _do_install(
    project_root: Path,
    manifest: Manifest,
    registry_url: str | None,
    frozen: bool,
    as_json: bool,
) -> None:
    lockfile_path = project_root / "fpm.lock"
    manifest_hash = manifest.compute_hash()

    if frozen:
        if not lockfile_path.exists():
            raise FrozenLockfileOutOfSyncError({"reason": "Missing fpm.lock"})
        lockfile = Lockfile.load_from_file(lockfile_path)
        if lockfile.manifest_hash != manifest_hash:
            raise FrozenLockfileOutOfSyncError(
                {
                    "lock_hash": lockfile.manifest_hash,
                    "current_hash": manifest_hash,
                }
            )

    # Resolve registry
    reg_src = (
        registry_url or os.environ.get("FPM_REGISTRY_URL") or (project_root / "tests" / "fixtures" / "mock_registry")
    )
    cache = GlobalCache()
    provider = StaticRegistryProvider(reg_src, cache=cache)
    current_engine = os.environ.get("FUNNELSCRIPT_VERSION", "0.4.0")
    resolver = DependencyResolver(provider, funnelscript_version=current_engine)

    try:
        resolved_nodes = resolver.resolve(manifest)
    except FpmError as err:
        _print_output(err.to_dict(), as_json, f"Error [{err.code}]: {err.message}")
        sys.exit(1)

    # Materialize packages into .fpm/packages/
    packages_dir = project_root / ".fpm" / "packages"
    packages_dir.mkdir(parents=True, exist_ok=True)

    locked_pkgs: dict[str, LockedPackage] = {}
    for name, node in resolved_nodes.items():
        dest_pkg = packages_dir / f"{name}@{node.version}"
        if node.local_dir:
            # Path dependency: copy or reference
            pass
        else:
            if not (dest_pkg / node.entry).exists():
                provider.install_package(name, node.version, dest_pkg)

        locked_pkgs[f"{name}@{node.version}"] = LockedPackage(
            name=name,
            version=node.version,
            resolved=node.resolved,
            integrity=node.integrity,
            entry=node.entry,
            dependencies=node.dependencies,
        )

    # Write lockfile
    lockfile = Lockfile(
        lockfile_version=1,
        manifest_hash=manifest_hash,
        packages=locked_pkgs,
    )
    lockfile.save_to_file(lockfile_path)

    # Write resolution map bridge
    map_file = write_resolution_map(project_root, resolved_nodes, packages_dir)

    res = {
        "status": "success",
        "action": "install",
        "packages_installed": len(resolved_nodes),
        "lockfile": str(lockfile_path),
        "resolution_map": str(map_file),
    }
    _print_output(res, as_json, f"Installed {len(resolved_nodes)} package(s). Generated {map_file.name}.")


@cli.command()
@click.pass_context
def verify(ctx: click.Context) -> None:
    """Verify integrity of installed packages in .fpm/packages/ against fpm.lock."""
    as_json = ctx.obj.get("json", False)
    cwd = Path.cwd()
    lockfile_path = cwd / "fpm.lock"
    if not lockfile_path.exists():
        err = {"status": "error", "message": "Missing fpm.lock. Run 'fpm install' first."}
        _print_output(err, as_json, "Error: Missing fpm.lock")
        sys.exit(1)

    lockfile = Lockfile.load_from_file(lockfile_path)
    packages_dir = cwd / ".fpm" / "packages"
    cache = GlobalCache()

    errors: list[dict[str, Any]] = []
    verified_count = 0

    for _pkg_key, locked in lockfile.packages.items():
        if locked.resolved.startswith("file://"):
            # Path dependency
            continue

        cached_tarball = cache.get_tarball(locked.integrity)
        pkg_install_dir = packages_dir / f"{locked.name}@{locked.version}"
        entry_file = pkg_install_dir / locked.entry

        if not entry_file.exists():
            errors.append(
                {
                    "package": locked.name,
                    "error": f"Entry file '{locked.entry}' missing in {pkg_install_dir}",
                    "code": "FPM-E401",
                }
            )
            continue

        # Check tarball integrity if available
        if cached_tarball:
            actual_digest = compute_file_sha256(cached_tarball)
            if actual_digest != locked.integrity:
                errors.append(
                    {
                        "package": locked.name,
                        "expected": locked.integrity,
                        "actual": actual_digest,
                        "code": "FPM-E401",
                    }
                )
                continue

        # Build in-memory hash of installed directory to detect tampering
        temp_tar = cwd / ".fpm" / "temp_verify.tar.gz"
        try:
            _, computed_hash = build_package_tarball(pkg_install_dir, temp_tar)
            temp_tar.unlink(missing_ok=True)
            if computed_hash != locked.integrity:
                errors.append(
                    {
                        "package": locked.name,
                        "expected": locked.integrity,
                        "actual": computed_hash,
                        "code": "FPM-E401",
                    }
                )
                continue
        except Exception as e:
            errors.append({"package": locked.name, "error": str(e), "code": "FPM-E401"})
            continue

        verified_count += 1

    if errors:
        err_report = {
            "status": "failed",
            "code": "FPM-E401",
            "message": "Integrity verification failed for one or more packages.",
            "errors": errors,
        }
        _print_output(err_report, as_json, f"Verification failed for {len(errors)} package(s).")
        sys.exit(1)

    res = {"status": "success", "verified_packages": verified_count}
    _print_output(res, as_json, f"Integrity verified for {verified_count} package(s). All hashes match.")


@cli.command()
@click.option("--out", default="dist", help="Output directory for tarball")
@click.pass_context
def pack(ctx: click.Context, out: str) -> None:
    """Build a deterministic .tar.gz archive of the current package."""
    as_json = ctx.obj.get("json", False)
    cwd = Path.cwd()
    try:
        audit = run_preflight_audit(cwd)
    except FpmError as err:
        _print_output(err.to_dict(), as_json, f"Error [{err.code}]: {err.message}")
        sys.exit(1)

    out_dir = cwd / out
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = Manifest.load_from_file(cwd / "fpm.toml")

    safe_name = manifest.name.replace("/", "-")
    tarball_file = out_dir / f"{safe_name}-{manifest.version}.tar.gz"
    _, digest = build_package_tarball(cwd, tarball_file)

    res = {
        "status": "success",
        "action": "pack",
        "package": manifest.name,
        "version": manifest.version,
        "tarball": str(tarball_file),
        "integrity": digest,
        "preflight": audit,
    }
    _print_output(res, as_json, f"Built package '{tarball_file.name}' (SHA-256: {digest})")


@cli.command()
@click.option("--dry-run", is_flag=True, default=True, help="Validate and simulate publish without mutating registry")
@click.option("--registry", default=None, help="Target registry URL")
@click.pass_context
def publish(ctx: click.Context, dry_run: bool, registry: str | None) -> None:
    """Publish the package to the FunnelScript package registry."""
    as_json = ctx.obj.get("json", False)
    cwd = Path.cwd()

    try:
        audit = run_preflight_audit(cwd)
    except FpmError as err:
        _print_output(err.to_dict(), as_json, f"Error [{err.code}]: {err.message}")
        sys.exit(1)

    # Optional compiler lint check
    compiler_report = run_compiler_check(cwd)

    # Deterministic tarball build
    dist_dir = cwd / ".fpm" / "publish_dist"
    manifest = Manifest.load_from_file(cwd / "fpm.toml")
    safe_name = manifest.name.replace("/", "-")
    tarball_path = dist_dir / f"{safe_name}-{manifest.version}.tar.gz"
    _, digest = build_package_tarball(cwd, tarball_path)

    res = {
        "status": "success",
        "action": "publish",
        "dry_run": dry_run,
        "package": manifest.name,
        "version": manifest.version,
        "integrity": digest,
        "registry": registry or "https://registry.funnelscript.org",
        "audit": audit,
        "compiler_check": compiler_report,
    }
    msg = (
        f"Publish pre-flight passed for '{manifest.name}@{manifest.version}'.\n"
        f"Tarball SHA-256: {digest}\n"
        f"Dry run complete. No remote registry mutated."
    )
    _print_output(res, as_json, msg)


@cli.command()
@click.pass_context
def graph(ctx: click.Context) -> None:
    """Print the resolved dependency tree for the current project."""
    as_json = ctx.obj.get("json", False)
    cwd = Path.cwd()
    lockfile_path = cwd / "fpm.lock"
    if not lockfile_path.exists():
        err = {"status": "error", "message": "Missing fpm.lock. Run 'fpm install' first."}
        _print_output(err, as_json, "Error: Missing fpm.lock")
        sys.exit(1)

    lockfile = Lockfile.load_from_file(lockfile_path)
    tree: dict[str, Any] = {}
    for pkg_key, locked in sorted(lockfile.packages.items()):
        tree[pkg_key] = {
            "version": locked.version,
            "resolved": locked.resolved,
            "dependencies": locked.dependencies,
        }

    if as_json:
        click.echo(json.dumps({"packages": tree}, indent=2))
    else:
        click.echo("Resolved Dependency Graph:")
        for pkg_key, info in tree.items():
            click.echo(f"  * {pkg_key} ({info['resolved']})")
            for dep_name, dep_ver in info["dependencies"].items():
                click.echo(f"      └─ {dep_name}: {dep_ver}")
