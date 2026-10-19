"""tests/unit/i18n/test_catalog.py"""

from __future__ import annotations

import pytest

from octop.i18n import all_keys_for_locale, tr
from octop.i18n.loader import product_name
from octop.infra.gateway.slash.catalog import CATALOG, category_label


def test_en_and_zh_share_same_keys():
    en_keys = all_keys_for_locale("en")
    zh_keys = all_keys_for_locale("zh")
    assert en_keys == zh_keys
    assert "errors.AGENT_NAME_TAKEN" in en_keys


def test_tr_fallback_to_en():
    assert tr("slash.help.title", "en") == "Available commands"
    assert tr("slash.help.title", "zh") == "可用指令"


def test_tr_interpolation():
    text = tr("slash.error.unknown_command", "en", name="foo")
    assert "/foo" in text


def test_tr_missing_key_raises():
    with pytest.raises(KeyError):
        tr("slash.no.such.key", "en")


def test_tr_uses_desktop_display_name(monkeypatch):
    monkeypatch.setenv("OCTOP_DISPLAY_NAME", "GoalPartner")
    text = tr("errors.CONNECTOR_OAUTH_HTTPS_REQUIRED", "en")
    assert text.startswith("GoalPartner ")
    assert "Octop" not in text


def test_product_name_env_override(monkeypatch):
    monkeypatch.setenv("OCTOP_DISPLAY_NAME", "GoalPartner")
    assert product_name() == "GoalPartner"
    monkeypatch.delenv("OCTOP_DISPLAY_NAME")
    assert product_name() == "Octop"


def test_catalog_labels_match_json():
    for spec in CATALOG:
        assert spec.label_en == tr(f"slash.catalog.{spec.name}.label", "en")
        assert spec.label_zh == tr(f"slash.catalog.{spec.name}.label", "zh")


def test_category_labels():
    assert category_label("core", "en") == "Core"
    assert category_label("core", "zh") == "核心命令"
