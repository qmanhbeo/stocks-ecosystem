#!/usr/bin/env python3
"""Unified CLI for heuristic-trader."""

from __future__ import annotations

import argparse
import importlib
from contextlib import contextmanager
from pathlib import Path
import runpy
import sys


ROOT = Path(__file__).resolve().parent


@contextmanager
def _patched_argv(argv0: str, args: list[str]):
    old_argv = sys.argv[:]
    sys.argv = [argv0, *args]
    try:
        yield
    finally:
        sys.argv = old_argv


def _coerce_exit_code(value: object) -> int:
    if value is None:
        return 0
    try:
        return int(value)
    except Exception:
        return 1


def _run_module_main(module_name: str, script_name: str, args: list[str]) -> int:
    module = importlib.import_module(module_name)
    if not hasattr(module, "main"):
        raise RuntimeError(f"Module {module_name} has no main()")
    try:
        with _patched_argv(script_name, args):
            result = module.main()
    except SystemExit as exc:
        return _coerce_exit_code(exc.code)
    return _coerce_exit_code(result)


def _run_module_as_script(module_name: str, script_name: str, args: list[str]) -> int:
    try:
        with _patched_argv(script_name, args):
            runpy.run_module(module_name, run_name="__main__")
    except SystemExit as exc:
        return _coerce_exit_code(exc.code)
    return 0


def _run_file_as_script(file_name: str, script_name: str, args: list[str]) -> int:
    path = ROOT / file_name
    if not path.exists():
        raise FileNotFoundError(f"Script file not found: {path}")
    try:
        with _patched_argv(script_name, args):
            runpy.run_path(str(path), run_name="__main__")
    except SystemExit as exc:
        return _coerce_exit_code(exc.code)
    return 0


