"use client";

import { useState, useTransition } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { searchSemantic, backfillEmbeddings, type SearchResult, type BackfillResult } from "@/app/search/actions";

export function SearchClient() {
  const [query, setQuery] = useState("");
  const [result, setResult] = useState<SearchResult | null>(null);
  const [backfill, setBackfill] = useState<BackfillResult | null>(null);
  const [pending, startTransition] = useTransition();
  const [backfilling, startBackfill] = useTransition();

  function run(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!query.trim()) return;
    startTransition(async () => {
      const next = await searchSemantic(query);
      setResult(next);
    });
  }

  function runBackfill() {
    startBackfill(async () => {
      const next = await backfillEmbeddings();
      setBackfill(next);
      // Refresh the count in the result panel if we have one already.
      if (result?.ok && next.ok) {
        setResult({
          ...result,
          totalChunks: result.totalChunks,
          embeddedChunks: result.embeddedChunks + next.embedded,
        });
      }
    });
  }

  return (
    <div className="space-y-6">
      <form onSubmit={run} className="flex gap-2">
        <Input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="e.g. caller's internet stopped working after a billing change"
          className="text-sm"
        />
        <Button type="submit" disabled={pending || query.trim().length === 0}>
          {pending ? "Searching…" : "Search"}
        </Button>
      </form>

      {result?.ok ? (
        <p className="text-xs text-muted-foreground">
          {result.embeddedChunks} of {result.totalChunks} chunks indexed
          {result.embeddedChunks < result.totalChunks ? (
            <>
              {" — "}
              <button
                type="button"
                onClick={runBackfill}
                disabled={backfilling}
                className="underline underline-offset-4 disabled:opacity-50"
              >
                {backfilling ? "Embedding…" : "Backfill the rest"}
              </button>
            </>
          ) : null}
        </p>
      ) : null}

      {result && !result.ok ? (
        <Card>
          <CardHeader>
            <CardTitle>Search failed</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="rounded-md bg-destructive px-3 py-2 text-xs text-destructive-foreground">
              {result.error}
            </p>
            <p className="text-xs text-muted-foreground">
              Common fixes: pull the embed model with{" "}
              <code className="font-mono">ollama pull nomic-embed-text</code>, ensure Ollama is reachable,
              or run the backfill to populate embeddings on existing chunks.
            </p>
            <Button type="button" variant="outline" onClick={runBackfill} disabled={backfilling}>
              {backfilling ? "Embedding chunks…" : "Backfill embeddings"}
            </Button>
          </CardContent>
        </Card>
      ) : null}

      {backfill ? (
        <div className="rounded-md border border-border bg-muted/30 px-3 py-2 text-xs">
          {backfill.ok ? (
            <>
              Embedded <span className="tabular-nums">{backfill.embedded}</span> chunks
              {backfill.skipped > 0 ? `, skipped ${backfill.skipped} empty` : null}.
              {backfill.remaining > 0 ? (
                <>
                  {" "}
                  {backfill.remaining} remaining —{" "}
                  <button type="button" onClick={runBackfill} className="underline underline-offset-4">
                    continue
                  </button>
                </>
              ) : (
                " All chunks indexed."
              )}
            </>
          ) : (
            <span className="text-destructive">{backfill.error}</span>
          )}
        </div>
      ) : null}

      {result?.ok ? (
        result.hits.length === 0 ? (
          <div className="rounded-md border border-border p-12 text-center text-sm text-muted-foreground">
            {result.embeddedChunks === 0
              ? "No chunks have embeddings yet. Run the backfill to index existing transcripts."
              : "No matches. Try a different phrasing."}
          </div>
        ) : (
          <div className="space-y-3">
            {result.hits.map((hit) => (
              <Card key={hit.chunkId}>
                <CardContent className="space-y-2 py-3">
                  <div className="flex items-start justify-between gap-3">
                    <div className="text-sm">{hit.content}</div>
                    <div className="shrink-0 text-right text-xs text-muted-foreground tabular-nums">
                      {(1 - hit.distance).toFixed(3)}
                    </div>
                  </div>
                  <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
                    {hit.incidentId ? (
                      <Link href={`/incidents/${hit.incidentId}`} className="underline underline-offset-4">
                        Incident #{hit.incidentId}
                      </Link>
                    ) : (
                      <span>Unlinked transcript chunk</span>
                    )}
                    {hit.incidentCategory ? <span>{hit.incidentCategory}</span> : null}
                    {hit.callerName ? <span>{hit.callerName}</span> : null}
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )
      ) : null}
    </div>
  );
}
