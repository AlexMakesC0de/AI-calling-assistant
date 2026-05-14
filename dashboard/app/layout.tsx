import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import Link from "next/link";
import "./globals.css";
import { Nav } from "@/components/nav";

const inter = Inter({ subsets: ["latin"], variable: "--font-sans", display: "swap" });
const mono = JetBrains_Mono({ subsets: ["latin"], variable: "--font-mono", display: "swap" });

export const metadata: Metadata = {
  title: "Support Pipeline Dashboard",
  description: "Upload call audio, browse AI-extracted incidents, and read the dispatch inbox.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${inter.variable} ${mono.variable}`}>
      <body className="min-h-screen bg-background font-sans text-foreground antialiased">
        <header className="sticky top-0 z-10 border-b border-border bg-background/80 backdrop-blur">
          <div className="container flex h-14 items-center justify-between">
            <Link href="/" className="font-medium tracking-tight">
              Support Pipeline
            </Link>
            <Nav />
          </div>
        </header>
        <main className="container py-8">{children}</main>
      </body>
    </html>
  );
}
