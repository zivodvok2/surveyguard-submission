"""
Generate multi-project QC presentation for the meeting.
Run: DATABASE_URL=... python3 generate_meeting_ppt.py
"""

import io
import os
from datetime import date

from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN

NAVY  = RGBColor(0x1B, 0x2A, 0x4A)
TEAL  = RGBColor(0x00, 0xB5, 0xA3)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
LIGHT = RGBColor(0xF1, 0xF4, 0xF8)
GRAY  = RGBColor(0x6B, 0x72, 0x80)
DARK  = RGBColor(0x1B, 0x2A, 0x4A)
LINE  = RGBColor(0xE2, 0xE6, 0xED)

SLIDE_W = Inches(13.33)
SLIDE_H = Inches(7.5)


def _prs():
    prs = Presentation()
    prs.slide_width = SLIDE_W
    prs.slide_height = SLIDE_H
    return prs


def _blank(prs):
    return prs.slides.add_slide(prs.slide_layouts[6])


def _bg(slide, color=WHITE):
    f = slide.background.fill
    f.solid()
    f.fore_color.rgb = color


def _rect(slide, x, y, w, h, color):
    sh = slide.shapes.add_shape(1, Inches(x), Inches(y), Inches(w), Inches(h))
    sh.fill.solid()
    sh.fill.fore_color.rgb = color
    sh.line.fill.background()
    return sh


def _txt(slide, text, x, y, w, h, size=12, bold=False, color=DARK,
         align=PP_ALIGN.LEFT, italic=False):
    txb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    txb.word_wrap = True
    tf = txb.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = str(text)
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    run.font.color.rgb = color
    run.font.name = "Calibri"


def _header(slide, title, subtitle=None):
    _rect(slide, 0, 0, 13.33, 0.95, NAVY)
    _txt(slide, title, 0.5, 0.08, 11, 0.58, size=26, bold=True, color=WHITE)
    if subtitle:
        _txt(slide, subtitle, 0.5, 0.65, 12.5, 0.28, size=11,
             color=RGBColor(0xCC, 0xDD, 0xFF))


def _kpi(slide, x, y, w, h, value, label, color=NAVY):
    _rect(slide, x, y, w, h, LIGHT)
    _rect(slide, x, y, w, 0.06, color)
    _txt(slide, value, x + 0.1, y + 0.15, w - 0.2, 0.65,
         size=30, bold=True, color=color, align=PP_ALIGN.CENTER)
    _txt(slide, label, x + 0.1, y + 0.82, w - 0.2, 0.4,
         size=9, color=GRAY, align=PP_ALIGN.CENTER)


# ── Slide 1: Title ─────────────────────────────────────────────────────────────

