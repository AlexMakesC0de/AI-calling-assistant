import type { Config } from "tailwindcss";

function oklch(variable: string) {
  return `oklch(var(--${variable}) / <alpha-value>)`;
}

const config: Config = {
  darkMode: ["class"],
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    container: {
      center: true,
      padding: "1.5rem",
      screens: { "2xl": "1280px" },
    },
    extend: {
      fontFamily: {
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "monospace"],
      },
      colors: {
        border: oklch("border"),
        input: oklch("input"),
        ring: oklch("ring"),
        background: oklch("background"),
        foreground: oklch("foreground"),
        primary: {
          DEFAULT: oklch("primary"),
          foreground: oklch("primary-foreground"),
        },
        secondary: {
          DEFAULT: oklch("secondary"),
          foreground: oklch("secondary-foreground"),
        },
        muted: {
          DEFAULT: oklch("muted"),
          foreground: oklch("muted-foreground"),
        },
        accent: {
          DEFAULT: oklch("accent"),
          foreground: oklch("accent-foreground"),
        },
        card: {
          DEFAULT: oklch("card"),
          foreground: oklch("card-foreground"),
        },
        destructive: {
          DEFAULT: oklch("destructive"),
          foreground: oklch("destructive-foreground"),
        },
        popover: {
          DEFAULT: oklch("popover"),
          foreground: oklch("popover-foreground"),
        },
        sidebar: {
          DEFAULT: oklch("sidebar-background"),
          foreground: oklch("sidebar-foreground"),
          primary: oklch("sidebar-primary"),
          "primary-foreground": oklch("sidebar-primary-foreground"),
          accent: oklch("sidebar-accent"),
          "accent-foreground": oklch("sidebar-accent-foreground"),
          border: oklch("sidebar-border"),
          ring: oklch("sidebar-ring"),
          "muted-foreground": oklch("sidebar-muted-foreground"),
        },
        success: {
          DEFAULT: oklch("success"),
          foreground: oklch("success-foreground"),
        },
        warning: {
          DEFAULT: oklch("warning"),
          foreground: oklch("warning-foreground"),
        },
        info: {
          DEFAULT: oklch("info"),
          foreground: oklch("info-foreground"),
        },
        chart: {
          "1": oklch("chart-1"),
          "2": oklch("chart-2"),
          "3": oklch("chart-3"),
          "4": oklch("chart-4"),
          "5": oklch("chart-5"),
        },
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
      keyframes: {
        "accordion-down": { from: { height: "0" }, to: { height: "var(--radix-accordion-content-height)" } },
        "accordion-up": { from: { height: "var(--radix-accordion-content-height)" }, to: { height: "0" } },
      },
      animation: {
        "accordion-down": "accordion-down 0.2s ease-out",
        "accordion-up": "accordion-up 0.2s ease-out",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};

export default config;
