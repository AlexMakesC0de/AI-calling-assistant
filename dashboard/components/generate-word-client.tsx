"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import type { IncidentFormData } from "@/lib/incident-form";

type Status = "idle" | "formatting" | "formatted" | "downloading" | "error";

function confidenceBadge(level: string | undefined) {
  if (!level) return null;
  const variant =
    level === "high"
      ? "solid"
      : level === "medium"
        ? "default"
        : "muted";
  return (
    <Badge variant={variant} className="ml-2 text-xs capitalize">
      {level}
    </Badge>
  );
}

function FieldRow({
  label,
  field,
  value,
  confidence,
  onChange,
  multiline,
}: {
  label: string;
  field: string;
  value: string;
  confidence?: string;
  onChange: (field: string, value: string) => void;
  multiline?: boolean;
}) {
  return (
    <div className="grid gap-1.5">
      <div className="flex items-center">
        <Label htmlFor={field} className="text-sm font-medium">
          {label}
        </Label>
        {confidenceBadge(confidence)}
      </div>
      {multiline ? (
        <Textarea
          id={field}
          value={value}
          onChange={(e) => onChange(field, e.target.value)}
          rows={3}
        />
      ) : (
        <Input
          id={field}
          value={value}
          onChange={(e) => onChange(field, e.target.value)}
        />
      )}
    </div>
  );
}