def _add_passthrough(subparser: argparse.ArgumentParser, help_text: str) -> None:
    subparser.add_argument(
        "script_args",
        nargs=argparse.REMAINDER,
        help=help_text,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Unified heuristic-trader CLI",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Core execution pipeline
    p_backtest = subparsers.add_parser("backtest", help="Run backtest pipeline")
    _add_passthrough(p_backtest, "Arguments forwarded to run_backtest.py")

    p_wfv = subparsers.add_parser("walk-forward", help="Run canonical walk-forward validation")
    _add_passthrough(p_wfv, "Arguments forwarded to walk_forward_validate.py")

    p_profit = subparsers.add_parser("profit", help="Run profit-readiness pipeline")
    _add_passthrough(p_profit, "Arguments forwarded to profit_pipeline.py")

    p_sweep = subparsers.add_parser("sweep", help="Run canonical signal sweep")
    _add_passthrough(p_sweep, "Arguments forwarded to signal_sweep.py")

    p_challenge = subparsers.add_parser("challenge", help="Build challenge set from latest sweep")
    _add_passthrough(p_challenge, "Arguments forwarded to select_challenge_set.py")

    p_shadow = subparsers.add_parser("shadow", help="Run fixed-window shadow phase")
    _add_passthrough(p_shadow, "Arguments forwarded to run_shadow_phase.py")

    p_disambiguate = subparsers.add_parser("disambiguate", help="Run signal-vs-translation disambiguation")
    _add_passthrough(p_disambiguate, "Arguments forwarded to run_signal_vs_translation_disambiguation.py")

    p_gate = subparsers.add_parser("gate-sweep", help="Run gate sweep on selected strategies")
    _add_passthrough(p_gate, "Arguments forwarded to run_gate_sweep.py")

    # Cache + parity
    p_cache = subparsers.add_parser("cache", help="Cache utilities")
    cache_sub = p_cache.add_subparsers(dest="cache_command", required=True)

    p_cache_build_price = cache_sub.add_parser("build-price", help="Build liquid/price lookup cache")
    _add_passthrough(p_cache_build_price, "Arguments forwarded to build_cache.py")

    p_cache_build_trad = cache_sub.add_parser("build-trad", help="Build tradability lookup cache")
    _add_passthrough(p_cache_build_trad, "Arguments forwarded to build_trad_cache.py")

    p_cache_validate = cache_sub.add_parser("validate", help="Validate liquid cache parity with legacy semantics")
    _add_passthrough(p_cache_validate, "Arguments forwarded to validate_liquid_cache.py")

    p_cache_report = cache_sub.add_parser("report", help="Report tradability cache coverage")
    _add_passthrough(p_cache_report, "Arguments forwarded to report_trad_cache_coverage.py")

    p_parity = subparsers.add_parser("parity", help="Run precomputed-vs-legacy parity check")
    _add_passthrough(p_parity, "Arguments forwarded to test_parity.py")

    # Diagnostics / analysis
    p_analyze = subparsers.add_parser("analyze", help="Analysis and diagnostics commands")
    analyze_sub = p_analyze.add_subparsers(dest="analyze_command", required=True)
    for name in (
        "cash-mechanics",
        "execution-ablation",
        "regime-failures",
        "ticker-pnl",
        "trade-level",
    ):
        p = analyze_sub.add_parser(name, help=f"Run analyze_{name.replace('-', '_')} flow")
        _add_passthrough(p, f"Arguments forwarded to analyzer: {name}")

    # Debug helpers
    p_debug = subparsers.add_parser("debug", help="Debug commands")
    debug_sub = p_debug.add_subparsers(dest="debug_command", required=True)
    p_dbg_liq = debug_sub.add_parser("liquidity-semantics", help="Debug liquidity semantics vs cache")
    _add_passthrough(p_dbg_liq, "Arguments forwarded to debug_liquidity_semantics.py")
    p_dbg_par = debug_sub.add_parser("parity-diagnostics", help="Deep parity diagnostics")
    _add_passthrough(p_dbg_par, "Arguments forwarded to debug_parity_diagnostics.py")

    # Legacy utility runners (still supported through unified CLI)
    p_utility = subparsers.add_parser("utility", help="Legacy utility runners")
    utility_sub = p_utility.add_subparsers(dest="utility_command", required=True)
    for name in (
        "depth-frontier-wfv",
        "execution-ablation-wfv",
        "s1-depth5-wfv",
    ):
        p = utility_sub.add_parser(name, help=f"Run {name}")
        _add_passthrough(p, f"Arguments forwarded to utility runner: {name}")

    return parser


def _clean_passthrough(args: list[str]) -> list[str]:
    if args and args[0] == "--":
        return args[1:]
    return args


def dispatch(namespace: argparse.Namespace) -> int:
    cmd = namespace.command

    if cmd == "backtest":
        return _run_module_main("run_backtest", "run_backtest.py", _clean_passthrough(namespace.script_args))
    if cmd == "walk-forward":
        return _run_module_main(
            "walk_forward_validate",
            "walk_forward_validate.py",
            _clean_passthrough(namespace.script_args),
        )
    if cmd == "profit":
        return _run_module_main("profit_pipeline", "profit_pipeline.py", _clean_passthrough(namespace.script_args))
    if cmd == "sweep":
        return _run_module_main("signal_sweep", "signal_sweep.py", _clean_passthrough(namespace.script_args))
    if cmd == "challenge":
        return _run_module_main(
            "select_challenge_set",
            "select_challenge_set.py",
            _clean_passthrough(namespace.script_args),
        )
    if cmd == "shadow":
        return _run_module_main("run_shadow_phase", "run_shadow_phase.py", _clean_passthrough(namespace.script_args))
    if cmd == "disambiguate":
        return _run_module_main(
            "run_signal_vs_translation_disambiguation",
            "run_signal_vs_translation_disambiguation.py",
            _clean_passthrough(namespace.script_args),
        )
    if cmd == "gate-sweep":
        return _run_module_main("run_gate_sweep", "run_gate_sweep.py", _clean_passthrough(namespace.script_args))

    if cmd == "cache":
        cache_cmd = namespace.cache_command
        passthrough = _clean_passthrough(namespace.script_args)
        if cache_cmd == "build-price":
            return _run_module_as_script("build_cache", "build_cache.py", passthrough)
        if cache_cmd == "build-trad":
            return _run_module_as_script("build_trad_cache", "build_trad_cache.py", passthrough)
        if cache_cmd == "validate":
            return _run_module_as_script("validate_liquid_cache", "validate_liquid_cache.py", passthrough)
        if cache_cmd == "report":
            return _run_module_as_script("report_trad_cache_coverage", "report_trad_cache_coverage.py", passthrough)
        raise RuntimeError(f"Unsupported cache command: {cache_cmd}")

    if cmd == "parity":
        return _run_module_as_script("test_parity", "test_parity.py", _clean_passthrough(namespace.script_args))

    if cmd == "analyze":
        analyze_cmd = namespace.analyze_command
        passthrough = _clean_passthrough(namespace.script_args)
        if analyze_cmd == "cash-mechanics":
            return _run_module_main("analyze_cash_mechanics", "analyze_cash_mechanics.py", passthrough)
        if analyze_cmd == "execution-ablation":
            return _run_module_main("analyze_execution_ablation", "analyze_execution_ablation.py", passthrough)
        if analyze_cmd == "regime-failures":
            return _run_module_main("analyze_regime_failures", "analyze_regime_failures.py", passthrough)
        if analyze_cmd == "ticker-pnl":
            return _run_module_main("analyze_ticker_pnl_regimes", "analyze_ticker_pnl_regimes.py", passthrough)
        if analyze_cmd == "trade-level":
            return _run_module_main("analyze_trade_level_regimes", "analyze_trade_level_regimes.py", passthrough)
        raise RuntimeError(f"Unsupported analyze command: {analyze_cmd}")

    if cmd == "debug":
        debug_cmd = namespace.debug_command
        passthrough = _clean_passthrough(namespace.script_args)
        if debug_cmd == "liquidity-semantics":
            return _run_module_main("debug_liquidity_semantics", "debug_liquidity_semantics.py", passthrough)
        if debug_cmd == "parity-diagnostics":
            return _run_module_main("debug_parity_diagnostics", "debug_parity_diagnostics.py", passthrough)
        raise RuntimeError(f"Unsupported debug command: {debug_cmd}")

    if cmd == "utility":
        utility_cmd = namespace.utility_command
        passthrough = _clean_passthrough(namespace.script_args)
        if utility_cmd == "depth-frontier-wfv":
            return _run_file_as_script("run_depth_frontier_walkforward.py", "run_depth_frontier_walkforward.py", passthrough)
        if utility_cmd == "execution-ablation-wfv":
            return _run_file_as_script(
                "run_execution_ablation_walkforward.py",
                "run_execution_ablation_walkforward.py",
                passthrough,
            )
        if utility_cmd == "s1-depth5-wfv":
            return _run_file_as_script(
                "run_s1_depth5_validation_walkforward.py",
                "run_s1_depth5_validation_walkforward.py",
                passthrough,
            )
        raise RuntimeError(f"Unsupported utility command: {utility_cmd}")

    raise RuntimeError(f"Unsupported command: {cmd}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    namespace = parser.parse_args(argv)
    return dispatch(namespace)


if __name__ == "__main__":
    raise SystemExit(main())
