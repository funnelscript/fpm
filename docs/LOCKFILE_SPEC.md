# Funnel Package Manager (`fpm.lock`) Deterministic Lockfile Specification

## 1. Overview

`fpm.lock` records the exact, deterministic dependency resolution graph for a FunnelScript project. It guarantees:
1. **Byte-for-byte reproducibility**: The same resolution produces identical JSON output across operating systems (canonical key sorting, 2-space indentation, unix line endings `\n`).
2. **Cryptographic integrity**: Every package is pinned with a SHA-256 digest (`integrity = "sha256-..."`).
3. **Offline verification**: With a lockfile present, `fpm install --frozen` installs packages without network queries, and `fpm verify` audits installed files against recorded digests.

---

## 2. Lockfile Schema (`fpm.lock`)

```json
{
  "lockfile_version": 1,
  "manifest_hash": "sha256-0123456789abcdef...",
  "packages": {
    "ecommerce/d2c_scale@0.1.0": {
      "name": "ecommerce/d2c_scale",
      "version": "0.1.0",
      "resolved": "https://registry.funnelscript.org/tarballs/ecommerce/d2c_scale-0.1.0.tar.gz",
      "integrity": "sha256-d7a8fbb56e13b0a04718534839cf1396b29f0e132952541a73dd708535a7b0a7",
      "entry": "index.fnl",
      "dependencies": {}
    }
  }
}
```

### Fields:
- **`lockfile_version`** *(int)*: Always `1` for the initial standard.
- **`manifest_hash`** *(string)*: SHA-256 hash of `fpm.toml` at the time of resolution. Used by `--frozen` to detect drift.
- **`packages`** *(dict)*: Map of `<scoped_name>@<version>` to `LockedPackage`:
  - `name`: Scoped name of the package.
  - `version`: Exact resolved SemVer.
  - `resolved`: Source URL, relative path, or git URI.
  - `integrity`: SHA-256 hash prefixed with `sha256-`. For path dependencies, it represents the recursive content hash of package files.
  - `entry`: Relative path to main `.fnl` file.
  - `dependencies`: Direct dependencies of this resolved package (`name` -> `constraint`).

---

## 3. Determinism Invariants

To achieve byte-for-byte identical output:
1. All JSON keys are sorted alphabetically at every nesting level.
2. The package dictionary keys are sorted alphabetically.
3. Indentation is strictly 2 spaces, with no trailing whitespace.
4. Line endings are strictly LF (`\n`).
5. Numbers are serialized without exponential notation or floating-point variance.

---

## 4. Diagnostics & Error Codes
- `FPM-E401`: Integrity verification failed (SHA-256 mismatch or file tampered).
- `FPM-E402`: Frozen lockfile out of sync with `fpm.toml` (run `fpm install` without `--frozen` to update).
