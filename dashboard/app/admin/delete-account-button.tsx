"use client";

import { useTransition } from "react";
import { deleteAccount } from "./actions";
import { Button } from "@/components/ui/button";

export function DeleteAccountButton({ accountId }: { accountId: number }) {
  const [pending, startTransition] = useTransition();

  return (
    <Button
      variant="outline"
      size="sm"
      disabled={pending}
      onClick={() => {
        if (!confirm("Delete this account?")) return;
        startTransition(() => deleteAccount(accountId));
      }}
    >
      {pending ? "Deleting..." : "Delete"}
    </Button>
  );
}
