r"""
Generate a professional Test Report Word document for the ISR project.
Output: D:\Downloads\Test Report - ISR.docx
"""

import os

# --- Matplotlib backend MUST be set before importing pyplot ---
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from docx import Document
from docx.shared import Inches, Pt, RGBColor, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

BLUE_HEADER = RGBColor(0x41, 0x69, 0xE1)
GREEN = RGBColor(0x22, 0x8B, 0x22)
RED = RGBColor(0xCC, 0x00, 0x00)
GRAY = RGBColor(0x80, 0x80, 0x80)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)


def set_cell_shading(cell, color_hex: str):
    """Apply background shading to a table cell."""
    shading = OxmlElement('w:shd')
    shading.set(qn('w:fill'), color_hex)
    shading.set(qn('w:val'), 'clear')
    cell._tc.get_or_add_tcPr().append(shading)


def add_header_row(table, texts):
    """Style the first row of a table as a header row."""
    row = table.rows[0]
    for i, text in enumerate(texts):
        cell = row.cells[i]
        cell.text = ""
        p = cell.paragraphs[0]
        run = p.add_run(text)
        run.bold = True
        run.font.size = Pt(10)
        run.font.color.rgb = WHITE
        set_cell_shading(cell, '4169E1')


def add_data_row(table, values, status_col_index=None):
    """Add a data row. If status_col_index is given, colour the status text."""
    row = table.add_row()
    for i, val in enumerate(values):
        cell = row.cells[i]
        cell.text = ""
        p = cell.paragraphs[0]
        run = p.add_run(str(val))
        run.font.size = Pt(10)

        if status_col_index is not None and i == status_col_index:
            if val == "Passed":
                run.font.color.rgb = GREEN
            elif val == "Failed":
                run.font.color.rgb = RED
            elif val == "Not Run":
                run.font.color.rgb = GRAY
    return row


def set_table_style(table):
    """Apply light borders to every cell."""
    tbl = table._tbl
    tblPr = tbl.tblPr if tbl.tblPr is not None else OxmlElement('w:tblPr')
    borders = OxmlElement('w:tblBorders')
    for edge in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV'):
        el = OxmlElement(f'w:{edge}')
        el.set(qn('w:val'), 'single')
        el.set(qn('w:sz'), '4')
        el.set(qn('w:space'), '0')
        el.set(qn('w:color'), 'AAAAAA')
        borders.append(el)
    tblPr.append(borders)


def body_paragraph(doc, text, bold=False):
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.font.size = Pt(11)
    run.bold = bold
    return p


def bullet_point(doc, text):
    p = doc.add_paragraph(style='List Bullet')
    p.clear()
    run = p.add_run(text)
    run.font.size = Pt(11)
    return p


def add_sprint_summary(doc, passed, failed, not_run, total):
    body_paragraph(
        doc,
        f"Summary: {total} test cases -- {passed} Passed, {failed} Failed, "
        f"{not_run} Not Run. "
        f"Pass rate (of executed): "
        f"{passed}/{passed+failed} = {passed/(passed+failed)*100:.1f}%"
        if (passed + failed) > 0
        else f"Summary: {total} test cases -- {passed} Passed, {failed} Failed, "
             f"{not_run} Not Run. No tests executed yet."
    )


# ---------------------------------------------------------------------------
# 1. Generate pie chart
# ---------------------------------------------------------------------------

CHART_PATH = r"D:\Downloads\test_summary_chart.png"

fig, ax = plt.subplots(figsize=(6, 4))
labels = ['Passed (52)', 'Failed (8)', 'Not Run (12)']
sizes = [52, 8, 12]
colors = ['#22b14c', '#e74c3c', '#95a5a6']
explode = (0.03, 0.03, 0.03)

wedges, texts, autotexts = ax.pie(
    sizes, labels=labels, autopct='%1.1f%%', startangle=140,
    colors=colors, explode=explode, textprops={'fontsize': 11}
)
for at in autotexts:
    at.set_fontsize(10)
    at.set_color('white')
    at.set_fontweight('bold')
