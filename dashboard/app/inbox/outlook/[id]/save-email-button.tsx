"use client";

import { useTransition, useState } from "react";
import { Check, Download } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { saveEmailToDbAction, type SaveEmailResult } from "../actions";

type Props = {
  messageId: string;
  provider: "microsoft" | "google";
  alreadySaved: boolean;
};

export function SaveEmailButton({ messageId, provider, alreadySaved }: Props) {
  const [isPending, startTransition] = useTransition();
  const [saved, setSaved] = useState(alreadySaved);

  if (saved) {
    return (
      <Button variant="outline" size="sm" disabled>
        <Check className="mr-2 h-3 w-3" />
        Saved to DB
      </Button>
    );
  }

  return (
    <Button
      variant="outline"
      size="sm"
      disabled={isPending}
      onClick={() => {
        startTransition(async () => {
          const result: SaveEmailResult = await saveEmailToDbAction(messageId, provider);
          if ("alreadySaved" in result && result.alreadySaved) {
            setSaved(true);
            toast.info("Email was already saved");
          } else if ("saved" in result && result.saved) {
            setSaved(true);
            toast.success("Email saved to database");
          } else if ("error" in result) {
            toast.error("Failed to save email", { description: result.error });
          }
        });
      }}
    >
      {isPending ? (
        <>
          <span className="mr-2 inline-block h-3 w-3 animate-spin rounded-full border-2 border-current border-t-transparent" />
          Saving…
        </>
      ) : (
        <>
          <Download className="mr-2 h-3 w-3" />
          Save to DB
        </>
      )}
    </Button>
  );
}
