import Image from "next/image";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  CardFooter,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

function Swatch({
  name,
  bg,
  fg,
  className,
}: {
  name: string;
  bg: string;
  fg?: string;
  className?: string;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <div
        className={`h-16 w-full rounded-lg border border-border ${bg} ${className ?? ""} flex items-end justify-start p-2`}
      >
        {fg && (
          <span className={`text-xs font-medium ${fg}`}>{name}</span>
        )}
      </div>
      <span className="text-xs text-muted-foreground">{name}</span>
    </div>
  );
}

function Section({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold tracking-tight">{title}</h2>
        {description && (
          <p className="text-sm text-muted-foreground">{description}</p>
        )}
      </div>
      {children}
    </section>
  );
}

export default function ThemePage() {
  return (
    <div className="space-y-12 pb-16">
      {/* Header */}
      <div className="space-y-4">
        <div className="flex items-center gap-6">
          {/* SVG icon (blue part only) */}
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src="/repak_icon.svg"
            alt=""
            width={48}
            height={56}
            className="h-14 w-auto"
          />
          {/* Full PNG logo for reference */}
          <Image
            src="/repak_logo.png"
            alt="Repak — Superior Packaging Solutions"
            width={180}
            height={54}
            priority
            className="h-12 w-auto"
          />
        </div>
        <div className="space-y-1">
          <h1 className="text-2xl font-semibold tracking-tight">
            Repak Design System
          </h1>
          <p className="text-muted-foreground max-w-2xl">
            Scandinavian-inspired palette built on oklch. Warm off-whites,
            natural linen textures, and muted earth tones paired with the Repak
            corporate blue.
          </p>
        </div>
      </div>

      {/* ── Core palette ── */}
      <Section title="Core Palette" description="Primary surface and text tokens">
        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-4">
          <Swatch name="background" bg="bg-background" fg="text-foreground" />
          <Swatch name="foreground" bg="bg-foreground" fg="text-background" />
          <Swatch name="card" bg="bg-card" fg="text-card-foreground" />
          <Swatch name="popover" bg="bg-popover" fg="text-popover-foreground" />
          <Swatch name="primary" bg="bg-primary" fg="text-primary-foreground" />
          <Swatch
            name="primary-foreground"
            bg="bg-primary-foreground"
            fg="text-primary"
          />
        </div>
      </Section>

      {/* ── Secondary / Muted / Accent ── */}
      <Section
        title="Secondary &amp; Accent"
        description="Supporting surfaces for layered UI"
      >
        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-4">
          <Swatch name="secondary" bg="bg-secondary" fg="text-secondary-foreground" />
          <Swatch name="muted" bg="bg-muted" fg="text-muted-foreground" />
          <Swatch name="accent" bg="bg-accent" fg="text-accent-foreground" />
          <Swatch name="border" bg="bg-border" />
          <Swatch name="input" bg="bg-input" />
          <Swatch name="ring" bg="bg-ring" fg="text-primary-foreground" />
        </div>
      </Section>

      {/* ── Semantic ── */}
      <Section title="Semantic Colors" description="Status signals for the dashboard">
        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-5 gap-4">
          <Swatch name="destructive" bg="bg-destructive" fg="text-destructive-foreground" />
          <Swatch name="success" bg="bg-success" fg="text-success-foreground" />
          <Swatch name="warning" bg="bg-warning" fg="text-warning-foreground" />
          <Swatch name="info" bg="bg-info" fg="text-info-foreground" />
        </div>
      </Section>

      {/* ── Chart ── */}
      <Section title="Chart Palette" description="Five harmonious tones for data visualisation">
        <div className="flex gap-0 rounded-lg overflow-hidden border border-border">
          <div className="h-20 flex-1 bg-chart-1 flex items-end justify-center p-2">
            <span className="text-xs font-medium text-white drop-shadow-sm">1 — Blue</span>
          </div>
          <div className="h-20 flex-1 bg-chart-2 flex items-end justify-center p-2">
            <span className="text-xs font-medium text-white drop-shadow-sm">2 — Sage</span>
          </div>
          <div className="h-20 flex-1 bg-chart-3 flex items-end justify-center p-2">
            <span className="text-xs font-medium text-white drop-shadow-sm">3 — Amber</span>
          </div>
          <div className="h-20 flex-1 bg-chart-4 flex items-end justify-center p-2">
            <span className="text-xs font-medium text-white drop-shadow-sm">4 — Clay</span>
          </div>
          <div className="h-20 flex-1 bg-chart-5 flex items-end justify-center p-2">
            <span className="text-xs font-medium text-white drop-shadow-sm">5 — Lavender</span>
          </div>
        </div>
      </Section>

      {/* ── Sidebar ── */}
      <Section title="Sidebar" description="Navigation sidebar tokens">
        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-4">
          <Swatch name="sidebar" bg="bg-sidebar" fg="text-sidebar-foreground" />
          <Swatch name="sidebar-primary" bg="bg-sidebar-primary" fg="text-white" />
          <Swatch name="sidebar-accent" bg="bg-sidebar-accent" fg="text-sidebar-accent-foreground" />
          <Swatch name="sidebar-border" bg="bg-sidebar-border" />
        </div>
      </Section>

      {/* ── Typography ── */}
      <Section title="Typography">
        <Card>
          <CardContent className="space-y-6">
            <div className="space-y-3">
              <h1 className="text-3xl font-semibold tracking-tight">
                Heading One — Inter
              </h1>
              <h2 className="text-2xl font-semibold tracking-tight">
                Heading Two
              </h2>
              <h3 className="text-xl font-semibold tracking-tight">
                Heading Three
              </h3>
              <h4 className="text-lg font-medium">Heading Four</h4>
            </div>
            <p className="max-w-prose leading-relaxed">
              Body text in the warm foreground. Hygge design emphasises
              readability and calm. Muted tones reduce cognitive load while the
              Repak blue anchors interactive elements.{" "}
              <span className="text-muted-foreground">
                Secondary text uses the muted-foreground token for reduced
                emphasis.
              </span>
            </p>
            <p className="font-mono text-sm text-muted-foreground">
              Monospace — JetBrains Mono for code and data.
            </p>
          </CardContent>
        </Card>
      </Section>

      {/* ── Buttons ── */}
      <Section title="Buttons" description="All button variants at each size">
        <Card>
          <CardContent className="space-y-6">
            <div className="flex flex-wrap items-center gap-3">
              <Button>Primary</Button>
              <Button variant="outline">Outline</Button>
              <Button variant="ghost">Ghost</Button>
              <Button variant="link">Link</Button>
            </div>

            <div className="flex flex-wrap items-center gap-3">
              <Button size="sm">Small</Button>
              <Button size="default">Default</Button>
              <Button size="lg">Large</Button>
            </div>

            <div className="flex flex-wrap items-center gap-3">
              <Button disabled>Disabled</Button>
              <Button variant="outline" disabled>
                Disabled Outline
              </Button>
            </div>

            {/* Semantic button examples using raw utility classes */}
            <div>
              <p className="text-sm text-muted-foreground mb-3">
                Semantic buttons (utility classes)
              </p>
              <div className="flex flex-wrap items-center gap-3">
                <button className="inline-flex h-9 items-center justify-center rounded-md bg-destructive px-4 text-sm font-medium text-destructive-foreground hover:bg-destructive/90 transition-colors">
                  Destructive
                </button>
                <button className="inline-flex h-9 items-center justify-center rounded-md bg-success px-4 text-sm font-medium text-success-foreground hover:bg-success/90 transition-colors">
                  Success
                </button>
                <button className="inline-flex h-9 items-center justify-center rounded-md bg-warning px-4 text-sm font-medium text-warning-foreground hover:bg-warning/90 transition-colors">
                  Warning
                </button>
                <button className="inline-flex h-9 items-center justify-center rounded-md bg-info px-4 text-sm font-medium text-info-foreground hover:bg-info/90 transition-colors">
                  Info
                </button>
              </div>
            </div>
          </CardContent>
        </Card>
      </Section>

      {/* ── Badges ── */}
      <Section title="Badges">
        <div className="flex flex-wrap gap-3">
          <Badge>Default</Badge>
          <Badge variant="solid">Solid</Badge>
          <Badge variant="muted">Muted</Badge>
          <Badge className="border-success/30 bg-success/10 text-success">
            Success
          </Badge>
          <Badge className="border-warning/30 bg-warning/10 text-warning">
            Warning
          </Badge>
          <Badge className="border-destructive/30 bg-destructive/10 text-destructive">
            Destructive
          </Badge>
          <Badge className="border-info/30 bg-info/10 text-info">Info</Badge>
        </div>
      </Section>

      {/* ── Cards ── */}
      <Section title="Cards" description="Layered card components">
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          <Card>
            <CardHeader>
              <CardTitle>Calls Processed</CardTitle>
              <CardDescription>Last 24 hours</CardDescription>
            </CardHeader>
            <CardContent>
              <p className="text-3xl font-semibold tracking-tight">1,284</p>
              <p className="text-sm text-success mt-1">+12.3% from yesterday</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Open Incidents</CardTitle>
              <CardDescription>Requires attention</CardDescription>
            </CardHeader>
            <CardContent>
              <p className="text-3xl font-semibold tracking-tight">7</p>
              <p className="text-sm text-warning mt-1">3 high priority</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>System Health</CardTitle>
              <CardDescription>All services</CardDescription>
            </CardHeader>
            <CardContent>
              <p className="text-3xl font-semibold tracking-tight">99.8%</p>
              <p className="text-sm text-muted-foreground mt-1">
                Uptime this month
              </p>
            </CardContent>
          </Card>
        </div>
      </Section>

      {/* ── Form Elements ── */}
      <Section title="Form Elements">
        <Card>
          <CardContent>
            <div className="grid gap-6 sm:grid-cols-2 max-w-xl">
              <div className="space-y-2">
                <Label htmlFor="name">Name</Label>
                <Input id="name" placeholder="Enter your name" />
              </div>
              <div className="space-y-2">
                <Label htmlFor="email">Email</Label>
                <Input
                  id="email"
                  type="email"
                  placeholder="name@repak.com"
                />
              </div>
              <div className="sm:col-span-2 flex gap-3">
                <Button>Submit</Button>
                <Button variant="outline">Cancel</Button>
              </div>
            </div>
          </CardContent>
        </Card>
      </Section>

      {/* ── Surfaces demo ── */}
      <Section
        title="Surface Layering"
        description="How background / card / secondary / muted / accent stack"
      >
        <div className="rounded-lg border border-border bg-background p-6 space-y-4">
          <p className="text-sm font-medium">Background</p>
          <div className="rounded-lg border border-border bg-card p-5 space-y-4">
            <p className="text-sm font-medium">Card</p>
            <div className="rounded-md bg-secondary p-4 space-y-3">
              <p className="text-sm font-medium text-secondary-foreground">
                Secondary
              </p>
              <div className="rounded-md bg-muted p-3 space-y-2">
                <p className="text-sm font-medium text-muted-foreground">
                  Muted
                </p>
                <div className="rounded-md bg-accent p-3">
                  <p className="text-sm font-medium text-accent-foreground">
                    Accent
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </Section>

      {/* ── Dark mode toggle hint ── */}
      <Section title="Dark Mode">
        <Card>
          <CardContent>
            <p className="text-sm text-muted-foreground">
              Add <code className="font-mono text-xs bg-muted px-1.5 py-0.5 rounded">class=&quot;dark&quot;</code> to{" "}
              <code className="font-mono text-xs bg-muted px-1.5 py-0.5 rounded">&lt;html&gt;</code> to
              preview the dark palette. The deep blue-charcoal tones evoke a
              cozy Nordic evening.
            </p>
          </CardContent>
        </Card>
      </Section>
    </div>
  );
}