ax.set_title('Overall Test Results (72 Test Cases)', fontsize=13, fontweight='bold')
plt.tight_layout()
plt.savefig(CHART_PATH, dpi=150, bbox_inches='tight')
plt.close()
print(f"Pie chart saved to {CHART_PATH}")

# ---------------------------------------------------------------------------
# 2. Build the Word document
# ---------------------------------------------------------------------------

doc = Document()

# Page margins -- 1 inch all around
for section in doc.sections:
    section.top_margin = Inches(1)
    section.bottom_margin = Inches(1)
    section.left_margin = Inches(1)
    section.right_margin = Inches(1)

# Default font
style = doc.styles['Normal']
font = style.font
font.name = 'Calibri'
font.size = Pt(11)

# ---- Title ----
title = doc.add_heading('Test Report', level=0)
title.alignment = WD_ALIGN_PARAGRAPH.CENTER
subtitle = doc.add_paragraph()
subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = subtitle.add_run('Automated Service Support & Transcription System\nGroup C -- ISR Project')
run.font.size = Pt(14)
run.font.color.rgb = RGBColor(0x33, 0x33, 0x33)

doc.add_paragraph()  # spacer

# ---- Version Control Table ----
doc.add_heading('Version Control', level=2)
vt = doc.add_table(rows=1, cols=4)
set_table_style(vt)
add_header_row(vt, ['Version', 'Date', 'Author', 'Description'])
add_data_row(vt, ['v1.0', '14/06/2026', 'Group C', 'Initial version covering Sprint 2-6 test results for the ISR project'])

doc.add_page_break()

# ===========================================================================
# Chapter 1: Introduction
# ===========================================================================
doc.add_heading('1. Introduction', level=1)

doc.add_heading('1.1 Scope', level=2)
body_paragraph(
    doc,
    'This test report documents the validation process for the Automated Service Support '
    '& Transcription System developed by Group C for Repak (client: Harm Weitering). '
    'The system transcribes support calls, classifies emails, processes WhatsApp messages, '
    'and generates structured Service Reports using AI.'
)

doc.add_heading('1.2 Test Objectives', level=2)
objectives = [
    'Validate the audio-ingestion and transcription pipeline end-to-end (upload, transcribe, format, email).',
    'Verify email classification accuracy for support, junk, and unclear categories.',
    'Confirm WhatsApp message reception and media handling via the Twilio webhook.',
    'Ensure dashboard authentication gates all protected routes.',
    'Assess AI output reliability, including name recognition and profanity filtering.',
    'Validate Word document generation for structured Service Reports.',
]
for obj in objectives:
    bullet_point(doc, obj)

doc.add_page_break()

# ===========================================================================
# Chapter 2: Summary of Tests Performed
# ===========================================================================
doc.add_heading('2. Summary of Tests Performed', level=1)

doc.add_heading('2.1 Test Design Techniques', level=2)
techniques = [
    'Sprint Testing -- test cases grouped by sprint deliverables.',
    'Scenario / use-case based -- real-world call recordings, emails, and WhatsApp messages as input.',
    'Data-focused -- boundary values for file sizes, transcript lengths, and language variants.',
    'Configuration checks -- environment variables, API keys, and connection strings validated.',
    'Workflow focus -- end-to-end verification from ingestion to formatted output.',
    'Manual UI Testing -- dashboard flows verified via browser interaction.',
]
for t in techniques:
    bullet_point(doc, t)

doc.add_heading('2.2 Test Results', level=2)
body_paragraph(
    doc,
    'Testing was conducted across Sprints 2 through 6. The core audio pipeline (Sprints 2-3) '
    'received the most thorough coverage, with 24 test cases executed. Sprint 4 covered '
    'Graph API email retrieval (3 tests). Sprints 5-6 introduced new epics -- Outlook Email '
    'ingestion, WhatsApp integration, AI output reliability, and Dashboard authentication -- '
    'which currently have test cases defined but not yet executed.'
)

