from __future__ import annotations

import cli


def test_backtest_dispatch(monkeypatch):
    called = {}

    def fake(module_name, script_name, args):
        called["value"] = (module_name, script_name, args)
        return 0

    monkeypatch.setattr(cli, "_run_module_main", fake)
    rc = cli.main(["backtest", "--", "--strategy", "s1_top5_rebal10"])
    assert rc == 0
    assert called["value"] == ("run_backtest", "run_backtest.py", ["--strategy", "s1_top5_rebal10"])


def test_cache_build_price_dispatch(monkeypatch):
    called = {}

    def fake(module_name, script_name, args):
        called["value"] = (module_name, script_name, args)
        return 0

    monkeypatch.setattr(cli, "_run_module_as_script", fake)
    rc = cli.main(["cache", "build-price"])
    assert rc == 0
    assert called["value"] == ("build_cache", "build_cache.py", [])


def test_analyze_trade_level_dispatch(monkeypatch):
    called = {}

    def fake(module_name, script_name, args):
        called["value"] = (module_name, script_name, args)
        return 0

    monkeypatch.setattr(cli, "_run_module_main", fake)
    rc = cli.main(["analyze", "trade-level", "--", "--start-date", "2025-01-01"])
    assert rc == 0
    assert called["value"] == (
        "analyze_trade_level_regimes",
        "analyze_trade_level_regimes.py",
        ["--start-date", "2025-01-01"],
    )


def test_utility_depth_frontier_dispatch(monkeypatch):
    called = {}

    def fake(file_name, script_name, args):
        called["value"] = (file_name, script_name, args)
        return 0

    monkeypatch.setattr(cli, "_run_file_as_script", fake)
    rc = cli.main(["utility", "depth-frontier-wfv"])
    assert rc == 0
    assert called["value"] == (
        "run_depth_frontier_walkforward.py",
        "run_depth_frontier_walkforward.py",
        [],
    )
