import { loadSelectableItems } from "./actions";
import { HistoryBuilder } from "./history-builder";

export const dynamic = "force-dynamic";
export const metadata = { title: "Generate Word" };

export default async function GenerateWordPage() {
  const data = await loadSelectableItems();

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-medium tracking-tight">
          Issue history report
        </h1>
        <p className="text-sm text-muted-foreground">
          Select incidents, WhatsApp conversations, and emails to compile into a
          Word document.
        </p>
      </div>

      <HistoryBuilder data={data} />
    </div>
  );
}