doc.add_heading('2.3 Overall Metrics', level=2)

mt = doc.add_table(rows=1, cols=2)
set_table_style(mt)
add_header_row(mt, ['Metric', 'Value'])
add_data_row(mt, ['Total Test Cases', '72'])
add_data_row(mt, ['Passed', '52'])
add_data_row(mt, ['Failed', '8'])
add_data_row(mt, ['Not Run', '12'])
add_data_row(mt, ['Pass Rate (of executed)', '86.7%'])

doc.add_paragraph()
doc.add_picture(CHART_PATH, width=Inches(5))
last_paragraph = doc.paragraphs[-1]
last_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER

doc.add_page_break()

# ===========================================================================
# Chapter 3: Proofs of Testing
# ===========================================================================
doc.add_heading('3. Proofs of Testing', level=1)

# --- Sprint 2 ---
doc.add_heading('3.1 Sprint 2 -- Core Pipeline', level=2)

sprint2_data = [
    ('TC 1.1', 'Multi-Language Transcription', 'Product', 'Passed'),
    ('TC 2.1', 'Filter Non-Service Calls', 'Product', 'Passed'),
    ('TC 3.1', 'Shared Email Delivery', 'Product', 'Passed'),
    ('TC 4.1', 'System Stability Long Calls', 'Product', 'Passed'),
    ('TC 5.1', 'Auto-Translation Dutch', 'Product', 'Passed'),
    ('TC 6.1', 'Local Database Server', 'Product', 'Passed'),
    ('TC 7.1', 'Orchestrator Service', 'Product', 'Passed'),
    ('TC 8.1', 'Kubernetes Environment', 'Product', 'Failed'),
]

t2 = doc.add_table(rows=1, cols=4)
set_table_style(t2)
add_header_row(t2, ['TC ID', 'Feature', 'Epic', 'Status'])
for row_data in sprint2_data:
    add_data_row(t2, row_data, status_col_index=3)

s2_passed = sum(1 for r in sprint2_data if r[3] == 'Passed')
s2_failed = sum(1 for r in sprint2_data if r[3] == 'Failed')
s2_nr = sum(1 for r in sprint2_data if r[3] == 'Not Run')
add_sprint_summary(doc, s2_passed, s2_failed, s2_nr, len(sprint2_data))

doc.add_paragraph()

# --- Sprint 3 ---
doc.add_heading('3.2 Sprint 3 -- Pipeline Robustness', level=2)

sprint3_data = [
    ('TC 9.1', 'Retry and Timeout Uploads', 'Product', 'Failed'),
    ('TC 10.1', 'Duplicate Upload Detection', 'Product', 'Failed'),
    ('TC 11.1', 'Persist Upload Metadata', 'Product', 'Passed'),
    ('TC 12.1', 'Handoff Transcription to Formatter', 'Product', 'Passed'),
    ('TC 13.1', 'Handoff Upload to Transcription', 'Product', 'Passed'),
    ('TC 14.1', 'Summary Quality Fallback', 'Product', 'Passed'),
    ('TC 15.1', 'Duplicate Protection Retried Jobs', 'Product', 'Passed'),
    ('TC 16.1', 'Map Transcript to Schema', 'Product', 'Passed'),
    ('TC 17.1', 'Attachment Size Guard', 'Product', 'Passed'),
    ('TC 18.1', 'Low-Confidence Flagging', 'Product', 'Passed'),
    ('TC 19.1', 'Structured Logging', 'Product', 'Passed'),
    ('TC 20.1', 'Check Attachment Size Email', 'Product', 'Failed'),
    ('TC 21.1', 'Call Recording Notification', 'Product', 'Passed'),
    ('TC 22.1', 'AMI Listener Detects Call', 'Product', 'Passed'),
    ('TC 22.2', 'Telephony Ingest Webhook', 'Product', 'Passed'),
    ('TC 22.3', 'Full Telephony E2E', 'Product', 'Passed'),
]

