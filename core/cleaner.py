from __future__ import annotations

import numpy as np
import pandas as pd


class DataCleaner:
    """Normalise transport artefacts without changing respondent meaning."""

    NULL_STRINGS = {"", "na", "n/a", "nan", "null", "none", "<na>"}

    def clean(self, frame: pd.DataFrame) -> pd.DataFrame:
        df = frame.copy()
        df.columns = [str(column).strip() for column in df.columns]
        for column in df.select_dtypes(include=["object", "string"]).columns:
            series = df[column].map(lambda value: value.strip() if isinstance(value, str) else value)
            df[column] = series.map(
                lambda value: np.nan
                if isinstance(value, str) and value.lower() in self.NULL_STRINGS
                else value
            )
        return df
