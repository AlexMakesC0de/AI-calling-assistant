import Link from "next/link";
import { cn } from "@/lib/utils";

type Source = "mailpit" | "outlook";

export function InboxTabs({
  active,
  outlookConfigured,
  mailpitUnread,
  outlookUnread,
}: {
  active: Source;
  outlookConfigured: boolean;
  mailpitUnread?: number;
  outlookUnread?: number;
}) {
  return (
    <div className="flex items-center gap-1 border-b border-border">
      <Tab href="/inbox" active={active === "mailpit"} label="Mailpit" badge={mailpitUnread} />
      <Tab
        href="/inbox/outlook"
        active={active === "outlook"}
        label="Outlook"
        badge={outlookUnread}
        muted={!outlookConfigured}
      />
    </div>
  );
}

function Tab({
  href,
  active,
  label,
  badge,
  muted,
}: {
  href: string;
  active: boolean;
  label: string;
  badge?: number;
  muted?: boolean;
}) {
  return (
    <Link
      href={href}
      aria-current={active ? "page" : undefined}
      className={cn(
        "relative -mb-px flex items-center gap-2 border-b-2 px-3 py-2 text-sm transition-colors",
        active
          ? "border-foreground text-foreground"
          : "border-transparent text-muted-foreground hover:text-foreground",
        muted && !active && "opacity-70"
      )}
    >
      <span>{label}</span>
      {typeof badge === "number" && badge > 0 ? (
        <span className="rounded-full bg-foreground px-1.5 py-0.5 text-[10px] font-medium tabular-nums text-background">
          {badge}
        </span>
      ) : null}
    </Link>
  );
}
