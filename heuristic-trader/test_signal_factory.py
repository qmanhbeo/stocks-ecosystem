from signal_factory import prepare_signal_df_from_config


TEST_START = "2024-01-01"
TEST_END = "2024-12-31"


def test_surface_col_mode_matrix_column() -> None:
    cfg = {
        "name": "test_surface",
        "signal_type": "surface_col",
        "source_surface": "rl_signal_matrix",
        "source_col": "c10_illiq_level_rank",
        "signal_col": "c10_illiq_level_rank",
        "top_k": 5,
        "rebalance_days": 10,
        "min_hold_days": 3,
    }
    df = prepare_signal_df_from_config(cfg, TEST_START, TEST_END, allow_2026=False)
    assert len(df) > 0
    assert list(df.columns) == ["time", "ticker", "c10_illiq_level_rank"]


def test_s1_surface_blend_mode() -> None:
    cfg = {
        "name": "test_blend",
        "signal_type": "s1_surface_blend",
        "source_surface": "rl_signal_matrix",
        "source_col": "c13_compress_blowoff_2",
        "signal_col": "blend",
        "w_s1": 0.7,
        "w_surface": 0.3,
        "top_k": 5,
        "rebalance_days": 10,
        "min_hold_days": 3,
    }
    df = prepare_signal_df_from_config(cfg, TEST_START, TEST_END, allow_2026=False)
    assert len(df) > 0
    assert list(df.columns) == ["time", "ticker", "blend"]

