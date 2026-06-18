"use client";

import { useCallback, useRef, useState, useTransition } from "react";
import Link from "next/link";
import {
  Upload,
  FileAudio,
  X,
  Loader2,
  CheckCircle2,
  XCircle,
  ArrowRight,
  Mic,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import {
  uploadAndAnalyzeAudio,
  type UploadResult,
} from "@/app/upload/actions";

const ACCEPT =
  "audio/*,.wav,.mp3,.ogg,.flac,.m4a,.webm";
const MAX_MB = 50;

export function UploadForm() {
  const [pending, startTransition] = useTransition();
  const [result, setResult] = useState<UploadResult | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [showOptional, setShowOptional] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const pickFile = useCallback((f: File | null) => {
    if (!f) return;
    setFile(f);
    setResult(null);
  }, []);

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragOver(false);
    const f = e.dataTransfer.files[0];
    if (f) pickFile(f);
  }

  function handleSubmit(formData: FormData) {
    if (!file) return;
    formData.set("audio", file);
    setResult(null);
    startTransition(async () => {
      const next = await uploadAndAnalyzeAudio(formData);
      setResult(next);
    });
  }

  const fileSizeMb = file ? (file.size / 1024 / 1024).toFixed(1) : null;

  return (
    <div className="space-y-5">
      <form action={handleSubmit} className="space-y-5">
        {/* Drop zone */}
        <div
          role="button"
          tabIndex={0}
          onClick={() => inputRef.current?.click()}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") inputRef.current?.click();
          }}
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
          className={`
            group relative flex cursor-pointer flex-col items-center justify-center
            rounded-lg border-2 border-dashed p-8 transition-colors
            ${
              dragOver
                ? "border-foreground bg-muted/60"
                : file
                  ? "border-foreground/30 bg-muted/30"
                  : "border-border hover:border-foreground/40 hover:bg-muted/30"
            }
          `}
        >
          <input
            ref={inputRef}
            type="file"
            accept={ACCEPT}
            className="hidden"
            onChange={(e) => pickFile(e.target.files?.[0] ?? null)}
          />

          {file ? (
            <div className="flex items-center gap-3">
              <FileAudio className="h-8 w-8 text-foreground/70" />
              <div className="text-left">
                <p className="text-sm font-medium">{file.name}</p>
                <p className="text-xs text-muted-foreground">
                  {fileSizeMb} MB — click or drop to replace
                </p>
              </div>
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  setFile(null);
                  setResult(null);
                  if (inputRef.current) inputRef.current.value = "";
                }}
                className="ml-2 rounded-md p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          ) : (
            <>
              <div className="mb-3 rounded-full bg-muted p-3">
                <Upload className="h-6 w-6 text-muted-foreground" />
              </div>
              <p className="text-sm font-medium">
                Drop an audio file here, or click to browse
              </p>
              <p className="mt-1 text-xs text-muted-foreground">
                WAV, MP3, OGG, FLAC, M4A, WebM — up to {MAX_MB} MB
              </p>
            </>
          )}
        </div>

        {/* Optional fields toggle */}
        <button
          type="button"
          onClick={() => setShowOptional((v) => !v)}
          className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
        >
          <ArrowRight
            className={`h-3 w-3 transition-transform ${showOptional ? "rotate-90" : ""}`}
          />
          Optional: caller details
        </button>

        {showOptional && (
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2 animate-in fade-in-0 slide-in-from-top-1 duration-200">
            <div className="space-y-1.5">
              <Label htmlFor="callerName" className="text-xs">
                Caller name
              </Label>
              <Input
                id="callerName"
                name="callerName"
                placeholder="Overrides AI guess"
                className="h-9"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="accountOrReference" className="text-xs">
                Account / reference
              </Label>
              <Input
                id="accountOrReference"
                name="accountOrReference"
                placeholder="e.g. AC-7781"
                className="h-9"
              />
            </div>
            <div className="space-y-1.5 md:col-span-2">
              <Label htmlFor="contactInfo" className="text-xs">
                Contact info
              </Label>
              <Input
                id="contactInfo"
                name="contactInfo"
                placeholder="Email or phone"
                className="h-9"
              />
            </div>
          </div>
        )}

        {/* Submit */}
        <Button type="submit" disabled={pending || !file} className="w-full">
          {pending ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Analyzing — this takes 30–120s…
            </>
          ) : (
            <>
              <Mic className="mr-2 h-4 w-4" />
              Upload &amp; analyze
            </>
          )}
        </Button>
      </form>

      {/* Pipeline progress (while running) */}
      {pending && !result && <PipelineProgress />}

      {/* Result */}
      {result && <ResultCard result={result} />}
    </div>
  );
}

