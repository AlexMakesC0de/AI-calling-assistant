"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";

export function DisconnectButton({ provider }: { provider: "microsoft" | "google" }) {
  const [pending, setPending] = useState(false);
  const router = useRouter();

  const label = provider === "microsoft" ? "Microsoft" : "Gmail";
  const endpoint = provider === "microsoft" ? "/api/outlook/disconnect" : "/api/gmail/disconnect";

  async function handleDisconnect() {
    if (!confirm(`Disconnect your ${label} account? You can reconnect at any time.`)) return;
    setPending(true);
    try {
      await fetch(endpoint, { method: "POST" });
      router.refresh();
    } finally {
      setPending(false);
    }
  }

  return (
    <Button variant="ghost" size="sm" onClick={handleDisconnect} disabled={pending}>
      {pending ? "Disconnecting..." : "Disconnect"}
    </Button>
  );
}

// Keep backward-compatible export
export { DisconnectButton as OutlookDisconnectButton };
