"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

type DeviceCodeState =
  | { phase: "idle" }
  | { phase: "loading" }
  | { phase: "waiting"; userCode: string; verificationUri: string; deviceCode: string; interval: number; expiresAt: number }
  | { phase: "success"; email: string }
  | { phase: "error"; message: string };

export function DeviceCodeConnect() {
  const [state, setState] = useState<DeviceCodeState>({ phase: "idle" });
  const router = useRouter();
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  useEffect(() => () => stopPolling(), [stopPolling]);

  async function startDeviceCode() {
    setState({ phase: "loading" });
    try {
      const res = await fetch("/api/outlook/device-code", { method: "POST" });
      if (!res.ok) {
        const data = await res.json().catch(() => ({ error: "Failed to start device code flow" }));
        setState({ phase: "error", message: data.error ?? `HTTP ${res.status}` });
        return;
      }
      const data = (await res.json()) as {
        deviceCode: string;
        userCode: string;
        verificationUri: string;
        expiresIn: number;
        interval: number;
      };

      const waitingState: DeviceCodeState = {
        phase: "waiting",
        userCode: data.userCode,
        verificationUri: data.verificationUri,
        deviceCode: data.deviceCode,
        interval: Math.max(data.interval, 5),
        expiresAt: Date.now() + data.expiresIn * 1000,
      };
      setState(waitingState);

      let interval = Math.max(data.interval, 5) * 1000;
      pollRef.current = setInterval(async () => {
        if (Date.now() > waitingState.expiresAt) {
          stopPolling();
          setState({ phase: "error", message: "Device code expired. Please try again." });
          return;
        }

        try {
          const pollRes = await fetch("/api/outlook/device-poll", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ deviceCode: data.deviceCode }),
          });
          const pollData = (await pollRes.json()) as { status: string; email?: string; error?: string };

          if (pollData.status === "success") {
            stopPolling();
            setState({ phase: "success", email: pollData.email ?? "" });
            setTimeout(() => router.refresh(), 1500);
          } else if (pollData.status === "slow_down") {
            interval += 5000;
          } else if (pollData.status === "error") {
            stopPolling();
            setState({ phase: "error", message: pollData.error ?? "Authentication failed" });
          }
        } catch {
          // Network error — keep polling
        }
      }, interval);
    } catch (err) {
      setState({ phase: "error", message: err instanceof Error ? err.message : "Network error" });
    }
  }

  if (state.phase === "idle") {
    return (
      <Button onClick={startDeviceCode}>
        Connect Outlook
      </Button>
    );
  }

  if (state.phase === "loading") {
    return <Button disabled>Starting...</Button>;
  }

  if (state.phase === "success") {
    return (
      <Card>
        <CardContent className="py-6 text-center">
          <p className="text-sm font-medium text-green-600">
            Connected as {state.email}
          </p>
          <p className="mt-1 text-xs text-muted-foreground">Refreshing...</p>
        </CardContent>
      </Card>
    );
  }

  if (state.phase === "error") {
    return (
      <Card>
        <CardContent className="space-y-3 py-6">
          <p className="text-sm text-destructive">{state.message}</p>
          <Button variant="outline" size="sm" onClick={startDeviceCode}>
            Try again
          </Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Sign in with Microsoft</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-sm text-muted-foreground">
          Open{" "}
          <a
            href={state.verificationUri}
            target="_blank"
            rel="noopener noreferrer"
            className="font-medium text-foreground underline underline-offset-4"
          >
            {state.verificationUri}
          </a>{" "}
          and enter this code:
        </p>
        <div className="flex items-center justify-center rounded-md border border-border bg-muted/40 py-4">
          <span className="select-all font-mono text-3xl font-bold tracking-widest">{state.userCode}</span>
        </div>
        <p className="text-xs text-muted-foreground">
          Waiting for authentication... This code expires in {Math.ceil((state.expiresAt - Date.now()) / 60000)} minutes.
        </p>
        <Button variant="ghost" size="sm" onClick={() => { stopPolling(); setState({ phase: "idle" }); }}>
          Cancel
        </Button>
      </CardContent>
    </Card>
  );
}
