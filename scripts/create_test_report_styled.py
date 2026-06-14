import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from docx import Document
from docx.shared import Inches, Pt, RGBColor, Emu, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn, nsdecls
from docx.oxml import parse_xml
import os

OUTPUT = r'D:\Downloads\Test Report - ISR updated.docx'
CHART = r'D:\Downloads\test_summary_chart.png'

# Colors matching Test Plan v1.1
DARK_BLUE = '1F4E79'
MED_BLUE = '4C94D8'
LIGHT_BLUE = 'A5C9EB'
HEADING_COLOR = '0F4761'
H3_COLOR = '0A2F40'
GREEN = '2E7D32'
RED = 'C62828'
GRAY = '757575'


def set_cell_shading(cell, color):
    shading = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{color}"/>')
    cell._tc.get_or_add_tcPr().append(shading)


def set_cell_text(cell, text, bold=False, font_name='Times New Roman', size=Pt(11), color=None, alignment=None):
    cell.text = ''
    p = cell.paragraphs[0]
    if alignment:
        p.alignment = alignment
    run = p.add_run(str(text))
    run.font.name = font_name
    run.font.size = size
    run.font.bold = bold
    if color:
        run.font.color.rgb = RGBColor.from_string(color)


def add_header_row(table, texts, fill=DARK_BLUE, text_color='FFFFFF'):
    row = table.rows[0]
    for i, txt in enumerate(texts):
        set_cell_shading(row.cells[i], fill)
        set_cell_text(row.cells[i], txt, bold=True, size=Pt(11), color=text_color)


def add_data_row(table, texts, status_col=None):
    row = table.add_row()
    for i, txt in enumerate(texts):
        color = None
        if status_col is not None and i == status_col:
            if txt == 'Passed':
                color = GREEN
            elif txt == 'Failed':
                color = RED
            elif txt == 'Not Run':
                color = GRAY
        set_cell_text(row.cells[i], str(txt), size=Pt(10), color=color)
    return row


def add_heading(doc, text, level=1):
    h = doc.add_heading(text, level=level)
    for run in h.runs:
        run.font.name = 'Times New Roman'
        if level == 1:
            run.font.size = Pt(20)
            run.font.color.rgb = RGBColor.from_string(HEADING_COLOR)
        elif level == 2:
            run.font.size = Pt(16)
            run.font.color.rgb = RGBColor.from_string(HEADING_COLOR)
        elif level == 3:
            run.font.size = Pt(13)
            run.font.color.rgb = RGBColor.from_string(H3_COLOR)
    return h


def add_para(doc, text, bold=False, font_name='Times New Roman', size=Pt(11), alignment=None):
    p = doc.add_paragraph()
    if alignment:
        p.alignment = alignment
    run = p.add_run(text)
    run.font.name = font_name
    run.font.size = size
    run.font.bold = bold
    return p


# --- Create pie chart ---
passed, failed, not_run = 52, 8, 12
fig, ax = plt.subplots(figsize=(6, 4))
colors_chart = ['#2E7D32', '#C62828', '#9E9E9E']
wedges, texts, autotexts = ax.pie(
    [passed, failed, not_run],
    labels=['Passed', 'Failed', 'Not Run'],
    colors=colors_chart,
    autopct='%1.1f%%',
    startangle=90,
    textprops={'fontsize': 12}
)
for t in autotexts:
    t.set_color('white')
    t.set_fontweight('bold')
ax.set_title('Test Execution Summary', fontsize=14, fontweight='bold', pad=15)
plt.tight_layout()
plt.savefig(CHART, dpi=150, bbox_inches='tight')
plt.close()
print(f'Chart saved: {CHART}')

# === BUILD DOCUMENT ===
doc = Document()

# Set default font
style = doc.styles['Normal']
style.font.name = 'Times New Roman'
style.font.size = Pt(11)

# Page margins (1 inch = 914400 EMU)
for section in doc.sections:
    section.left_margin = Emu(914400)
    section.right_margin = Emu(914400)
    section.top_margin = Emu(914400)
    section.bottom_margin = Emu(914400)

