"use client";

import { useEffect, useRef } from "react";
import { useRouter } from "next/navigation";

const GO_ROUTES: Record<string, string> = {
  o: "/",
  i: "/incidents",
  w: "/whatsapp",
  c: "/calls",
  u: "/upload",
  m: "/inbox",
  s: "/search",
};

export function useKeyboardShortcuts() {
  const router = useRouter();
  const lastKeyRef = useRef<{ key: string; time: number } | null>(null);

  useEffect(() => {
    function handler(e: KeyboardEvent) {
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || (e.target as HTMLElement)?.isContentEditable) {
        if (e.key === "Escape") (e.target as HTMLElement).blur();
        return;
      }

      if (e.key === "/") {
        e.preventDefault();
        const input = document.querySelector<HTMLInputElement>("input[name='q']");
        input?.focus();
        return;
      }

      if (e.key === "g") {
        lastKeyRef.current = { key: "g", time: Date.now() };
        return;
      }

      if (lastKeyRef.current?.key === "g" && Date.now() - lastKeyRef.current.time < 500) {
        const route = GO_ROUTES[e.key];
        if (route) {
          e.preventDefault();
          router.push(route);
        }
        lastKeyRef.current = null;
        return;
      }

      lastKeyRef.current = null;
    }

    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [router]);
}
