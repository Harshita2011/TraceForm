import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        canvas:           "#0A0A0A",
        surface:          "#111111",
        "surface-elevated":"#161616",
        "surface-border": "#1F1F1F",
        "surface-border-sub":"#2A2A2A",

        "text-primary":   "#F3F3EF",
        "text-secondary": "#8A8A8A",
        "text-tertiary":  "#555555",

        accent:           "#F5A623",
        "accent-subtle":  "rgba(245,166,35,0.12)",
        "accent-border":  "rgba(245,166,35,0.25)",

        "status-pass":    "#3D7A5E",
        "status-fail":    "#9B4040",
        "status-budget":  "#7A6B3D",
        "status-pending": "#555555",
        "status-running": "#3D6B9B",
      },
      fontFamily: {
        display: ["var(--font-display)", "Impact", "sans-serif"],
        body:    ["var(--font-body)",    "system-ui", "sans-serif"],
        mono:    ["var(--font-mono)",    "Fira Code",  "monospace"],
      },
      fontSize: {
        "hero-xl": ["clamp(4rem,10vw,8rem)",   { lineHeight: "1.0", letterSpacing: "-0.02em" }],
        "hero-lg": ["clamp(3rem,7vw,6rem)",    { lineHeight: "1.0", letterSpacing: "-0.02em" }],
        "display-lg": ["clamp(2rem,4vw,3.5rem)", { lineHeight: "1.1" }],
      },
      spacing: {
        "18": "72px",
        "22": "88px",
        "30": "120px",
      },
      maxWidth: {
        content:   "1440px",
        dashboard: "1280px",
      },
      borderRadius: {
        "sm": "4px",
        DEFAULT: "6px",
        "md": "8px",
        "lg": "12px",
        "xl": "16px",
      },
      transitionTimingFunction: {
        "out-expo":  "cubic-bezier(0.16, 1, 0.3, 1)",
        "out-quart": "cubic-bezier(0.25, 1, 0.5, 1)",
      },
      transitionDuration: {
        "0":   "0ms",
        "150": "150ms",
        "200": "200ms",
        "300": "300ms",
        "500": "500ms",
        "750": "750ms",
      },
      animation: {
        "pulse-slow": "pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite",
      },
      backdropBlur: {
        xs: "2px",
      },
    },
  },
  plugins: [],
};

export default config;
