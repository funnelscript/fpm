# Funnel Package Manager (`fpm`)

The official package manager, lockfile resolver, and registry client for the **FunnelScript** marketing programming language.

```
                          ┌───────────────────────────────┐
                          │     fpm Registry (Static)     │
                          │   (GitHub Pages / Fastly CDN) │
                          └───────────────┬───────────────┘
                                          │
                                   fpm add / install
                                          │
                                          ▼
                            ┌───────────────────────────┐
                            │    .fpm/packages/...      │
                            │   (SHA-256 Verified)      │
                            └─────────────┬─────────────┘
                                          │
                                     writes bridge
                                          │
                                          ▼
                         ┌─────────────────────────────────┐
                         │   .fpm/resolution-map.json      │
                         └────────────────┬────────────────┘
                                          │
                                  reads map directly
                                          │
                                          ▼
                      ┌───────────────────────────────────────┐
                      │         FunnelScript Compiler         │
                      │  (Zero TOML / SemVer / Network Deps)  │
                      └───────────────────────────────────────┘
```

---

## 1. Quickstart

### Installation
`fpm` is managed via Python 3.11+ and `uv`:
```bash
# In the fpm repository
uv sync
source .venv/bin/activate
fpm --help
```

### Core Commands
```bash
# 1. Initialize a new FunnelScript package
fpm init agency/custom_funnel

# 2. Add dependencies from registry, path, or git
fpm add ecommerce/d2c_scale@0.1.0
fpm add leadgen/sales_capacity --path ../leadgen/sales_capacity
fpm add partner/retention --git https://github.com/org/retention.git --rev v1.0.0

# 3. Deterministic installation (mandatory in CI)
fpm install --frozen

# 4. Cryptographic integrity audit & tamper detection
fpm verify

# 5. Build deterministic distribution tarball
fpm pack --out dist/

# 6. Pre-flight publishing verification (dry-run)
fpm publish --dry-run

# 7. Print resolved dependency DAG
fpm graph
```

---

## 2. FunnelScript Compiler Integration (10-Line Bridge)

The FunnelScript compiler and runtime do **not** need to parse `fpm.toml`, compute SemVer graphs, or connect to networks. `fpm install` materializes all verified packages into `.fpm/packages/` and writes `.fpm/resolution-map.json`.

Add this exact snippet to the FunnelScript import resolver:

```python
import json
from pathlib import Path

def resolve_package_import(project_root: Path, import_spec: str) -> Path:
    map_file = project_root / ".fpm" / "resolution-map.json"
    if not map_file.exists():
        raise FileNotFoundError("Missing .fpm/resolution-map.json. Run 'fpm install' first.")
    res_map = json.loads(map_file.read_text(encoding="utf-8"))
    parts = import_spec.split("/", 2)  # e.g. "ecommerce/d2c_scale/treasury" or "ecommerce/d2c_scale"
    pkg_key = f"{parts[0]}/{parts[1]}" if len(parts) >= 2 else parts[0]
    pkg_info = res_map["packages"].get(pkg_key)
    if not pkg_info:
        raise ModuleNotFoundError(f"Package '{pkg_key}' not found in .fpm/resolution-map.json")
    if len(parts) == 3:
        return Path(pkg_info["modules"][parts[2]])
    return Path(pkg_info["entry"])
```

---

## 3. Specifications & Architecture

- **[Specification Contract](docs/SPEC_CONTRACT.md)**: Exact architectural boundary between `fpm` and `funnelscript`.
- **[Manifest Specification (`fpm.toml`)](docs/MANIFEST_SPEC.md)**: Format, parameters, metrics, and schema definitions.
- **[Lockfile Specification (`fpm.lock`)](docs/LOCKFILE_SPEC.md)**: Deterministic canonical JSON and SHA-256 digest format.
- **[Registry Protocol](docs/REGISTRY_PROTOCOL.md)**: Static index + content-addressed tarball architecture for GitHub Pages.

---

## 4. Development & Testing

```bash
# Run full pytest & Hypothesis property-based suite
uv run pytest -v

# Run code formatting and linting
uv run ruff check .
uv run ruff format --check .
```