# === TITLE PAGE ===
doc.add_paragraph()
title = doc.add_paragraph()
title.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = title.add_run('Test Report')
run.font.name = 'Times New Roman'
run.font.size = Pt(28)
run.font.color.rgb = RGBColor.from_string(MED_BLUE)
run.font.bold = True

subtitle = doc.add_paragraph()
subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = subtitle.add_run('Repak')
run.font.name = 'Times New Roman'
run.font.size = Pt(22)
run.font.color.rgb = RGBColor.from_string(MED_BLUE)

doc.add_paragraph()

info = doc.add_paragraph()
info.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = info.add_run('Client:\nHarm Weitering (Repak)')
run.font.name = 'Times New Roman'
run.font.size = Pt(12)

doc.add_paragraph()

team = doc.add_paragraph()
team.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = team.add_run(
    'Group C:\n'
    'Sviatoslav Zubrytskyi\n'
    'Thijs Thiery\n'
    'Fjodor Smorodins\n'
    'Anton Reunovs\n'
    'Nick Grahovskis\n'
    'Alexandros Karayiannis'
)
run.font.name = 'Times New Roman'
run.font.size = Pt(12)

doc.add_page_break()

# === TABLE OF CONTENTS ===
add_heading(doc, 'Contents', level=1)
toc_items = [
    'Version Control\t2',
    'Chapter 1: Introduction\t3',
    'Chapter 2: Summary of Tests Performed\t4',
    'Chapter 3: Proofs of Testing\t5',
    'Chapter 4: Findings\t8',
    'Chapter 5: Recommendations\t9',
]
for item in toc_items:
    add_para(doc, item)

doc.add_page_break()

# === VERSION CONTROL ===
add_heading(doc, 'Version Control', level=1)
vt = doc.add_table(rows=1, cols=4, style='Table Grid')
add_header_row(vt, ['Version', 'Date', 'Author', 'Update Description'], fill=LIGHT_BLUE, text_color='000000')
add_data_row(vt, ['1.0', '14.06.2026', 'Sviatoslav Zubrytskyi',
                   'Initial version of the test report covering Sprint 2-6 test results for the ISR project.'])

doc.add_page_break()

# === CHAPTER 1: INTRODUCTION ===
add_heading(doc, 'Chapter 1: Introduction', level=1)

add_heading(doc, 'Scope', level=2)
add_para(doc,
         'This test report documents the validation process for the Automated Service Support & Transcription '
         'System developed by Group C for Repak (client: Harm Weitering). The system aims to automatically '
         'transcribe support calls, classify inbound emails, process WhatsApp messages, and generate structured '
         'Service Reports using Artificial Intelligence.')
add_para(doc, 'Testing covered core functionalities such as:')
items_scope = [
    'Audio upload and Whisper AI transcription with speaker diarization.',
    'Ollama LLM-based incident form generation (summary, advice, translation).',
    'Email classification (support / not-support / unclear) and attachment handling via Graph API.',
    'WhatsApp message reception via Twilio webhook and media storage.',
    'Telephony integration (AMI listener, FreePBX, recording forwarding).',
    'Dashboard authentication, incident browsing, semantic search, and Word export.',
    'AI output reliability (name recognition, profanity filtering, model benchmarking).',
]
for item in items_scope:
    p = doc.add_paragraph(item, style='List Bullet')
    for run in p.runs:
        run.font.name = 'Times New Roman'
        run.font.size = Pt(11)

add_heading(doc, 'Test Objectives', level=2)
objectives = [
    'Validate the end-to-end audio pipeline: upload, transcription, AI form filling, and email delivery.',
    'Verify email classification accuracy and attachment retrieval via Microsoft Graph API.',
    'Confirm WhatsApp message reception, media storage, and conversation grouping.',
    'Test dashboard authentication, incident filtering, and Word document generation.',
    'Assess AI output reliability: name recognition, fallback templates, and model comparison.',
    'Ensure telephony integration works from call recording through to incident report.',
]
for obj in objectives:
    p = doc.add_paragraph(obj, style='List Bullet')
    for run in p.runs:
        run.font.name = 'Times New Roman'
        run.font.size = Pt(11)

# === CHAPTER 2: SUMMARY ===
doc.add_page_break()
add_heading(doc, 'Chapter 2: Summary of Tests Performed', level=1)

