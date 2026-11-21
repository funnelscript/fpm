"""Optional subprocess/adapter hook to run FunnelScript compiler validation."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

from fpm.errors import CompilerLintError


def run_compiler_check(
    package_dir: Path,
    strict: bool = False,
) -> dict[str, Any]:
    funnelscript_bin = shutil.which("funnelscript")
    if not funnelscript_bin:
        return {
            "status": "skipped",
            "reason": "funnelscript CLI executable not found on PATH",
        }

    cmd = [funnelscript_bin, "check", str(package_dir)]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        if proc.returncode != 0 and strict:
            raise CompilerLintError(proc.stderr or proc.stdout)
        return {
            "status": "passed" if proc.returncode == 0 else "warning",
            "exit_code": proc.returncode,
            "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip(),
        }
    except Exception as err:
        if strict:
            raise CompilerLintError(str(err)) from err
        return {
            "status": "skipped",
            "reason": f"Execution failed: {err}",
        }
