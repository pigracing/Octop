"""tests/unit/test_release_download_links.py"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _REPO_ROOT / "scripts" / "release_download_links.py"
_BRANDING_CONFIG = _REPO_ROOT / "desktop" / "branding.json"


def _load():
    spec = importlib.util.spec_from_file_location("release_download_links", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_split_tag_accepts_with_or_without_v() -> None:
    mod = _load()
    assert mod.split_tag("0.9.31") == ("v0.9.31", "0.9.31")
    assert mod.split_tag("v0.9.31") == ("v0.9.31", "0.9.31")


def test_configured_app_name_reads_branding_json() -> None:
    mod = _load()
    config = json.loads(_BRANDING_CONFIG.read_text(encoding="utf-8"))
    assert mod.configured_app_name() == config["display_name"].strip()


def test_render_download_section_matches_github_asset_names() -> None:
    mod = _load()
    prefix = mod.configured_app_name()
    body = mod.render_download_section("0.9.31")
    base = "https://github.com/TencentCloud/Octop/releases/download/v0.9.31"
    assert f"{base}/{prefix}-desktop-windows-amd64-0.9.31.exe" in body
    assert f"{base}/{prefix}-desktop-windows-arm64-0.9.31.exe" in body
    assert f"{base}/{prefix}-portable-windows-amd64-0.9.31.zip" in body
    assert f"{base}/{prefix}-portable-windows-arm64-0.9.31.zip" in body
    assert f"{base}/{prefix}-desktop-darwin-arm64-0.9.31.dmg" in body
    assert f"{base}/{prefix}-desktop-darwin-amd64-0.9.31.dmg" in body
    assert f"{base}/{prefix}-portable-darwin-arm64-0.9.31.zip" in body
    assert f"{base}/{prefix}-portable-darwin-amd64-0.9.31.zip" in body
    assert f"{base}/{prefix}-desktop-linux-amd64-0.9.31.tar.gz" in body
    assert f"{base}/{prefix}-desktop-linux-arm64-0.9.31.tar.gz" in body
    assert f"{base}/{prefix}-portable-linux-amd64-0.9.31.zip" in body
    assert f"{base}/{prefix}-portable-linux-arm64-0.9.31.zip" in body
    assert f"{base}/Octop-fnos-docker-0.9.31.fpk" in body
    assert f"{base}/Octop-fnos-native-0.9.31.fpk" in body
    assert f"{base}/Octop-fnos-native-arm64-0.9.31.fpk" in body
    assert "Docker (recommended; x86 and ARM)" in body
    assert "Native x86_64" in body
    assert "Native ARM64 (no Docker)" in body
    assert "pip install" not in body
    assert "## Downloads" in body


def test_render_download_section_accepts_explicit_app_name() -> None:
    mod = _load()
    body = mod.render_download_section("0.9.31", app_name="Octop")
    assert "Octop-desktop-windows-amd64-0.9.31.exe" in body
    assert "Octop-portable-linux-arm64-0.9.31.zip" in body