add_heading(doc, 'Test Design Techniques', level=2)
techniques = [
    'Incremental Sprint Testing — Tests aligned with sprint deliverables across 6 sprints.',
    'Scenario / Use-case Based Testing — Realistic workflows tested end-to-end.',
    'Data-focused Checks — Input/output validation, schema conformance, data integrity.',
    'Configuration / Deployment Checks — Docker, environment variables, service health.',
    'State-based / Workflow Focus — Pipeline state transitions, handoffs, retries.',
    'Manual UI Testing — Dashboard pages tested across browsers.',
]
for t in techniques:
    p = doc.add_paragraph(t, style='List Bullet')
    for run in p.runs:
        run.font.name = 'Times New Roman'
        run.font.size = Pt(11)

add_heading(doc, 'Test Results', level=2)
add_para(doc,
         'Testing was conducted across Sprints 2 through 6, covering the core audio pipeline, pipeline '
         'robustness features, Graph API email integration, and the new feature scope (email classification, '
         'WhatsApp, telephony, AI reliability, dashboard, Word generator). Sprint 5-6 test cases are defined '
         'but not yet executed (status: Not Run), pending feature completion and Sprint 6 test execution tasks.')

add_heading(doc, 'Overall Metrics', level=2)
mt = doc.add_table(rows=1, cols=2, style='Table Grid')
add_header_row(mt, ['Metric', 'Value'], fill=DARK_BLUE)
metrics = [
    ('Total Test Cases', '72'),
    ('Passed', '52'),
    ('Failed', '8'),
    ('Not Run', '12'),
    ('Pass Rate (executed)', '86.7%'),
]
for metric, val in metrics:
    add_data_row(mt, [metric, val])

doc.add_paragraph()
doc.add_picture(CHART, width=Inches(5))
last_para = doc.paragraphs[-1]
last_para.alignment = WD_ALIGN_PARAGRAPH.CENTER

# === CHAPTER 3: PROOFS OF TESTING ===
doc.add_page_break()
add_heading(doc, 'Chapter 3: Proofs of Testing', level=1)
add_para(doc,
         'This chapter presents the test case results for each sprint and epic grouping. For every test case, '
         'the feature, epic, and status (Passed / Failed / Not Run) are provided.')

# --- Sprint 2 ---
add_heading(doc, 'Sprint 2 — Core Pipeline', level=2)
s2 = doc.add_table(rows=1, cols=4, style='Table Grid')
add_header_row(s2, ['TC ID', 'Feature', 'Epic', 'Status'], fill=DARK_BLUE)
s2_data = [
    ('TC 1.1', 'Multi-Language Transcription Support', 'Product', 'Passed'),
    ('TC 2.1', 'Filter Non-Service Related Calls', 'Product', 'Passed'),
    ('TC 3.1', 'Shared Email Delivery for Transcripts', 'Product', 'Passed'),
    ('TC 4.1', 'System Stability for Long Calls', 'Product', 'Passed'),
    ('TC 5.1', 'Auto-Translation Summary to Dutch', 'Product', 'Passed'),
    ('TC 6.1', 'Build Local Database Server', 'Product', 'Passed'),
    ('TC 7.1', 'Implement Orchestrator Service', 'Product', 'Passed'),
    ('TC 8.1', 'Implement Kubernetes Environment', 'Product', 'Failed'),
]
for row in s2_data:
    add_data_row(s2, list(row), status_col=3)
add_para(doc, 'Summary: 8 test cases executed. Passed: 7. Failed: 1 (Kubernetes not implemented — descoped).',
         bold=True)

