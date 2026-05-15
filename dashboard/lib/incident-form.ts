// Shape of the JSON document the transcript-formatter writes into
// `incident_general_information.form_data`. Defined as a Zod-light type — we
// don't want to over-validate, since the AI may add fields the dashboard
// hasn't seen. Treat unknown fields as opaque rather than rejecting them.
export type IncidentFormData = {
  form_id?: string;
  completed_at?: string;
  status?: string;
  caller_information?: { name?: string; account_or_reference?: string; contact_info?: string };
  call_details?: { date?: string; agent_name?: string; duration_estimate?: string };
  issue?: { category?: string; priority?: string; description?: string; error_messages?: string };
  resolution?: { status?: string; steps_taken?: string[] | string; outcome?: string };
  follow_up?: { required?: boolean; actions?: string[] | string; department?: string };
  customer_sentiment?: string;
  call_summary?: string;
  confidence?: { overall?: string | number } & Record<string, unknown>;
  transcript?: { full_text?: string; word_count?: number };
  metadata?: Record<string, unknown>;
  translated_nl?: { transcript_text?: string; call_summary?: string; issue_description?: string };
};

export function asFormData(value: unknown): IncidentFormData {
  if (!value || typeof value !== "object") return {};
  return value as IncidentFormData;
}

export function stepsToList(value: string[] | string | undefined): string[] {
  if (Array.isArray(value)) return value.filter((s) => typeof s === "string" && s.trim().length > 0);
  if (typeof value === "string" && value.trim().length > 0) {
    return value.split(/\n|;/).map((s) => s.trim()).filter(Boolean);
  }
  return [];
}

export function sentimentTone(sentiment: string | undefined | null): "neutral" | "positive" | "negative" {
  if (!sentiment) return "neutral";
  const s = sentiment.toLowerCase();
  if (/(positive|happy|satisfied|pleased)/.test(s)) return "positive";
  if (/(negative|frustrated|angry|upset|annoyed|unhappy)/.test(s)) return "negative";
  return "neutral";
}
