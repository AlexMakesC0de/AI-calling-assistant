"use client";

import { useState, type ReactNode } from "react";
import { cn } from "@/lib/utils";

type Json = string | number | boolean | null | Json[] | { [key: string]: Json };

type Props = {
  value: unknown;
  rootName?: string;
  defaultOpenDepth?: number;
};

// Collapsible JSON tree. Keys and primitive values are styled distinctly so
// the structure is scannable; arrays show their length, objects show their key
// count. Primitive long strings are clipped with a hover-to-expand title.
export function JsonTree({ value, rootName, defaultOpenDepth = 2 }: Props) {
  return (
    <div className="font-mono text-xs leading-relaxed">
      <Node value={value as Json} name={rootName} depth={0} openDepth={defaultOpenDepth} />
    </div>
  );
}

function Node({
  value,
  name,
  depth,
  openDepth,
}: {
  value: Json;
  name?: string | number;
  depth: number;
  openDepth: number;
}) {
  if (value === null) return <Leaf name={name} valueText="null" tone="muted" />;
  if (typeof value === "string") return <Leaf name={name} valueText={JSON.stringify(value)} tone="string" />;
  if (typeof value === "number") return <Leaf name={name} valueText={String(value)} tone="number" />;
  if (typeof value === "boolean") return <Leaf name={name} valueText={String(value)} tone="bool" />;
  if (Array.isArray(value)) {
    return <Branch name={name} depth={depth} openDepth={openDepth} kind="array" items={value.map((v, i) => ({ key: i, value: v }))} />;
  }
  const entries = Object.entries(value);
  return <Branch name={name} depth={depth} openDepth={openDepth} kind="object" items={entries.map(([k, v]) => ({ key: k, value: v }))} />;
}

function Leaf({
  name,
  valueText,
  tone,
}: {
  name?: string | number;
  valueText: string;
  tone: "string" | "number" | "bool" | "muted";
}) {
  const toneClass =
    tone === "string"
      ? "text-foreground"
      : tone === "number"
      ? "text-foreground"
      : tone === "bool"
      ? "text-foreground"
      : "text-muted-foreground";
  return (
    <div className="flex items-baseline gap-2">
      {name !== undefined ? <KeyLabel name={name} /> : null}
      <span className={cn("break-words", toneClass)} title={valueText.length > 80 ? valueText : undefined}>
        {valueText.length > 200 ? `${valueText.slice(0, 200)}…` : valueText}
      </span>
    </div>
  );
}

function Branch({
  name,
  depth,
  openDepth,
  kind,
  items,
}: {
  name?: string | number;
  depth: number;
  openDepth: number;
  kind: "object" | "array";
  items: Array<{ key: string | number; value: Json }>;
}) {
  const [open, setOpen] = useState<boolean>(depth < openDepth);
  const summary = kind === "array" ? `[${items.length}]` : `{${items.length}}`;
  if (items.length === 0) {
    return (
      <div className="flex items-baseline gap-2">
        {name !== undefined ? <KeyLabel name={name} /> : null}
        <span className="text-muted-foreground">{kind === "array" ? "[]" : "{}"}</span>
      </div>
    );
  }
  return (
    <div>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex items-baseline gap-2 text-left hover:text-foreground"
      >
        <Triangle open={open} />
        {name !== undefined ? <KeyLabel name={name} /> : null}
        <span className="text-muted-foreground">{summary}</span>
      </button>
      {open ? (
        <div className="ml-4 border-l border-border pl-3">
          {items.map((entry) => (
            <Node
              key={String(entry.key)}
              value={entry.value}
              name={entry.key}
              depth={depth + 1}
              openDepth={openDepth}
            />
          ))}
        </div>
      ) : null}
    </div>
  );
}

function KeyLabel({ name }: { name: string | number }) {
  return <span className="text-muted-foreground">{typeof name === "number" ? `[${name}]` : `${name}:`}</span>;
}

function Triangle({ open }: { open: boolean }) {
  return (
    <span
      aria-hidden
      className={cn(
        "inline-block h-0 w-0 border-y-[4px] border-y-transparent transition-transform",
        open ? "border-l-[6px] border-l-foreground rotate-90" : "border-l-[6px] border-l-muted-foreground"
      )}
    />
  );
}

// Helper: render a single key/value pair where the value is JSON-tree.
export function JsonRow({ label, value, children }: { label: string; value?: unknown; children?: ReactNode }) {
  return (
    <div className="space-y-1">
      <div className="text-xs uppercase tracking-wide text-muted-foreground">{label}</div>
      <div className="rounded-md border border-border bg-muted/20 p-3">
        {children ?? <JsonTree value={value} />}
      </div>
    </div>
  );
}
