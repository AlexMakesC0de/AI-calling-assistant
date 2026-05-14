import { SystemHealth } from "@/components/system-health";
import { runHealthChecks } from "@/lib/health";

export const dynamic = "force-dynamic";
export const metadata = { title: "System" };

export default async function SystemPage() {
  const checks = await runHealthChecks();
  const generatedAt = new Date().toISOString();
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-medium tracking-tight">System</h1>
        <p className="text-sm text-muted-foreground">
          Live health of every service the dashboard depends on. The bars animate the first time you load
          this page each day; after that, status is rendered instantly.
        </p>
      </div>
      <SystemHealth checks={checks} generatedAt={generatedAt} />
    </div>
  );
}
