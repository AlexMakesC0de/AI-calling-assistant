"use client";

import { useState } from "react";
import { Copy, Check } from "lucide-react";
import { toast } from "sonner";

export function CopyButton({ value, className }: { value: string; className?: string }) {
  const [copied, setCopied] = useState(false);

  return (
    <button
      type="button"
      className={`inline-flex items-center justify-center text-muted-foreground hover:text-foreground transition-colors ${className ?? ""}`}
      onClick={async (e) => {
        e.preventDefault();
        e.stopPropagation();
        await navigator.clipboard.writeText(value);
        setCopied(true);
        toast.success("Copied to clipboard");
        setTimeout(() => setCopied(false), 2000);
      }}
      title={`Copy "${value}"`}
    >
      {copied ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
    </button>
  );
}
