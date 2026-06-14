"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import {
  Phone,
  MessageCircle,
  Mail,
  Download,
  CheckSquare,
  Square,
  X,
} from "lucide-react";
import type { IncidentItem, WhatsAppItem, EmailItem } from "./actions";

type Tab = "incidents" | "whatsapp" | "email";

type Props = {
  data: {
    incidents: IncidentItem[];
    whatsapp: WhatsAppItem[];
    email: EmailItem[];
  };
};

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString("en-IE", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function HistoryBuilder({ data }: Props) {
  const [tab, setTab] = useState<Tab>("incidents");
  const [selectedIncidents, setSelectedIncidents] = useState<Set<number>>(new Set());
  const [selectedWhatsapp, setSelectedWhatsapp] = useState<Set<number>>(new Set());
  const [selectedEmail, setSelectedEmail] = useState<Set<number>>(new Set());
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState("");

  const totalSelected = selectedIncidents.size + selectedWhatsapp.size + selectedEmail.size;

  function toggle(set: Set<number>, setFn: (s: Set<number>) => void, id: number) {
    const next = new Set(set);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setFn(next);
  }

  function clearAll() {
    setSelectedIncidents(new Set());
    setSelectedWhatsapp(new Set());
    setSelectedEmail(new Set());
  }

  async function handleDownload() {
    setDownloading(true);
    setError("");
    try {
      const res = await fetch("/api/generate-word/history", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          incidentIds: Array.from(selectedIncidents),
          whatsappIds: Array.from(selectedWhatsapp),
          emailIds: Array.from(selectedEmail),
        }),
      });
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        throw new Error(d.error ?? `Server error ${res.status}`);
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      const disposition = res.headers.get("Content-Disposition") ?? "";
      const match = disposition.match(/filename="(.+?)"/);
      a.download = match?.[1] ?? "issue-history.docx";
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setDownloading(false);
    }
  }

  const tabs: { key: Tab; label: string; icon: typeof Phone; count: number }[] = [
    { key: "incidents", label: "Calls", icon: Phone, count: data.incidents.length },
    { key: "whatsapp", label: "WhatsApp", icon: MessageCircle, count: data.whatsapp.length },
    { key: "email", label: "Email", icon: Mail, count: data.email.length },
  ];

  return (
    <div className="space-y-4">
      {/* Selection summary bar */}
      <div className="flex items-center justify-between rounded-md border border-border bg-muted/30 px-4 py-3">
        <div className="flex items-center gap-4 text-sm">
          <span className="font-medium">
            {totalSelected} item{totalSelected !== 1 ? "s" : ""} selected
          </span>
          {selectedIncidents.size > 0 && (
            <span className="flex items-center gap-1 text-muted-foreground">
              <Phone className="h-3.5 w-3.5" /> {selectedIncidents.size}
            </span>
          )}
          {selectedWhatsapp.size > 0 && (
            <span className="flex items-center gap-1 text-muted-foreground">
              <MessageCircle className="h-3.5 w-3.5" /> {selectedWhatsapp.size}
            </span>
          )}
          {selectedEmail.size > 0 && (
            <span className="flex items-center gap-1 text-muted-foreground">
              <Mail className="h-3.5 w-3.5" /> {selectedEmail.size}
            </span>
          )}
          {totalSelected > 0 && (
            <button onClick={clearAll} className="text-xs text-muted-foreground hover:text-foreground">
              Clear all
            </button>
          )}
        </div>
        <Button onClick={handleDownload} disabled={totalSelected === 0 || downloading} size="sm">
          <Download className="mr-1.5 h-4 w-4" />
          {downloading ? "Generating..." : "Download .docx"}
        </Button>
      </div>

      {error && (
        <div className="rounded-md border border-destructive/20 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 rounded-md border border-border p-1">
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={cn(
              "flex items-center gap-2 rounded px-3 py-1.5 text-sm transition-colors",
              tab === t.key
                ? "bg-foreground text-background"
                : "text-muted-foreground hover:text-foreground"
            )}
          >
            <t.icon className="h-4 w-4" />
            {t.label}
            <span className="tabular-nums text-xs opacity-60">{t.count}</span>
          </button>
        ))}
      </div>

      {/* Content */}
      {tab === "incidents" && (
        <div className="space-y-2">
          {data.incidents.length === 0 ? (
            <Empty>No incidents found.</Empty>
          ) : (
            data.incidents.map((inc) => (
              <SelectableRow
                key={inc.id}
                selected={selectedIncidents.has(inc.id)}
                onToggle={() => toggle(selectedIncidents, setSelectedIncidents, inc.id)}
              >
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium">
                      {inc.callerName || `Incident #${inc.id}`}
                    </span>
                    {inc.category && (
                      <Badge variant="muted">{inc.category}</Badge>
                    )}
                    {inc.priority && (
                      <Badge variant={/high|urgent/i.test(inc.priority) ? "solid" : "default"}>
                        {inc.priority}
                      </Badge>
                    )}
                  </div>
                  <p className="line-clamp-1 text-xs text-muted-foreground">
                    {inc.summary || "No summary"}
                  </p>
                </div>
                <span className="shrink-0 text-xs text-muted-foreground">
                  {formatDate(inc.completedAt)}
                </span>
              </SelectableRow>
            ))
          )}
        </div>
      )}

      {tab === "whatsapp" && (
        <div className="space-y-2">
          {data.whatsapp.length === 0 ? (
            <Empty>No WhatsApp conversations found.</Empty>
          ) : (
            data.whatsapp.map((conv) => (
              <SelectableRow
                key={conv.id}
                selected={selectedWhatsapp.has(conv.id)}
                onToggle={() => toggle(selectedWhatsapp, setSelectedWhatsapp, conv.id)}
              >
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium">
                      {conv.contactName || conv.contactPhone}
                    </span>
                    <span className="text-xs text-muted-foreground">
                      {conv.messageCount} msg{conv.messageCount !== 1 ? "s" : ""}
                    </span>
                  </div>
                  <p className="line-clamp-1 text-xs text-muted-foreground">
                    {conv.lastMessage || "[Media]"}
                  </p>
                </div>
                <span className="shrink-0 text-xs text-muted-foreground">
                  {formatDate(conv.lastMessageAt)}
                </span>
              </SelectableRow>
            ))
          )}
        </div>
      )}

      {tab === "email" && (
        <div className="space-y-2">
          {data.email.length === 0 ? (
            <Empty>No email conversations found.</Empty>
          ) : (
            data.email.map((conv) => (
              <SelectableRow
                key={conv.id}
                selected={selectedEmail.has(conv.id)}
                onToggle={() => toggle(selectedEmail, setSelectedEmail, conv.id)}
              >
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium">
                      {conv.senderName || conv.senderEmail}
                    </span>
                    <span className="text-xs text-muted-foreground">
                      {conv.messageCount} msg{conv.messageCount !== 1 ? "s" : ""}
                    </span>
                  </div>
                  <p className="line-clamp-1 text-xs text-muted-foreground">
                    {conv.lastSubject || "No subject"}
                  </p>
                </div>
                <span className="shrink-0 text-xs text-muted-foreground">
                  {formatDate(conv.lastMessageAt)}
                </span>
              </SelectableRow>
            ))
          )}
        </div>
      )}

      {/* Selected items preview */}
      {totalSelected > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Selected items</CardTitle>
          </CardHeader>
          <CardContent className="space-y-1.5">
            {Array.from(selectedIncidents).map((id) => {
              const inc = data.incidents.find((i) => i.id === id);
              if (!inc) return null;
              return (
                <SelectedChip
                  key={`inc-${id}`}
                  icon={Phone}
                  label={inc.callerName || `Incident #${inc.id}`}
                  sub={inc.category}
                  onRemove={() => toggle(selectedIncidents, setSelectedIncidents, id)}
                />
              );
            })}
            {Array.from(selectedWhatsapp).map((id) => {
              const conv = data.whatsapp.find((c) => c.id === id);
              if (!conv) return null;
              return (
                <SelectedChip
                  key={`wa-${id}`}
                  icon={MessageCircle}
                  label={conv.contactName || conv.contactPhone}
                  sub={`${conv.messageCount} messages`}
                  onRemove={() => toggle(selectedWhatsapp, setSelectedWhatsapp, id)}
                />
              );
            })}
            {Array.from(selectedEmail).map((id) => {
              const conv = data.email.find((c) => c.id === id);
              if (!conv) return null;
              return (
                <SelectedChip
                  key={`em-${id}`}
                  icon={Mail}
                  label={conv.senderName || conv.senderEmail}
                  sub={conv.lastSubject}
                  onRemove={() => toggle(selectedEmail, setSelectedEmail, id)}
                />
              );
            })}
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function SelectableRow({
  selected,
  onToggle,
  children,
}: {
  selected: boolean;
  onToggle: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onToggle}
      className={cn(
        "flex w-full items-center gap-3 rounded-md border px-4 py-3 text-left transition-colors",
        selected
          ? "border-primary/30 bg-primary/5"
          : "border-border hover:bg-muted/40"
      )}
    >
      {selected ? (
        <CheckSquare className="h-4 w-4 shrink-0 text-primary" />
      ) : (
        <Square className="h-4 w-4 shrink-0 text-muted-foreground" />
      )}
      {children}
    </button>
  );
}

function SelectedChip({
  icon: Icon,
  label,
  sub,
  onRemove,
}: {
  icon: typeof Phone;
  label: string;
  sub: string | null;
  onRemove: () => void;
}) {
  return (
    <div className="flex items-center gap-2 rounded-md border border-border px-3 py-2 text-sm">
      <Icon className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
      <span className="font-medium">{label}</span>
      {sub && <span className="text-xs text-muted-foreground">{sub}</span>}
      <button
        onClick={onRemove}
        className="ml-auto text-muted-foreground hover:text-foreground"
      >
        <X className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}

function Empty({ children }: { children: React.ReactNode }) {
  return (
    <div className="rounded-md border border-border p-12 text-center text-sm text-muted-foreground">
      {children}
    </div>
  );
}
