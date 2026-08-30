from __future__ import annotations

import re
from collections import Counter
from typing import Any, Callable, Iterable

import numpy as np
import pandas as pd


def _json_value(value: Any) -> Any:
    if value is None or value is pd.NA:
        return None
    if isinstance(value, (np.integer, np.floating, np.bool_)):
        value = value.item()
    if isinstance(value, float) and np.isnan(value):
        return None
    if isinstance(value, (pd.Timestamp,)):
        return value.isoformat()
    return value


def _rows(df: pd.DataFrame, mask: pd.Series, message: str, evidence: str, limit: int = 500) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for index, row in df.loc[mask].head(limit).iterrows():
        record = {str(key): _json_value(value) for key, value in row.to_dict().items()}
        record.update({"_row_number": int(index) + 2 if isinstance(index, (int, np.integer)) else str(index), "_message": message, "_evidence": evidence})
        output.append(record)
    return output


def _result(name: str, issue_type: str, severity: str, rows: list[dict[str, Any]], total: int | None = None) -> dict[str, Any]:
    return {
        "check_name": name,
        "issue_type": issue_type,
        "severity": severity,
        "flag_count": len(rows) if total is None else int(total),
        "flagged_rows": rows,
    }


def _compare(series: pd.Series, operator: str, value: Any = None) -> pd.Series:
    if operator == "is_null":
        return series.isna()
    if operator == "not_null":
        return series.notna()
    if operator == "is_numeric":
        return pd.to_numeric(series, errors="coerce").notna()
    if operator == "is_string":
        return series.map(lambda item: isinstance(item, str))
    if operator in {"in_list", "not_in_list"}:
        values = value if isinstance(value, list) else [part.strip() for part in str(value).split(",")]
        mask = series.astype(str).isin([str(item) for item in values])
        return ~mask if operator == "not_in_list" else mask
    numeric_series = pd.to_numeric(series, errors="coerce")
    numeric_value = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    left, right = (numeric_series, numeric_value) if pd.notna(numeric_value) else (series.astype(str), str(value))
    operations: dict[str, Callable[[], pd.Series]] = {
        "==": lambda: left == right,
        "!=": lambda: left != right,
        ">": lambda: left > right,
        "<": lambda: left < right,
        ">=": lambda: left >= right,
        "<=": lambda: left <= right,
    }
    if operator not in operations:
        raise ValueError(f"Unsupported operator: {operator}")
    return operations[operator]().fillna(False)


def evaluate_conditions(df: pd.DataFrame, conditions: Iterable[dict[str, Any]], connector: str = "AND") -> pd.Series:
    masks: list[pd.Series] = []
    for condition in conditions:
        column = condition.get("column") or condition.get("col")
        if column not in df.columns:
            return pd.Series(False, index=df.index)
        masks.append(_compare(df[column], condition.get("operator") or condition.get("op") or "==", condition.get("value", condition.get("val"))))
    if not masks:
        return pd.Series(False, index=df.index)
    combined = masks[0]
    for mask in masks[1:]:
        combined = combined | mask if connector.upper() == "OR" else combined & mask
    return combined.fillna(False)


