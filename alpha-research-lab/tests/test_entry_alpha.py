from __future__ import annotations

import numpy as np
import pandas as pd

from src.entry_alpha import build_entry_allowed_matrix, build_entry_candidate_panel, build_entry_labels


def test_build_entry_candidate_panel_assigns_ranks_and_hold_flags():
    feature_frame = pd.DataFrame(
        {
            "time": pd.to_datetime(
                [
                    "2024-01-02",
                    "2024-01-02",
                    "2024-01-02",
                    "2024-01-03",
                    "2024-01-03",
                    "2024-01-03",
                ]
            ),
            "ticker": ["AAA", "BBB", "CCC", "AAA", "BBB", "CCC"],
            "score__full_library": [0.90, 0.70, 0.60, 0.40, 0.80, 0.50],
            "can_buy_next_open": [True, True, False, True, True, True],
            "can_sell_next_open": [True, True, True, True, True, True],
            "actual": [1, 0, 0, 0, 1, 0],
        }
    )
    activation_meta = pd.DataFrame(
        {
            "time": pd.to_datetime(["2024-01-02", "2024-01-03"]),
            "activation_state": ["off", "on"],
            "activation_scale": [0.0, 1.0],
            "activation_rel2": [-0.01, 0.02],
        }
    )
    dummy_inputs = type(
        "DummyEntryAlphaInputs",
        (),
        {
            "feature_frame": feature_frame,
            "activation_meta": activation_meta,
            "selector_name": "full_library_k5_r5_eq",
            "strategy_name": "full_library",
            "top_k": 2,
            "rebalance_every": 5,
        },
    )()

    panel = build_entry_candidate_panel(
        dummy_inputs,
        top_m_max=2,
        held_prev_close_lookup={pd.Timestamp("2024-01-03"): {"BBB"}},
    )

    assert panel.loc[panel["time"] == pd.Timestamp("2024-01-02"), "ticker"].tolist() == ["AAA", "BBB"]
    assert panel.loc[panel["time"] == pd.Timestamp("2024-01-02"), "candidate_pool_rank"].tolist() == [1, 2]
    assert np.allclose(
        panel.loc[panel["time"] == pd.Timestamp("2024-01-02"), "selection_score_gap_to_next_candidate"].to_numpy(dtype=float),
        np.array([0.20, 0.10], dtype=float),
    )
    held_row = panel.loc[(panel["time"] == pd.Timestamp("2024-01-03")) & (panel["ticker"] == "BBB")].iloc[0]
    assert bool(held_row["is_held_prev_close"]) is True
    assert held_row["activation_state"] == "on"


def test_build_entry_labels_aligns_cycle_dates_and_returns():
    candidate_panel = pd.DataFrame(
        {
            "time": pd.to_datetime(["2024-01-02", "2024-01-03"]),
            "ticker": ["AAA", "AAA"],
        }
    )
    price_panel = pd.DataFrame(
        {
            "time": pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"]),
            "ticker": ["AAA", "AAA", "AAA", "AAA"],
            "open": [10.0, 11.0, 12.0, 13.0],
        }
    )
    benchmark_open = pd.Series(
        [100.0, 102.0, 103.0, 104.0],
        index=pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"]),
        dtype=float,
    )

    labels = build_entry_labels(
        candidate_panel,
        price_panel=price_panel,
        benchmark_open=benchmark_open,
        horizon_signal_steps=1,
        signal_dates=pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04"]),
        round_trip_cost=0.003,
        label_edge_buffer=0.0,
    )

    first = labels.iloc[0]
    assert pd.Timestamp(first["entry_execution_date"]) == pd.Timestamp("2024-01-03")
    assert pd.Timestamp(first["cycle_exit_date"]) == pd.Timestamp("2024-01-04")
    assert np.isclose(float(first["entry_open_t1"]), 11.0)
    assert np.isclose(float(first["cycle_exit_open"]), 12.0)
    assert np.isclose(float(first["cycle_return_gross"]), 12.0 / 11.0 - 1.0)
    assert np.isclose(float(first["cycle_return_net"]), 12.0 / 11.0 - 1.0 - 0.003)
    assert int(first["buy_now_label"]) == 1
    second = labels.iloc[1]
    assert pd.isna(second["cycle_exit_date"])
    assert pd.isna(second["buy_now_label"])


def test_build_entry_labels_respects_label_edge_buffer():
    candidate_panel = pd.DataFrame(
        {
            "time": pd.to_datetime(["2024-01-02"]),
            "ticker": ["AAA"],
        }
    )
    price_panel = pd.DataFrame(
        {
            "time": pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04"]),
            "ticker": ["AAA", "AAA", "AAA"],
            "open": [10.0, 10.0, 10.12],
        }
    )
    benchmark_open = pd.Series(
        [100.0, 100.0, 100.0],
        index=pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04"]),
        dtype=float,
    )

    loose = build_entry_labels(
        candidate_panel,
        price_panel=price_panel,
        benchmark_open=benchmark_open,
        horizon_signal_steps=1,
        signal_dates=pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04"]),
        round_trip_cost=0.003,
        label_edge_buffer=0.0,
    )
    strict = build_entry_labels(
        candidate_panel,
        price_panel=price_panel,
        benchmark_open=benchmark_open,
        horizon_signal_steps=1,
        signal_dates=pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04"]),
        round_trip_cost=0.003,
        label_edge_buffer=0.01,
    )

    assert float(loose.loc[0, "cycle_return_net"]) > 0.0
    assert float(loose.loc[0, "cycle_return_net"]) < 0.01
    assert int(loose.loc[0, "buy_now_label"]) == 1
    assert int(strict.loc[0, "buy_now_label"]) == 0


def test_build_entry_allowed_matrix_respects_rank_score_and_gap():
    candidate_panel = pd.DataFrame(
        {
            "time": pd.to_datetime(["2024-01-02", "2024-01-02", "2024-01-02"]),
            "ticker": ["AAA", "BBB", "CCC"],
            "candidate_pool_rank": [1, 2, 3],
            "selection_score": [0.90, 0.72, 0.60],
            "selection_score_gap_to_next_candidate": [0.18, 0.12, np.nan],
            "can_buy_next_open": [True, True, False],
        }
    )

    matrix = build_entry_allowed_matrix(
        candidate_panel,
        dates=[pd.Timestamp("2024-01-02")],
        tickers=["AAA", "BBB", "CCC"],
        top_m=2,
        min_selection_score=0.70,
        min_score_gap=0.15,
        require_buyable=True,
    )

    assert matrix.shape == (1, 3)
    assert matrix.tolist() == [[True, False, False]]
