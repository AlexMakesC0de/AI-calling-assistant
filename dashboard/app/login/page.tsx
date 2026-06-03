"use client";

import { useActionState } from "react";
import { login } from "./actions";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default function LoginPage() {
  const [state, formAction, pending] = useActionState(login, null);

  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      {/* Left panel — branding */}
      <div className="hidden lg:flex flex-col justify-between bg-primary p-10 text-primary-foreground">
        <div className="flex items-center gap-3">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src="/repak_icon.svg"
            alt=""
            className="h-8 w-auto brightness-0 invert"
          />
          <span className="text-lg font-semibold tracking-tight">Repak</span>
        </div>
        <div className="space-y-4">
          <blockquote className="text-xl/relaxed font-medium">
            Support Pipeline Dashboard
          </blockquote>
          <p className="text-sm text-primary-foreground/70">
            AI-extracted incidents, transcriptions, and dispatch inbox — all in one place.
          </p>
        </div>
        <p className="text-xs text-primary-foreground/50">
          &copy; {new Date().getFullYear()} Repak
        </p>
      </div>

      {/* Right panel — sign-in form */}
      <div className="flex flex-col items-center justify-center px-6 py-12">
        <div className="w-full max-w-[360px] space-y-8">
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
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                name="password"
                type="password"
                placeholder="&bull;&bull;&bull;&bull;&bull;&bull;&bull;&bull;"
                autoComplete="current-password"
                required
              />
            </div>
            <Button type="submit" className="w-full" disabled={pending}>
              {pending ? "Signing in…" : "Sign in"}
            </Button>
          </form>
        </div>
      </div>
    </div>
  );
}
