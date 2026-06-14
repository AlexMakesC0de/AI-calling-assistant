"use client"

import Link from "next/link"
import Image from "next/image"
import { usePathname } from "next/navigation"
import {
  LayoutDashboard,
  Upload,
  AlertTriangle,
  FileText,
  Inbox,
  MessageCircle,
  Search,
  Settings,
  ShieldCheck,
  PanelLeft,
} from "lucide-react"

import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
  SidebarSeparator,
  useSidebar,
} from "@/components/ui/sidebar"
import type { SessionPayload } from "@/lib/auth"

const workspaceItems = [
  { href: "/", label: "Overview", icon: LayoutDashboard, match: (p: string) => p === "/" },
  { href: "/incidents", label: "Incidents", icon: AlertTriangle, match: (p: string) => p.startsWith("/incidents") },
  { href: "/generate-word", label: "Issue History", icon: FileText, match: (p: string) => p.startsWith("/generate-word") },
]

const ingestItems = [
  { href: "/upload", label: "Upload", icon: Upload, match: (p: string) => p.startsWith("/upload") },
  { href: "/inbox", label: "Inbox", icon: Inbox, match: (p: string) => p.startsWith("/inbox") },
  { href: "/whatsapp", label: "WhatsApp", icon: MessageCircle, match: (p: string) => p.startsWith("/whatsapp") },
]

const utilityItems = [
  { href: "/search", label: "Search", icon: Search, match: (p: string) => p.startsWith("/search") },
  { href: "/system", label: "System", icon: Settings, match: (p: string) => p.startsWith("/system") },
]

function CollapseToggle() {
  const { toggleSidebar } = useSidebar()

  return (
    <SidebarMenuButton tooltip="Toggle sidebar" onClick={toggleSidebar}>
      <PanelLeft />
      <span>Collapse</span>
    </SidebarMenuButton>
  )
}

export function AppSidebar({ session }: { session: SessionPayload }) {
  const pathname = usePathname()

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton size="lg" asChild tooltip="REPAK">
              <Link href="/" className="gap-3">
                <div className="flex size-8 shrink-0 items-center justify-center">
                  <Image
                    src="/repak_icon.svg"
                    alt="Repak"
                    width={24}
                    height={28}
                    className="size-6"
                  />
                </div>
                <div className="flex flex-col gap-0.5 leading-none">
                  <span className="text-sm font-bold tracking-tight">REPAK</span>
                  <span className="text-[10px] text-muted-foreground">Support Pipeline</span>
                </div>
              </Link>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>

      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>Workspace</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {workspaceItems.map((item) => (
                <SidebarMenuItem key={item.href}>
                  <SidebarMenuButton
                    asChild
                    isActive={item.match(pathname)}
                    tooltip={item.label}
                  >
                    <Link href={item.href}>
                      <item.icon />
                      <span>{item.label}</span>
                    </Link>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

        <SidebarGroup>
          <SidebarGroupLabel>Ingest</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {ingestItems.map((item) => (
                <SidebarMenuItem key={item.href}>
                  <SidebarMenuButton
                    asChild
                    isActive={item.match(pathname)}
                    tooltip={item.label}
                  >
                    <Link href={item.href}>
                      <item.icon />
                      <span>{item.label}</span>
                    </Link>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

        <SidebarSeparator />

        <SidebarGroup>
          <SidebarGroupContent>
            <SidebarMenu>
              {utilityItems.map((item) => (
                <SidebarMenuItem key={item.href}>
                  <SidebarMenuButton
                    asChild
                    isActive={item.match(pathname)}
                    tooltip={item.label}
                  >
                    <Link href={item.href}>
                      <item.icon />
                      <span>{item.label}</span>
                    </Link>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
              {session.role === "super_admin" && (
                <SidebarMenuItem>
                  <SidebarMenuButton
                    asChild
                    isActive={pathname.startsWith("/admin")}
                    tooltip="Accounts"
                  >
                    <Link href="/admin">
                      <ShieldCheck />
                      <span>Accounts</span>
                    </Link>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              )}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      <SidebarFooter>
        <SidebarMenu>
          <SidebarMenuItem>
            <CollapseToggle />
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>
    </Sidebar>
  )
}
