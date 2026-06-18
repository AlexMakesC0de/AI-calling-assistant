"""
modify_test_plan_v2.py

Opens Test Plan v1.1.docx and makes MINIMAL in-place additions:
- Adds a version row to Table 1 (version history)
- Adds new test items to Table 2
- Adds new functional requirements to Table 3
- Adds new acceptance criteria to Table 5
- Adds new rows to Table 8 (test case index)
- Adds new test case spec tables after existing ones (section 9.2)
- Adds new risks to Table 39
Saves as Test Plan v1.2.docx
"""

from docx import Document
from docx.shared import Pt
from copy import deepcopy

INPUT_PATH = r"D:\Downloads\Test Plan v1.1.docx"
OUTPUT_PATH = r"D:\Downloads\Test Plan v1.2.docx"


def add_row_to_table(table, cells_text):
    """Add a row to an existing table, preserving formatting from the last data row."""
    new_row = table.add_row()
    for i, text in enumerate(cells_text):
        cell = new_row.cells[i]
        cell.text = ""
        p = cell.paragraphs[0]
        run = p.add_run(str(text))
    return new_row


def insert_heading_before(doc, paragraph, text, level):
    """Insert a heading paragraph before a given paragraph."""
    new_p = deepcopy(paragraph._element)
    paragraph._element.addprevious(new_p)
    from docx.oxml.ns import qn
    # Clear existing content
    for child in list(new_p):
        if child.tag.endswith('}r') or child.tag.endswith('}hyperlink'):
            new_p.remove(child)
    # Set heading style
    pPr = new_p.find(qn('w:pPr'))
    if pPr is None:
        pPr = new_p.makeelement(qn('w:pPr'), {})
        new_p.insert(0, pPr)
    pStyle = pPr.find(qn('w:pStyle'))
    if pStyle is None:
        pStyle = pPr.makeelement(qn('w:pStyle'), {})
        pPr.insert(0, pStyle)
    pStyle.set(qn('w:val'), 'Heading3')
    # Add text run
    r = new_p.makeelement(qn('w:r'), {})
    t = r.makeelement(qn('w:t'), {})
    t.text = text
    r.append(t)
    new_p.append(r)
    return new_p


def add_spec_table_after(doc, after_element, spec_data, ref_tbl_element):
    """Add a 7-row x 2-col test case specification table after a given element.
    spec_data is a dict with keys: techniques, test_items, test_level, report_ref, description, steps, expected
    ref_tbl_element is the XML element of a reference spec table to clone.
    """
    from docx.oxml.ns import qn
    from lxml import etree

    ref_table = ref_tbl_element

    # Create a new table element by deep copying the reference
    new_tbl = deepcopy(ref_table)

    # Clear and set cell contents
    rows_data = [
        ("Technique(s):", spec_data["techniques"]),
        ("Test item(s):", spec_data["test_items"]),
        ("Test level:", spec_data["test_level"]),
        ("Test report reference:", spec_data["report_ref"]),
        ("Description", spec_data["description"]),
        ("Steps", spec_data["steps"]),
        ("Expected results", spec_data["expected"]),
    ]

    trs = new_tbl.findall(qn('w:tr'))
    for row_idx, (left_text, right_text) in enumerate(rows_data):
        if row_idx < len(trs):
            tr = trs[row_idx]
            tcs = tr.findall(qn('w:tc'))
            for col_idx, text in enumerate([left_text, right_text]):
                if col_idx < len(tcs):
                    tc = tcs[col_idx]
                    # Clear all paragraphs
                    for p_el in tc.findall(qn('w:p')):
                        for r_el in p_el.findall(qn('w:r')):
                            p_el.remove(r_el)
                        # Add new run with text
                        r_el = p_el.makeelement(qn('w:r'), {})
                        t_el = r_el.makeelement(qn('w:t'), {})
                        t_el.text = text
                        t_el.set(qn('xml:space'), 'preserve')
                        r_el.append(t_el)
                        p_el.append(r_el)

    after_element.addnext(new_tbl)
    return new_tbl


