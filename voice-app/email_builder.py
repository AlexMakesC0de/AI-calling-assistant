from typing import Any


class EmailBodyBuilder:
    @staticmethod
    def build(form: dict[str, Any]) -> str:
        issue = form.get("issue", {})
        resolution = form.get("resolution", {})
        caller = form.get("caller_information", {})
        call = form.get("call_details", {})
        follow_up = form.get("follow_up", {})
        confidence = form.get("confidence", {})

        steps = "\n".join(f"  - {s}" for s in resolution.get("steps_taken", [])) or "  (none)"
        follow_actions = "\n".join(f"  - {a}" for a in follow_up.get("actions", [])) or "  (none)"

        confidence_section = ""
        if confidence:
            overall = confidence.get("overall")
            low_fields = confidence.get("low_confidence_fields", [])
            if overall:
                confidence_section = f"\n\nAI CONFIDENCE: {overall}"
            if low_fields:
                confidence_section += "\n  ⚠ Low-confidence fields (may need manual review):"
                for field in low_fields:
                    confidence_section += f"\n    - {field}"

        return f"""An incident form has been automatically completed from a support call recording.

═══ FORM ID: {form.get('form_id', 'N/A')} ═══

CALLER INFORMATION
  Name:      {caller.get('name', 'N/A')}
  Account:   {caller.get('account_or_reference', 'N/A')}
  Contact:   {caller.get('contact_info', 'N/A')}

CALL DETAILS
  Date:      {call.get('date', 'N/A')}
  Agent:     {call.get('agent_name', 'N/A')}
  Duration:  {call.get('duration_estimate', 'N/A')}

ISSUE
  Category:  {issue.get('category', 'N/A')}
  Priority:  {issue.get('priority', 'N/A')}
  Description: {issue.get('description', 'N/A')}
  Error messages: {issue.get('error_messages', 'None')}

RESOLUTION
  Status:    {resolution.get('status', 'N/A')}
  Steps taken:
{steps}
  Outcome:   {resolution.get('outcome', 'N/A')}

FOLLOW-UP
  Required:  {'Yes' if follow_up.get('required') else 'No'}
  Actions:
{follow_actions}
  Department: {follow_up.get('department', 'N/A')}

CUSTOMER SENTIMENT: {form.get('customer_sentiment', 'N/A')}
{confidence_section}

SUMMARY
{form.get('call_summary', 'N/A')}

───────────────────────────────────────
The full form data and transcript are attached as JSON below.
This form was generated automatically by the AI system.
"""