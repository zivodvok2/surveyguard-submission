from __future__ import annotations

from io import BytesIO
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill


def build_excel_report(results: dict[str, Any]) -> bytes:
    workbook = Workbook()
    summary = workbook.active
    summary.title = "Summary"
    summary.append(["Servallab Survey QC Report"])
    summary["A1"].font = Font(size=16, bold=True, color="FFFFFF")
    summary["A1"].fill = PatternFill("solid", fgColor="13263D")
    summary.append(["Rows checked", results.get("rows_checked", "")])
    summary.append(["Total flags", results.get("total_flags", 0)])
    summary.append([])
    summary.append(["Check", "Severity", "Issue type", "Flags"])
    for cell in summary[5]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="007F73")
    for check in results.get("checks", []):
        summary.append([check["check_name"], check["severity"], check["issue_type"], check["flag_count"]])
    summary.column_dimensions["A"].width = 42
    for index, check in enumerate(results.get("checks", []), start=1):
        rows = check.get("flagged_rows", [])
        if not rows:
            continue
        sheet = workbook.create_sheet(f"Issue {index}"[:31])
        headers = list(dict.fromkeys(key for row in rows for key in row))
        sheet.append(headers)
        for cell in sheet[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="13263D")
            cell.alignment = Alignment(wrap_text=True)
        for row in rows:
            sheet.append([row.get(header) for header in headers])
        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = sheet.dimensions
        for column in sheet.columns:
            letter = column[0].column_letter
            sheet.column_dimensions[letter].width = min(50, max(12, max(len(str(cell.value or "")) for cell in column) + 2))
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()