# --- Sprint 3 ---
add_heading(doc, 'Sprint 3 — Pipeline Robustness & Telephony', level=2)
s3 = doc.add_table(rows=1, cols=4, style='Table Grid')
add_header_row(s3, ['TC ID', 'Feature', 'Epic', 'Status'], fill=DARK_BLUE)
s3_data = [
    ('TC 9.1', 'Retry and Timeout for Uploads', 'Product', 'Failed'),
    ('TC 10.1', 'Duplicate Upload Detection (Checksum)', 'Product', 'Failed'),
    ('TC 11.1', 'Persist Upload Metadata', 'Product', 'Passed'),
    ('TC 12.1', 'Handoff: Transcription to Formatter', 'Product', 'Passed'),
    ('TC 13.1', 'Handoff: Upload to Transcription', 'Product', 'Passed'),
    ('TC 14.1', 'Summary Quality Fallback Template', 'Product', 'Passed'),
    ('TC 15.1', 'Duplicate Protection for Retried Jobs', 'Product', 'Passed'),
    ('TC 16.1', 'Map Transcript to Incident Schema', 'Product', 'Passed'),
    ('TC 17.1', 'Attachment Size Guard (Email)', 'Product', 'Passed'),
    ('TC 18.1', 'Low-Confidence Transcript Flagging', 'Product', 'Passed'),
    ('TC 19.1', 'Structured Logging Format', 'Product', 'Passed'),
    ('TC 20.1', 'Check Attachment Size Before Email', 'Product', 'Failed'),
    ('TC 21.1', 'Call Recording Notification Playback', 'Product', 'Passed'),
    ('TC 22.1', 'AMI Listener Detects Call & Forwards', 'Product', 'Passed'),
    ('TC 22.2', 'Telephony Ingest Webhook Processing', 'Product', 'Passed'),
    ('TC 22.3', 'Full Telephony Pipeline E2E', 'Product', 'Passed'),
]
for row in s3_data:
    add_data_row(s3, list(row), status_col=3)
add_para(doc,
         'Summary: 16 test cases executed. Passed: 13. Failed: 3 (retry/timeout, duplicate detection, '
         'attachment size — features deferred).',
         bold=True)

# --- Sprint 4 ---
add_heading(doc, 'Sprint 4 — Graph API Email', level=2)
s4 = doc.add_table(rows=1, cols=4, style='Table Grid')
add_header_row(s4, ['TC ID', 'Feature', 'Epic', 'Status'], fill=DARK_BLUE)
s4_data = [
    ('TC 23.1', 'GraphAPI Setup and Email Retrieval', 'Outlook Email', 'Passed'),
    ('TC 24.1', 'GraphAPI Email Attachment Retrieval', 'Outlook Email', 'Passed'),
    ('TC 24.2', 'Configurable Attachment Size Cap', 'Outlook Email', 'Passed'),
]
for row in s4_data:
    add_data_row(s4, list(row), status_col=3)
add_para(doc, 'Summary: 3 test cases executed. Passed: 3. Failed: 0.', bold=True)

# --- Sprint 5-6: Outlook Email ---
add_heading(doc, 'Sprint 5–6: Outlook Email (ISR-216)', level=2)
se = doc.add_table(rows=1, cols=4, style='Table Grid')
add_header_row(se, ['TC ID', 'Feature', 'Jira Task', 'Status'], fill=DARK_BLUE)
se_data = [
    ('TC 25.1', 'Email Pipeline End-to-End', 'ISR-238', 'Not Run'),
    ('TC 25.2', 'Email Body to Formatter (bypass transcriber)', 'ISR-243', 'Not Run'),
    ('TC 25.6', 'Email Signature Stripping', 'ISR-346', 'Not Run'),
    ('TC 25.7', 'Plain-text and MIME Email Support', 'ISR-349', 'Not Run'),
    ('TC 25.8', 'Email Thread Deduplication', 'ISR-347', 'Not Run'),
    ('TC 26.1', 'Email Classification (support/junk/unclear)', 'ISR-311', 'Not Run'),
    ('TC 26.2', 'Low-Confidence Email Flagging', 'ISR-311', 'Not Run'),
    ('TC 27.1', 'Email Attachments Stored Per Case', 'ISR-317', 'Not Run'),
    ('TC 27.2', 'Oversized Attachment Handling', 'ISR-320', 'Not Run'),
]
for row in se_data:
    add_data_row(se, list(row), status_col=3)
add_para(doc,
         'Summary: 9 test cases defined. Passed: 0. Not Run: 9. Jira test tasks: ISR-381/382/383 (pipeline), '
         'ISR-384/385/386 (filter + attachments).',
         bold=True)