function PipelineProgress() {
  const steps = [
    "Uploading audio file",
    "Transcribing with Whisper",
    "AI analyzing transcript",
    "Generating incident form",
    "Sending email notification",
    "Saving to database",
  ];

  return (
    <Card>
      <CardContent className="p-5">
        <div className="space-y-3">
          {steps.map((step, i) => (
            <div key={i} className="flex items-center gap-3 text-sm">
              <Loader2 className="h-4 w-4 shrink-0 animate-spin text-muted-foreground" />
              <span className="text-muted-foreground">{step}</span>
            </div>
          ))}
          <p className="pt-1 text-xs text-muted-foreground">
            The pipeline runs server-side. This page will update when complete.
          </p>
        </div>
      </CardContent>
    </Card>
  );
}

function ResultCard({ result }: { result: UploadResult }) {
  if (!result.ok) {
    return (
      <Card className="border-red-200 dark:border-red-900">
        <CardContent className="flex items-start gap-3 p-5">
          <XCircle className="mt-0.5 h-5 w-5 shrink-0 text-red-500" />
          <div>
            <p className="text-sm font-medium">Analysis failed</p>
            <p className="mt-1 text-sm text-muted-foreground">
              {result.error}
            </p>
          </div>
        </CardContent>
      </Card>
    );
  }

  const r = result.result;
  const transcription = r.pipeline.transcription;
  const form = r.pipeline.incident_form;
  const email = r.pipeline.email;
  const db = r.pipeline.database;

  const steps: {
    label: string;
    status: string | undefined;
    detail?: string;
  }[] = [
    {
      label: "Transcription",
      status: transcription?.status,
      detail: transcription?.word_count
        ? `${transcription.word_count} words`
        : undefined,
    },
    {
      label: "Incident form",
      status: form?.status,
      detail: form?.form_id ?? undefined,
    },
    {
      label: "Email",
      status: email?.status,
      detail: email?.sent_to ? `→ ${email.sent_to}` : undefined,
    },
    {
      label: "Database",
      status: db?.status,
      detail: db?.note ?? undefined,
    },
  ];

  return (
    <Card>
      <CardContent className="space-y-4 p-5">
        {/* Success header */}
        <div className="flex items-center gap-2">
          <CheckCircle2 className="h-5 w-5 text-emerald-500" />
          <span className="text-sm font-medium">Analysis complete</span>
          <Badge variant="muted" className="ml-auto">
            {r.filename}
          </Badge>
        </div>

        {/* Pipeline steps */}
        <div className="divide-y divide-border rounded-md border">
          {steps.map((step) => {
            const ok = step.status === "ok" || step.status === "saved";
            return (
              <div
                key={step.label}
                className="flex items-center gap-3 px-3 py-2.5 text-sm"
              >
                {ok ? (
                  <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-500" />
                ) : (
                  <XCircle className="h-4 w-4 shrink-0 text-muted-foreground" />
                )}
                <span className="font-medium">{step.label}</span>
                {step.detail && (
                  <span className="text-muted-foreground">{step.detail}</span>
                )}
                <Badge
                  variant={ok ? "default" : "muted"}
                  className="ml-auto uppercase"
                >
                  {step.status ?? "—"}
                </Badge>
              </div>
            );
          })}
        </div>

        {/* Transcript preview */}
        {transcription?.text && (
          <details className="rounded-md border bg-muted/30 p-3">
            <summary className="cursor-pointer text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Transcript preview
            </summary>
            <pre className="mt-3 max-h-64 overflow-y-auto whitespace-pre-wrap font-mono text-xs leading-relaxed">
              {transcription.text}
            </pre>
          </details>
        )}

        {/* Actions */}
        <div className="flex items-center gap-2 pt-1">
          {result.incidentId ? (
            <Button asChild size="sm">
              <Link href={`/incidents/${result.incidentId}`}>
                View incident
                <ArrowRight className="ml-1.5 h-3.5 w-3.5" />
              </Link>
            </Button>
          ) : (
            <p className="text-xs text-muted-foreground">
              Incident not yet linked — check the incidents page in a moment.
            </p>
          )}
          <Button asChild variant="outline" size="sm">
            <Link href="/inbox">Check inbox</Link>
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