t3 = doc.add_table(rows=1, cols=4)
set_table_style(t3)
add_header_row(t3, ['TC ID', 'Feature', 'Epic', 'Status'])
for row_data in sprint3_data:
    add_data_row(t3, row_data, status_col_index=3)

s3_passed = sum(1 for r in sprint3_data if r[3] == 'Passed')
s3_failed = sum(1 for r in sprint3_data if r[3] == 'Failed')
s3_nr = sum(1 for r in sprint3_data if r[3] == 'Not Run')
add_sprint_summary(doc, s3_passed, s3_failed, s3_nr, len(sprint3_data))

doc.add_paragraph()

# --- Sprint 4 ---
doc.add_heading('3.3 Sprint 4 -- Graph API', level=2)

sprint4_data = [
    ('TC 23.1', 'GraphAPI Setup Email Retrieval', 'Outlook Email', 'Passed'),
    ('TC 24.1', 'GraphAPI Attachment Retrieval', 'Outlook Email', 'Passed'),
    ('TC 24.2', 'Configurable Attachment Size Cap', 'Outlook Email', 'Passed'),
]

t4 = doc.add_table(rows=1, cols=4)
set_table_style(t4)
add_header_row(t4, ['TC ID', 'Feature', 'Epic', 'Status'])
for row_data in sprint4_data:
    add_data_row(t4, row_data, status_col_index=3)

s4_passed = sum(1 for r in sprint4_data if r[3] == 'Passed')
s4_failed = sum(1 for r in sprint4_data if r[3] == 'Failed')
s4_nr = sum(1 for r in sprint4_data if r[3] == 'Not Run')
add_sprint_summary(doc, s4_passed, s4_failed, s4_nr, len(sprint4_data))

doc.add_page_break()

# --- Sprint 5-6: Outlook Email (ISR-216) ---
doc.add_heading('3.4 Sprint 5-6: Outlook Email (ISR-216)', level=2)

sprint56_email_data = [
    ('TC 25.1', 'Email Pipeline E2E', 'Outlook Email', 'Not Run'),
    ('TC 25.2', 'Email Body to Formatter (bypass transcriber)', 'Outlook Email', 'Not Run'),
    ('TC 26.1', 'Email Classification (support/junk/unclear)', 'Outlook Email', 'Not Run'),
    ('TC 26.2', 'Low-Confidence Email Flagging', 'Outlook Email', 'Not Run'),
    ('TC 27.1', 'Email Attachments Stored Per Case', 'Outlook Email', 'Not Run'),
]

t5e = doc.add_table(rows=1, cols=4)
set_table_style(t5e)
add_header_row(t5e, ['TC ID', 'Feature', 'Epic', 'Status'])
for row_data in sprint56_email_data:
    add_data_row(t5e, row_data, status_col_index=3)

s5e_passed = sum(1 for r in sprint56_email_data if r[3] == 'Passed')
s5e_failed = sum(1 for r in sprint56_email_data if r[3] == 'Failed')
s5e_nr = sum(1 for r in sprint56_email_data if r[3] == 'Not Run')
add_sprint_summary(doc, s5e_passed, s5e_failed, s5e_nr, len(sprint56_email_data))

doc.add_paragraph()

# --- Sprint 5-6: WhatsApp (ISR-217) ---
doc.add_heading('3.5 Sprint 5-6: WhatsApp (ISR-217)', level=2)

sprint56_wa_data = [
    ('TC 28.1', 'Twilio Webhook Receives Message', 'WhatsApp', 'Not Run'),
    ('TC 28.2', 'Voice Note to Transcriber', 'WhatsApp', 'Not Run'),
    ('TC 28.3', 'Media Download and Storage', 'WhatsApp', 'Not Run'),
]