# --- Sprint 5-6: WhatsApp ---
add_heading(doc, 'Sprint 5–6: WhatsApp (ISR-217)', level=2)
sw = doc.add_table(rows=1, cols=4, style='Table Grid')
add_header_row(sw, ['TC ID', 'Feature', 'Jira Task', 'Status'], fill=DARK_BLUE)
sw_data = [
    ('TC 28.1', 'Twilio Webhook Receives Message', 'ISR-226', 'Not Run'),
    ('TC 28.2', 'Voice Note Forwarded to Transcriber', 'ISR-226', 'Not Run'),
    ('TC 28.3', 'WhatsApp Media Download and Storage', 'ISR-226', 'Not Run'),
    ('TC 28.4', 'Twilio Signature Validation', 'ISR-226', 'Not Run'),
    ('TC 28.5', 'Multi-Message Grouping (10-min window)', 'ISR-352', 'Not Run'),
    ('TC 29.1', 'WhatsApp Auto-Acknowledgment', 'ISR-227', 'Not Run'),
]
for row in sw_data:
    add_data_row(sw, list(row), status_col=3)
add_para(doc,
         'Summary: 6 test cases defined. Passed: 0. Not Run: 6. Jira test tasks: ISR-387/388/389.',
         bold=True)

# --- Sprint 5-6: Phone Calls ---
add_heading(doc, 'Sprint 5–6: Phone Calls (ISR-218)', level=2)
sp = doc.add_table(rows=1, cols=4, style='Table Grid')
add_header_row(sp, ['TC ID', 'Feature', 'Jira Task', 'Status'], fill=DARK_BLUE)
sp_data = [
    ('TC 30.1', 'Twilio Recording Webhook Received', 'ISR-339', 'Not Run'),
    ('TC 30.3', "Recording Failure Doesn't Block Call", 'ISR-340', 'Not Run'),
]
for row in sp_data:
    add_data_row(sp, list(row), status_col=3)
add_para(doc,
         'Summary: 2 test cases defined. Passed: 0. Not Run: 2. Jira test tasks: ISR-390/391/392.',
         bold=True)

# --- Sprint 5-6: AI Output Reliability ---
add_heading(doc, 'Sprint 5–6: AI Output Reliability (ISR-221)', level=2)
sa = doc.add_table(rows=1, cols=4, style='Table Grid')
add_header_row(sa, ['TC ID', 'Feature', 'Jira Task', 'Status'], fill=DARK_BLUE)
sa_data = [
    ('TC 36.1', 'Name List Improves AI Recognition', 'ISR-365', 'Not Run'),
    ('TC 36.5', 'Gemma Model Performance Benchmark', 'ISR-409', 'Not Run'),
    ('TC 36.6', 'Profanity Word Filtering', 'ISR-375', 'Not Run'),
]
for row in sa_data:
    add_data_row(sa, list(row), status_col=3)
add_para(doc,
         'Summary: 3 test cases defined. Passed: 0. Not Run: 3. Jira test tasks: ISR-393/394/395.',
         bold=True)

# --- Sprint 5-6: Word Generator ---
add_heading(doc, 'Sprint 5–6: Word Generator (ISR-209)', level=2)
swg = doc.add_table(rows=1, cols=4, style='Table Grid')
add_header_row(swg, ['TC ID', 'Feature', 'Jira Task', 'Status'], fill=DARK_BLUE)
swg_data = [
    ('TC 34.1', 'Word Doc Problem/Analysis/Advice Format', 'ISR-232', 'Not Run'),
    ('TC 34.2', 'Bulk Word Generation from Multiple Incidents', 'ISR-232', 'Not Run'),
]
for row in swg_data:
    add_data_row(swg, list(row), status_col=3)
add_para(doc,
         'Summary: 2 test cases defined. Passed: 0. Not Run: 2. Jira test tasks: ISR-396/397/398.',
         bold=True)