def main():
    doc = Document(INPUT_PATH)

    # Capture all table references BEFORE inserting new tables (indices shift after insert)
    t_version = doc.tables[0]    # Table 1: Version History
    t_items = doc.tables[1]      # Table 2: Test Items
    t_reqs = doc.tables[2]       # Table 3: Functional Requirements
    t_index = doc.tables[7]      # Table 8: Test Case Index
    ref_spec_tbl = doc.tables[8] # Table 9: Reference spec card for cloning
    last_spec_tbl = doc.tables[34] # Table 35: Last spec card
    t_risks_39 = doc.tables[38]  # Table 39: Key Risks (5 cols)
    t_risks_40 = doc.tables[39]  # Table 40: Risks and Mitigation (3 cols)

    # === 1. Version History ===
    add_row_to_table(t_version, [
        "1.2", "14.06.2026", "Sviatoslav Zubrytskyi",
        "Added Sprint 5-6 test items, requirements, test cases, and risks for new epics (Outlook Email, WhatsApp, Phone Calls, AI Output, Dashboard, Word Generator)."
    ])

    # === 2. Test Items ===
    new_items = [
        ("Email Classifier", "Ollama LLM-based classification of inbound emails as support / not-support / unclear before case creation.", "False positives create junk cases; threshold sensitivity"),
        ("WhatsApp Ingest", "Twilio webhook receiver for WhatsApp text messages, voice notes, and media attachments.", "Signature validation failure; media download timeout"),
        ("Dashboard Auth", "Session-based login gating all dashboard routes except login and health check.", "Session bypass exposes customer data"),
        ("Semantic Search", "pgvector cosine similarity search over transcript embeddings for finding incidents.", "Embedding quality dependent on Ollama model"),
        ("Email Signature Stripper", "Preprocessing step to strip signatures and quoted replies from inbound emails before classification.", "Over-stripping removes relevant content from email body"),
        ("Gemma Model", "Alternative Ollama AI model benchmarking against llama3.1 for incident form generation.", "Quality regression on edge cases compared to llama3.1"),
    ]
    for item in new_items:
        add_row_to_table(t_items, list(item))

    # === 3. Functional Requirements ===
    new_reqs = [
        ("ISR-238", "Must-Have", "Inbound support emails flow through the pipeline end-to-end and produce an incident form."),
        ("ISR-311", "Should-Have", "Inbound emails are classified as support / not-support / unclear before case creation."),
        ("ISR-317", "Should-Have", "Email attachments are downloaded and stored per case."),
        ("ISR-226", "Must-Have", "WhatsApp messages are received and stored via Twilio webhook."),
        ("ISR-227", "Should-Have", "WhatsApp auto-acknowledgment is sent upon receiving a message."),
        ("ISR-339", "Must-Have", "Real provider call recordings are captured via Twilio webhook."),
        ("ISR-365", "Should-Have", "Name list improves AI caller/agent name recognition."),
        ("ISR-409", "Should-Have", "Gemma model is benchmarked against llama3.1 for quality and latency."),
        ("ISR-375", "Should-Have", "Profanity words are filtered from AI-generated output."),
        ("ISR-232", "Must-Have", "Word document uses Repak's Problem/Analysis/Advice format."),
        ("ISR-401", "Should-Have", "Dashboard login gates all routes; invalid credentials are rejected."),
        ("ISR-400", "Should-Have", "Semantic search over transcripts using pgvector cosine similarity."),
    ]
    for req in new_reqs:
        add_row_to_table(t_reqs, list(req))

    # === 4. Test Case Index ===
    new_cases = [
        ("26", "ISR-238", "TC 25.1", "Email Pipeline End-to-End", "Integration", "Sprint 5 #28"),
        ("27", "ISR-243", "TC 25.2", "Email Body to Formatter (bypass transcriber)", "Component", "Sprint 5 #29"),
        ("28", "ISR-346", "TC 25.6", "Email Signature Stripping", "Component", "Sprint 5 #30"),
        ("29", "ISR-349", "TC 25.7", "Plain-text and MIME Email Support", "Component", "Sprint 5 #31"),
        ("30", "ISR-347", "TC 25.8", "Email Thread Deduplication", "Integration", "Sprint 5 #32"),
        ("31", "ISR-311", "TC 26.1", "Email Classification (support/junk/unclear)", "Component", "Sprint 5 #33"),
        ("32", "ISR-311", "TC 26.2", "Low-Confidence Email Flagging", "Integration", "Sprint 5 #34"),
        ("33", "ISR-317", "TC 27.1", "Email Attachments Stored Per Case", "Component", "Sprint 5 #35"),
        ("34", "ISR-320", "TC 27.2", "Oversized Attachment Handling", "Integration", "Sprint 5 #36"),
        ("35", "ISR-226", "TC 28.1", "Twilio Webhook Receives WhatsApp Message", "Component", "Sprint 5 #37"),
        ("36", "ISR-226", "TC 28.2", "Voice Note Forwarded to Transcriber", "Integration", "Sprint 5 #38"),
        ("37", "ISR-226", "TC 28.3", "WhatsApp Media Download and Storage", "Component", "Sprint 5 #39"),
        ("38", "ISR-226", "TC 28.4", "Twilio Signature Validation", "Component", "Sprint 5 #40"),
        ("39", "ISR-352", "TC 28.5", "Multi-Message Grouping (10-min window)", "Integration", "Sprint 5 #41"),
        ("40", "ISR-227", "TC 29.1", "WhatsApp Auto-Acknowledgment", "Component", "Sprint 5 #42"),
        ("41", "ISR-339", "TC 30.1", "Twilio Recording Webhook Received", "Component", "Sprint 6 #43"),
        ("42", "ISR-340", "TC 30.3", "Recording Failure Does Not Block Call", "Component", "Sprint 6 #44"),
        ("43", "ISR-365", "TC 36.1", "Name List Improves AI Recognition", "Component", "Sprint 6 #45"),
        ("44", "ISR-409", "TC 36.5", "Gemma Model Performance Benchmark", "Component", "Sprint 6 #46"),
        ("45", "ISR-375", "TC 36.6", "Profanity Word Filtering", "Component", "Sprint 6 #47"),
        ("46", "ISR-232", "TC 34.1", "Word Doc Problem/Analysis/Advice Format", "Component", "Sprint 6 #48"),
        ("47", "ISR-232", "TC 34.2", "Bulk Word Generation from Multiple Incidents", "Integration", "Sprint 6 #49"),
        ("48", "ISR-401", "TC 37.1", "Login Gates All Routes", "Component", "Sprint 6 #50"),
        ("49", "ISR-401", "TC 37.2", "Invalid Credentials Rejected", "Component", "Sprint 6 #51"),
        ("50", "ISR-401", "TC 37.4", "Admin Create/Delete Accounts", "Acceptance", "Sprint 6 #52"),
        ("51", "ISR-403", "TC 38.1", "Incident List Filtering", "Component", "Sprint 6 #53"),
        ("52", "ISR-400", "TC 38.3", "Semantic Search (pgvector)", "Integration", "Sprint 6 #54"),
    ]
    for case in new_cases:
        add_row_to_table(t_index, list(case))

    # === 5. Test Case Specification Tables (after existing Table 35, section 9.2) ===
    # Each spec is a 2-col, 7-row table matching the existing format
    spec_cards = [
        {
            "heading": "ISR-238: Email Pipeline End-to-End",
            "techniques": "Scenario / use-case based, State-based / workflow focus",
            "test_items": "Email Monitor, Transcript Formatter, Ollama LLM, Email Sender",
            "test_level": "Integration",
            "report_ref": "Sprint 5 #28",
            "description": "Given an inbound support email arrives in the Outlook inbox, when the email monitor picks it up, the body is sent to the formatter, processed by LLM, and an incident form is created.",
            "steps": "1. Send a test support email to the monitored Outlook inbox\n2. Wait for the email monitor to detect and process it\n3. Check that the email body is forwarded to the formatter service\n4. Verify an incident form is generated in the database\n5. Confirm a confirmation email is sent",
            "expected": "1. Email is detected within the polling interval\n2. Email body is correctly extracted and passed to the formatter\n3. Incident form is created with Problem/Analysis/Advice fields populated\n4. Confirmation email arrives at the configured address",
        },
        {
            "heading": "ISR-243: Email Body to Formatter",
            "techniques": "Data-focused checks, State-based / workflow focus",
            "test_items": "Email Monitor, Transcript Formatter",
            "test_level": "Component",
            "report_ref": "Sprint 5 #29",
            "description": "Given an email is received, the email body text is sent directly to the formatter service, bypassing the transcriber (since email text does not need speech-to-text).",
            "steps": "1. Send a test email with a clear support request in the body\n2. Monitor the formatter service logs\n3. Verify the email text arrives at the formatter without going through the transcriber",
            "expected": "1. Formatter receives the email body text directly\n2. Transcriber is not invoked for email-type inputs\n3. The resulting incident form contains the email content",
        },
        {
            "heading": "ISR-346: Email Signature Stripping",
            "techniques": "Data-focused checks, Scenario / use-case based",
            "test_items": "Email Signature Stripper, Email Monitor",
            "test_level": "Component",
            "report_ref": "Sprint 5 #30",
            "description": "Given an inbound email contains a signature block (e.g. 'Kind regards, Name, Company'), the signature is stripped before the body is sent to the formatter.",
            "steps": "1. Send a test email with a standard signature block\n2. Check the text passed to the formatter\n3. Verify the signature is removed\n4. Test with various signature formats (dashes, 'Sent from iPhone', etc.)",
            "expected": "1. Signature block is removed from the email body\n2. Main email content is preserved intact\n3. Different signature formats are all handled",
        },
        {
            "heading": "ISR-349: Plain-text and MIME Email Support",
            "techniques": "Data-focused checks, Scenario / use-case based",
            "test_items": "Email Monitor",
            "test_level": "Component",
            "report_ref": "Sprint 5 #31",
            "description": "Given emails arrive in different formats (HTML, plain-text, multipart MIME), the system extracts the text body correctly regardless of format.",
            "steps": "1. Send a plain-text email\n2. Send an HTML-only email\n3. Send a multipart MIME email\n4. Verify each is processed and text content is extracted",
            "expected": "1. Plain-text email body is extracted as-is\n2. HTML email has tags stripped, text content preserved\n3. Multipart MIME email selects the text part correctly",
        },
        {
            "heading": "ISR-347: Email Thread Deduplication",
            "techniques": "Scenario / use-case based, Data-focused checks",
            "test_items": "Email Monitor",
            "test_level": "Integration",
            "report_ref": "Sprint 5 #32",
            "description": "Given a reply email contains quoted previous messages, only the new content is processed to avoid creating duplicate incidents from the same thread.",
            "steps": "1. Send an initial support email\n2. Reply to that email with additional info\n3. Verify only the new reply content is processed\n4. Check that a duplicate incident is not created",
            "expected": "1. Quoted/previous content is detected and stripped\n2. Only new reply text is sent to the formatter\n3. No duplicate incident forms are generated",
        },
        {
            "heading": "ISR-311: Email Classification",
            "techniques": "Data-focused checks, Scenario / use-case based",
            "test_items": "Email Classifier, Ollama LLM",
            "test_level": "Component",
            "report_ref": "Sprint 5 #33",
            "description": "Given an inbound email, the LLM classifies it as support / not-support / unclear before a case is created.",
            "steps": "1. Send a clear support request email\n2. Send a newsletter/spam email\n3. Send an ambiguous email\n4. Check classification result for each",
            "expected": "1. Support email is classified as 'support' and enters the pipeline\n2. Newsletter is classified as 'not-support' and is logged but not processed\n3. Ambiguous email is classified as 'unclear' and flagged for review",
        },
        {
            "heading": "ISR-311: Low-Confidence Email Flagging",
            "techniques": "Data-focused checks, State-based / workflow focus",
            "test_items": "Email Classifier, Dashboard",
            "test_level": "Integration",
            "report_ref": "Sprint 5 #34",
            "description": "Given an email classified as 'unclear', a low-confidence case is created and flagged for engineer review in the dashboard.",
            "steps": "1. Send an ambiguous email that triggers 'unclear' classification\n2. Verify a case is created with low-confidence flag\n3. Check the dashboard shows the flagged case",
            "expected": "1. Unclear emails create a case with a confidence flag\n2. The case appears in the dashboard with visual indication of low confidence\n3. Engineer can review and reclassify",
        },
        {
            "heading": "ISR-317: Email Attachments Stored Per Case",
            "techniques": "Data-focused checks, Scenario / use-case based",
            "test_items": "Email Monitor, File Storage",
            "test_level": "Component",
            "report_ref": "Sprint 5 #35",
            "description": "Given a support email has attachments (images, PDFs), they are downloaded and stored alongside the case record.",
            "steps": "1. Send a support email with a JPEG image attached\n2. Send a support email with a PDF document attached\n3. Verify attachments are downloaded and stored in the case directory\n4. Check the incident form references the attachments",
            "expected": "1. Image attachment is stored in the case folder\n2. PDF attachment is stored in the case folder\n3. File paths are referenced in the incident form\n4. Original filenames are preserved",
        },
        {
            "heading": "ISR-320: Oversized Attachment Handling",
            "techniques": "Data-focused checks, Scenario / use-case based",
            "test_items": "Email Monitor, File Storage",
            "test_level": "Integration",
            "report_ref": "Sprint 5 #36",
            "description": "Given an email attachment exceeds the configured size limit (10 MB), it is logged and the engineer is notified rather than silently dropped.",
            "steps": "1. Send an email with an attachment larger than 10 MB\n2. Check that the attachment is not downloaded\n3. Verify a log entry is created\n4. Confirm engineer notification is triggered",
            "expected": "1. Oversized attachment is rejected\n2. A warning is logged with the filename and size\n3. Engineer receives notification about the skipped attachment\n4. The rest of the email is still processed normally",
        },
        {
            "heading": "ISR-226: Twilio Webhook Receives WhatsApp Message",
            "techniques": "Scenario / use-case based, Configuration / deployment checks",
            "test_items": "WhatsApp Ingest, Twilio Webhook",
            "test_level": "Component",
            "report_ref": "Sprint 5 #37",
            "description": "Given a WhatsApp message is sent to the Twilio number, the webhook endpoint receives and stores the message.",
            "steps": "1. Send a WhatsApp text message to the configured Twilio number\n2. Check the webhook endpoint logs for the incoming request\n3. Verify the message body is stored in the database\n4. Check the sender phone number is recorded",
            "expected": "1. Webhook receives the message within seconds\n2. Message body is stored correctly\n3. Sender number is associated with the message\n4. Timestamp is recorded",
        },
        {
            "heading": "ISR-226: Voice Note Forwarded to Transcriber",
            "techniques": "State-based / workflow focus, Data-focused checks",
            "test_items": "WhatsApp Ingest, Transcriber Service",
            "test_level": "Integration",
            "report_ref": "Sprint 5 #38",
            "description": "Given a WhatsApp voice note is received, it is downloaded and forwarded to the transcriber service for speech-to-text processing.",
            "steps": "1. Send a WhatsApp voice note to the Twilio number\n2. Verify the voice note media is downloaded from Twilio\n3. Check that the audio file is forwarded to the transcriber\n4. Verify a transcript is produced",
            "expected": "1. Voice note audio is downloaded and stored\n2. Audio is sent to the transcriber service\n3. Transcript text is generated from the voice note\n4. Transcript enters the formatter pipeline",
        },
        {
            "heading": "ISR-226: WhatsApp Media Download and Storage",
            "techniques": "Data-focused checks, Configuration / deployment checks",
            "test_items": "WhatsApp Ingest, File Storage",
            "test_level": "Component",
            "report_ref": "Sprint 5 #39",
            "description": "Given a WhatsApp message includes media (image, document), the media is downloaded from Twilio and stored on disk.",
            "steps": "1. Send a WhatsApp message with an image attachment\n2. Send a WhatsApp message with a document attachment\n3. Verify media files are downloaded via Twilio media URL\n4. Check files are stored in the expected directory",
            "expected": "1. Image is downloaded and stored with correct MIME type\n2. Document is downloaded and stored\n3. Files are accessible from the case directory\n4. Media metadata (type, size) is recorded in the database",
        },
        {
            "heading": "ISR-226: Twilio Signature Validation",
            "techniques": "Scenario / use-case based, Configuration / deployment checks",
            "test_items": "WhatsApp Ingest, Twilio Webhook",
            "test_level": "Component",
            "report_ref": "Sprint 5 #40",
            "description": "Given an incoming webhook request, the Twilio signature header is validated to prevent spoofed messages from being processed.",
            "steps": "1. Send a legitimate WhatsApp message (valid Twilio signature)\n2. Send a crafted HTTP request with an invalid signature header\n3. Send a request with no signature header\n4. Check processing status for each",
            "expected": "1. Valid signature: message is accepted and processed\n2. Invalid signature: request is rejected with 403\n3. Missing signature: request is rejected with 403\n4. Rejected requests are logged for security auditing",
        },
        {
            "heading": "ISR-352: Multi-Message Grouping (10-min window)",
            "techniques": "Scenario / use-case based, State-based / workflow focus",
            "test_items": "WhatsApp Ingest",
            "test_level": "Integration",
            "report_ref": "Sprint 5 #41",
            "description": "Given multiple WhatsApp messages arrive from the same sender within a 10-minute window, they are grouped into a single conversation/case rather than creating separate incidents.",
            "steps": "1. Send three WhatsApp messages from the same number within 5 minutes\n2. Wait 15 minutes, then send another message\n3. Check how messages are grouped\n4. Verify the grouped messages form one incident",
            "expected": "1. Three messages within 5 minutes are grouped into one conversation\n2. The message after 15 minutes starts a new conversation\n3. The incident form for the first group contains all three messages\n4. Grouping is based on sender number + time window",
        },
        {
            "heading": "ISR-227: WhatsApp Auto-Acknowledgment",
            "techniques": "Scenario / use-case based, Data-focused checks",
            "test_items": "WhatsApp Ingest, Twilio API",
            "test_level": "Component",
            "report_ref": "Sprint 5 #42",
            "description": "Given a WhatsApp message is received, an auto-acknowledgment reply is sent to the sender confirming receipt.",
            "steps": "1. Send a WhatsApp message to the Twilio number\n2. Check that an auto-reply is sent back\n3. Verify the reply content is appropriate\n4. Check that the reply is sent only once per message",
            "expected": "1. Auto-acknowledgment is sent within seconds\n2. Reply confirms message receipt\n3. No duplicate replies are sent\n4. Reply is logged in the system",
        },
        {
            "heading": "ISR-339: Twilio Recording Webhook Received",
            "techniques": "Scenario / use-case based, Configuration / deployment checks",
            "test_items": "Telephony Ingest, Twilio API",
            "test_level": "Component",
            "report_ref": "Sprint 6 #43",
            "description": "Given a phone call is completed via Twilio, the recording webhook delivers the audio URL to the telephony-ingest service.",
            "steps": "1. Initiate a test call through Twilio\n2. Complete the call so a recording is generated\n3. Check that the recording webhook fires\n4. Verify the telephony-ingest service receives the recording URL",
            "expected": "1. Recording webhook fires after call completion\n2. Audio URL is received by telephony-ingest\n3. Recording metadata (duration, caller, timestamp) is logged\n4. Audio is queued for transcription",
        },
        {
            "heading": "ISR-340: Recording Failure Does Not Block Call",
            "techniques": "Scenario / use-case based, State-based / workflow focus",
            "test_items": "Telephony Ingest, Twilio API",
            "test_level": "Component",
            "report_ref": "Sprint 6 #44",
            "description": "Given the recording service fails or is unavailable, the live phone call continues without interruption.",
            "steps": "1. Simulate a recording service failure (stop the service)\n2. Initiate a test call through Twilio\n3. Verify the call proceeds normally for the human agents\n4. Check error logs for the recording failure",
            "expected": "1. Phone call completes successfully despite recording failure\n2. An error is logged indicating recording was not captured\n3. No interruption or audio quality degradation for the callers\n4. System recovers when the recording service comes back",
        },
        {
            "heading": "ISR-365: Name List Improves AI Recognition",
            "techniques": "Data-focused checks, Scenario / use-case based",
            "test_items": "Ollama LLM, Transcript Formatter, Name List",
            "test_level": "Component",
            "report_ref": "Sprint 6 #45",
            "description": "Given a name list of known callers/agents is configured, the AI uses it to improve name recognition in generated incident forms.",
            "steps": "1. Configure a name list with known caller and agent names\n2. Process a transcript where names are mentioned\n3. Compare AI output with and without the name list\n4. Verify names in the incident form match the name list",
            "expected": "1. With name list: caller/agent names are correctly identified\n2. Without name list: names may be misspelled or missing\n3. Name list entries appear in the correct form fields\n4. Unknown names are still captured as-is",
        },
        {
            "heading": "ISR-409: Gemma Model Performance Benchmark",
            "techniques": "Data-focused checks, Scenario / use-case based",
            "test_items": "Ollama LLM (Gemma), Ollama LLM (llama3.1)",
            "test_level": "Component",
            "report_ref": "Sprint 6 #46",
            "description": "Given the same set of test transcripts, compare Gemma and llama3.1 output quality, latency, and edge case handling.",
            "steps": "1. Prepare a set of 10+ test transcripts (varied complexity)\n2. Process each through both Gemma and llama3.1\n3. Compare output quality (accuracy, completeness)\n4. Measure response latency for each model\n5. Test edge cases (short calls, multilingual, poor audio)",
            "expected": "1. Quality comparison documented per transcript\n2. Latency measurements recorded\n3. Edge case results documented\n4. Recommendation made based on evidence",
        },
        {
            "heading": "ISR-375: Profanity Word Filtering",
            "techniques": "Data-focused checks, Scenario / use-case based",
            "test_items": "Ollama LLM, Transcript Formatter, Profanity Filter",
            "test_level": "Component",
            "report_ref": "Sprint 6 #47",
            "description": "Given a transcript contains profanity, the words are filtered or masked in the generated incident form.",
            "steps": "1. Process a transcript containing profanity words\n2. Check the generated incident form for profanity\n3. Verify filtered words are masked or replaced\n4. Ensure non-profanity words are not affected",
            "expected": "1. Profanity words are masked (e.g., '****') in the output\n2. Context around the profanity is preserved\n3. Non-profanity words remain unchanged\n4. Filter works across languages if configured",
        },
        {
            "heading": "ISR-232: Word Doc Problem/Analysis/Advice Format",
            "techniques": "Data-focused checks, Scenario / use-case based",
            "test_items": "Word Generator",
            "test_level": "Component",
            "report_ref": "Sprint 6 #48",
            "description": "Given an incident form is complete, the Word document generator outputs a file using Repak's Problem / Analysis / Advice format.",
            "steps": "1. Generate a Word document from a completed incident form\n2. Open the document and check section structure\n3. Verify Problem / Analysis / Advice sections exist\n4. Check header metadata (case ID, date, channel, agent, caller)",
            "expected": "1. Word document is generated successfully\n2. Document has Problem, Analysis, and Advice sections\n3. Each section contains AI-extracted content\n4. Header metadata is correct and complete",
        },
        {
            "heading": "ISR-232: Bulk Word Generation",
            "techniques": "State-based / workflow focus, Scenario / use-case based",
            "test_items": "Word Generator, Dashboard",
            "test_level": "Integration",
            "report_ref": "Sprint 6 #49",
            "description": "Given multiple incidents are selected in the dashboard, a bulk Word generation produces individual documents for each.",
            "steps": "1. Select 3+ incidents in the dashboard\n2. Trigger bulk Word generation\n3. Verify a document is created for each incident\n4. Check each document has correct content",
            "expected": "1. All selected incidents produce individual Word documents\n2. Each document is correctly formatted\n3. No documents are skipped or duplicated\n4. Generation completes within reasonable time",
        },
        {
            "heading": "ISR-401: Login Gates All Routes",
            "techniques": "Scenario / use-case based, Configuration / deployment checks",
            "test_items": "Dashboard Auth, Next.js Middleware",
            "test_level": "Component",
            "report_ref": "Sprint 6 #50",
            "description": "Given the dashboard requires authentication, all routes except login and health check redirect unauthenticated users to the login page.",
            "steps": "1. Access the dashboard root URL without authentication\n2. Try accessing /incidents, /cases, /search directly\n3. Access /login and /api/health without authentication\n4. Log in and verify all routes become accessible",
            "expected": "1. Unauthenticated requests to protected routes redirect to /login\n2. /login and /api/health are accessible without authentication\n3. After login, all routes are accessible\n4. Session persists across page navigations",
        },
        {
            "heading": "ISR-401: Invalid Credentials Rejected",
            "techniques": "Scenario / use-case based, Data-focused checks",
            "test_items": "Dashboard Auth",
            "test_level": "Component",
            "report_ref": "Sprint 6 #51",
            "description": "Given a user enters invalid credentials on the login page, access is denied with an appropriate error message.",
            "steps": "1. Enter a wrong username with correct password\n2. Enter correct username with wrong password\n3. Enter empty credentials\n4. Verify error messages and that no session is created",
            "expected": "1. Invalid credentials show an error message\n2. No session cookie is set on failure\n3. Login page remains accessible for retry\n4. Failed attempts are logged",
        },
        {
            "heading": "ISR-401: Admin Create/Delete Accounts",
            "techniques": "Scenario / use-case based, Data-focused checks",
            "test_items": "Dashboard Auth, Admin Panel",
            "test_level": "Acceptance",
            "report_ref": "Sprint 6 #52",
            "description": "Given an admin user is logged in, they can create and delete user accounts from the admin panel.",
            "steps": "1. Log in as admin\n2. Navigate to user management\n3. Create a new user account\n4. Log in with the new account\n5. Delete the new account as admin\n6. Verify the deleted account can no longer log in",
            "expected": "1. Admin can access user management panel\n2. New user account is created successfully\n3. New user can log in\n4. Deleted user can no longer log in\n5. Actions are audited",
        },
        {
            "heading": "ISR-403: Incident List Filtering",
            "techniques": "Scenario / use-case based, Data-focused checks",
            "test_items": "Dashboard, Database",
            "test_level": "Component",
            "report_ref": "Sprint 6 #53",
            "description": "Given the dashboard incident list page, engineers can filter incidents by status, channel, date, and search by caller name.",
            "steps": "1. Open the incident list page\n2. Apply status filter (e.g., 'open' only)\n3. Apply channel filter (e.g., 'email' only)\n4. Search by caller name\n5. Combine multiple filters",
            "expected": "1. Status filter shows only matching incidents\n2. Channel filter shows only matching incidents\n3. Name search returns relevant results\n4. Combined filters work together correctly\n5. Results are paginated",
        },
        {
            "heading": "ISR-400: Semantic Search (pgvector)",
            "techniques": "Data-focused checks, Scenario / use-case based",
            "test_items": "Dashboard, pgvector, Ollama Embeddings",
            "test_level": "Integration",
            "report_ref": "Sprint 6 #54",
            "description": "Given a search query is entered in the dashboard, pgvector cosine similarity finds semantically related incidents even if exact keywords do not match.",
            "steps": "1. Create several test incidents with varied content\n2. Search for a concept using different wording than the stored text\n3. Verify semantically similar incidents are returned\n4. Check relevance ranking",
            "expected": "1. Semantic search returns relevant results despite different wording\n2. Results are ranked by similarity score\n3. Exact keyword matches are ranked higher\n4. Search completes within acceptable latency (<2s)",
        },
    ]

    # Insert new spec card tables after the last existing spec table

    last_spec_table_element = last_spec_tbl._tbl

    # We'll insert in reverse order so each new element goes right after the last spec table
    # Actually, let's insert forward - each new item goes after the previous one
    insert_after = last_spec_table_element

    for spec in spec_cards:
        # Add a heading paragraph
        from docx.oxml.ns import qn as _qn
        from lxml import etree

        # Create heading paragraph
        heading_p = doc.add_paragraph()._element
        # Remove it from end of document
        heading_p.getparent().remove(heading_p)

        # Set heading style
        pPr = heading_p.find(_qn('w:pPr'))
        if pPr is None:
            pPr = heading_p.makeelement(_qn('w:pPr'), {})
            heading_p.insert(0, pPr)
        pStyle = pPr.find(_qn('w:pStyle'))
        if pStyle is None:
            pStyle = pPr.makeelement(_qn('w:pStyle'), {})
            pPr.append(pStyle)
        pStyle.set(_qn('w:val'), 'Heading3')
        # Add text
        r = heading_p.makeelement(_qn('w:r'), {})
        t = r.makeelement(_qn('w:t'), {})
        t.text = spec["heading"]
        t.set(_qn('xml:space'), 'preserve')
        r.append(t)
        heading_p.append(r)

        insert_after.addnext(heading_p)
        insert_after = heading_p

        # Add spec table
        new_tbl = add_spec_table_after(doc, insert_after, spec, ref_spec_tbl._tbl)
        insert_after = new_tbl

    # === 6. Key Risks — Table 39 (5 cols: ID | Description | Probability | Impact | Mitigation) ===
    new_risks_39 = [
        ("R5", "Email classifier false positives create junk cases", "3", "3",
         "Test with 30+ real emails; tune threshold; add engineer override"),
        ("R6", "WhatsApp Twilio signature validation fails in production", "2", "4",
         "Test with real Twilio account in staging; document configuration"),
        ("R7", "Gemma model quality regression vs llama3.1 on edge cases", "3", "3",
         "Benchmark both models with identical test data before switching"),
        ("R8", "Dashboard session bypass exposes customer data", "2", "5",
         "Security review of middleware; test with dev tools; HTTPS-only cookies"),
    ]
    for risk in new_risks_39:
        add_row_to_table(t_risks_39, list(risk))

    # === 7. Risks and Mitigation — Table 40 (3 cols: Risk | Possible Impact | Mitigation) ===
    new_risks_40 = [
        ("Email classifier creates false support cases from newsletters/spam",
         "Engineers waste time reviewing junk cases; trust in system decreases",
         "Test with diverse real email set; tune confidence threshold; add manual override"),
        ("WhatsApp webhook signature validation rejects legitimate messages",
         "Customer messages are silently dropped; support requests missed",
         "Test with real Twilio account; add fallback logging for rejected messages"),
        ("AI model switch (Gemma) degrades output quality",
         "Misleading incident forms; engineers must manually correct AI output",
         "Benchmark both models with same data; only switch after documented evidence"),
        ("Dashboard session bypass exposes customer support data",
         "Unauthorized access to customer data; privacy/compliance violation",
         "Security audit of Next.js middleware; enforce HTTPS-only session cookies"),
    ]
    for risk in new_risks_40:
        add_row_to_table(t_risks_40, list(risk))

    # === Save ===
    doc.save(OUTPUT_PATH)
    print("Saved to " + OUTPUT_PATH)

    # Verify
    import os
    size = os.path.getsize(OUTPUT_PATH)
    print("File size: " + str(size) + " bytes")

    # Quick check
    check = Document(OUTPUT_PATH)
    print("Tables: " + str(len(check.tables)))
    print("Test case index rows: " + str(len(check.tables[7].rows)))


if __name__ == "__main__":
    main()
