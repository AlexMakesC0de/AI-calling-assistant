import Link from "next/link";
import type { LucideIcon } from "lucide-react";

type Props = {
  icon?: LucideIcon;
  title: string;
  description?: string;
  action?: { label: string; href: string };
};

export function EmptyState({ icon: Icon, title, description, action }: Props) {
  return (
    <div className="rounded-md border border-border p-12 text-center">
      {Icon && (
        <div className="mx-auto mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-muted">
          <Icon className="h-5 w-5 text-muted-foreground" />
        </div>
      )}
      <p className="text-sm text-muted-foreground">{title}</p>
      {description && <p className="mt-1 text-xs text-muted-foreground">{description}</p>}
      {action && (
        <Link
          href={action.href}
          className="mt-3 inline-block text-sm text-foreground underline underline-offset-4"
        >
          {action.label}
        </Link>
      )}
    </div>
  );
}