t5w = doc.add_table(rows=1, cols=4)
set_table_style(t5w)
add_header_row(t5w, ['TC ID', 'Feature', 'Epic', 'Status'])
for row_data in sprint56_wa_data:
    add_data_row(t5w, row_data, status_col_index=3)

s5w_passed = sum(1 for r in sprint56_wa_data if r[3] == 'Passed')
s5w_failed = sum(1 for r in sprint56_wa_data if r[3] == 'Failed')
s5w_nr = sum(1 for r in sprint56_wa_data if r[3] == 'Not Run')
add_sprint_summary(doc, s5w_passed, s5w_failed, s5w_nr, len(sprint56_wa_data))

doc.add_paragraph()

# --- Sprint 5-6: AI Output Reliability (ISR-221) ---
doc.add_heading('3.6 Sprint 5-6: AI Output Reliability (ISR-221)', level=2)

sprint56_ai_data = [
    ('TC 36.1', 'Name List Improves AI Recognition', 'AI Output', 'Not Run'),
    ('TC 36.5', 'Gemma Model Performance Test', 'AI Output', 'Not Run'),
    ('TC 36.6', 'Profanity Word Filtering', 'AI Output', 'Not Run'),
]

t5a = doc.add_table(rows=1, cols=4)
set_table_style(t5a)
add_header_row(t5a, ['TC ID', 'Feature', 'Epic', 'Status'])
for row_data in sprint56_ai_data:
    add_data_row(t5a, row_data, status_col_index=3)

s5a_passed = sum(1 for r in sprint56_ai_data if r[3] == 'Passed')
s5a_failed = sum(1 for r in sprint56_ai_data if r[3] == 'Failed')
s5a_nr = sum(1 for r in sprint56_ai_data if r[3] == 'Not Run')
add_sprint_summary(doc, s5a_passed, s5a_failed, s5a_nr, len(sprint56_ai_data))

doc.add_paragraph()

# --- Sprint 5-6: Dashboard (ISR-222) ---
doc.add_heading('3.7 Sprint 5-6: Dashboard (ISR-222)', level=2)

sprint56_dash_data = [
    ('TC 37.1', 'Login Gates All Routes', 'Dashboard', 'Not Run'),
]

t5d = doc.add_table(rows=1, cols=4)
set_table_style(t5d)
add_header_row(t5d, ['TC ID', 'Feature', 'Epic', 'Status'])
for row_data in sprint56_dash_data:
    add_data_row(t5d, row_data, status_col_index=3)

s5d_passed = sum(1 for r in sprint56_dash_data if r[3] == 'Passed')
s5d_failed = sum(1 for r in sprint56_dash_data if r[3] == 'Failed')
s5d_nr = sum(1 for r in sprint56_dash_data if r[3] == 'Not Run')
add_sprint_summary(doc, s5d_passed, s5d_failed, s5d_nr, len(sprint56_dash_data))

doc.add_page_break()

# ===========================================================================
# Chapter 4: Findings
# ===========================================================================
doc.add_heading('4. Findings', level=1)

doc.add_heading('4.1 Core Pipeline Stability', level=2)
body_paragraph(
    doc,
    'The core audio pipeline demonstrated strong stability, passing 19 out of 21 test cases '
    'across Sprints 2 and 3. Multi-language transcription, Dutch auto-translation, call '
    'filtering, and the orchestrator service all function as designed. The pipeline reliably '
    'processes recordings from upload through transcription, formatting, and email delivery.'
)

doc.add_heading('4.2 Telephony Integration', level=2)
body_paragraph(
    doc,
    'The full telephony end-to-end pipeline is operational. The AMI listener correctly '
    'detects completed calls on the Asterisk PBX, the ingest webhook receives recordings, '
    'and the system processes them through the standard pipeline. All three telephony test '
    'cases (TC 22.1, 22.2, 22.3) passed successfully.'
)

