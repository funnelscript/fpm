# FunnelScript Registry Protocol (`fpm` Registry)

## 1. Overview

The FunnelScript package registry follows a **static index + content-addressed tarball protocol**. It requires zero dynamic backend servers and can be hosted entirely on **GitHub Pages**, AWS S3, Cloudflare R2, or any static HTTP CDN.

---

## 2. Directory Layout of Static Registry

A registry endpoint (e.g. `https://registry.funnelscript.org` or `https://username.github.io/fpm-registry`) serves the following structure:

```text
registry-root/
├── index/
│   ├── ecommerce/
│   │   └── d2c_scale.json
│   └── leadgen/
│       └── sales_capacity.json
└── tarballs/
    ├── ecommerce/
    │   └── d2c_scale-0.1.0.tar.gz
    └── leadgen/
        └── sales_capacity-0.1.0.tar.gz
```

### 2.1 Package Index File (`index/<scope>/<name>.json`)
Each package has a single JSON metadata file listing all published versions:
```json
{
  "name": "ecommerce/d2c_scale",
  "description": "Flagship FunnelScript D2C scale strategy with dual Prepaid & COD payment channels",
  "latest": "0.1.0",
  "versions": {
    "0.1.0": {
      "version": "0.1.0",
      "tarball_url": "tarballs/ecommerce/d2c_scale-0.1.0.tar.gz",
      "integrity": "sha256-d7a8fbb56e13b0a04718534839cf1396b29f0e132952541a73dd708535a7b0a7",
      "funnelscript_version": ">=0.4.0",
      "dependencies": {},
      "entry": "index.fnl",
      "published_at": "2026-11-21T12:00:00Z"
    }
  }
}
```

---

## 3. GitHub Pages Architecture (Zero-Server Registry)

Using a standalone GitHub Pages repository for the public FunnelScript package registry provides massive operational benefits:
1. **Zero Infrastructure Cost**: No servers, no database, no maintenance.
2. **Global CDN Distribution**: Fast downloads via GitHub's global edge network.
3. **Transparent Audit Trail**: Every package release is backed by a Git commit in the registry index.
4. **GitHub Releases for Large Tarballs**: Tarballs can be attached as GitHub Release assets or stored directly in the repository via Git LFS / standard git commits under `tarballs/`.

---

## 4. Packaging Format (`fpm pack`)

Package tarballs are `.tar.gz` archives built with deterministic settings:
- Entry filenames sorted in alphabetical order.
- Normalized file permissions (`0o755` for directories, `0o644` for files).
- Normalized timestamps (`mtime` set to `1700000000`).
- User and group ownership set to root (`uid=0`, `gid=0`, `uname=""`, `gname=""`).
- Exclusion of `.git`, `.venv`, `.DS_Store`, `__pycache__`, and tests.

---

## 5. Publishing Validation (`fpm publish --dry-run`)

Before a package can be accepted by the registry, `fpm` performs:
1. Manifest validity check (`fpm.toml`).
2. Verification that `README.md` and `LICENSE` exist and are non-empty.
3. Verification that `index.fnl` exists and parses cleanly.
4. Export check ensuring every symbol mapped in `[modules]` / `[exports]` exists.
5. Parameter validation ensuring numeric defaults lie within declared `[min, max]` intervals.
6. Deterministic packaging and output of the exact SHA-256 integrity hash.
