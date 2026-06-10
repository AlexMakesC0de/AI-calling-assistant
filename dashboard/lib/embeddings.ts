import { env } from "./env";

// Ollama's /api/embeddings endpoint:
//   POST { model, prompt }  →  { embedding: number[] }
// We use it both for backfilling existing transcript chunks and for embedding
// search queries before pgvector ANN.
const EMBED_TIMEOUT_MS = 30_000;

export async function embedText(text: string): Promise<number[]> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), EMBED_TIMEOUT_MS);
  try {
    const response = await fetch(`${env.ollamaBaseUrl}/api/embeddings`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model: env.ollamaEmbedModel, prompt: text }),
      cache: "no-store",
      signal: controller.signal,
    });
    if (!response.ok) {
      throw new Error(`Ollama embeddings ${response.status}: ${await response.text().catch(() => "")}`);
    }
    const json = (await response.json()) as { embedding?: number[] };
    if (!Array.isArray(json.embedding) || json.embedding.length === 0) {
      throw new Error("Ollama returned empty embedding");
    }
    return json.embedding;
  } finally {
    clearTimeout(timer);
  }
}

// pgvector accepts an embedding as either a typed cast (`'[1.0,2.0,...]'::vector`)
// or a string literal — we use the string form so the value can flow through
// Prisma's parameterized $queryRaw without shape problems.
export function vectorLiteral(values: number[]): string {
  return `[${values.join(",")}]`;
}