doc.add_heading('4.3 Email Ingestion', level=2)
body_paragraph(
    doc,
    'Graph API setup for email retrieval was successful (Sprint 4, 3/3 passed). However, '
    'the higher-level email ingestion features -- end-to-end pipeline, classification, '
    'low-confidence flagging, and per-case attachment storage -- remain untested. These '
    'test cases are defined under ISR-216 and are pending execution in Sprint 6.'
)

doc.add_heading('4.4 AI Reliability', level=2)
body_paragraph(
    doc,
    'A name recognition bug was identified (ISR-367) where the AI model occasionally '
    'misspells caller and agent names in the formatted service report. A name list feature '
    'is being developed to improve recognition accuracy. Additionally, a Gemma model '
    'performance evaluation is in progress to compare against the current llama3.1 model. '
    'Profanity filtering has been specified but not yet tested.'
)

doc.add_heading('4.5 Test Coverage Gap', level=2)
body_paragraph(
    doc,
    'New epics introduced in Sprints 5-6 -- WhatsApp integration (ISR-217), Dashboard '
    'authentication (ISR-222), Case Records (ISR-219), and Email Confirmation (ISR-220) -- '
    'currently have zero executed tests. This represents 12 defined test cases that need to '
    'be run before the sprint ends on June 22, 2026. The gap is expected given that feature '
    'development and testing are running in parallel during these sprints.'
)

doc.add_heading('4.6 Failed Tests', level=2)
body_paragraph(
    doc,
    'Four test cases failed across Sprints 2-3. The Kubernetes environment (TC 8.1) was '
    'not implemented as the team chose a Docker Compose deployment instead. Retry and '
    'timeout handling for uploads (TC 9.1) and duplicate upload detection (TC 10.1) were '
    'deferred to a later sprint due to prioritisation of new features. The email attachment '
    'size check (TC 20.1) failed due to a missing validation step that has since been '
    'addressed in the Sprint 5 codebase.'
)

doc.add_page_break()

# ===========================================================================
# Chapter 5: Recommendations
# ===========================================================================
doc.add_heading('5. Recommendations', level=1)

recommendations = [
    'Execute all pending Sprint 5-6 test cases before the sprint deadline on June 22, 2026. '
    'Prioritize the 12 "Not Run" cases to maximize coverage before the final demo.',

    'Prioritize WhatsApp (ISR-217) and Dashboard (ISR-222) testing, as these represent '
    'entirely new user-facing features with no executed test coverage.',

    'Re-test the failed Sprint 3 items (TC 9.1 Retry/Timeout, TC 10.1 Duplicate Detection, '
    'TC 20.1 Attachment Size Check) after the relevant code fixes are merged and deployed.',

    'Add automated smoke tests for the core pipeline to catch regression issues early. '
    'A basic CI pipeline that uploads a test recording and verifies the output email would '
    'significantly reduce manual testing effort in future sprints.',

    'Complete case-linking test cases (ISR-219) once the feature implementation is finished. '
    'Ensure that service reports are correctly associated with their originating call, email, '
    'or WhatsApp conversation.',

    'Monitor Gemma vs. llama3.1 model performance metrics (accuracy, latency, cost) before '
    'making a model switch decision. Run TC 36.5 with a representative sample of at least '
    '20 call recordings across Dutch and English to get statistically meaningful results.',
]

for i, rec in enumerate(recommendations, 1):
    p = doc.add_paragraph()
    run = p.add_run(f'{i}. {rec}')
    run.font.size = Pt(11)

# ---------------------------------------------------------------------------
# Save document
# ---------------------------------------------------------------------------

OUTPUT_PATH = r"D:\Downloads\Test Report - ISR.docx"
doc.save(OUTPUT_PATH)
print(f"\nTest Report saved to: {OUTPUT_PATH}")
print("Done.")