def slide_title(prs):
    s = _blank(prs)
    _bg(s, WHITE)
    _rect(s, 0, 0, 13.33, 3.8, NAVY)
    _rect(s, 0, 3.8, 13.33, 0.08, TEAL)
    _txt(s, "QC Dashboard", 0.7, 0.45, 12, 1.0,
         size=52, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
    _txt(s, "Operations Status Report  ·  All Active Projects",
         0.7, 1.6, 12, 0.55,
         size=18, color=RGBColor(0xCC, 0xDD, 0xFF), align=PP_ALIGN.CENTER)
    _txt(s, f"{date.today().strftime('%B %Y')}  ·  Confidential",
         0.7, 2.28, 12, 0.38, size=12, color=GRAY, align=PP_ALIGN.CENTER, italic=True)
    _txt(s, "Presented by Quality Control Division",
         0.7, 4.05, 12, 0.42, size=14, bold=True, color=NAVY, align=PP_ALIGN.CENTER)
    bullets = ["3 Active Projects", "4,929 QC Records", "Live Dashboard", "Real-time Monitoring"]
    bx = [0.8, 3.85, 6.9, 9.9]
    for txt, bxi in zip(bullets, bx):
        _rect(s, bxi, 4.75, 2.7, 1.35, LIGHT)
        _rect(s, bxi, 4.75, 2.7, 0.06, TEAL)
        _txt(s, txt, bxi + 0.1, 4.98, 2.5, 0.8,
             size=13, bold=True, color=NAVY, align=PP_ALIGN.CENTER)


# ── Slide 2: Portfolio Overview ─────────────────────────────────────────────────

def slide_portfolio(prs, projects):
    s = _blank(prs)
    _bg(s, WHITE)
    _header(s, "Portfolio Overview", f"3 active projects · {date.today().strftime('%d %B %Y')}")

    col_headers = ["Project", "QC Records", "Approval %", "Flags", "Backchecks", "Listen-in", "Interviewers"]
    col_x = [0.5, 4.0, 5.5, 6.8, 8.0, 9.3, 10.6]
    col_w = [3.4, 1.4, 1.2, 1.1, 1.2, 1.2, 1.2]

    # Header row
    _rect(s, 0.5, 1.1, 12.3, 0.48, NAVY)
    for h, x, w in zip(col_headers, col_x, col_w):
        _txt(s, h, x + 0.08, 1.18, w, 0.35, size=9, bold=True, color=WHITE)

    for i, p in enumerate(projects):
        y = 1.66 + i * 1.52
        bg = LIGHT if i % 2 == 0 else WHITE
        _rect(s, 0.5, y, 12.3, 1.4, bg)
        _rect(s, 0.5, y, 0.06, 1.4, TEAL if i % 2 == 0 else NAVY)

        total = p['total_qc']
        apr = round(p['approved'] / total * 100) if total else 0
        flags = p['dur_flags'] + p['sl_flags']

        vals = [
            p['project_name'],
            f"{total:,}",
            f"{apr}%",
            str(flags),
            str(p['bc_total']),
            str(p['li_total']),
            str(p['interviewer_count']),
        ]
        val_colors = [
            DARK, DARK,
            TEAL if apr >= 80 else NAVY,
            NAVY if flags > 20 else GRAY,
            DARK, DARK, DARK,
        ]
        for v, x, w, vc in zip(vals, col_x, col_w, val_colors):
            _txt(s, v, x + 0.08, y + 0.45, w, 0.45, size=10, bold=(vals.index(v) == 0), color=vc)

        # Mini bar for approval rate
        _rect(s, col_x[2] + 0.08, y + 0.95, max(0.05, col_w[2] * apr / 100), 0.12, TEAL)

    # Totals row
    ty = 1.66 + len(projects) * 1.52
    _rect(s, 0.5, ty, 12.3, 0.52, NAVY)
    total_all = sum(p['total_qc'] for p in projects)
    overall_apr = round(sum(p['approved'] for p in projects) / total_all * 100) if total_all else 0
    _txt(s, "TOTAL / AVERAGE", 0.6, ty + 0.12, 3.3, 0.3, size=10, bold=True, color=WHITE)
    _txt(s, f"{total_all:,}", col_x[1] + 0.08, ty + 0.12, col_w[1], 0.3, size=10, bold=True, color=WHITE)
    _txt(s, f"{overall_apr}%", col_x[2] + 0.08, ty + 0.12, col_w[2], 0.3, size=10, bold=True, color=RGBColor(0x90, 0xFF, 0xD0))
    _txt(s, f"{sum(p['bc_total'] for p in projects)}", col_x[4] + 0.08, ty + 0.12, col_w[4], 0.3, size=10, bold=True, color=WHITE)
    _txt(s, f"{sum(p['li_total'] for p in projects)}", col_x[5] + 0.08, ty + 0.12, col_w[5], 0.3, size=10, bold=True, color=WHITE)


# ── Slide 3: QC Results Breakdown ──────────────────────────────────────────────

def slide_qc_breakdown(prs, projects):
    s = _blank(prs)
    _bg(s, WHITE)
    _header(s, "Quality Control Results", "Approval status and flag rates by project")

    col_w = 3.8
    for i, p in enumerate(projects):
        x = 0.5 + i * (col_w + 0.27)
        total = p['total_qc']
        apr = round(p['approved'] / total * 100) if total else 0
        flags = p['dur_flags'] + p['sl_flags']
        flag_rate = round(flags / total * 100) if total else 0

        _rect(s, x, 1.1, col_w, 6.2, LIGHT)
        _rect(s, x, 1.1, col_w, 0.06, TEAL if i == 0 else NAVY)
        name = p['project_name']
        short = name[:32] + '…' if len(name) > 32 else name
        _txt(s, short, x + 0.15, 1.2, col_w - 0.25, 0.38, size=9, bold=True, color=DARK)

        # Approval rate big number
        _txt(s, f"{apr}%", x + 0.15, 1.68, col_w - 0.25, 0.72,
             size=36, bold=True, color=TEAL if apr >= 80 else NAVY, align=PP_ALIGN.CENTER)
        _txt(s, "Approval Rate", x + 0.15, 2.4, col_w - 0.25, 0.3,
             size=9, color=GRAY, align=PP_ALIGN.CENTER)

        # Bars
        rows = [
            ("Approved", p['approved'], total, TEAL),
            ("Pending", p['pending'], total, NAVY),
            ("Cancelled", p['cancelled_qc'], total, GRAY),
        ]
        for j, (label, count, tot, color) in enumerate(rows):
            pct = count / tot if tot else 0
            ry = 2.82 + j * 0.78
            _txt(s, f"{label}: {count:,}", x + 0.15, ry, col_w - 0.25, 0.28, size=8.5, color=DARK)
            _rect(s, x + 0.15, ry + 0.3, max(0.04, (col_w - 0.4) * pct), 0.18, color)
            _txt(s, f"{round(pct*100)}%", x + 0.15 + (col_w - 0.5) * pct + 0.06,
                 ry + 0.28, 0.5, 0.22, size=7.5, color=color)

        # Flag section
        _rect(s, x + 0.15, 5.25, col_w - 0.3, 0.04, LINE)
        _txt(s, f"Flags: {flags} ({flag_rate}%)", x + 0.15, 5.38, col_w - 0.25, 0.3,
             size=9, bold=True, color=NAVY if flag_rate > 10 else GRAY)
        _txt(s, f"Duration: {p['dur_flags']}  ·  Straight-lining: {p['sl_flags']}",
             x + 0.15, 5.72, col_w - 0.25, 0.3, size=8.5, color=GRAY)
        _txt(s, f"Total records: {total:,}", x + 0.15, 6.1, col_w - 0.25, 0.3,
             size=8, color=GRAY, italic=True)


# ── Slide 4: Field Monitoring ───────────────────────────────────────────────────

def slide_field_monitoring(prs, projects):
    s = _blank(prs)
    _bg(s, WHITE)
    _header(s, "Field Monitoring", "Back-check and listen-in outcomes across all projects")

    # Backcheck section (left)
    _rect(s, 0.5, 1.1, 6.0, 5.9, LIGHT)
    _rect(s, 0.5, 1.1, 6.0, 0.06, NAVY)
    _txt(s, "Back-check Results", 0.7, 1.22, 5.5, 0.38, size=13, bold=True, color=DARK)

    bc_total = sum(p['bc_total'] for p in projects)
    bc_errors = sum(p['bc_errors'] for p in projects)
    bc_err_rate = round(bc_errors / bc_total * 100) if bc_total else 0

    _kpi(s, 0.65, 1.72, 1.7, 1.35, str(bc_total), "BC Records", NAVY)
    _kpi(s, 2.45, 1.72, 1.7, 1.35, str(bc_errors), "Errors", TEAL)
    _kpi(s, 4.25, 1.72, 1.7, 1.35, f"{bc_err_rate}%", "Error Rate", NAVY)

    _txt(s, "By Project:", 0.7, 3.22, 5.5, 0.28, size=9, bold=True, color=GRAY)
    for i, p in enumerate(projects):
        y = 3.55 + i * 0.78
        _rect(s, 0.65, y, 5.6, 0.68, WHITE if i % 2 == 0 else LIGHT)
        short = p['project_name'][:28] + '…' if len(p['project_name']) > 28 else p['project_name']
        _txt(s, short, 0.8, y + 0.15, 3.2, 0.35, size=8.5, color=DARK)
        _txt(s, f"{p['bc_total']} checks  ·  {p['bc_errors']} errors",
             4.0, y + 0.15, 2.0, 0.35, size=8.5, color=TEAL if p['bc_errors'] == 0 else NAVY)

    # Listen-in section (right)
    _rect(s, 6.9, 1.1, 6.0, 5.9, LIGHT)
    _rect(s, 6.9, 1.1, 6.0, 0.06, TEAL)
    _txt(s, "Listen-in Results", 7.1, 1.22, 5.5, 0.38, size=13, bold=True, color=DARK)

    li_total = sum(p['li_total'] for p in projects)
    li_pass = sum(p['li_pass'] for p in projects)
    li_fail = sum(p['li_fail'] for p in projects)
    li_pass_rate = round(li_pass / li_total * 100) if li_total else 0

    _kpi(s, 7.05, 1.72, 1.7, 1.35, str(li_total), "Sessions", TEAL)
    _kpi(s, 8.85, 1.72, 1.7, 1.35, f"{li_pass_rate}%", "Pass Rate", NAVY)
    _kpi(s, 10.65, 1.72, 1.7, 1.35, str(li_fail), "Failed", TEAL)

    _txt(s, "By Project:", 7.1, 3.22, 5.5, 0.28, size=9, bold=True, color=GRAY)
    for i, p in enumerate(projects):
        y = 3.55 + i * 0.78
        _rect(s, 7.05, y, 5.6, 0.68, WHITE if i % 2 == 0 else LIGHT)
        short = p['project_name'][:28] + '…' if len(p['project_name']) > 28 else p['project_name']
        _txt(s, short, 7.2, y + 0.15, 3.2, 0.35, size=8.5, color=DARK)
        pr = round(p['li_pass'] / p['li_total'] * 100) if p['li_total'] else 0
        _txt(s, f"{p['li_total']} sessions  ·  {pr}% pass",
             10.2, y + 0.15, 1.6, 0.35, size=8.5, color=TEAL if pr >= 80 else NAVY)

    # Divider note
    _txt(s, f"Total interviewers monitored: {sum(p['interviewer_count'] for p in projects)}  ·  "
         f"Cancelled interviews: {sum(p.get('cancelled_total', 0) for p in projects)}",
         0.5, 7.1, 12.3, 0.3, size=9, color=GRAY, italic=True, align=PP_ALIGN.CENTER)


# ── Slide 5: Interviewer Performance ───────────────────────────────────────────

def slide_interviewers(prs, projects):
    s = _blank(prs)
    _bg(s, WHITE)
    _header(s, "Interviewer Performance", "Flag rates and field output — highest-flag performers highlighted")

    all_itvs = []
    for p in projects:
        for itv in p.get('interviewers', []):
            all_itvs.append({**itv, 'project': p['project_name']})

    top_flagged = sorted(all_itvs, key=lambda x: x.get('flags', 0), reverse=True)[:8]
    top_clean = sorted(all_itvs, key=lambda x: x.get('flags', 0))[:8]

    def _panel(x, w, title, color, items, flag_color):
        _rect(s, x, 1.1, w, 6.2, LIGHT)
        _rect(s, x, 1.1, w, 0.06, color)
        _txt(s, title, x + 0.18, 1.22, w - 0.3, 0.38, size=12, bold=True, color=DARK)
        headers = ["Interviewer", "Project", "Completes", "Flags", "Flag %"]
        hx = [x + 0.18, x + 1.6, x + 3.3, x + 4.3, x + 5.0]
        hw = [1.35, 1.65, 0.85, 0.65, 0.7]
        for h, hxi, hwi in zip(headers, hx, hw):
            _txt(s, h, hxi, 1.65, hwi, 0.28, size=8, bold=True, color=GRAY)
        _rect(s, x + 0.18, 1.96, w - 0.32, 0.04, LINE)
        for i, itv in enumerate(items):
            ry = 2.06 + i * 0.74
            bg = WHITE if i % 2 == 0 else LIGHT
            _rect(s, x + 0.18, ry, w - 0.32, 0.68, bg)
            comp = itv.get('completes', 0)
            flags = itv.get('flags', 0)
            pct = round(flags / comp * 100) if comp else 0
            short_proj = itv['project'][:20] + '…' if len(itv['project']) > 20 else itv['project']
            vals = [itv.get('name', '?'), short_proj, str(comp), str(flags), f"{pct}%"]
            colors = [DARK, GRAY, DARK, flag_color if flags > 0 else GRAY, flag_color if flags > 0 else GRAY]
            for v, hxi, hwi, vc in zip(vals, hx, hw, colors):
                _txt(s, v, hxi, ry + 0.2, hwi, 0.3, size=8.5, bold=(vals.index(v) == 0), color=vc)

    _panel(0.5, 6.15, "Highest Flag Rate (Needs Attention)", NAVY, top_flagged, NAVY)
    _panel(6.85, 6.15, "Clean Performance (Lowest Flags)", TEAL, top_clean, TEAL)


# ── Slide 6: Key Findings ───────────────────────────────────────────────────────

def slide_findings(prs, projects):
    s = _blank(prs)
    _bg(s, WHITE)
    _header(s, "Key Findings & Recommendations",
            f"Summary across 3 projects  ·  {date.today().strftime('%d %B %Y')}")

    total_all = sum(p['total_qc'] for p in projects)
    apr_all = round(sum(p['approved'] for p in projects) / total_all * 100) if total_all else 0
    flags_all = sum(p['dur_flags'] + p['sl_flags'] for p in projects)
    flag_rate_all = round(flags_all / total_all * 100) if total_all else 0
    li_all = sum(p['li_total'] for p in projects)
    li_pass_rate = round(sum(p['li_pass'] for p in projects) / li_all * 100) if li_all else 0
    bc_all = sum(p['bc_total'] for p in projects)
    bc_err_all = sum(p['bc_errors'] for p in projects)
    bc_err_rate = round(bc_err_all / bc_all * 100) if bc_all else 0

    findings = [
        (
            "Overall Approval Rate" + (" ✓" if apr_all >= 80 else " ⚠"),
            f"{apr_all}% across {total_all:,} records — "
            + ("above 80% benchmark" if apr_all >= 80 else "below 80% target — needs review"),
            TEAL if apr_all >= 80 else NAVY,
        ),
        (
            "Flag Rate",
            f"{flag_rate_all}% flagged ({flags_all:,} records) — "
            + ("within acceptable range" if flag_rate_all <= 10 else "elevated, investigate duration and straightlining"),
            TEAL if flag_rate_all <= 10 else NAVY,
        ),
        (
            "Back-check Coverage",
            f"{bc_all} records verified · {bc_err_rate}% error rate detected. "
            + ("Error rate is high — increase BC coverage" if bc_err_rate > 15 else "Error rate acceptable"),
            NAVY if bc_err_rate > 15 else TEAL,
        ),
        (
            "Listen-in Performance",
            f"{li_all} sessions completed · {li_pass_rate}% pass rate. "
            + ("All supervisors meeting quality standards" if li_pass_rate >= 80 else "Some sessions below standard — follow-up required"),
            TEAL if li_pass_rate >= 80 else NAVY,
        ),
        (
            "Recommended Actions",
            "1) Review interviewers with flag rates >15%   "
            "2) Ensure backcheck coverage ≥10% per interviewer   "
            "3) Escalate any listen-in fails to project managers",
            NAVY,
        ),
        (
            "Next Steps",
            "Monitor project progress via the live QC dashboard. "
            "Wave closures require sign-off from QC Executive before data is released to the client.",
            TEAL,
        ),
    ]

    # Summary KPIs at top
    _kpi(s, 0.5, 1.1, 2.8, 1.35, f"{apr_all}%", "Avg Approval Rate", TEAL)
    _kpi(s, 3.5, 1.1, 2.8, 1.35, f"{flag_rate_all}%", "Flag Rate", NAVY)
    _kpi(s, 6.5, 1.1, 2.8, 1.35, f"{bc_err_rate}%", "BC Error Rate", NAVY if bc_err_rate > 15 else TEAL)
    _kpi(s, 9.5, 1.1, 2.8, 1.35, f"{li_pass_rate}%", "Listen-in Pass Rate", TEAL)

    for i, (title, body, color) in enumerate(findings):
        col, row = i % 2, i // 2
        x = 0.5 + col * 6.3
        y = 2.65 + row * 1.52
        _rect(s, x, y, 6.0, 1.38, LIGHT)
        _rect(s, x, y, 6.0, 0.06, color)
        _txt(s, title, x + 0.18, y + 0.14, 5.6, 0.38, size=11, bold=True, color=color)
        _txt(s, body, x + 0.18, y + 0.56, 5.6, 0.76, size=9, color=DARK)


# ── Build ───────────────────────────────────────────────────────────────────────

def build():
    from ppt_generator import _fetch_data

    print("Fetching project data…")
    projects = []
    for pid in [1, 2, 3]:
        try:
            d = _fetch_data(pid)
            projects.append(d)
            print(f"  ✓ {d['project_name']}: {d['total_qc']} QC records")
        except Exception as e:
            print(f"  ✗ Project {pid}: {e}")

    if not projects:
        print("No data — aborting")
        return

    prs = _prs()
    slide_title(prs)
    slide_portfolio(prs, projects)
    slide_qc_breakdown(prs, projects)
    slide_field_monitoring(prs, projects)
    slide_interviewers(prs, projects)
    slide_findings(prs, projects)

    out = "QC_Dashboard_Meeting_Presentation.pptx"
    prs.save(out)
    print(f"\nSaved {len(prs.slides)} slides → {out}")


if __name__ == "__main__":
    build()
