from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt
import copy

# ── Brand colours ──────────────────────────────────────────────────────────────
NAVY   = RGBColor(0x0A, 0x1F, 0x44)   # deep navy
BLUE   = RGBColor(0x00, 0x5B, 0xB5)   # ipsos blue
TEAL   = RGBColor(0x00, 0x99, 0x9A)   # accent teal
WHITE  = RGBColor(0xFF, 0xFF, 0xFF)
LGREY  = RGBColor(0xF4, 0xF6, 0xF9)
DGREY  = RGBColor(0x55, 0x65, 0x7A)

prs = Presentation()
prs.slide_width  = Inches(13.33)
prs.slide_height = Inches(7.5)

BLANK = prs.slide_layouts[6]  # completely blank


# ── Helpers ────────────────────────────────────────────────────────────────────

def add_rect(slide, l, t, w, h, fill, alpha=None):
    shape = slide.shapes.add_shape(1, Inches(l), Inches(t), Inches(w), Inches(h))
    shape.line.fill.background()
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill
    return shape

def add_text(slide, text, l, t, w, h, size, bold=False, color=WHITE,
             align=PP_ALIGN.LEFT, italic=False, wrap=True):
    txb = slide.shapes.add_textbox(Inches(l), Inches(t), Inches(w), Inches(h))
    txb.word_wrap = wrap
    tf = txb.text_frame
    tf.word_wrap = wrap
    p = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = text
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    run.font.color.rgb = color
    return txb

def add_bullet_box(slide, items, l, t, w, h, size=13, color=NAVY, title=None, title_color=BLUE):
    txb = slide.shapes.add_textbox(Inches(l), Inches(t), Inches(w), Inches(h))
    txb.word_wrap = True
    tf = txb.text_frame
    tf.word_wrap = True
    first = True
    if title:
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        p.alignment = PP_ALIGN.LEFT
        run = p.add_run()
        run.text = title
        run.font.size = Pt(size + 1)
        run.font.bold = True
        run.font.color.rgb = title_color
    for item in items:
        p = tf.paragraphs[0] if (first and not title) else tf.add_paragraph()
        first = False
        p.alignment = PP_ALIGN.LEFT
        run = p.add_run()
        run.text = f"  {item}"
        run.font.size = Pt(size)
        run.font.color.rgb = color

def header_bar(slide, label=""):
    add_rect(slide, 0, 0, 13.33, 0.7, NAVY)
    add_rect(slide, 0, 0.7, 13.33, 0.06, TEAL)
    if label:
        add_text(slide, label, 0.4, 0.1, 12, 0.5, 20, bold=True, color=WHITE)

def footer(slide, page_num):
    add_rect(slide, 0, 7.1, 13.33, 0.4, NAVY)
    add_text(slide, "Ipsos QC Engine — Confidential User Guide", 0.3, 7.12, 9, 0.3, 8, color=RGBColor(0xAA,0xBB,0xCC))
    add_text(slide, str(page_num), 12.5, 7.12, 0.6, 0.3, 8, color=WHITE, align=PP_ALIGN.RIGHT)

def section_label(slide, text):
    add_rect(slide, 0, 0.76, 0.22, 0.8, TEAL)
    add_text(slide, text, 0.35, 0.82, 5, 0.5, 11, color=DGREY, bold=False, italic=True)

# ══════════════════════════════════════════════════════════════════════════════
# SLIDE 1 — Title
# ══════════════════════════════════════════════════════════════════════════════
slide = prs.slides.add_slide(BLANK)
add_rect(slide, 0, 0, 13.33, 7.5, NAVY)
add_rect(slide, 0, 0, 13.33, 0.12, TEAL)
add_rect(slide, 0, 7.38, 13.33, 0.12, TEAL)
add_rect(slide, 9.5, 1.2, 3.5, 5.8, BLUE)

add_text(slide, "QC ENGINE", 0.6, 1.8, 8.5, 1.0, 48, bold=True, color=WHITE)
add_text(slide, "& MANAGER DASHBOARD", 0.6, 2.75, 8.5, 0.8, 28, bold=False, color=TEAL)
add_text(slide, "User Guide", 0.6, 3.55, 8.5, 0.7, 22, color=RGBColor(0xCC,0xDD,0xEE))
add_text(slide, "Confidential  ·  Ipsos", 0.6, 6.6, 8, 0.5, 10, color=RGBColor(0x88,0x99,0xAA))

