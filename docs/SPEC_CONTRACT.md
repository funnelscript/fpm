# Funnel Package Manager (`fpm`) & FunnelScript Runtime Contract

## 1. Architectural Mission & Boundary Isolation

`fpm` is the official package manager, lockfile resolver, and registry client for the **FunnelScript** marketing programming language.

### Boundary Invariant
To prevent tight coupling and synchronization debt between repositories:
- `fpm` owns **package lifecycle**: dependency declarations (`fpm.toml`), lockfiles (`fpm.lock`), SemVer resolution, integrity verification (SHA-256), global package caching, package installation into `.fpm/packages/`, and emitting `.fpm/resolution-map.json`.
- `fpm` does **NOT** compile, parse, or execute `.fnls` files.
- `funnelscript` compiler owns **execution and evaluation**: AST parsing, dimensional verification, DEVS discrete event simulation, and runtime execution.
- `funnelscript` does **NOT** parse `fpm.toml`, compute SemVer, or connect to package registries. It only consumes `.fpm/resolution-map.json` to resolve imports to disk paths.

---

## 2. Reconciled Manifest Contract (`fpm.toml`)

In early conceptual designs (`docs/fpm.md` in the core language repo), JSON manifests (`funnelscript.json`) were sketched. Production implementations adopt **TOML** (`fpm.toml`) for readability, comments, and strict alignment with the existing flagship packages (`ecommerce/d2c_scale` and `leadgen/sales_capacity`).

### Canonical Sections in `fpm.toml`:
1. `[package]`:
   - `name`: String, matching `^[a-z0-9-]+/[a-z0-9_]+$` (e.g. `ecommerce/d2c_scale`).
   - `version`: Strict SemVer 2.0 string (e.g. `0.1.0`).
   - `description`: String.
   - `license`: SPDX license identifier string (e.g. `MIT`).
   - `author`: String (e.g. `FunnelScript Core Team <core@funnelscript.org>`).
   - `funnelscript_version`: SemVer range constraint (e.g. `>=0.4.0,<1.0.0`).
   - `entry`: Relative path to main `.fnls` file (defaults to `index.fnls`; legacy `main` is accepted as an alias).
2. `[modules]` / `[exports]`:
   - Mapping of export alias to relative `.fnls` file path.
   - Example:
     ```toml
     [modules]
     acquisition = "acquisition.fnls"
     fulfillment = "fulfillment.fnls"
     treasury = "treasury.fnls"
     index = "index.fnls"
     ```
3. `[parameters.<name>]`:
   - Declarative parameter metadata for simulation tuning and registry documentation:
     - `type`: `"float" | "int" | "str" | "bool"`
     - `dimension`: `"Currency" | "Scalar" | "Ratio" | "Duration" | "Count" | "Boolean"`
     - `unit`: Optional unit string (`"USD"`, `"days"`, `"minutes"`)
     - `default`: Numeric/value default matching type
     - `min`: Optional lower bound
     - `max`: Optional upper bound
     - `description`: Parameter explanation
4. `[metrics.<name>]`:
   - Declarative simulation outputs:
     - `dimension`: Metric dimension string
     - `unit`: Optional unit string
     - `description`: Metric explanation
5. `[dependencies]`:
   - Direct package dependencies. Supported forms:
     - SemVer range: `ecommerce/d2c_scale = "^0.1.0"`
     - Relative path: `leadgen/sales_capacity = { path = "../leadgen/sales_capacity" }`
     - Pinned Git: `agency/b2b = { git = "https://github.com/org/b2b.git", rev = "v1.2.0" }`

---

## 3. The Runtime Bridge: `.fpm/resolution-map.json`

When `fpm install` runs in a FunnelScript project, it:
1. Resolves all direct and transitive dependencies deterministically.
2. Materializes or symlinks packages into `.fpm/packages/<scope>/<name>@<version>/`.
3. Verifies SHA-256 integrity against `fpm.lock`.
4. Writes the bridge artifact: `.fpm/resolution-map.json`.

### Schema of `.fpm/resolution-map.json`:
```json
{
  "schema_version": "1.0.0",
  "generated_at": "2026-11-21T15:00:00Z",
  "funnelscript_version_target": ">=0.4.0",
  "packages": {
    "ecommerce/d2c_scale": {
      "version": "0.1.0",
      "entry": "/project/.fpm/packages/ecommerce/d2c_scale@0.1.0/index.fnls",
      "integrity": "sha256-a1b2c3d4...",
      "modules": {
        "acquisition": "/project/.fpm/packages/ecommerce/d2c_scale@0.1.0/acquisition.fnls",
        "fulfillment": "/project/.fpm/packages/ecommerce/d2c_scale@0.1.0/fulfillment.fnls",
        "treasury": "/project/.fpm/packages/ecommerce/d2c_scale@0.1.0/treasury.fnls",
        "index": "/project/.fpm/packages/ecommerce/d2c_scale@0.1.0/index.fnls"
      }
    }
  }
}
```

### FunnelScript Import Resolution (10-Line Integration):
In the FunnelScript compiler/resolver:
```python
import json
from pathlib import Path


def resolve_package_import(project_root: Path, import_spec: str) -> Path:
    map_path = project_root / ".fpm" / "resolution-map.json"
    if not map_path.exists():
        raise FileNotFoundError("Missing .fpm/resolution-map.json. Run 'fpm install' first.")
    res_map = json.loads(map_path.read_text(encoding="utf-8"))
    parts = import_spec.split("/", 2)  # e.g. "ecommerce/d2c_scale/treasury" or "ecommerce/d2c_scale"
    pkg_key = f"{parts[0]}/{parts[1]}" if len(parts) >= 2 else parts[0]
    pkg_info = res_map["packages"].get(pkg_key)
    if not pkg_info:
        raise ModuleNotFoundError(f"Package '{pkg_key}' not found in .fpm/resolution-map.json")
    if len(parts) == 3:
        return Path(pkg_info["modules"][parts[2]])
    return Path(pkg_info["entry"])
```
