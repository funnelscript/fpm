"""End-to-end integration tests for fpm CLI workflows."""

import json
from pathlib import Path

from click.testing import CliRunner

from fpm.cli import cli


def test_cli_init_and_pack(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()

    # 1. fpm init
    res = runner.invoke(cli, ["init", "agency/custom_funnel"])
    assert res.exit_code == 0
    assert "Initialized new package" in res.output
    assert (tmp_path / "fpm.toml").exists()
    assert (tmp_path / "index.fnls").exists()
    assert (tmp_path / "README.md").exists()
    assert (tmp_path / ".gitignore").exists()

    # 2. fpm pack
    dist_dir = tmp_path / "dist"
    res_pack = runner.invoke(cli, ["pack", "--out", "dist"])
    assert res_pack.exit_code == 0
    assert "Built package" in res_pack.output
    assert (dist_dir / "agency-custom_funnel-0.1.0.tar.gz").exists()

    # 3. fpm publish --dry-run
    res_pub = runner.invoke(cli, ["publish", "--dry-run"])
    assert res_pub.exit_code == 0
    assert "Publish pre-flight passed" in res_pub.output


def test_cli_consumer_flow_and_tamper_detection(tmp_path: Path, monkeypatch):
    runner = CliRunner()
    repo_root = Path(__file__).parent.parent
    mock_registry = repo_root / "tests" / "fixtures" / "mock_registry"

    project_dir = tmp_path / "consumer_project"
    project_dir.mkdir()
    monkeypatch.chdir(project_dir)

    # Initialize consumer project
    res_init = runner.invoke(cli, ["init", "consumer/app"])
    assert res_init.exit_code == 0

    # Add dependency from mock registry
    res_add = runner.invoke(
        cli,
        ["add", "ecommerce/d2c_scale@0.1.0", "--registry", str(mock_registry)],
    )
    assert res_add.exit_code == 0
    assert (project_dir / "fpm.lock").exists()
    assert (project_dir / ".fpm" / "resolution-map.json").exists()

    # Verify resolution map contents
    res_map = json.loads((project_dir / ".fpm" / "resolution-map.json").read_text())
    assert "ecommerce/d2c_scale" in res_map["packages"]
    assert Path(res_map["packages"]["ecommerce/d2c_scale"]["entry"]).exists()

    # fpm graph
    res_graph = runner.invoke(cli, ["graph"])
    assert res_graph.exit_code == 0
    assert "ecommerce/d2c_scale@0.1.0" in res_graph.output

    # fpm install --frozen
    res_install = runner.invoke(
        cli,
        ["install", "--frozen", "--registry", str(mock_registry)],
    )
    assert res_install.exit_code == 0

    # fpm verify (clean state)
    res_verify = runner.invoke(cli, ["verify"])
    assert res_verify.exit_code == 0
    assert "Integrity verified" in res_verify.output

    # Tamper detection: modify a file in .fpm/packages/
    installed_entry = Path(res_map["packages"]["ecommerce/d2c_scale"]["entry"])
    installed_entry.write_text("// TAMPERED CONTENT\n", encoding="utf-8")

    res_tampered = runner.invoke(cli, ["verify"])
    assert res_tampered.exit_code != 0
    assert "Verification failed" in res_tampered.output or "failed" in res_tampered.output.lower()