# decorative lines
for i, y in enumerate([4.6, 4.72, 4.84]):
    w = [3.5, 2.0, 1.0][i]
    add_rect(slide, 0.6, y, w, 0.06, TEAL)

# ══════════════════════════════════════════════════════════════════════════════
# SLIDE 2 — Table of Contents
# ══════════════════════════════════════════════════════════════════════════════
slide = prs.slides.add_slide(BLANK)
add_rect(slide, 0, 0, 13.33, 7.5, LGREY)
header_bar(slide, "Contents")
footer(slide, 2)

sections = [
    ("01", "System Overview",          "How the two products connect"),
    ("02", "QC Engine — Getting Started", "Uploading data and configuring checks"),
    ("03", "QC Engine — Results Tabs",  "Reading every output tab"),
    ("04", "Manager Dashboard — Login", "Accessing the dashboard and roles"),
    ("05", "Manager Dashboard — Projects", "Creating and managing survey projects"),
    ("06", "Manager Dashboard — Quality Records", "Logging QC, backcheck, listen-in data"),
    ("07", "Manager Dashboard — Reports", "Performance, timing, and wave reports"),
    ("08", "Getting Started",           "Access, browser requirements, and setup"),
]

for i, (num, title, sub) in enumerate(sections):
    col = 0 if i < 4 else 6.7
    row = i % 4
    y = 1.05 + row * 1.45

    add_rect(slide, col + 0.35, y, 0.62, 0.62, BLUE)
    add_text(slide, num, col + 0.35, y + 0.08, 0.62, 0.5, 16, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
    add_text(slide, title, col + 1.1, y + 0.04, 5.2, 0.35, 13, bold=True, color=NAVY)
    add_text(slide, sub,   col + 1.1, y + 0.38, 5.2, 0.28, 10, color=DGREY)

# ══════════════════════════════════════════════════════════════════════════════
# SLIDE 3 — System Overview
# ══════════════════════════════════════════════════════════════════════════════
slide = prs.slides.add_slide(BLANK)
add_rect(slide, 0, 0, 13.33, 7.5, LGREY)
header_bar(slide, "01  ·  System Overview")
section_label(slide, "Architecture")
footer(slide, 3)

boxes = [
    (1.5,  1.8, 4.5, 3.8, BLUE,  "QC Engine",
     ["React web app", "Upload CSV / XLSX / SAV", "Run automated checks", "View results instantly", "No installation needed"]),
    (7.3,  1.8, 4.5, 3.8, NAVY,  "Manager Dashboard",
     ["React web app", "Project management", "Quality record logs", "Interviewer tracking", "Accessible from any browser"]),
]

for bx, by, bw, bh, col, title, pts in boxes:
    add_rect(slide, bx, by, bw, bh, col)
    add_text(slide, title, bx+0.15, by+0.15, bw-0.3, 0.6, 14, bold=True, color=WHITE)
    for j, pt in enumerate(pts):
        add_text(slide, f"• {pt}", bx+0.15, by+0.9+j*0.52, bw-0.3, 0.48, 11, color=WHITE)

add_text(slide, "→", 6.2, 3.2, 0.8, 0.5, 26, bold=True, color=NAVY, align=PP_ALIGN.CENTER)
add_text(slide, "Both tools are accessed through your browser — no software installation required.",
         0.35, 6.0, 12.6, 0.5, 10.5, color=DGREY, italic=True)

# ══════════════════════════════════════════════════════════════════════════════
# SLIDE 4 — QC Engine: Getting Started
# ══════════════════════════════════════════════════════════════════════════════
slide = prs.slides.add_slide(BLANK)
add_rect(slide, 0, 0, 13.33, 7.5, LGREY)
header_bar(slide, "02  ·  QC Engine — Getting Started")
section_label(slide, "Upload & Configure")
footer(slide, 4)

steps = [
    ("1", "Open the QC Engine", "Navigate to the web URL provided by your administrator."),
    ("2", "Upload Your Data File", "Drag and drop or click to upload a CSV, XLSX, or SAV file.\nThe file is processed securely and never stored permanently."),
    ("3", "Configure QC Checks", "Use the left sidebar to toggle which checks to run:\nMissing values · Duration · Straightlining · Logic rules · Anomalies"),
    ("4", "Run the QC", "Click Run QC. A progress bar tracks the job.\nResults appear automatically across all tabs when complete."),
]

for i, (num, title, desc) in enumerate(steps):
    y = 1.1 + i * 1.42
    add_rect(slide, 0.35, y, 0.55, 0.55, BLUE)
    add_text(slide, num, 0.35, y + 0.06, 0.55, 0.45, 18, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
    add_rect(slide, 1.1, y, 11.85, 1.25, WHITE)
    add_text(slide, title, 1.25, y + 0.07, 11.4, 0.38, 13, bold=True, color=NAVY)
    add_text(slide, desc,  1.25, y + 0.5,  11.4, 0.75, 11, color=DGREY)

# ══════════════════════════════════════════════════════════════════════════════
# SLIDE 5 — QC Engine: Results Tabs
# ══════════════════════════════════════════════════════════════════════════════
slide = prs.slides.add_slide(BLANK)
add_rect(slide, 0, 0, 13.33, 7.5, LGREY)
header_bar(slide, "03  ·  QC Engine — Results Tabs")
section_label(slide, "Reading the output")
footer(slide, 5)

tabs = [
    ("QC Report",      "Summary of all flagged rows across every check. Filter by severity (info / warning / critical). Download as Excel."),
    ("Logic Checks",   "Rows that violate custom IF/THEN rules — e.g. under-18 respondents with a salary value."),
    ("Straightlining", "Respondents who gave the same answer to every grid question — a common data quality signal."),
    ("Interviewers",   "Per-interviewer flag rates, duration averages, and risk scores. Colour-coded risk levels."),
    ("Quotas",         "Compares achieved sample counts against your defined quota targets."),
    ("Wave Compare",   "Upload a second wave file to diff response distributions and detect interviewer shift."),
    ("EDA",            "Exploratory charts — bar, scatter, histogram, heatmap, box plot — to profile the dataset."),
    ("Data Preview",   "Scrollable raw data table with column search and type inference."),
]

col1, col2 = 0.35, 6.85
for i, (tab, desc) in enumerate(tabs):
    col = col1 if i < 4 else col2
    row = i % 4
    y = 1.05 + row * 1.52
    add_rect(slide, col, y, 6.1, 1.38, WHITE)
    add_rect(slide, col, y, 0.18, 1.38, TEAL)
    add_text(slide, tab,  col+0.3, y+0.1,  5.65, 0.38, 12, bold=True, color=NAVY)
    add_text(slide, desc, col+0.3, y+0.5,  5.65, 0.82, 10.5, color=DGREY)

# ══════════════════════════════════════════════════════════════════════════════
# SLIDE 6 — Dashboard: Login & Roles
# ══════════════════════════════════════════════════════════════════════════════
slide = prs.slides.add_slide(BLANK)
add_rect(slide, 0, 0, 13.33, 7.5, LGREY)
header_bar(slide, "04  ·  Manager Dashboard — Login & Roles")
section_label(slide, "Access control")
footer(slide, 6)

add_rect(slide, 0.35, 1.1, 5.8, 5.5, WHITE)
add_rect(slide, 0.35, 1.1, 5.8, 0.5, NAVY)
add_text(slide, "Logging In", 0.55, 1.15, 5.4, 0.4, 13, bold=True, color=WHITE)
login_steps = [
    "Navigate to your dashboard URL",
    "Enter your email and password",
    "If 2FA is enabled, open Google Authenticator\nand enter the 6-digit code",
    "You are now signed in",
]
for i, s in enumerate(login_steps):
    add_rect(slide, 0.55, 1.8 + i*1.15, 0.38, 0.38, BLUE)
    add_text(slide, str(i+1), 0.55, 1.83+i*1.15, 0.38, 0.35, 13, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
    add_text(slide, s, 1.05, 1.82+i*1.15, 4.8, 0.6, 11, color=DGREY)

add_rect(slide, 6.8, 1.1, 6.1, 5.5, WHITE)
add_rect(slide, 6.8, 1.1, 6.1, 0.5, NAVY)
add_text(slide, "User Roles", 7.0, 1.15, 5.7, 0.4, 13, bold=True, color=WHITE)

roles = [
    ("Admin",       BLUE,  ["Full access to all projects", "Create/manage users", "Access admin panel"]),
    ("Manager",     TEAL,  ["View all projects", "Add quality records", "View all reports"]),
    ("QC Officer",  NAVY,  ["View assigned projects", "Log QC and backcheck data", "View own reports"]),
]
for i, (role, col, perms) in enumerate(roles):
    y = 1.75 + i * 1.65
    add_rect(slide, 7.0, y, 1.5, 0.38, col)
    add_text(slide, role, 7.0, y+0.04, 1.5, 0.32, 11, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
    for j, perm in enumerate(perms):
        add_text(slide, f"• {perm}", 8.65, y+0.04+j*0.38, 3.9, 0.36, 10.5, color=DGREY)

# ══════════════════════════════════════════════════════════════════════════════
# SLIDE 7 — Dashboard: Projects
# ══════════════════════════════════════════════════════════════════════════════
slide = prs.slides.add_slide(BLANK)
add_rect(slide, 0, 0, 13.33, 7.5, LGREY)
header_bar(slide, "05  ·  Manager Dashboard — Projects")
section_label(slide, "Project management")
footer(slide, 7)

add_text(slide, "Each survey is tracked as a Project. Projects hold all QC, backcheck, and performance data for a field period.",
         0.35, 0.95, 12.6, 0.5, 11, color=DGREY, italic=True)

cards = [
    ("Create a Project",  BLUE, ["Go to Projects → New Project", "Enter name, job number, client", "Set sample target, start/end dates", "Set LOI (length of interview) in minutes", "Save — project is now active"]),
    ("Project Overview",  TEAL, ["Completion % vs sample target", "Backcheck rate & listen-in rate", "Flag rate (warning / critical)", "RAG status — auto-calculated", "All records linked to this project"]),
    ("Project Settings",  NAVY, ["Edit targets at any time", "Assign QC officers to project", "Set flag thresholds for RAG", "Archive completed projects", "Export all records as CSV"]),
]

for i, (title, col, pts) in enumerate(cards):
    x = 0.35 + i * 4.3
    add_rect(slide, x, 1.55, 4.0, 4.9, WHITE)
    add_rect(slide, x, 1.55, 4.0, 0.55, col)
    add_text(slide, title, x+0.2, 1.62, 3.6, 0.42, 12, bold=True, color=WHITE)
    for j, pt in enumerate(pts):
        add_text(slide, f"• {pt}", x+0.2, 2.28+j*0.76, 3.65, 0.7, 11, color=DGREY)

# ══════════════════════════════════════════════════════════════════════════════
# SLIDE 8 — Dashboard: Quality Records
# ══════════════════════════════════════════════════════════════════════════════
slide = prs.slides.add_slide(BLANK)
add_rect(slide, 0, 0, 13.33, 7.5, LGREY)
header_bar(slide, "06  ·  Manager Dashboard — Quality Records")
section_label(slide, "Logging field data")
footer(slide, 8)

record_types = [
    ("QC Records",          BLUE, "Logged after each QC check run.",
     ["Select project + interviewer", "Enter number of interviews checked", "Record flag count and severity", "Add notes / outcome (pass/warn/block)"]),
    ("Backcheck Records",   TEAL, "Phone-back verification of completed interviews.",
     ["Select interviewer and date", "Enter interviews backchecked", "Record confirmed vs. fabricated", "Outcome auto-flags high fabrication"]),
    ("Listen-in Records",   NAVY, "Real-time observation of live interviews.",
     ["Select interviewer", "Enter number of interviews observed", "Score on protocol adherence", "Add qualitative comments"]),
]

for i, (title, col, sub, pts) in enumerate(record_types):
    x = 0.35 + i * 4.3
    add_rect(slide, x, 1.05, 4.0, 5.55, WHITE)
    add_rect(slide, x, 1.05, 4.0, 0.55, col)
    add_text(slide, title, x+0.18, 1.12, 3.65, 0.42, 12, bold=True, color=WHITE)
    add_text(slide, sub, x+0.18, 1.7, 3.65, 0.38, 10, color=DGREY, italic=True)
    for j, pt in enumerate(pts):
        add_text(slide, f"• {pt}", x+0.18, 2.2+j*0.82, 3.65, 0.75, 11, color=DGREY)

# ══════════════════════════════════════════════════════════════════════════════
# SLIDE 9 — Dashboard: Reports
# ══════════════════════════════════════════════════════════════════════════════
slide = prs.slides.add_slide(BLANK)
add_rect(slide, 0, 0, 13.33, 7.5, LGREY)
header_bar(slide, "07  ·  Manager Dashboard — Reports")
section_label(slide, "Analytics & exports")
footer(slide, 9)

reports = [
    ("Performance Report",  "Interviewer-level composite scores combining QC flag rate, backcheck results, and listen-in scores. Identifies top/bottom performers."),
    ("Timing Report",       "Average interview durations per interviewer vs. the project LOI. Flags interviewers who are consistently too fast or too slow."),
    ("Wave Comparison",     "Side-by-side breakdown of response distributions across field waves to detect data drift over time."),
    ("Cancelled Interviews","Log of interviews that were voided with reason codes — useful for audit trails and client reporting."),
    ("Interviewer Directory","Full registry of all interviewers across projects with cumulative performance history and risk level."),
    ("Admin Panel",         "User management, system health, database stats. Admin role only."),
]

for i, (title, desc) in enumerate(reports):
    col = 0.35 if i < 3 else 6.85
    row = i % 3
    y = 1.05 + row * 2.0
    add_rect(slide, col, y, 6.1, 1.78, WHITE)
    add_rect(slide, col, y, 0.2, 1.78, TEAL)
    add_text(slide, title, col+0.38, y+0.14, 5.45, 0.38, 12, bold=True, color=NAVY)
    add_text(slide, desc,  col+0.38, y+0.55, 5.45, 1.1,  10.5, color=DGREY)

# ══════════════════════════════════════════════════════════════════════════════
# SLIDE 10 — Deployment
# ══════════════════════════════════════════════════════════════════════════════
slide = prs.slides.add_slide(BLANK)
add_rect(slide, 0, 0, 13.33, 7.5, LGREY)
header_bar(slide, "08  ·  Getting Started")
section_label(slide, "Access & setup")
footer(slide, 10)

deploy = [
    (BLUE,  "Your Administrator Will Provide",
     ["A URL to access the QC Engine", "A URL to access the Manager Dashboard", "Your login credentials", "A brief onboarding walkthrough"]),
    (TEAL,  "What You Need",
     ["A modern web browser (Chrome, Edge, Firefox)", "Your email and password", "Google Authenticator app (if 2FA is enabled)", "No software installation required"]),
    (NAVY,  "System Requirements",
     ["Any Windows, Mac, or Linux computer", "Stable internet connection", "Screen resolution 1280×720 or higher", "Browser up to date"]),
]

for i, (col, title, pts) in enumerate(deploy):
    x = 0.35 + i * 4.3
    add_rect(slide, x, 1.05, 4.0, 5.55, col)
    add_text(slide, title, x+0.2, 1.15, 3.65, 0.75, 12, bold=True, color=WHITE)
    add_rect(slide, x+0.2, 1.95, 3.5, 0.04, WHITE)
    for j, pt in enumerate(pts):
        add_text(slide, f"• {pt}", x+0.2, 2.15+j*0.88, 3.65, 0.8, 11, color=WHITE)

add_text(slide,
    "Both tools run entirely in your browser. There is nothing to install or configure on your computer.",
    0.35, 6.75, 12.6, 0.4, 10, color=DGREY, italic=True)

# ══════════════════════════════════════════════════════════════════════════════
# Save
# ══════════════════════════════════════════════════════════════════════════════
out = "Ipsos_QC_Engine_User_Guide.pptx"
prs.save(out)
print(f"Saved: {out}")
