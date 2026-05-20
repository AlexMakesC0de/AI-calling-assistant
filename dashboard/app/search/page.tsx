import { SearchClient } from "@/components/search-client";

export const dynamic = "force-dynamic";
export const metadata = { title: "Search" };

export default function SearchPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-medium tracking-tight">Semantic search</h1>
        <p className="text-sm text-muted-foreground">
          Find call transcripts by meaning, not just keywords. Queries are embedded by Ollama
          (<code className="font-mono text-[11px]">nomic-embed-text</code>) and matched against pgvector.
        </p>
      </div>
      <SearchClient />
    </div>
  );
}
