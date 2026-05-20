"use server";

import { Prisma } from "@prisma/client";
import { prisma } from "@/lib/prisma";
import { embedText, vectorLiteral } from "@/lib/embeddings";

export type SearchHit = {
  chunkId: number;
  fileId: number;
  chunkIndex: number;
  content: string;
  distance: number;
  incidentId: number | null;
  incidentCategory: string | null;
  callerName: string | null;
  completedAt: Date | null;
};

export type SearchResult =
  | { ok: true; hits: SearchHit[]; query: string; embedded: boolean; totalChunks: number; embeddedChunks: number }
  | { ok: false; error: string };

const MAX_HITS = 20;

// Hits are joined with their parent incident (via file_id → incident_form.file_id)
// so the UI can deep-link to /incidents/{id}.
export async function searchSemantic(query: string): Promise<SearchResult> {
  const trimmed = query.trim();
  if (!trimmed) return { ok: false, error: "Empty query" };

  let embedding: number[];
  try {
    embedding = await embedText(trimmed);
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : String(err) };
  }
  const literal = vectorLiteral(embedding);

  try {
    const rows = await prisma.$queryRaw<Array<{
      chunk_id: number;
      file_id: number;
      chunk_index: number;
      content: string;
      distance: number;
      incident_id: number | null;
      incident_category: string | null;
      caller_name: string | null;
      completed_at: Date | null;
    }>>(Prisma.sql`
      SELECT
        tc.id                       AS chunk_id,
        tc.file_id                  AS file_id,
        tc.chunk_index              AS chunk_index,
        tc.content                  AS content,
        (tc.embedding <=> ${literal}::vector) AS distance,
        f.id                        AS incident_id,
        f.category                  AS incident_category,
        gi.caller_name              AS caller_name,
        f.completed_at              AS completed_at
      FROM transcriptchunk tc
      LEFT JOIN incident_form f ON f.file_id = tc.file_id
      LEFT JOIN incident_general_information gi ON gi.incident_form_id = f.id
      WHERE tc.embedding IS NOT NULL
      ORDER BY tc.embedding <=> ${literal}::vector
      LIMIT ${MAX_HITS}
    `);

    const counts = await prisma.$queryRaw<Array<{ total: bigint; embedded: bigint }>>(Prisma.sql`
      SELECT
        COUNT(*)::bigint AS total,
        COUNT(*) FILTER (WHERE embedding IS NOT NULL)::bigint AS embedded
      FROM transcriptchunk
    `);
    const totalChunks = Number(counts[0]?.total ?? 0n);
    const embeddedChunks = Number(counts[0]?.embedded ?? 0n);

    return {
      ok: true,
      query: trimmed,
      embedded: true,
      totalChunks,
      embeddedChunks,
      hits: rows.map((r) => ({
        chunkId: r.chunk_id,
        fileId: r.file_id,
        chunkIndex: r.chunk_index,
        content: r.content,
        distance: Number(r.distance),
        incidentId: r.incident_id,
        incidentCategory: r.incident_category,
        callerName: r.caller_name,
        completedAt: r.completed_at,
      })),
    };
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : String(err) };
  }
}

export type BackfillResult =
  | { ok: true; embedded: number; skipped: number; remaining: number }
  | { ok: false; error: string; embedded: number };

// Embeds every chunk with NULL embedding. Returns counts so the UI can show
// progress; the user can click again to continue if there are still rows left.
const BACKFILL_BATCH_SIZE = 50;

export async function backfillEmbeddings(): Promise<BackfillResult> {
  let embeddedCount = 0;
  try {
    // The embedding column isn't modeled in Prisma (Unsupported type), so we
    // pull the pending batch via raw SQL.
    const pending = await prisma.$queryRaw<Array<{ id: number; content: string | null }>>(Prisma.sql`
      SELECT id, content FROM transcriptchunk
      WHERE embedding IS NULL
      ORDER BY id ASC
      LIMIT ${BACKFILL_BATCH_SIZE}
    `);
    if (pending.length === 0) {
      return { ok: true, embedded: 0, skipped: 0, remaining: 0 };
    }

    let skipped = 0;
    for (const chunk of pending) {
      const text = chunk.content?.trim();
      if (!text) {
        skipped++;
        continue;
      }
      try {
        const embedding = await embedText(text);
        const literal = vectorLiteral(embedding);
        await prisma.$executeRaw(Prisma.sql`
          UPDATE transcriptchunk
          SET embedding = ${literal}::vector
          WHERE id = ${chunk.id}
        `);
        embeddedCount++;
      } catch (err) {
        return {
          ok: false,
          error: `Embedding failed at chunk ${chunk.id}: ${err instanceof Error ? err.message : String(err)}`,
          embedded: embeddedCount,
        };
      }
    }

    const remainingRow = await prisma.$queryRaw<Array<{ count: bigint }>>(
      Prisma.sql`SELECT COUNT(*)::bigint AS count FROM transcriptchunk WHERE embedding IS NULL`
    );
    const remaining = Number(remainingRow[0]?.count ?? 0n);
    return { ok: true, embedded: embeddedCount, skipped, remaining };
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : String(err), embedded: embeddedCount };
  }
}
