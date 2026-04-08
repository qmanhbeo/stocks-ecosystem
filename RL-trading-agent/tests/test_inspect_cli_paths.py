from __future__ import annotations

import sys
from pathlib import Path

from vn_stock_rl.data_tools import inspect_fx_commodities, inspect_stock


def test_inspect_stock_joins_data_dir_without_trailing_slash(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, str] = {}

    def fake_inspect_file(file_path: str) -> bool:
        captured["path"] = file_path
        return True

    monkeypatch.setattr(inspect_stock, "inspect_file", fake_inspect_file)
    monkeypatch.setattr(
        sys,
        "argv",
        ["inspect_stock", "--ticker", "acb", "--data-dir", str(tmp_path / "stock")],
    )

    assert inspect_stock.main() == 0
    assert captured["path"] == str(tmp_path / "stock" / "gia_lich_su_ACB_1D.parquet")


def test_inspect_fx_commodities_joins_data_dir_without_trailing_slash(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, str] = {}

    def fake_inspect_file(file_path: str) -> bool:
        captured["path"] = file_path
        return True

    monkeypatch.setattr(inspect_fx_commodities, "inspect_file", fake_inspect_file)
    monkeypatch.setattr(
        sys,
        "argv",
        ["inspect_fx_commodities", "--ticker", "GC=F", "--data-dir", str(tmp_path / "fx")],
    )

    assert inspect_fx_commodities.main() == 0
    assert captured["path"] == str(tmp_path / "fx" / "fx_commodities_gold_1d.parquet")
