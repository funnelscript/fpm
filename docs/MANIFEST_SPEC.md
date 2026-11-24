# Funnel Package Manager (`fpm.toml`) Manifest Specification

## 1. Overview

`fpm.toml` is the declarative package manifest for FunnelScript libraries and projects. Every package published or consumed by `fpm` must contain a valid `fpm.toml` in its root directory.

---

## 2. Specification Fields

### 2.1 `[package]`
- **`name`** *(required, string)*: Scoped package identifier matching `^[a-z0-9-]+/[a-z0-9_]+$`. Example: `ecommerce/d2c_scale`.
- **`version`** *(required, string)*: Strict SemVer 2.0 version. Example: `0.1.0`.
- **`description`** *(required, string)*: Brief description of the package capability.
- **`license`** *(required, string)*: SPDX license identifier (e.g. `MIT`, `Apache-2.0`).
- **`author`** *(optional, string)*: Author contact info (e.g. `FunnelScript Core Team <core@funnelscript.org>`).
- **`funnelscript_version`** *(required, string)*: SemVer constraint for compatible FunnelScript language versions (e.g. `>=0.4.0,<1.0.0`).
- **`entry`** *(optional, string)*: Path to the main entry point file. Defaults to `index.fnls`. `main` is accepted as an alias.

### 2.2 `[modules]` / `[exports]`
Mapping of symbol or submodule names to their `.fnls` file paths relative to the package root.
```toml
[modules]
acquisition = "acquisition.fnls"
fulfillment = "fulfillment.fnls"
treasury = "treasury.fnls"
index = "index.fnls"
```

### 2.3 `[parameters.<name>]`
Declarative parameters for simulation tuning and registry discovery.
- **`type`** *(required)*: `"float"` | `"int"` | `"str"` | `"bool"`
- **`dimension`** *(required)*: `"Currency"` | `"Scalar"` | `"Ratio"` | `"Duration"` | `"Count"` | `"Boolean"`
- **`unit`** *(optional)*: `"USD"` | `"EUR"` | `"days"` | `"minutes"` | etc.
- **`default`** *(required)*: Default value matching `type`.
- **`min`** *(optional)*: Minimum allowed numeric bound.
- **`max`** *(optional)*: Maximum allowed numeric bound.
- **`description`** *(required)*: Explanation of the parameter.

Validation invariant: For numeric parameters with bounds, `min <= default <= max` must hold strictly.

### 2.4 `[metrics.<name>]`
Declarative outputs produced by the package's FunnelScript models:
- **`dimension`** *(required)*: Dimension name.
- **`unit`** *(optional)*: Output unit.
- **`description`** *(required)*: Explanation of the metric.

### 2.5 `[dependencies]`
Table of package dependencies.
- **SemVer registry dependency**: `scope/pkg = "^1.0.0"`
- **Path dependency**: `scope/pkg = { path = "../relative/path" }`
- **Git dependency**: `scope/pkg = { git = "https://github.com/org/repo.git", rev = "v1.0.0" }`

---

## 3. Diagnostics & Error Codes
- `FPM-E101`: Manifest syntax or parsing error.
- `FPM-E102`: Invalid package name schema (must match `^[a-z0-9-]+/[a-z0-9_]+$`).
- `FPM-E103`: Invalid SemVer 2.0 version string.
- `FPM-E104`: Missing required manifest fields.
- `FPM-E105`: Invalid parameter bounds (`min > default` or `default > max`).
