import type { Config } from "tailwindcss";

// Theme is driven by CSS variables in tokens.css; Tailwind just maps a few of
// them so utility classes (bg-surface-1, text-muted, …) stay in sync with the
// single source of theme truth.
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "var(--bg)",
        "surface-1": "var(--surface-1)",
        "surface-2": "var(--surface-2)",
        border: "var(--border)",
        "border-strong": "var(--border-strong)",
        hairline: "var(--hairline)",
        text: "var(--text)",
        muted: "var(--text-muted)",
        faint: "var(--text-faint)",
        accent: "var(--accent)",
        win: "var(--win)",
        loss: "var(--loss)",
        warn: "var(--warn)",
        info: "var(--info)",
      },
      fontFamily: {
        display: "var(--font-display)",
        body: "var(--font-body)",
        mono: "var(--font-mono)",
      },
      borderRadius: {
        DEFAULT: "var(--radius)",
        sm: "var(--radius-sm)",
        lg: "var(--radius-lg)",
      },
      maxWidth: {
        content: "var(--maxw)",
      },
    },
  },
  plugins: [],
} satisfies Config;