export function GenerateWordClient() {
  const [transcript, setTranscript] = useState("");
  const [status, setStatus] = useState<Status>("idle");
  const [error, setError] = useState("");
  const [formData, setFormData] = useState<IncidentFormData | null>(null);
  const [confidence, setConfidence] =
    useState<Record<string, string | undefined>>();

  async function handleFormat() {
    setStatus("formatting");
    setError("");
    try {
      const res = await fetch("/api/generate-word/format", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ transcript }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.error ?? `Server error ${res.status}`);
      }
      const data = await res.json();
      setFormData(data);
      const perField = data.confidence?.per_field ?? {};
      setConfidence(perField);
      setStatus("formatted");
    } catch (e) {
      setError((e as Error).message);
      setStatus("error");
    }
  }

  function updateField(dottedPath: string, value: string) {
    if (!formData) return;
    const clone = structuredClone(formData);
    const parts = dottedPath.split(".");
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    let target: any = clone;
    for (let i = 0; i < parts.length - 1; i++) {
      if (!target[parts[i]]) target[parts[i]] = {};
      target = target[parts[i]];
    }
    target[parts[parts.length - 1]] = value;
    setFormData(clone);
  }

  function getField(dottedPath: string): string {
    if (!formData) return "";
    const parts = dottedPath.split(".");
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    let target: any = formData;
    for (const part of parts) {
      if (target == null) return "";
      target = target[part];
    }
    if (Array.isArray(target)) return target.join("; ");
    return target?.toString() ?? "";
  }

  async function handleDownload() {
    if (!formData) return;
    setStatus("downloading");
    setError("");
    try {
      const res = await fetch("/api/generate-word/download", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(formData),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.error ?? `Server error ${res.status}`);
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      const disposition = res.headers.get("Content-Disposition") ?? "";
      const match = disposition.match(/filename="(.+?)"/);
      a.download = match?.[1] ?? "incident-report.docx";
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      setStatus("formatted");
    } catch (e) {
      setError((e as Error).message);
      setStatus("error");
    }
  }

  const sections: {
    title: string;
    fields: {
      label: string;
      path: string;
      confidenceKey?: string;
      multiline?: boolean;
    }[];
  }[] = [
    {
      title: "Caller Information",
      fields: [
        { label: "Name", path: "caller_information.name", confidenceKey: "caller_name" },
        { label: "Account / Reference", path: "caller_information.account_or_reference", confidenceKey: "account_or_reference" },
        { label: "Contact Info", path: "caller_information.contact_info", confidenceKey: "contact_info" },
      ],
    },
    {
      title: "Call Details",
      fields: [
        { label: "Date", path: "call_details.date" },
        { label: "Duration Estimate", path: "call_details.duration_estimate" },
        { label: "Agent Name", path: "call_details.agent_name", confidenceKey: "agent_name" },
      ],
    },
    {
      title: "Issue",
      fields: [
        { label: "Category", path: "issue.category", confidenceKey: "issue_category" },
        { label: "Priority", path: "issue.priority", confidenceKey: "issue_priority" },
        { label: "Description", path: "issue.description", confidenceKey: "issue_description", multiline: true },
        { label: "Error Messages", path: "issue.error_messages", confidenceKey: "error_messages" },
      ],
    },
    {
      title: "Resolution",
      fields: [
        { label: "Status", path: "resolution.status", confidenceKey: "resolution_status" },
        { label: "Steps Taken", path: "resolution.steps_taken", confidenceKey: "steps_taken", multiline: true },
        { label: "Outcome", path: "resolution.outcome", confidenceKey: "resolution_outcome", multiline: true },
      ],
    },
    {
      title: "Follow-up",
      fields: [
        { label: "Required", path: "follow_up.required", confidenceKey: "follow_up_required" },
        { label: "Actions", path: "follow_up.actions", confidenceKey: "follow_up_actions", multiline: true },
        { label: "Department", path: "follow_up.department", confidenceKey: "follow_up_department" },
      ],
    },
    {
      title: "Summary",
      fields: [
        { label: "Customer Sentiment", path: "customer_sentiment", confidenceKey: "customer_sentiment" },
        { label: "Call Summary", path: "call_summary", confidenceKey: "call_summary", multiline: true },
      ],
    },
  ];

  return (
    <div className="space-y-6">
      {/* Step 1: Transcript input */}
      <Card>
        <CardHeader>
          <CardTitle>1. Paste transcript</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <Textarea
            placeholder="Paste the call transcript here..."
            value={transcript}
            onChange={(e) => setTranscript(e.target.value)}
            rows={8}
            disabled={status === "formatting"}
          />
          <Button
            onClick={handleFormat}
            disabled={
              transcript.trim().length === 0 || status === "formatting"
            }
          >
            {status === "formatting" ? "Extracting..." : "Extract form data"}
          </Button>
        </CardContent>
      </Card>

      {error && (
        <Card className="border-destructive">
          <CardContent className="pt-6">
            <p className="text-sm text-destructive">{error}</p>
          </CardContent>
        </Card>
      )}

      {/* Step 2: Review & edit extracted data */}
      {formData && (
        <>
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-medium">2. Review extracted data</h2>
              {formData.confidence?.overall && (
                <p className="text-sm text-muted-foreground">
                  Overall confidence:{" "}
                  <span className="font-medium">
                    {String(formData.confidence.overall)}
                  </span>
                </p>
              )}
            </div>
            <Button
              onClick={handleDownload}
              disabled={status === "downloading"}
            >
              {status === "downloading"
                ? "Generating..."
                : "Download Word document"}
            </Button>
          </div>

          {sections.map((section) => (
            <Card key={section.title}>
              <CardHeader>
                <CardTitle className="text-base">{section.title}</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {section.fields.map((f, i) => (
                  <div key={f.path}>
                    {i > 0 && <Separator className="mb-4" />}
                    <FieldRow
                      label={f.label}
                      field={f.path}
                      value={getField(f.path)}
                      confidence={
                        f.confidenceKey
                          ? confidence?.[f.confidenceKey]
                          : undefined
                      }
                      onChange={updateField}
                      multiline={f.multiline}
                    />
                  </div>
                ))}
              </CardContent>
            </Card>
          ))}

          <div className="flex justify-end">
            <Button
              onClick={handleDownload}
              disabled={status === "downloading"}
              size="lg"
            >
              {status === "downloading"
                ? "Generating..."
                : "Download Word document"}
            </Button>
          </div>
        </>
      )}
    </div>
  );
}
