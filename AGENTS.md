# AGENTS.md — AI Agent Operating Constitution for `fpm`

> Operating rules, architectural boundaries, and coding standards for all AI agents working on the Funnel Package Manager (`fpm`) repository.

---

## 1. Architectural Mission & Invariants

1. **Strict Boundary Isolation**:
   - `fpm` owns package manifest validation (`fpm.toml`), deterministic lockfile resolution (`fpm.lock`), SemVer 2.0 evaluation, content-addressed tarball storage, cryptographic verification (SHA-256), and emitting `.fpm/resolution-map.json`.
   - `fpm` must **never** duplicate the FunnelScript parser, AST structures, dimensional checker, or DEVS simulator.
   - When package `.fnls` validation is required, `fpm` interfaces via `fpm.validator.compiler_hook` by invoking the external `funnelscript` executable.

2. **Zero-Drift Schema Standard**:
   - All models live in `src/fpm/models/` using Pydantic v2.
   - Any modification to manifest, lockfile, or registry index models must be followed by exporting the updated JSON schemas in `schemas/` with zero drift.

3. **Deterministic Reproducibility**:
   - `fpm.lock` must be serialized with sorted keys, 2-space indentation, and unix line endings (`\n`).
   - Packaged tarballs (`.tar.gz`) must normalize file permissions (`0o644`/`0o755`), ownership (`uid=0`, `gid=0`), and timestamps (`mtime=1700000000`).

---

## 2. Toolchain & Quality Gates

- **Language Runtime**: Python 3.11+
- **Package Manager**: Strictly `uv` (`pyproject.toml` + `uv.lock`). Do not use `pip` directly.
- **Linting & Formatting**: `uv run ruff check .` and `uv run ruff format --check .` must pass with zero errors.
- **Testing**: `uv run pytest -v` must pass 100%. All tests must be 100% offline-testable with mock registry fixtures.
- **Property-Based Testing**: Use Hypothesis for mathematical and DAG properties (transitivity, idempotency, cycle freedom).

---

## 3. Diagnostic Error Code Matrix

All user-facing errors must subclass `FpmError` and report a structured diagnostic code:

| Code Range | Subsystem | Examples |
|---|---|---|
| `FPM-E1xx` | Manifest & Schema | `FPM-E101` (Syntax), `FPM-E102` (Name), `FPM-E103` (SemVer), `FPM-E105` (Bounds) |
| `FPM-E2xx` | Resolver & Graph | `FPM-E201` (Cycle), `FPM-E202` (Conflict), `FPM-E203` (Engine mismatch) |
| `FPM-E3xx` | Fetcher & Registry | `FPM-E301` (Package not found), `FPM-E302` (Fetch failure) |
| `FPM-E4xx` | Integrity & Lockfile | `FPM-E401` (Hash mismatch / tampering), `FPM-E402` (Frozen out of sync) |
| `FPM-E5xx` | Packager & Pre-flight | `FPM-E501` (Missing required file), `FPM-E502` (Missing export) |
