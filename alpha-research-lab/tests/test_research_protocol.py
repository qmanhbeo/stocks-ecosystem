from __future__ import annotations

import pandas as pd

from src.research_protocol import DEFAULT_PROTOCOL, assign_research_phase, phase_mask, split_by_phase


def test_assign_research_phase_maps_expected_year_buckets() -> None:
    frame = pd.DataFrame(
        {
            "time": pd.to_datetime(
                [
                    "2014-12-31",
                    "2015-01-05",
                    "2023-01-03",
                    "2025-12-31",
                    "2026-01-02",
                ]
            )
        }
    )
    phased = assign_research_phase(frame, protocol=DEFAULT_PROTOCOL)
    assert phased["research_phase"].tolist() == [None, "dev", "validation", "confirmation", "forward"]


def test_phase_mask_accepts_single_and_multiple_phases() -> None:
    frame = pd.DataFrame(
        {"time": pd.to_datetime(["2015-01-05", "2023-01-03", "2024-06-01", "2025-12-31"])}
    )
    validation_only = phase_mask(frame, "validation", protocol=DEFAULT_PROTOCOL)
    assert validation_only.tolist() == [False, True, True, False]

    dev_or_confirmation = phase_mask(frame, ["dev", "confirmation"], protocol=DEFAULT_PROTOCOL)
    assert dev_or_confirmation.tolist() == [True, False, False, True]


def test_split_by_phase_returns_disjoint_frames() -> None:
    frame = pd.DataFrame(
        {
            "time": pd.to_datetime(
                ["2015-01-05", "2019-01-02", "2023-03-04", "2024-05-06", "2025-07-08", "2026-01-02"]
            ),
            "value": range(6),
        }
    )
    split = split_by_phase(frame, protocol=DEFAULT_PROTOCOL)
    assert split["dev"]["value"].tolist() == [0, 1]
    assert split["validation"]["value"].tolist() == [2, 3]
    assert split["confirmation"]["value"].tolist() == [4]
    assert split["forward"]["value"].tolist() == [5]

