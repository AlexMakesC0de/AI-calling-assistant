"use client";

import { type ReactNode, useEffect, useMemo, useState, useTransition } from "react";
import Link from "next/link";
import { useRouter, useSearchParams, usePathname } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { formatDateTime } from "@/lib/utils";
import type { MailpitMessageSummary } from "@/lib/mailpit";
import { deleteMessages, markRead, updateTags } from "@/app/inbox/actions";

type Props = {
  initialMessages: MailpitMessageSummary[];
  total: number;
  unread: number;
  query: string;
  knownTags: string[];
  tabs?: ReactNode;
};

const QUALIFIER_HINT = "Try: from:support@example.com  •  subject:incident  •  tag:billing  •  is:unread  •  has:attachment";

export function InboxList({ initialMessages, total, unread, query, knownTags, tabs }: Props) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();
  const [pulseUntil, setPulseUntil] = useState<number>(0);

  // Live updates via SSE: when Mailpit's total/unread changes, refresh the list.
  useEffect(() => {
    const source = new EventSource("/api/inbox/stream");
    let firstTick = true;
    source.addEventListener("tick", () => {
      if (firstTick) {
        firstTick = false;
        return;
      }
      setPulseUntil(Date.now() + 1500);
      router.refresh();
    });
    source.addEventListener("error", () => {
      // Browser will reconnect automatically; surface only if it stays closed.
    });
    return () => source.close();
  }, [router]);

  const inputDefault = query;
  const allIds = useMemo(() => initialMessages.map((m) => m.ID), [initialMessages]);
  const allSelected = selected.size > 0 && selected.size === allIds.length;
  const someSelected = selected.size > 0;

  function toggle(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleAll() {
    setSelected(allSelected ? new Set() : new Set(allIds));
  }

  function submitSearch(formData: FormData) {
    const q = String(formData.get("q") ?? "").trim();
    const params = new URLSearchParams(searchParams.toString());
    if (q) params.set("q", q);
    else params.delete("q");
    router.push(`${pathname}?${params.toString()}`);
  }

  function applyChip(qualifier: string) {
    const params = new URLSearchParams(searchParams.toString());
    params.set("q", qualifier);
    router.push(`${pathname}?${params.toString()}`);
  }

  function run(action: () => Promise<{ ok: boolean; error?: string }>) {
    setError(null);
    startTransition(async () => {
      const res = await action();
      if (!res.ok) setError(res.error ?? "Failed");
      else setSelected(new Set());
    });
  }

  return (
    <div className="space-y-4">
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-medium tracking-tight">Inbox</h1>
          <p className="text-sm text-muted-foreground">
            Mailpit · {total} total · {unread} unread
            <span
              className={cn(
                "ml-2 inline-block h-1.5 w-1.5 rounded-full bg-foreground transition-opacity",
                Date.now() < pulseUntil ? "opacity-100" : "opacity-0"
              )}
              aria-hidden
            />
          </p>
        </div>
      </div>

      {tabs}

      <form action={submitSearch} className="space-y-2">
        <div className="flex gap-2">
          <Input
            name="q"
            defaultValue={inputDefault}
            placeholder="Search messages…"
            aria-label="Search inbox"
            className="font-mono text-sm"
          />
          <Button type="submit" variant="outline">
            Search
          </Button>
          {query ? (
            <Button
              type="button"
              variant="ghost"
              onClick={() => router.push(pathname)}
            >
              Clear
            </Button>
          ) : null}
        </div>
        <p className="text-xs text-muted-foreground">{QUALIFIER_HINT}</p>
      </form>

      {knownTags.length > 0 ? (
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="text-xs uppercase tracking-wide text-muted-foreground">Tags:</span>
          {knownTags.slice(0, 12).map((tag) => (
            <button
              key={tag}
              type="button"
              onClick={() => applyChip(`tag:"${tag}"`)}
              className="rounded-md border border-border px-2 py-0.5 text-xs hover:bg-muted"
            >
              {tag}
            </button>
          ))}
        </div>
      ) : null}

      <div className="flex items-center gap-2 border-y border-border py-2">
        <input
          type="checkbox"
          aria-label="Select all"
          checked={allSelected}
          ref={(el) => {
            if (el) el.indeterminate = someSelected && !allSelected;
          }}
          onChange={toggleAll}
          className="h-4 w-4 cursor-pointer"
        />
        <span className="text-xs text-muted-foreground">
          {selected.size > 0 ? `${selected.size} selected` : "Select"}
        </span>
        <div className="ml-auto flex items-center gap-2">
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={!someSelected || pending}
            onClick={() => run(() => markRead([...selected], true))}
          >
            Mark read
          </Button>
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={!someSelected || pending}
            onClick={() => run(() => markRead([...selected], false))}
          >
            Mark unread
          </Button>
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={!someSelected || pending}
            onClick={() => {
              const input = window.prompt("Tags (comma-separated). Empty clears tags.");
              if (input === null) return;
              const tags = input.split(",").map((s) => s.trim()).filter(Boolean);
              run(() => updateTags([...selected], tags));
            }}
          >
            Tag…
          </Button>
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={!someSelected || pending}
            onClick={() => {
              if (!confirm(`Delete ${selected.size} message(s)?`)) return;
              run(() => deleteMessages([...selected]));
            }}
          >
            Delete
          </Button>
        </div>
      </div>

      {error ? (
        <div className="rounded-md bg-destructive px-3 py-2 text-xs text-destructive-foreground">{error}</div>
      ) : null}

      {initialMessages.length === 0 ? (
        <div className="rounded-md border border-border p-12 text-center text-sm text-muted-foreground">
          {query ? "No messages match this search." : (
            <>No emails yet. Run an analysis from <Link className="underline underline-offset-4" href="/upload">Upload</Link>.</>
          )}
        </div>
      ) : (
        <div className="divide-y divide-border rounded-md border border-border">
          {initialMessages.map((msg) => {
            const isSelected = selected.has(msg.ID);
            return (
              <div
                key={msg.ID}
                className={cn(
                  "flex items-start gap-3 px-3 py-3",
                  isSelected && "bg-muted/40",
                  !msg.Read && !isSelected && "bg-muted/20"
                )}
              >
                <input
                  type="checkbox"
                  aria-label={`Select ${msg.Subject || msg.ID}`}
                  checked={isSelected}
                  onChange={() => toggle(msg.ID)}
                  className="mt-1 h-4 w-4 cursor-pointer"
                />
                <Link
                  href={`/inbox/${encodeURIComponent(msg.ID)}`}
                  className="flex min-w-0 flex-1 items-start gap-3"
                >
                  <div className="hidden w-40 shrink-0 text-xs text-muted-foreground md:block">
                    {formatDateTime(msg.Created)}
                  </div>
                  <div className="hidden w-48 shrink-0 truncate font-mono text-xs text-muted-foreground sm:block">
                    {msg.From.Address}
                  </div>
                  <div className="min-w-0 flex-1 space-y-1">
                    <div className="flex flex-wrap items-center gap-2">
                      {!msg.Read ? (
                        <span className="h-1.5 w-1.5 rounded-full bg-foreground" aria-label="unread" />
                      ) : null}
                      <span className={cn("truncate text-sm", !msg.Read && "font-medium")}>
                        {msg.Subject || "(no subject)"}
                      </span>
                      {msg.Tags?.map((tag) => (
                        <Badge key={tag} variant="muted" className="text-[10px]">
                          {tag}
                        </Badge>
                      ))}
                    </div>
                    {msg.Snippet ? (
                      <p className="line-clamp-1 text-xs text-muted-foreground">{msg.Snippet}</p>
                    ) : null}
                  </div>
                  <div className="ml-auto flex shrink-0 items-center gap-3 text-xs text-muted-foreground">
                    {msg.Attachments > 0 ? <span>{msg.Attachments} att.</span> : null}
                    <span className="tabular-nums">{Math.round(msg.Size / 1024)}KB</span>
                  </div>
                </Link>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
