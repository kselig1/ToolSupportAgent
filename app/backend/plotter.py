from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import Lock

import pandas as pd


DATA_FILE = Path(__file__).resolve().parents[2] / "data" / "engineering_metrics.psv"


@dataclass
class PlotterConfig:
    delimiter: str = ","  # Intentionally wrong: the source is pipe-delimited.
    timestamp_column: str = "timestamp"
    value_column: str = "latency_ms"


class EngineeringPlotter:
    """Small stateful tool whose broken configuration drives the demo."""

    def __init__(self) -> None:
        self.config = PlotterConfig()
        self._lock = Lock()

    def reset(self) -> None:
        with self._lock:
            self.config.delimiter = ","

    def apply_fix(self) -> None:
        with self._lock:
            self.config.delimiter = "|"

    def inspect(self) -> dict:
        first_line = DATA_FILE.read_text(encoding="utf-8").splitlines()[0]
        parsed_columns = list(pd.read_csv(DATA_FILE, sep=self.config.delimiter, nrows=1).columns)
        return {
            "source": str(DATA_FILE.name),
            "header": first_line,
            "configured_delimiter": self.config.delimiter,
            "expected_columns": [self.config.timestamp_column, self.config.value_column],
            "parsed_columns": parsed_columns,
            "is_fixed": self.config.delimiter == "|",
        }

    def load(self) -> dict:
        try:
            frame = pd.read_csv(DATA_FILE, sep=self.config.delimiter)
            required = [self.config.timestamp_column, self.config.value_column]
            missing = [column for column in required if column not in frame.columns]
            if missing:
                parsed = ", ".join(frame.columns)
                raise ValueError(
                    f"Missing required column '{missing[0]}'. Parser produced: [{parsed}]. "
                    f"Configured delimiter is {self.config.delimiter!r}."
                )
            return {
                "status": "healthy",
                "metric": self.config.value_column,
                "points": [
                    {"timestamp": row[self.config.timestamp_column], "value": float(row[self.config.value_column])}
                    for _, row in frame.iterrows()
                ],
                "config": self.inspect(),
            }
        except Exception as exc:
            return {
                "status": "error",
                "error_type": type(exc).__name__,
                "message": str(exc),
                "config": self.inspect(),
            }


plotter = EngineeringPlotter()

