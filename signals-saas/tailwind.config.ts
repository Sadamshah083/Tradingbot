import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#0b1020",
        panel: "#121a2d",
        panel2: "#151e34",
        line: "#233049",
        muted: "#8c98b3",
        teal: { DEFAULT: "#2dd4bf", dark: "#14b8a6" },
        danger: "#f87171",
        amber: "#fbbf24",
      },
      fontFamily: { sans: ["Inter", "ui-sans-serif", "system-ui", "Segoe UI", "sans-serif"], mono: ["JetBrains Mono", "ui-monospace", "Consolas", "monospace"] },
      boxShadow: { card: "0 20px 60px rgba(0,0,0,.45)" },
    },
  },
  plugins: [],
};
export default config;
