"use client";

import { useActionState } from "react";
import { login } from "./actions";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Headphones, BrainCircuit, MailCheck } from "lucide-react";

export default function LoginPage() {
  const [state, formAction, pending] = useActionState(login, null);

  return (
    <div className="grid min-h-screen lg:grid-cols-5">
      {/* Left panel — branding */}
      <div className="relative hidden lg:col-span-3 lg:flex flex-col justify-between overflow-hidden bg-primary p-10 text-primary-foreground">
        {/* Decorative rings — echo the Repak logo motif */}
        <div className="pointer-events-none absolute inset-0">
          <div className="absolute -right-24 -top-24 h-[420px] w-[420px] rounded-full border-[40px] border-white/[0.06] animate-[spin_90s_linear_infinite]" />
          <div className="absolute -right-8 top-8 h-[300px] w-[300px] rounded-full border-[28px] border-white/[0.04] animate-[spin_120s_linear_infinite_reverse]" />
          <div className="absolute -bottom-32 -left-16 h-[500px] w-[500px] rounded-full border-[48px] border-white/[0.05] animate-[spin_150s_linear_infinite]" />
          <div className="absolute bottom-20 left-40 h-[180px] w-[180px] rounded-full border-[20px] border-white/[0.04] animate-[spin_80s_linear_infinite_reverse]" />
          {/* Gradient glow */}
          <div className="absolute right-1/4 top-1/3 h-64 w-64 rounded-full bg-white/[0.06] blur-3xl" />
          <div className="absolute bottom-1/4 left-1/4 h-48 w-48 rounded-full bg-white/[0.04] blur-3xl" />
        </div>

        {/* Content */}
        <div className="relative z-10 flex items-center gap-3">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src="/repak_icon.svg"
            alt=""
            className="h-8 w-auto brightness-0 invert"
          />
          <span className="text-lg font-semibold tracking-tight">Repak</span>
        </div>

        <div className="relative z-10 max-w-lg space-y-6">
          <h2 className="text-3xl/snug font-semibold tracking-tight">
            Support Pipeline Dashboard
          </h2>
          <p className="text-base/relaxed text-primary-foreground/70">
            From phone call to resolved incident — powered by AI transcription, automated form extraction, and multi-channel dispatch.
          </p>

          {/* Feature highlights */}
          <div className="grid gap-4 pt-4 sm:grid-cols-3">
            <div className="flex items-start gap-3 rounded-lg bg-white/[0.07] px-4 py-3.5 backdrop-blur-sm">
              <Headphones className="mt-0.5 h-5 w-5 shrink-0 text-primary-foreground/80" />
              <div>
                <p className="text-sm font-medium">Transcribe</p>
                <p className="text-xs text-primary-foreground/60">Calls to text with speaker diarization</p>
              </div>
            </div>
            <div className="flex items-start gap-3 rounded-lg bg-white/[0.07] px-4 py-3.5 backdrop-blur-sm">
              <BrainCircuit className="mt-0.5 h-5 w-5 shrink-0 text-primary-foreground/80" />
              <div>
                <p className="text-sm font-medium">Extract</p>
                <p className="text-xs text-primary-foreground/60">AI-powered incident form generation</p>
              </div>
            </div>
            <div className="flex items-start gap-3 rounded-lg bg-white/[0.07] px-4 py-3.5 backdrop-blur-sm">
              <MailCheck className="mt-0.5 h-5 w-5 shrink-0 text-primary-foreground/80" />
              <div>
                <p className="text-sm font-medium">Dispatch</p>
                <p className="text-xs text-primary-foreground/60">Email, WhatsApp &amp; Outlook inbox</p>
              </div>
            </div>
          </div>
        </div>

        <p className="relative z-10 text-xs text-primary-foreground/40">
          &copy; {new Date().getFullYear()} Repak
        </p>
      </div>

      {/* Right panel — sign-in form */}
      <div className="relative flex flex-col items-center justify-center px-6 py-12 lg:col-span-2">
        {/* Subtle background texture for the form side */}
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(oklch(0.4515_0.0902_230.26/0.04)_1px,transparent_1px)] [background-size:24px_24px]" />

        <div className="relative z-10 w-full max-w-[360px] space-y-8">
          {/* Mobile-only logo */}
          <div className="flex items-center justify-center gap-2.5 lg:hidden">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src="/repak_icon.svg" alt="" className="h-7 w-auto" />
            <span className="text-lg font-semibold tracking-tight">Repak</span>
          </div>

          <div className="space-y-2 text-center">
            <h1 className="text-2xl font-medium tracking-tight">Welcome back</h1>
            <p className="text-sm text-muted-foreground">
              Sign in to your account to continue
            </p>
          </div>

          <form action={formAction} className="space-y-4">
            {state?.error && (
              <div className="rounded-md border border-destructive/20 bg-destructive/10 px-4 py-3 text-sm text-destructive">
                {state.error}
              </div>
            )}
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                name="email"
                type="email"
                placeholder="name@company.com"
                autoComplete="email"
                className="h-10"
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                name="password"
                type="password"
                placeholder="&#8226;&#8226;&#8226;&#8226;&#8226;&#8226;&#8226;&#8226;"
                autoComplete="current-password"
                className="h-10"
                required
              />
            </div>
            <Button type="submit" className="h-10 w-full" disabled={pending}>
              {pending ? "Signing in…" : "Sign in"}
            </Button>
          </form>

          <p className="text-center text-xs text-muted-foreground/60 lg:hidden">
            &copy; {new Date().getFullYear()} Repak
          </p>
        </div>
      </div>
    </div>
  );
}
