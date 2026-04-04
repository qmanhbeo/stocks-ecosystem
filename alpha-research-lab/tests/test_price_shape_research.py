from __future__ import annotations

import pandas as pd

from src.price_shape_research import build_upward_w_shape_features, triangular_band_score


def test_triangular_band_score_peaks_at_center() -> None:
    frame = pd.DataFrame([[0.12, 0.15, 0.20]], columns=["left", "center", "right"])

    scored = triangular_band_score(frame, center=0.15, width=0.05)

    assert scored.loc[0, "center"] == 1.0
    assert 0.0 < scored.loc[0, "left"] < 1.0
    assert scored.loc[0, "right"] == 0.0


def test_upward_w_reclaim_prefers_clean_double_bottom_breakout() -> None:
    dates = pd.date_range("2020-01-01", periods=25, freq="D")
    close = pd.DataFrame(
        {
            "W": [
                110,
                109,
                108,
                110,
                109,
                108,
                107,
                109,
                110,
                108,
                109,
                110,
                96,
                92,
                90,
                91,
                95,
                98,
                100,
                99,
                96,
                94,
                93,
                95,
                101,
            ],
            "NO_BREAK": [
                110,
                109,
                108,
                110,
                109,
                108,
                107,
                109,
                110,
                108,
                109,
                110,
                96,
                92,
                90,
                91,
                95,
                98,
                100,
                99,
                96,
                94,
                93,
                95,
                98,
            ],
            "BLOWOFF": [
                110,
                109,
                108,
                110,
                109,
                108,
                107,
                109,
                110,
                108,
                109,
                110,
                96,
                92,
                90,
                91,
                95,
                98,
                100,
                99,
                96,
                94,
                93,
                95,
                108,
            ],
        },
        index=dates,
        dtype=float,
    )

    features = build_upward_w_shape_features(close)
    last_row = features["xs_upward_w_reclaim_12d"].iloc[-1]

    assert last_row["W"] > last_row["NO_BREAK"]
    assert last_row["W"] > last_row["BLOWOFF"]
