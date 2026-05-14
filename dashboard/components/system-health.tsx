"use client";

import { useEffect, useMemo, useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { ServiceCheck } from "@/lib/health";

const STORAGE_KEY = "dashboard:lastHealthAnimDate";
const PER_SERVICE_MS = 480;
const STAGGER_MS = 220;

function todayKey(): string {
  const d = new Date();
  return `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`;
}

export function SystemHealth({ checks, generatedAt }: { checks: ServiceCheck[]; generatedAt: string }) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  // null = not yet decided (SSR / first render). false = animate. true = skip.
  const [skipAnimation, setSkipAnimation] = useState<boolean | null>(null);

  useEffect(() => {
    try {
      const last = window.localStorage.getItem(STORAGE_KEY);
      const today = todayKey();
      if (last === today) {
        setSkipAnimation(true);
        return;
      }
      setSkipAnimation(false);
      // Mark as animated AFTER the longest possible animation finishes.
      const totalMs = checks.length * STAGGER_MS + PER_SERVICE_MS + 200;
      const timer = window.setTimeout(() => {
        try {
          window.localStorage.setItem(STORAGE_KEY, today);
        } catch {
          // ignore quota errors
        }
      }, totalMs);
      return () => window.clearTimeout(timer);
    } catch {
      setSkipAnimation(true);
    }
  }, [checks.length]);

  const allHealthy = checks.every((c) => c.status === "healthy");
  const unhealthyCount = checks.filter((c) => c.status === "unhealthy").length;
  const generated = useMemo(() => new Date(generatedAt).toLocaleTimeString(), [generatedAt]);

  function refresh() {
    startTransition(() => router.refresh());
  }

  function reAnimate() {
    try {
      window.localStorage.removeItem(STORAGE_KEY);
    } catch {
      // ignore
    }
    setSkipAnimation(null);
    // Force a re-mount so the animation runs again with the same data.
    window.requestAnimationFrame(() => setSkipAnimation(false));
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0">
        <div className="space-y-1">
          <CardTitle>{allHealthy ? "All systems operational" : `${unhealthyCount} service${unhealthyCount === 1 ? "" : "s"} unhealthy`}</CardTitle>
          <p className="text-xs text-muted-foreground">Checked at {generated}</p>
        </div>
        <div className="flex items-center gap-2">
          <Button type="button" size="sm" variant="ghost" onClick={reAnimate}>
            Replay
          </Button>
          <Button type="button" size="sm" variant="outline" onClick={refresh} disabled={pending}>
            {pending ? "Refreshing…" : "Refresh"}
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-2">
        {checks.map((check, idx) => (
          <ServiceRow
            key={check.key}
            check={check}
            index={idx}
            skipAnimation={skipAnimation}
          />
        ))}
      </CardContent>
    </Card>
  );
}

function ServiceRow({
  check,
  index,
  skipAnimation,
}: {
  check: ServiceCheck;
  index: number;
  skipAnimation: boolean | null;
}) {
  // Three visual phases per row:
  //  - "idle"     : bar empty (only used pre-animation)
  //  - "filling"  : bar transitioning from 0% → 100%
  //  - "settled"  : bar at 100%, status icon revealed
  const [phase, setPhase] = useState<"idle" | "filling" | "settled">(
    skipAnimation === true ? "settled" : "idle"
  );

  useEffect(() => {
    if (skipAnimation === null) return;
    if (skipAnimation) {
      setPhase("settled");
      return;
    }
    setPhase("idle");
    const startDelay = index * STAGGER_MS;
    const startTimer = window.setTimeout(() => setPhase("filling"), startDelay);
    const settleTimer = window.setTimeout(() => setPhase("settled"), startDelay + PER_SERVICE_MS);
    return () => {
      window.clearTimeout(startTimer);
      window.clearTimeout(settleTimer);
    };
  }, [skipAnimation, index]);

  const isHealthy = check.status === "healthy";
  const fillWidth =
    phase === "idle"
      ? "0%"
      : phase === "filling"
      ? isHealthy
        ? "100%"
        : "62%"
      : "100%";

  return (
    <div className="flex items-center gap-4 py-2">
      <div className="w-44 shrink-0 text-sm font-medium">{check.name}</div>
      <div className="relative h-2 flex-1 overflow-hidden rounded-full border border-border bg-background">
        <div
          className={cn(
            "h-full transition-[width] ease-out",
            phase === "filling" ? "duration-500" : "duration-200",
            isHealthy ? "bg-foreground" : "bg-foreground/40"
          )}
          style={{ width: fillWidth }}
        />
        {!isHealthy && phase === "settled" ? (
          <div
            aria-hidden
            className="absolute inset-y-0 right-0 flex w-[38%] items-center justify-end pr-2"
          >
            <div
              className="h-full w-full bg-foreground"
              style={{
                clipPath:
                  "polygon(8% 0, 100% 0, 100% 100%, 0 100%)",
              }}
            />
          </div>
        ) : null}
      </div>
      <div className="w-44 shrink-0 text-right text-xs">
        {phase !== "settled" ? (
          <span className="text-muted-foreground">checking…</span>
        ) : isHealthy ? (
          <span className="inline-flex items-center gap-1.5">
            <CheckIcon />
            <span>healthy</span>
            {check.latencyMs != null ? (
              <span className="text-muted-foreground tabular-nums">{check.latencyMs}ms</span>
            ) : null}
          </span>
        ) : (
          <span className="inline-flex items-center gap-1.5" title={check.detail ?? undefined}>
            <CrossIcon />
            <span>unhealthy</span>
          </span>
        )}
      </div>
      {phase === "settled" && !isHealthy && check.detail ? (
        <div className="hidden text-xs text-muted-foreground md:block md:max-w-[220px] md:truncate" title={check.detail}>
          {check.detail}
        </div>
      ) : null}
    </div>
  );
}

function CheckIcon() {
  return (
    <svg viewBox="0 0 12 12" className="h-3 w-3" aria-hidden>
      <path d="M2 6.5l2.5 2.5L10 3.5" stroke="currentColor" strokeWidth="1.5" fill="none" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function CrossIcon() {
  return (
    <svg viewBox="0 0 12 12" className="h-3 w-3" aria-hidden>
      <path d="M3 3l6 6M9 3l-6 6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}
