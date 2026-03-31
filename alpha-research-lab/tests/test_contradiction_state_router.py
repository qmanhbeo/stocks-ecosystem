from __future__ import annotations

import pytest
import pandas as pd

from src.contradiction_state_router import add_h250_router_signals


def test_add_h250_router_signals_builds_sparse_router_scores() -> None:
    frame = pd.DataFrame(
        {
            "s1_proba": [0.70, 0.20, 0.70, 0.60],
            "c9_reversal_1d": [0.60, 0.70, 0.70, 0.60],
            "c12_gap_absorb_3": [0.60, 0.20, 0.60, 0.60],
            "c13_compress_blowoff_2": [0.60, 0.80, 0.20, 0.20],
            "c14_clv_volconf_resid_rank": [0.70, 0.20, 0.60, 0.70],
            "h199_sector_laggard_gap_absorb": [0.70, 0.20, 0.40, 0.70],
        }
    )

    out = add_h250_router_signals(frame)

    assert round(float(out.loc[0, "h250_disagreement_balance"]), 6) == 0.405
    assert round(float(out.loc[1, "h250_blowoff_reset_router"]), 6) == 0.78
    assert round(float(out.loc[2, "h250_momentum_pullback_acceptance"]), 6) == 0.65
    assert round(float(out.loc[2, "h250_sector_laggard_pullback_acceptance"]), 6) == 0.0
    assert round(float(out.loc[3, "h250_gap_trend_without_blowoff"]), 6) == 0.65


def test_add_h250_router_signals_requires_all_inputs() -> None:
    with pytest.raises(ValueError, match="Missing H250 router columns"):
        add_h250_router_signals(pd.DataFrame({"s1_proba": [0.5]}))
