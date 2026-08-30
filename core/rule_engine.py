from __future__ import annotations

from typing import Any

import pandas as pd

from checks.deterministic import run_deterministic_checks


class RuleEngine:
    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}

    def run(self, df: pd.DataFrame) -> dict[str, Any]:
        checks = run_deterministic_checks(df, self.config)
        severity = {"critical": 0, "warning": 0, "info": 0}
        for check in checks:
            severity[check["severity"]] = severity.get(check["severity"], 0) + check["flag_count"]
        return {
            "total_flags": sum(check["flag_count"] for check in checks),
            "flagged_by_severity": severity,
            "checks": checks,
            "rows_checked": len(df),
        }
