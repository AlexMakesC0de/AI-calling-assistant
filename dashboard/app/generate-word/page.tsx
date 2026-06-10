import { GenerateWordClient } from "@/components/generate-word-client";

export const metadata = { title: "Generate Word" };

export default function GenerateWordPage() {
  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <h1 className="text-2xl font-medium tracking-tight">
          Generate incident report
        </h1>
        <p className="text-sm text-muted-foreground">
          Paste a call transcript to extract form fields using the AI formatter,
          review and edit the results, then download a filled Word document.
        </p>
      </div>

      <GenerateWordClient />
    </div>
  );
}