def run_deterministic_checks(df: pd.DataFrame, config: dict[str, Any]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    missing_columns = [column for column in config.get("missing_columns", []) if column in df.columns]
    excluded = set(config.get("missing_exclude_columns", []))
    columns = missing_columns or [column for column in df.columns if column not in excluded]
    threshold = float(config.get("missing_threshold", 0.1))
    for column in columns:
        mask = df[column].isna()
        count = int(mask.sum())
        if count and (count / max(len(df), 1) >= threshold or column in missing_columns):
            results.append(_result(f"Missing values — {column}", "missing_value", "warning", _rows(df, mask, f"{column} is blank", f"Missing rate {count / max(len(df), 1):.1%}"), count))

    duplicate_config = config.get("duplicate_check", {})
    if duplicate_config.get("enabled", True):
        subset = [column for column in duplicate_config.get("subset_columns", []) if column in df.columns] or None
        mask = df.duplicated(subset=subset, keep=False)
        count = int(mask.sum())
        if count:
            results.append(_result("Duplicate responses", "duplicate", "critical", _rows(df, mask, "Response duplicates another row", f"Compared on {subset or 'all columns'}"), count))

    for rule in config.get("range_rules", []):
        column = rule.get("column")
        if column not in df.columns:
            continue
        numeric = pd.to_numeric(df[column], errors="coerce")
        mask = numeric.notna() & False
        evidence: list[str] = []
        if rule.get("min") is not None:
            mask |= numeric < float(rule["min"])
            evidence.append(f"minimum {rule['min']}")
        if rule.get("max") is not None:
            mask |= numeric > float(rule["max"])
            evidence.append(f"maximum {rule['max']}")
        count = int(mask.sum())
        if count:
            results.append(_result(f"Range — {column}", "range_violation", "critical", _rows(df, mask, f"{column} is outside its allowed range", ", ".join(evidence)), count))

    for index, rule in enumerate(config.get("logic_rules", []), start=1):
        if_conditions = rule.get("if_conditions") or [{"column": rule.get("if_column"), "operator": "==", "value": rule.get("if_value")}]
        then_conditions = rule.get("then_conditions") or [{"column": rule.get("then_column"), "operator": rule.get("then_condition", "not_null")}]
        trigger = evaluate_conditions(df, if_conditions, rule.get("if_connector", "AND"))
        expected = evaluate_conditions(df, then_conditions, rule.get("then_connector", "AND"))
        mask = trigger & ~expected
        count = int(mask.sum())
        if count:
            description = rule.get("description") or f"Logic rule {index}"
            results.append(_result(description, "logic_violation", "critical", _rows(df, mask, description, f"IF matched but THEN failed: {then_conditions}"), count))

    for rule in config.get("pattern_rules", []):
        column, pattern = rule.get("column"), rule.get("pattern")
        if column not in df.columns or not pattern:
            continue
        try:
            valid = df[column].astype("string").str.match(pattern, na=False)
        except re.error:
            continue
        mask = df[column].notna() & ~valid
        count = int(mask.sum())
        if count:
            description = rule.get("description") or f"Invalid pattern in {column}"
            results.append(_result(description, "pattern_violation", "warning", _rows(df, mask, description, f"Expected pattern {pattern}"), count))

    duration = config.get("interview_duration", {})
    column = duration.get("column")
    if duration.get("enabled") and column in df.columns:
        values = pd.to_numeric(df[column], errors="coerce")
        minimum, maximum = float(duration.get("min_expected", 0)), float(duration.get("max_expected", float("inf")))
        mask = values.notna() & ((values < minimum) | (values > maximum))
        count = int(mask.sum())
        if count:
            results.append(_result("Interview duration", "duration_anomaly", "warning", _rows(df, mask, "Interview duration is outside the configured range", f"Expected {minimum:g}–{maximum:g} minutes"), count))

    straightlining = config.get("straightlining", {})
    question_columns = [column for column in straightlining.get("question_columns", []) if column in df.columns]
    if straightlining.get("enabled") and len(question_columns) >= int(straightlining.get("min_questions", 3)):
        threshold_value = float(straightlining.get("threshold", 0.9))
        ratios = df[question_columns].apply(lambda row: row.value_counts(dropna=True).max() / max(row.notna().sum(), 1), axis=1)
        mask = ratios >= threshold_value
        count = int(mask.sum())
        if count:
            results.append(_result("Straightlining", "straightlining", "warning", _rows(df, mask, "Response repeats the same option across a battery", f"Dominant-answer ratio ≥ {threshold_value:.0%}"), count))

    consent = config.get("consent_eligibility_check", {})
    screener = consent.get("screener_column")
    if consent.get("enabled") and screener in df.columns:
        disqualified = _compare(df[screener], consent.get("disqualify_operator", "=="), consent.get("disqualify_value"))
        subsequent = [column for column in consent.get("subsequent_columns", []) if column in df.columns]
        if subsequent:
            mask = disqualified & df[subsequent].notna().any(axis=1)
            count = int(mask.sum())
            if count:
                results.append(_result("Consent / eligibility routing", "eligibility_violation", "critical", _rows(df, mask, "Interview continued after a disqualifying response", f"Subsequent fields populated: {subsequent}"), count))

    near_duplicate = config.get("near_duplicate_check", {})
    combo = [column for column in near_duplicate.get("combo_columns", []) if column in df.columns]
    if near_duplicate.get("enabled") and combo:
        tuples = df[combo].fillna("<MISSING>").astype(str).agg("¦".join, axis=1)
        counts = Counter(tuples)
        maximum = int(near_duplicate.get("max_combo_count", 3))
        mask = tuples.map(counts) > maximum
        count = int(mask.sum())
        if count:
            results.append(_result("Repeated response combinations", "near_duplicate", "warning", _rows(df, mask, "Unusually frequent answer combination", f"Combination appears more than {maximum} times"), count))
    return results
