"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import {
  LayoutDashboard,
  Upload,
  AlertTriangle,
  Inbox,
  MessageCircle,
  Search,
  Settings,
} from "lucide-react"

import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
} from "@/components/ui/sidebar"

const navItems = [
  { href: "/", label: "Overview", icon: LayoutDashboard, match: (p: string) => p === "/" },
  { href: "/upload", label: "Upload", icon: Upload, match: (p: string) => p.startsWith("/upload") },
  { href: "/incidents", label: "Incidents", icon: AlertTriangle, match: (p: string) => p.startsWith("/incidents") },
  { href: "/inbox", label: "Inbox", icon: Inbox, match: (p: string) => p.startsWith("/inbox") },
  { href: "/whatsapp", label: "WhatsApp", icon: MessageCircle, match: (p: string) => p.startsWith("/whatsapp") },
  { href: "/search", label: "Search", icon: Search, match: (p: string) => p.startsWith("/search") },
  { href: "/system", label: "System", icon: Settings, match: (p: string) => p.startsWith("/system") },
]

export function AppSidebar() {
  const pathname = usePathname()

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton size="lg" asChild>
              <Link href="/">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src="/repak_icon.svg"
                  alt=""
                  width={20}
                  height={24}
                  className="h-5 w-auto shrink-0"
                />
                <span className="font-semibold tracking-tight">Repak</span>
              </Link>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>Navigation</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {navItems.map((item) => {
                const active = item.match(pathname)
                return (
                  <SidebarMenuItem key={item.href}>
                    <SidebarMenuButton
                      asChild
                      isActive={active}
                      tooltip={item.label}
                    >
                      <Link href={item.href}>
                        <item.icon />
                        <span>{item.label}</span>
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                )
              })}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
      <SidebarRail />
    </Sidebar>
  )
}