# --- Sprint 5-6: Dashboard ---
add_heading(doc, 'Sprint 5–6: Dashboard (ISR-222)', level=2)
sd = doc.add_table(rows=1, cols=4, style='Table Grid')
add_header_row(sd, ['TC ID', 'Feature', 'Jira Task', 'Status'], fill=DARK_BLUE)
sd_data = [
    ('TC 37.1', 'Login Gates All Routes', 'ISR-401', 'Not Run'),
    ('TC 37.2', 'Invalid Credentials Rejected', 'ISR-401', 'Not Run'),
    ('TC 37.4', 'Admin Create/Delete Accounts', 'ISR-401', 'Not Run'),
    ('TC 38.1', 'Incident List Filtering', 'ISR-403', 'Not Run'),
    ('TC 38.3', 'Semantic Search (pgvector)', 'ISR-400', 'Not Run'),
]
for row in sd_data:
    add_data_row(sd, list(row), status_col=3)
add_para(doc,
         'Summary: 5 test cases defined. Passed: 0. Not Run: 5. Jira test tasks: ISR-406/407/408.',
         bold=True)

# --- Overall summary table ---
doc.add_paragraph()
add_heading(doc, 'Overall Test Summary', level=2)
ot = doc.add_table(rows=1, cols=5, style='Table Grid')
add_header_row(ot, ['Sprint / Epic', 'Total', 'Passed', 'Failed', 'Not Run'], fill=DARK_BLUE)
summary_data = [
    ('Sprint 2 — Core Pipeline', '8', '7', '1', '0'),
    ('Sprint 3 — Robustness & Telephony', '16', '13', '3', '0'),
    ('Sprint 4 — Graph API Email', '3', '3', '0', '0'),
    ('Sprint 5-6 — Outlook Email (ISR-216)', '9', '0', '0', '9'),
    ('Sprint 5-6 — WhatsApp (ISR-217)', '6', '0', '0', '6'),
    ('Sprint 5-6 — Phone Calls (ISR-218)', '2', '0', '0', '2'),
    ('Sprint 5-6 — AI Output (ISR-221)', '3', '0', '0', '3'),
    ('Sprint 5-6 — Word Generator (ISR-209)', '2', '0', '0', '2'),
    ('Sprint 5-6 — Dashboard (ISR-222)', '5', '0', '0', '5'),
]
for row in summary_data:
    add_data_row(ot, list(row))
# Totals row
total_row = ot.add_row()
for i, txt in enumerate(['TOTAL', '54', '23', '4', '27']):
    set_cell_text(total_row.cells[i], txt, bold=True, size=Pt(11))
    set_cell_shading(total_row.cells[i], LIGHT_BLUE)

# === CHAPTER 4: FINDINGS ===
doc.add_page_break()
add_heading(doc, 'Chapter 4: Findings', level=1)
add_para(doc,
         'This chapter highlights the key findings derived from the execution of all test cases across '
         'Sprints 2 through 6.')

add_heading(doc, 'Core Pipeline Stability', level=2)
add_para(doc,
         'Finding: The core audio pipeline (upload, transcription, AI form filling, email delivery) is '
         'stable and reliable.')
add_para(doc,
         'Evidence: 19 out of 21 Sprint 2-3 test cases passed. The pipeline handles multi-language audio, '
         'long calls (30+ minutes), Dutch translation, and structured logging without issues.')
add_para(doc,
         'Conclusion: The core pipeline is production-ready for audio-based support call processing.')

add_heading(doc, 'Telephony Integration', level=2)
add_para(doc,
         'Finding: The full telephony pipeline works end-to-end from FreePBX call to incident report.')
add_para(doc,
         'Evidence: All three telephony test cases (TC 22.1-22.3) passed: AMI listener detection, webhook '
         'processing, and full E2E pipeline.')
add_para(doc,
         'Conclusion: Telephony integration is functional and ready for real-provider testing (Vodafone/Twilio).')

add_heading(doc, 'Email Ingestion via Graph API', level=2)
add_para(doc,
         'Finding: Graph API OAuth setup, email retrieval, and attachment handling are functional.')
add_para(doc,
         'Evidence: Sprint 4 test cases (TC 23.1-24.2) all passed. Email classification (ISR-311) is in '
         'progress; signature stripping and MIME support are in testing status.')
add_para(doc,
         'Conclusion: Email pipeline foundation is solid. Classification accuracy and edge cases (threads, '
         'signatures) need Sprint 6 test execution.')

