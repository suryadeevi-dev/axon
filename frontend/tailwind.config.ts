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
          bg: "#08080f",
          surface: "#0f0f1a",
          border: "#1e1e2e",
          cyan: "#00d4ff",
          purple: "#7c3aed",
          green: "#00ff88",
          muted: "#4a4a6a",
          text: "#e2e2f0",
        },
      },
      fontFamily: {
        mono: ["'Geist Mono'", "ui-monospace", "SFMono-Regular", "monospace"],
        sans: ["'Inter'", "system-ui", "sans-serif"],
      },
      animation: {
        "pulse-cyan": "pulse-cyan 2s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        "slide-up": "slide-up 0.3s ease-out",
        "fade-in": "fade-in 0.2s ease-out",
        "cursor-blink": "cursor-blink 1s step-end infinite",
      },
      keyframes: {
        "pulse-cyan": {
          "0%, 100%": { opacity: "1", boxShadow: "0 0 0 0 rgba(0,212,255,0.4)" },
          "50%": { opacity: "0.8", boxShadow: "0 0 0 8px rgba(0,212,255,0)" },
        },
        "slide-up": {
          "0%": { transform: "translateY(8px)", opacity: "0" },
          "100%": { transform: "translateY(0)", opacity: "1" },
        },
        "fade-in": {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
        "cursor-blink": {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0" },
        },
      },
      backgroundImage: {
        "grid-pattern":
          "linear-gradient(rgba(0,212,255,0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(0,212,255,0.03) 1px, transparent 1px)",
        "hero-glow":
          "radial-gradient(ellipse 80% 50% at 50% -20%, rgba(0,212,255,0.15), transparent)",
      },
      backgroundSize: {
        "grid-sm": "32px 32px",
      },
    },
  },
  plugins: [],
};

export default config;
