from __future__ import annotations

import pandas as pd

from data_tools import fetch_cafef_order_stats as order_stats
from data_tools import fetch_cafef_proprietary_trading as proprietary
from data_tools.cafef_history_common import combine_frames


def test_order_stats_normalize_payload_rows_parses_signed_imbalance():
    frame = order_stats.normalize_payload_rows(
        [
            {
                "Date": "24/01/2025",
                "ThayDoi": "153,4 ( -0,58 %)",
                "SoLenhMua": 4877,
                "KLDatMua": 6648600,
                "KLTB1LenhMua": 1363,
                "SoLenhDatBan": 5946,
                "KLDatBan": 5997300,
                "KLTB1LenhBan": 1009,
                "ChenhLechKL": "651.300",
            },
            {
                "Date": "23/01/2025",
                "ThayDoi": "154,3 ( 3,07 %)",
                "SoLenhMua": 7367,
                "KLDatMua": 11613100,
                "KLTB1LenhMua": 1576,
                "SoLenhDatBan": 10394,
                "KLDatBan": 11994400,
                "KLTB1LenhBan": 1154,
                "ChenhLechKL": "-381.300",
            },
        ],
        "FPT",
    )

    assert frame["ticker"].tolist() == ["FPT", "FPT"]
    assert frame["date"].tolist() == ["2025-01-23", "2025-01-24"]
    assert frame["buy_sell_volume_imbalance"].tolist() == [-381300, 651300]


def test_proprietary_trading_normalize_payload_rows_builds_net_fields():
    frame = proprietary.normalize_payload_rows(
        [
            {
                "Symbol": "FPT",
                "Date": "24/01/2025",
                "KLcpMua": 346400,
                "KlcpBan": 195900,
                "GtMua": 53259410000,
                "GtBan": 30161490000,
            }
        ],
        "FPT",
    )

    row = frame.iloc[0]
    assert row["ticker"] == "FPT"
    assert row["date"] == "2025-01-24"
    assert row["proprietary_net_volume"] == 150500
    assert row["proprietary_net_value"] == 23097920000


def test_combine_frames_keeps_latest_duplicate_and_contract_shape():
    existing = pd.DataFrame(
        {
            "ticker": ["FPT"],
            "date": ["2025-01-24"],
            "source": ["old"],
            "metric": [1],
        }
    )
    incoming = pd.DataFrame(
        {
            "ticker": ["FPT", "FPT"],
            "date": ["2025-01-24", "2025-01-25"],
            "source": ["new", "new"],
            "metric": [2, 3],
        }
    )

    combined = combine_frames(existing, incoming, ["ticker", "date", "source", "metric"])

    assert combined["date"].tolist() == ["2025-01-24", "2025-01-25"]
    assert combined["metric"].tolist() == [2, 3]
