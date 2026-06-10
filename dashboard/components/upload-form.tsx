"use client";

import { useState, useTransition } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { uploadAndAnalyzeAudio, type UploadResult } from "@/app/upload/actions";

export function UploadForm() {
  const [pending, startTransition] = useTransition();
  const [result, setResult] = useState<UploadResult | null>(null);

  function handleSubmit(formData: FormData) {
    setResult(null);
    startTransition(async () => {
      const next = await uploadAndAnalyzeAudio(formData);
      setResult(next);
    });
  }

  return (
    <div className="space-y-6">
      <form action={handleSubmit} className="space-y-4">
        <div className="space-y-1.5">
          <Label htmlFor="audio">Audio file</Label>
          <Input id="audio" name="audio" type="file" accept="audio/*,.wav,.mp3,.ogg,.flac,.m4a,.webm" required />
          <p className="text-xs text-muted-foreground">
            wav, mp3, ogg, flac, m4a, webm. Max 50&nbsp;MB. Pipeline takes ~30–120s on CPU.
          </p>
        </div>

        <Separator />

        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <div className="space-y-1.5">
            <Label htmlFor="callerName">Caller name</Label>
            <Input id="callerName" name="callerName" placeholder="Optional — overrides AI guess" />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="accountOrReference">Account / reference</Label>
            <Input id="accountOrReference" name="accountOrReference" placeholder="e.g. AC-7781" />
          </div>
          <div className="space-y-1.5 md:col-span-2">
            <Label htmlFor="contactInfo">Contact info</Label>
            <Input id="contactInfo" name="contactInfo" placeholder="email or phone" />
          </div>
        </div>

        <div className="flex items-center gap-3 pt-2">
          <Button type="submit" disabled={pending}>
            {pending ? "Analyzing…" : "Upload & analyze"}
          </Button>
          <p className="text-xs text-muted-foreground">
            The audio is forwarded to the voice-app pipeline (transcribe → AI form fill → email).
          </p>
        </div>
      </form>

      {result ? <ResultCard result={result} /> : null}
    </div>
  );
}

function ResultCard({ result }: { result: UploadResult }) {
  if (!result.ok) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Failed</CardTitle>
        </CardHeader>
        <CardContent className="text-sm">
          <p className="text-destructive-foreground bg-destructive rounded-md px-3 py-2">
            {result.error}
          </p>
        </CardContent>
      </Card>
    );
  }

  const r = result.result;
  const transcription = r.pipeline.transcription;
  const form = r.pipeline.incident_form;
  const email = r.pipeline.email;
  const db = r.pipeline.database;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Pipeline result</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        <Row label="File">{r.filename} ({r.file_size_mb ?? "?"} MB)</Row>
        <Row label="Transcription">
          <span className="font-mono text-xs uppercase">{transcription?.status ?? "—"}</span>
          {transcription?.word_count ? <span className="ml-2 text-muted-foreground">{transcription.word_count} words</span> : null}
        </Row>
        {transcription?.text ? (
          <details className="rounded-md border border-border bg-muted/30 p-3">
            <summary className="cursor-pointer text-xs uppercase tracking-wide text-muted-foreground">Transcript preview</summary>
            <pre className="mt-2 whitespace-pre-wrap font-mono text-xs leading-relaxed">{transcription.text}</pre>
          </details>
        ) : null}
        <Row label="Incident form">
          <span className="font-mono text-xs uppercase">{form?.status ?? "—"}</span>
          {form?.form_id ? <span className="ml-2 font-mono text-xs">{form.form_id}</span> : null}
        </Row>
        <Row label="Email">
          <span className="font-mono text-xs uppercase">{email?.status ?? "—"}</span>
          {email?.sent_to ? <span className="ml-2 text-muted-foreground">→ {email.sent_to}</span> : null}
        </Row>
        <Row label="Database">
          <span className="font-mono text-xs uppercase">{db?.status ?? "—"}</span>
          {db?.note ? <span className="ml-2 text-muted-foreground">{db.note}</span> : null}
        </Row>

        <div className="flex items-center gap-3 pt-2">
          {result.incidentId ? (
            <Button asChild>
              <Link href={`/incidents/${result.incidentId}`}>Open incident</Link>
            </Button>
          ) : (
            <p className="text-xs text-muted-foreground">
              Incident not yet linked — refresh the Incidents page in a moment.
            </p>
          )}
          <Button asChild variant="outline">
            <Link href="/inbox">Check inbox</Link>
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-baseline gap-3">
      <div className="w-32 shrink-0 text-xs uppercase tracking-wide text-muted-foreground">{label}</div>
      <div className="flex-1">{children}</div>
    </div>
  );
}
