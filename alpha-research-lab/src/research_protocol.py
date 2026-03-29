from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import pandas as pd


PHASE_ORDER = ("dev", "validation", "confirmation", "forward")


@dataclass(frozen=True)
class ResearchProtocol:
    dev_start_year: int = 2015
    dev_end_year: int = 2022
    validation_start_year: int = 2023
    validation_end_year: int = 2024
    confirmation_year: int = 2025
    forward_start_year: int = 2026

    def phase_for_year(self, year: int) -> str | None:
        year = int(year)
        if self.dev_start_year <= year <= self.dev_end_year:
            return "dev"
        if self.validation_start_year <= year <= self.validation_end_year:
            return "validation"
        if year == self.confirmation_year:
            return "confirmation"
        if year >= self.forward_start_year:
            return "forward"
        return None

    def years_for_phase(self, phase: str) -> tuple[int, ...]:
        if phase == "dev":
            return tuple(range(int(self.dev_start_year), int(self.dev_end_year) + 1))
        if phase == "validation":
            return tuple(range(int(self.validation_start_year), int(self.validation_end_year) + 1))
        if phase == "confirmation":
            return (int(self.confirmation_year),)
        if phase == "forward":
            return tuple(range(int(self.forward_start_year), int(self.forward_start_year) + 100))
        raise ValueError(f"Unknown phase {phase!r}")

    def describe(self) -> dict[str, object]:
        return {
            "dev_years": [int(self.dev_start_year), int(self.dev_end_year)],
            "validation_years": [int(self.validation_start_year), int(self.validation_end_year)],
            "confirmation_year": int(self.confirmation_year),
            "forward_start_year": int(self.forward_start_year),
        }


DEFAULT_PROTOCOL = ResearchProtocol()


def assign_research_phase(
    frame: pd.DataFrame,
    *,
    date_column: str = "time",
    protocol: ResearchProtocol = DEFAULT_PROTOCOL,
    out_column: str = "research_phase",
) -> pd.DataFrame:
    work = frame.copy()
    years = pd.to_datetime(work[date_column]).dt.year
    work[out_column] = years.map(protocol.phase_for_year)
    return work


def phase_mask(
    frame: pd.DataFrame,
    phase: str | Iterable[str],
    *,
    date_column: str = "time",
    protocol: ResearchProtocol = DEFAULT_PROTOCOL,
) -> pd.Series:
    phases = {str(value) for value in ([phase] if isinstance(phase, str) else phase)}
    years = pd.to_datetime(frame[date_column]).dt.year
    return years.map(protocol.phase_for_year).isin(phases)


def split_by_phase(
    frame: pd.DataFrame,
    *,
    date_column: str = "time",
    protocol: ResearchProtocol = DEFAULT_PROTOCOL,
) -> dict[str, pd.DataFrame]:
    assigned = assign_research_phase(frame, date_column=date_column, protocol=protocol)
    return {
        phase: assigned.loc[assigned["research_phase"] == phase].copy()
        for phase in PHASE_ORDER
    }