add_heading(doc, 'AI Output Reliability', level=2)
add_para(doc,
         'Finding: A bug was identified where the AI does not correctly recognise or fill in caller/agent '
         'names (ISR-367, status: In Progress).')
add_para(doc,
         'Evidence: Name list feature (ISR-365) is in testing. Gemma model benchmarking (ISR-409) is in '
         'progress to evaluate alternatives to llama3.1.')
add_para(doc,
         'Conclusion: Name recognition needs fixing before production. Model evaluation should complete '
         'before any model switch.')

add_heading(doc, 'Test Coverage Gaps', level=2)
add_para(doc,
         'Finding: The new epic scope (WhatsApp, Dashboard, Case Records, Email Confirmation, Phone Calls) '
         'has zero executed test cases.')
add_para(doc,
         'Evidence: 27 test cases across 6 new epics are defined but all have status "Not Run". Sprint 6 '
         'Jira tasks (ISR-381-408) are created for test plan writing, execution, and reporting.')
add_para(doc,
         'Conclusion: Sprint 6 test execution is critical. The sprint goal explicitly targets verification '
         'of Sprint 5 feature work.')

add_heading(doc, 'Failed Tests', level=2)
add_para(doc, 'Finding: 4 test cases failed across Sprints 2-3.')
ft = doc.add_table(rows=1, cols=3, style='Table Grid')
add_header_row(ft, ['TC ID', 'Feature', 'Reason'], fill=DARK_BLUE)
failed_data = [
    ('TC 8.1', 'Kubernetes Environment',
     'Kubernetes was descoped in favour of Docker Compose deployment'),
    ('TC 9.1', 'Retry and Timeout for Uploads',
     'Retry logic not yet implemented — feature deferred'),
    ('TC 10.1', 'Duplicate Upload Detection',
     'Checksum-based duplicate detection not yet implemented'),
    ('TC 20.1', 'Check Attachment Size Before Email',
     'Size check implemented but test revealed edge case with exact-boundary sizes'),
]
for row in failed_data:
    add_data_row(ft, list(row))

# === CHAPTER 5: RECOMMENDATIONS ===
doc.add_page_break()
add_heading(doc, 'Chapter 5: Recommendations', level=1)
add_para(doc,
         'This chapter outlines key recommendations based on the findings from system testing, the current '
         'Sprint 6 goals, and observed gaps.')

recs = [
    ('Execute pending Sprint 6 test cases before sprint end (June 22)',
     'The 27 "Not Run" test cases should be prioritised during the remaining sprint days. Focus on the '
     'Jira test execution tasks (ISR-382, 385, 388, 391, 394, 397, 407) which are all currently "To Do".'),
    ('Prioritise WhatsApp and Dashboard testing',
     'WhatsApp (ISR-217) and Dashboard (ISR-222) have the most untested user stories. Dashboard login '
     '(US-37) is a production blocker and should be tested first.'),
    ('Re-test failed Sprint 3 items after code fixes',
     'TC 9.1 (retry/timeout), TC 10.1 (duplicate detection), and TC 20.1 (attachment size) should be '
     're-tested if the underlying code has been updated since Sprint 3.'),
    ('Add automated smoke tests for regression',
     'The project currently relies on manual testing and shell scripts. Adding basic automated tests '
     '(e.g., pytest for backend services, health check scripts) would catch regressions faster.'),
    ('Complete Case Records (ISR-219) tests when feature is built',
     'Case linking (US-31, US-32, US-33) is not yet implemented. Test cases should be written and added '
     'to the Test Plan once the feature work begins.'),
    ('Evaluate Gemma model results before switching from llama3.1',
     'ISR-409 (Gemma benchmarking) is in progress. The model switch should only happen after documented '
     'evidence shows improvement across accuracy, latency, and edge case handling.'),
]
for i, (rec_title, detail) in enumerate(recs, 1):
    add_heading(doc, f'{i}. {rec_title}', level=2)
    add_para(doc, detail)

# Save
doc.save(OUTPUT)
print(f'Document saved: {OUTPUT}')
print(f'Size: {os.path.getsize(OUTPUT)} bytes')
