from __future__ import annotations

from pathlib import Path

import pandas as pd


class DataLoader:
    """Load the tabular formats used by CATI/CAPI projects."""

    SUPPORTED = {".csv", ".tsv", ".xlsx", ".xls", ".sav", ".parquet"}

    def load(self, path: str | Path) -> pd.DataFrame:
        file_path = Path(path)
        suffix = file_path.suffix.lower()
        if suffix not in self.SUPPORTED:
            raise ValueError(f"Unsupported dataset format: {suffix or 'unknown'}")
        if suffix == ".csv":
            return pd.read_csv(file_path, low_memory=False)
        if suffix == ".tsv":
            return pd.read_csv(file_path, sep="\t", low_memory=False)
        if suffix in {".xlsx", ".xls"}:
            return pd.read_excel(file_path)
        if suffix == ".parquet":
            return pd.read_parquet(file_path)
        try:
            import pyreadstat
        except ImportError as exc:
            raise RuntimeError("SPSS .sav support requires pyreadstat") from exc
        frame, _ = pyreadstat.read_sav(str(file_path))
        return frame
