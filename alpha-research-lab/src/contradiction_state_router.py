from __future__ import annotations

import pandas as pd


H250_CONTINUATION_ON_THRESHOLD = 0.55
H250_VETO_OFF_THRESHOLD = 0.45

H250_REQUIRED_COLUMNS = (
    "s1_proba",
    "c9_reversal_1d",
    "c12_gap_absorb_3",
    "c13_compress_blowoff_2",
    "c14_clv_volconf_resid_rank",
    "h199_sector_laggard_gap_absorb",
)

H250_SIGNAL_NAMES = (
    "h250_momentum_pullback_acceptance",
    "h250_sector_laggard_pullback_acceptance",
    "h250_gap_trend_without_blowoff",
    "h250_disagreement_balance",
    "h250_blowoff_reset_router",
)


def _clip01(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").clip(0.0, 1.0).fillna(0.0)


def _sparse(mask: pd.Series, score: pd.Series) -> pd.Series:
    return pd.to_numeric(score, errors="coerce").where(mask.fillna(False), 0.0).fillna(0.0)


def add_h250_router_signals(frame: pd.DataFrame) -> pd.DataFrame:
    missing = sorted(set(H250_REQUIRED_COLUMNS) - set(frame.columns))
    if missing:
        raise ValueError(f"Missing H250 router columns: {missing}")

    work = frame.copy()
    s1 = _clip01(work["s1_proba"])
    c9 = _clip01(work["c9_reversal_1d"])
    c12 = _clip01(work["c12_gap_absorb_3"])
    c13 = _clip01(work["c13_compress_blowoff_2"])
    c14 = _clip01(work["c14_clv_volconf_resid_rank"])
    h199 = _clip01(work["h199_sector_laggard_gap_absorb"])

    trend_combo = (s1 + h199 + c12 + c14) / 4.0
    reversal_combo = (c9 + c13) / 2.0

    work["h250_momentum_pullback_acceptance"] = _sparse(
        (s1 >= H250_CONTINUATION_ON_THRESHOLD)
        & (c9 >= H250_CONTINUATION_ON_THRESHOLD)
        & (c12 >= H250_CONTINUATION_ON_THRESHOLD)
        & (c13 <= H250_VETO_OFF_THRESHOLD),
        (s1 + c9 + c12 + c14) / 4.0,
    )
    work["h250_sector_laggard_pullback_acceptance"] = _sparse(
        (h199 >= H250_CONTINUATION_ON_THRESHOLD)
        & (c9 >= H250_CONTINUATION_ON_THRESHOLD)
        & (c12 >= H250_CONTINUATION_ON_THRESHOLD)
        & (c13 <= H250_VETO_OFF_THRESHOLD),
        (h199 + c9 + c12 + c14) / 4.0,
    )
    work["h250_gap_trend_without_blowoff"] = _sparse(
        (s1 >= H250_CONTINUATION_ON_THRESHOLD)
        & (h199 >= H250_CONTINUATION_ON_THRESHOLD)
        & (c12 >= H250_CONTINUATION_ON_THRESHOLD)
        & (c13 <= H250_VETO_OFF_THRESHOLD),
        trend_combo,
    )
    work["h250_disagreement_balance"] = _sparse(
        (trend_combo >= H250_CONTINUATION_ON_THRESHOLD)
        & (reversal_combo >= H250_CONTINUATION_ON_THRESHOLD),
        trend_combo * reversal_combo,
    )
    work["h250_blowoff_reset_router"] = _sparse(
        (c9 >= H250_CONTINUATION_ON_THRESHOLD)
        & (c13 >= H250_CONTINUATION_ON_THRESHOLD)
        & (c12 <= H250_VETO_OFF_THRESHOLD)
        & (c14 <= H250_VETO_OFF_THRESHOLD)
        & (s1 <= H250_VETO_OFF_THRESHOLD),
        (c9 + c13 + (1.0 - c12) + (1.0 - c14) + (1.0 - s1)) / 5.0,
    )
    return work
