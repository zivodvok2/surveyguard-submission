"""
Live QC project PPT generator — pulls data from DB and builds Ipsos-branded PPTX.
"""

import io
from datetime import date
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN

# ── Ipsos palette ──────────────────────────────────────────────────────────────
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
    _txt(slide, value, x + 0.1, y + 0.18, w - 0.2, 0.65,
         size=34, bold=True, color=color, align=PP_ALIGN.CENTER)
    _txt(slide, label, x + 0.1, y + 0.85, w - 0.2, 0.42,
         size=10, color=GRAY, align=PP_ALIGN.CENTER)


def _bar_row(slide, x, y, label, value, pct, bar_w, color):
    _txt(slide, label, x, y, 2.8, 0.32, size=9, color=DARK)
    _txt(slide, str(value), x + 2.85, y, 0.5, 0.32, size=9, bold=True, color=color)
    if bar_w > 0:
        max_bar = 6.0
        _rect(slide, x + 3.45, y + 0.05, max_bar * pct, 0.22, color)
    _txt(slide, f"{round(pct * 100)}%", x + 3.5 + bar_w, y, 0.7, 0.32,
         size=9, color=GRAY)


# ── Slides ─────────────────────────────────────────────────────────────────────

def slide_title(prs, project_name):
    s = _blank(prs)
    _bg(s, WHITE)
    _rect(s, 0, 0, 13.33, 3.8, NAVY)
    _rect(s, 0, 3.8, 13.33, 0.07, TEAL)
    _txt(s, "QC Project Report", 0.7, 0.55, 12, 0.9,
         size=48, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
    _txt(s, project_name, 0.7, 1.6, 12, 0.65,
         size=22, color=RGBColor(0xCC, 0xDD, 0xFF), align=PP_ALIGN.CENTER)
    _txt(s, f"Generated: {date.today().strftime('%d %B %Y')}",
         0.7, 2.35, 12, 0.38, size=12, color=GRAY, align=PP_ALIGN.CENTER, italic=True)
    _txt(s, "Confidential  ·  Quality Control Division",
         0.7, 4.1, 12, 0.4, size=13, bold=True, color=NAVY, align=PP_ALIGN.CENTER)


def slide_executive_summary(prs, data):
    s = _blank(prs)
    _bg(s, WHITE)
    _header(s, "Executive Summary", f"Project: {data['project_name']}")

    total_qc = data['total_qc']
    approved = data['approved']
    flags = data['dur_flags'] + data['sl_flags']
    approval_rate = round(approved / total_qc * 100) if total_qc else 0

    _kpi(s, 0.5, 1.1, 2.9, 1.55, str(total_qc), "QC Records", NAVY)
    _kpi(s, 3.6, 1.1, 2.9, 1.55, f"{approval_rate}%", "Approval Rate", TEAL)
    _kpi(s, 6.7, 1.1, 2.9, 1.55, str(flags), "Total Flags", NAVY)
    _kpi(s, 9.8, 1.1, 2.9, 1.55, str(data['bc_total'] + data['li_total']),
         "BC + Listen-in", TEAL)

    _rect(s, 0.5, 2.9, 12.3, 0.05, TEAL)
    _txt(s, "Field Monitoring at a Glance", 0.5, 3.05, 12.3, 0.4,
         size=13, bold=True, color=NAVY)

    summary_items = [
        (f"{data['bc_total']} backchecks", f"completed — {data['bc_errors']} errors detected"),
        (f"{data['li_total']} listen-in sessions", f"conducted — {data['li_pass_rate']}% pass rate"),
        (f"{data['cancelled_total']} cancelled interviews", "logged across all interviewers"),
        (f"{data['interviewer_count']} interviewers", "active on this project"),
    ]
    for i, (bold_part, rest) in enumerate(summary_items):
        col, row = i % 2, i // 2
        x, y = 0.5 + col * 6.3, 3.55 + row * 0.9
        _rect(s, x, y, 6.0, 0.78, LIGHT)
        _rect(s, x, y, 6.0, 0.05, TEAL if col == 0 else NAVY)
        _txt(s, bold_part + " " + rest, x + 0.2, y + 0.18, 5.7, 0.5, size=11, color=DARK)

    _txt(s, f"Flags: {data['dur_flags']} duration  ·  {data['sl_flags']} straight-lining",
         0.5, 5.5, 12.3, 0.35, size=10, color=GRAY, italic=True)


def slide_qc_results(prs, data):
    s = _blank(prs)
    _bg(s, WHITE)
    _header(s, "Quality Control Results", "Approval status and flag breakdown")

    total = data['total_qc']
    approved = data['approved']
    pending = data['pending']
    cancelled_qc = data['cancelled_qc']
    dur_flags = data['dur_flags']
    sl_flags = data['sl_flags']

    # Left panel — approval breakdown
    _rect(s, 0.5, 1.1, 5.9, 5.9, LIGHT)
    _rect(s, 0.5, 1.1, 5.9, 0.06, TEAL)
    _txt(s, "Approval Status", 0.7, 1.22, 5.5, 0.4, size=13, bold=True, color=DARK)

    items = [
        ("Approved", approved, TEAL),
        ("Pending", pending, NAVY),
        ("Cancelled", cancelled_qc, GRAY),
    ]
    for i, (label, count, color) in enumerate(items):
        pct = count / total if total else 0
        y = 1.75 + i * 1.55
        _rect(s, 0.65, y, 5.6, 1.35, WHITE)
        _txt(s, label, 0.8, y + 0.1, 3.0, 0.38, size=12, bold=True, color=color)
        _txt(s, f"{count:,}", 0.8, y + 0.52, 2.0, 0.55, size=28, bold=True, color=color)
        _txt(s, f"of {total:,} records ({round(pct*100)}%)",
             2.5, y + 0.62, 3.5, 0.35, size=10, color=GRAY)
        _rect(s, 0.65, y + 1.2, 5.6 * pct, 0.08, color)

    # Right panel — flag breakdown
    _rect(s, 6.9, 1.1, 5.9, 5.9, LIGHT)
    _rect(s, 6.9, 1.1, 5.9, 0.06, NAVY)
    _txt(s, "QC Flag Breakdown", 7.1, 1.22, 5.5, 0.4, size=13, bold=True, color=DARK)

    flag_items = [
        ("Duration Flag", dur_flags, NAVY),
        ("Straight-lining", sl_flags, TEAL),
        ("Combined Flag Rate", dur_flags + sl_flags, GRAY),
    ]
    for i, (label, count, color) in enumerate(flag_items):
        pct = count / total if total else 0
        y = 1.75 + i * 1.55
        _rect(s, 7.05, y, 5.6, 1.35, WHITE)
        _txt(s, label, 7.2, y + 0.1, 4.0, 0.38, size=12, bold=True, color=color)
        _txt(s, f"{count:,}", 7.2, y + 0.52, 2.0, 0.55, size=28, bold=True, color=color)
        _txt(s, f"{round(pct*100)}% of total records",
             9.0, y + 0.62, 2.8, 0.35, size=10, color=GRAY)
        _rect(s, 7.05, y + 1.2, 5.6 * pct, 0.08, color)


def slide_interviewer_performance(prs, data):
    s = _blank(prs)
    _bg(s, WHITE)
    _header(s, "Interviewer Performance", "Flag rates and field output by interviewer")

    interviewers = data.get('interviewers', [])
    if not interviewers:
        _txt(s, "No interviewer data available for this project.",
             0.5, 2.5, 12.3, 0.5, size=14, color=GRAY, align=PP_ALIGN.CENTER)
        return

    sorted_itv = sorted(interviewers, key=lambda x: x.get('flags', 0), reverse=True)
    top5 = sorted_itv[:5]
    bottom5 = sorted(interviewers, key=lambda x: x.get('flags', 0))[:5]

    def _itv_panel(x, title, color, items):
        _rect(s, x, 1.1, 5.9, 5.9, LIGHT)
        _rect(s, x, 1.1, 5.9, 0.06, color)
        _txt(s, title, x + 0.2, 1.22, 5.5, 0.4, size=13, bold=True, color=DARK)
        headers = ['Interviewer', 'Completes', 'Flags', 'Flag %']
        col_w = [2.5, 1.0, 0.9, 0.9]
        col_x = [x + 0.2, x + 2.8, x + 3.9, x + 4.85]
        for j, (h, cx) in enumerate(zip(headers, col_x)):
            _txt(s, h, cx, 1.72, col_w[j], 0.3, size=9, bold=True, color=GRAY)
        _rect(s, x + 0.2, 2.05, 5.5, 0.04, LINE)
        for i, itv in enumerate(items[:5]):
            y = 2.15 + i * 0.88
            bg = WHITE if i % 2 == 0 else LIGHT
            _rect(s, x + 0.2, y, 5.5, 0.82, bg)
            completes = itv.get('completes', itv.get('interviews', 0))
            flags = itv.get('flags', 0)
            flag_pct = round(flags / completes * 100) if completes else 0
            vals = [itv.get('name', '—'), str(completes), str(flags), f"{flag_pct}%"]
            row_colors = [DARK, DARK, color if flags > 0 else GRAY, color if flags > 0 else GRAY]
            for j, (v, cx) in enumerate(zip(vals, col_x)):
                _txt(s, v, cx, y + 0.22, col_w[j], 0.36,
                     size=9, bold=(j == 0), color=row_colors[j])

    _itv_panel(0.5, "Highest Flag Rate (Attention Required)", NAVY, top5)
    _itv_panel(6.9, "Lowest Flag Rate (Strong Performers)", TEAL, bottom5)


def slide_backcheck(prs, data):
    s = _blank(prs)
    _bg(s, WHITE)
    _header(s, "Back-check Analysis", "Error type breakdown and field verification results")

    bc_total = data['bc_total']
    bc_errors = data['bc_errors']

    _kpi(s, 0.5, 1.1, 2.9, 1.55, str(bc_total), "BC Records", NAVY)
    _kpi(s, 3.6, 1.1, 2.9, 1.55, str(bc_errors), "Errors Found", TEAL)
    err_rate = round(bc_errors / bc_total * 100) if bc_total else 0
    _kpi(s, 6.7, 1.1, 2.9, 1.55, f"{err_rate}%", "Error Rate", NAVY)
    _kpi(s, 9.8, 1.1, 2.9, 1.55, str(data.get('bc_unique_interviewers', 0)),
         "Interviewers Checked", TEAL)

    BACKCHECK_LABELS = {
        'error_01': 'Fraudulent', 'error_02': 'Wrong respondent',
        'error_03': 'Wrong quotas', 'error_04': 'Wrong usership',
        'error_05': 'Wrong phone', 'error_06': 'Unattainable',
        'error_07': 'Answerphone', 'error_08': 'Refused',
        "error_09": "Doesn't remember", 'error_10': 'BC abandoned',
        'error_11': 'Wrong mode', 'error_12': 'Voice permission',
        'error_13': 'Already participated',
    }

    error_counts = data.get('bc_error_breakdown', {})
    sorted_errors = sorted(error_counts.items(), key=lambda x: x[1], reverse=True)[:8]
    max_err = sorted_errors[0][1] if sorted_errors else 1

    _rect(s, 0.5, 2.9, 12.3, 0.38, LIGHT)
    _rect(s, 0.5, 2.9, 12.3, 0.05, TEAL)
    _txt(s, "Top Error Types", 0.7, 2.97, 12.0, 0.28, size=12, bold=True, color=DARK)

    for i, (key, count) in enumerate(sorted_errors):
        col, row = i % 2, i // 2
        x = 0.5 + col * 6.3
        y = 3.42 + row * 0.82
        label = BACKCHECK_LABELS.get(key, key)
        pct = count / max_err if max_err else 0
        _rect(s, x, y, 6.0, 0.72, LIGHT if row % 2 == 0 else WHITE)
        _txt(s, label, x + 0.15, y + 0.12, 3.2, 0.32, size=9, color=DARK)
        _txt(s, str(count), x + 3.4, y + 0.12, 0.6, 0.32, size=9, bold=True, color=NAVY)
        _rect(s, x + 4.1, y + 0.22, max(0.05, 1.7 * pct), 0.22, TEAL)


def slide_listenin(prs, data):
    s = _blank(prs)
    _bg(s, WHITE)
    _header(s, "Listen-in & Field Monitoring", "Supervisor monitoring sessions and pass/fail outcomes")

    li_total = data['li_total']
    li_pass = data['li_pass']
    li_fail = data['li_fail']
    li_partial = data['li_partial']
    pass_rate = round(li_pass / li_total * 100) if li_total else 0

    _kpi(s, 0.5, 1.1, 2.9, 1.55, str(li_total), "Sessions", NAVY)
    _kpi(s, 3.6, 1.1, 2.9, 1.55, f"{pass_rate}%", "Pass Rate", TEAL)
    _kpi(s, 6.7, 1.1, 2.9, 1.55, str(li_pass), "Pass", TEAL)
    _kpi(s, 9.8, 1.1, 2.9, 1.55, str(li_fail), "Fail", NAVY)

    _rect(s, 0.5, 2.9, 12.3, 0.05, TEAL)
    _txt(s, "Result Breakdown", 0.5, 3.05, 12.3, 0.38,
         size=13, bold=True, color=DARK)

    results = [
        ("Pass", li_pass, TEAL, "Interviewer met quality standards"),
        ("Partial", li_partial, NAVY, "Minor issues noted — follow-up required"),
        ("Fail", li_fail, GRAY, "Significant issues — corrective action needed"),
    ]
    for i, (label, count, color, desc) in enumerate(results):
        y = 3.58 + i * 1.12
        _rect(s, 0.5, y, 12.3, 1.0, LIGHT)
        _rect(s, 0.5, y, 12.3, 0.05, color)
        _txt(s, label, 0.7, y + 0.12, 1.5, 0.38, size=12, bold=True, color=color)
        _txt(s, str(count), 2.3, y + 0.12, 1.2, 0.38, size=20, bold=True, color=color)
        pct_bar = count / li_total if li_total else 0
        _rect(s, 3.8, y + 0.28, max(0.05, 6.5 * pct_bar), 0.28, color)
        _txt(s, f"{round(pct_bar*100)}%  —  {desc}",
             3.8, y + 0.6, 8.5, 0.3, size=9, color=GRAY)


def slide_key_findings(prs, data):
    s = _blank(prs)
    _bg(s, WHITE)
    _header(s, "Key Findings & Recommendations",
            f"Project: {data['project_name']}  ·  Report Date: {date.today().strftime('%d %B %Y')}")

    total = data['total_qc']
    approval_rate = round(data['approved'] / total * 100) if total else 0
    flag_rate = round((data['dur_flags'] + data['sl_flags']) / total * 100) if total else 0
    pass_rate = data['li_pass_rate']

    findings = []
    if approval_rate >= 80:
        findings.append(("Strong Approval Rate",
                          f"{approval_rate}% of QC records approved — above the 80% benchmark.",
                          TEAL))
    else:
        findings.append(("Low Approval Rate",
                          f"Only {approval_rate}% approved. Review pending/cancelled interviews urgently.",
                          NAVY))

    if flag_rate > 10:
        findings.append(("Elevated Flag Rate",
                          f"{flag_rate}% of records flagged for duration or straight-lining issues.",
                          NAVY))
    else:
        findings.append(("Flag Rate Within Threshold",
                          f"Flag rate at {flag_rate}% — within acceptable limits.",
                          TEAL))

    if data['bc_total'] > 0:
        err_rate = round(data['bc_errors'] / data['bc_total'] * 100)
        findings.append(("Back-check Results",
                          f"{data['bc_total']} records checked, {err_rate}% error rate. "
                          f"Top issues: {', '.join(list(data.get('bc_top_errors', ['N/A']))[:2])}.",
                          NAVY if err_rate > 15 else TEAL))

    if data['li_total'] > 0:
        findings.append(("Listen-in Coverage",
                          f"{data['li_total']} sessions completed. Pass rate: {pass_rate}%. "
                          + ("Action needed on failed sessions." if data['li_fail'] > 0 else "All sessions passed."),
                          TEAL))

    findings.append(("Interviewer Oversight",
                      f"{data['interviewer_count']} interviewers active. "
                      f"Review the Interviewer Performance tab for flagged individuals.",
                      NAVY))

    _rect(s, 0.5, 1.1, 12.3, 0.35, LIGHT)
    _txt(s, f"Based on {total:,} QC records — {data['project_name']}",
         0.7, 1.17, 12.0, 0.25, size=10, color=GRAY, italic=True)

    for i, (title, body, color) in enumerate(findings[:6]):
        col, row = i % 2, i // 2
        x = 0.5 + col * 6.3
        y = 1.6 + row * 1.82
        _rect(s, x, y, 6.0, 1.65, LIGHT)
        _rect(s, x, y, 6.0, 0.06, color)
        _txt(s, title, x + 0.18, y + 0.14, 5.6, 0.38, size=11, bold=True, color=color)
        _txt(s, body, x + 0.18, y + 0.56, 5.6, 1.0, size=9, color=DARK)


# ── Main builder ───────────────────────────────────────────────────────────────

def build_project_ppt(project_id: int) -> bytes:
    import shared_db

    data = _fetch_data(project_id)
    prs = _prs()

    slide_title(prs, data['project_name'])
    slide_executive_summary(prs, data)
    slide_qc_results(prs, data)
    slide_interviewer_performance(prs, data)
    slide_backcheck(prs, data)
    slide_listenin(prs, data)
    slide_key_findings(prs, data)

    buf = io.BytesIO()
    prs.save(buf)
    return buf.getvalue()


def _fetch_data(project_id: int) -> dict:
    import shared_db

    conn = shared_db.get_conn()
    try:
        # Project name
        cur = conn.execute("SELECT name FROM projects WHERE id = %s", (project_id,))
        row = cur.fetchone()
        project_name = row['name'] if row else f"Project {project_id}"

        # QC records
        cur = conn.execute("""
            SELECT approval_status, duration_flag, straight_lining, interviewer_id
            FROM quality_report_records WHERE project_id = %s
        """, (project_id,))
        qc_rows = cur.fetchall()
        total_qc = len(qc_rows)
        approved = sum(1 for r in qc_rows if r['approval_status'] == 'Approved')
        pending = sum(1 for r in qc_rows if r['approval_status'] == 'Pending')
        cancelled_qc = sum(1 for r in qc_rows if r['approval_status'] == 'Cancelled')
        dur_flags = sum(1 for r in qc_rows if r['duration_flag'] == 'Flag')
        sl_flags = sum(1 for r in qc_rows if r['straight_lining'] == 'Flag')

        # Per-interviewer QC aggregation
        itv_map: dict = {}
        for r in qc_rows:
            itv_id = r['interviewer_id']
            if not itv_id:
                continue
            if itv_id not in itv_map:
                itv_map[itv_id] = {'name': itv_id, 'completes': 0, 'flags': 0}
            itv_map[itv_id]['completes'] += 1
            if r['duration_flag'] == 'Flag' or r['straight_lining'] == 'Flag':
                itv_map[itv_id]['flags'] += 1

        # Performance records (for completes)
        cur = conn.execute("""
            SELECT interviewer_id, interview_completes
            FROM performance_records WHERE project_id = %s
        """, (project_id,))
        for r in cur.fetchall():
            itv_id = r['interviewer_id']
            if itv_id not in itv_map:
                itv_map[itv_id] = {'name': itv_id, 'completes': 0, 'flags': 0}
            if r['interview_completes']:
                itv_map[itv_id]['completes'] = r['interview_completes']

        # Backcheck records
        error_cols = [f"error_{str(i).zfill(2)}" for i in range(1, 14)]
        cur = conn.execute(f"""
            SELECT interviewer_id, {', '.join(error_cols)}
            FROM backcheck_records WHERE project_id = %s
        """, (project_id,))
        bc_rows = cur.fetchall()
        bc_total = len(bc_rows)
        bc_error_breakdown: dict = {}
        bc_unique_interviewers: set = set()
        for r in bc_rows:
            itv_id = r.get('interviewer_id')
            if itv_id:
                bc_unique_interviewers.add(itv_id)
            for col in error_cols:
                val = r.get(col) or 0
                if val > 0:
                    bc_error_breakdown[col] = bc_error_breakdown.get(col, 0) + val
        bc_errors = sum(bc_error_breakdown.values())

        BACKCHECK_LABELS = {
            'error_01': 'Fraudulent', 'error_02': 'Wrong respondent',
            'error_03': 'Wrong quotas', 'error_04': 'Wrong usership',
            'error_05': 'Wrong phone', 'error_06': 'Unattainable',
            'error_07': 'Answerphone', 'error_08': 'Refused',
            'error_09': "Doesn't remember", 'error_10': 'BC abandoned',
            'error_11': 'Wrong mode', 'error_12': 'Voice permission',
            'error_13': 'Already participated',
        }
        bc_top_errors = [
            BACKCHECK_LABELS.get(k, k)
            for k, _ in sorted(bc_error_breakdown.items(), key=lambda x: x[1], reverse=True)[:3]
        ]

        # Listen-in records
        cur = conn.execute(
            "SELECT result FROM listen_in_records WHERE project_id = %s", (project_id,)
        )
        li_rows = cur.fetchall()
        li_total = len(li_rows)
        li_pass = sum(1 for r in li_rows if r['result'] == 'Pass')
        li_fail = sum(1 for r in li_rows if r['result'] == 'Fail')
        li_partial = sum(1 for r in li_rows if r['result'] == 'Partial')
        li_pass_rate = round(li_pass / li_total * 100) if li_total else 0

        # Cancelled
        cur = conn.execute(
            "SELECT COUNT(*) AS cnt FROM cancelled_interview_records WHERE project_id = %s", (project_id,)
        )
        row = cur.fetchone()
        cancelled_total = row['cnt'] if row else 0

    finally:
        conn.close()

    return {
        'project_name': project_name,
        'total_qc': total_qc,
        'approved': approved,
        'pending': pending,
        'cancelled_qc': cancelled_qc,
        'dur_flags': dur_flags,
        'sl_flags': sl_flags,
        'interviewers': list(itv_map.values()),
        'interviewer_count': len(itv_map),
        'bc_total': bc_total,
        'bc_errors': bc_errors,
        'bc_error_breakdown': bc_error_breakdown,
        'bc_unique_interviewers': len(bc_unique_interviewers),
        'bc_top_errors': bc_top_errors,
        'li_total': li_total,
        'li_pass': li_pass,
        'li_fail': li_fail,
        'li_partial': li_partial,
        'li_pass_rate': li_pass_rate,
        'cancelled_total': cancelled_total,
    }
