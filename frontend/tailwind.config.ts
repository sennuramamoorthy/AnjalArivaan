import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx,js,jsx,mdx}"],
  theme: {
    extend: {
      colors: {
        // Takshashila University palette — inspired by Tamil Nadu red soil + temple gopuram
        brand: {
          50: "#fff4ec",
          100: "#ffe1cc",
          200: "#ffbe8f",
          300: "#ff9851",
          400: "#ff7a29",
          500: "#e8580a",
          600: "#c04306",
          700: "#952f07",
          800: "#6a1e04",
          900: "#3f1102",
        },
        ink: {
          50: "#f7f7f8",
          100: "#eeeef1",
          200: "#d9d9df",
          300: "#b7b7c1",
          400: "#8a8a99",
          500: "#5f5f70",
          600: "#434354",
          700: "#2e2e3c",
          800: "#1c1c27",
          900: "#0f0f16",
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "monospace"],
      },
      borderRadius: {
        xl: "0.9rem",
      },
    },
  },
  plugins: [],
};

export default config;
