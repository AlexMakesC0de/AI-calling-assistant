"use client"

import Link from "next/link"
import {
  User,
  Settings,
  ShieldCheck,
  Palette,
  Bell,
  LogOut,
} from "lucide-react"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { logout } from "@/app/login/actions"

interface HeaderProfileProps {
  name: string | null
  email: string
  role: string
}

function getInitials(name: string | null, email: string) {
  return (name ?? email)
    .split(/[\s@.]+/)
    .slice(0, 2)
    .map((s) => s[0]?.toUpperCase() ?? "")
    .join("")
}

export function HeaderProfile({ name, email, role }: HeaderProfileProps) {
  const isAdmin = role === "super_admin"

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button className="flex items-center gap-2 rounded-full p-1 transition-colors hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
          <span className="hidden sm:block px-2 text-sm font-medium">
            {name ?? email}
          </span>
          <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-primary text-xs font-semibold text-primary-foreground">
            {getInitials(name, email)}
          </div>
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        <DropdownMenuLabel className="font-normal">
          <div className="flex flex-col gap-1">
            <p className="text-sm font-medium">{name ?? email}</p>
            <p className="text-xs text-muted-foreground">{email}</p>
          </div>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuGroup>
          <DropdownMenuItem disabled>
            <User />
            <span>Profile</span>
          </DropdownMenuItem>
          <DropdownMenuItem asChild>
            <Link href="/system">
              <Settings />
              <span>Settings</span>
            </Link>
          </DropdownMenuItem>
          {isAdmin && (
            <DropdownMenuItem asChild>
              <Link href="/admin">
                <ShieldCheck />
                <span>Accounts</span>
              </Link>
            </DropdownMenuItem>
          )}
        </DropdownMenuGroup>
        <DropdownMenuSeparator />
        <DropdownMenuGroup>
          <DropdownMenuItem disabled>
            <Palette />
            <span>Theme</span>
          </DropdownMenuItem>
          <DropdownMenuItem disabled>
            <Bell />
            <span>Notifications</span>
          </DropdownMenuItem>
        </DropdownMenuGroup>
        <DropdownMenuSeparator />
        <DropdownMenuItem asChild>
          <form action={logout} className="w-full">
            <button type="submit" className="flex w-full items-center gap-2">
              <LogOut className="size-4 shrink-0" />
              <span>Sign out</span>
            </button>
          </form>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
