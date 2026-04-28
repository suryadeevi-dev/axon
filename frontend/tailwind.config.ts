import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        axon: {
          bg:      "rgb(var(--axon-bg) / <alpha-value>)",
          surface: "rgb(var(--axon-surface) / <alpha-value>)",
          border:  "rgb(var(--axon-border) / <alpha-value>)",
          cyan:    "rgb(var(--axon-cyan) / <alpha-value>)",
          purple:  "rgb(var(--axon-purple) / <alpha-value>)",
          green:   "rgb(var(--axon-green) / <alpha-value>)",
          muted:   "rgb(var(--axon-muted) / <alpha-value>)",
          text:    "rgb(var(--axon-text) / <alpha-value>)",
        },
      },
      fontFamily: {
        mono: ["'Geist Mono'", "ui-monospace", "SFMono-Regular", "monospace"],
        sans: ["'Inter'", "system-ui", "sans-serif"],
      },
      animation: {
        "pulse-cyan":   "pulse-cyan 2s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        "slide-up":     "slide-up 0.3s ease-out",
        "fade-in":      "fade-in 0.2s ease-out",
        "cursor-blink": "cursor-blink 1s step-end infinite",
      },
      keyframes: {
        "pulse-cyan": {
          "0%, 100%": { opacity: "1", boxShadow: "0 0 0 0 rgba(var(--axon-cyan),0.4)" },
          "50%":      { opacity: "0.8", boxShadow: "0 0 0 8px rgba(var(--axon-cyan),0)" },
        },
        "slide-up": {
          "0%":   { transform: "translateY(8px)", opacity: "0" },
          "100%": { transform: "translateY(0)",   opacity: "1" },
        },
        "fade-in": {
          "0%":   { opacity: "0" },
          "100%": { opacity: "1" },
        },
        "cursor-blink": {
          "0%, 100%": { opacity: "1" },
          "50%":      { opacity: "0" },
        },
      },
      backgroundImage: {
        "grid-pattern":
          "linear-gradient(rgba(var(--axon-cyan),0.04) 1px, transparent 1px), linear-gradient(90deg, rgba(var(--axon-cyan),0.04) 1px, transparent 1px)",
        "hero-glow":
          "radial-gradient(ellipse 80% 50% at 50% -20%, rgba(var(--axon-cyan),0.15), transparent)",
      },
      backgroundSize: {
        "grid-sm": "32px 32px",
      },
    },
  },
  plugins: [],
};

export default config;
