import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./lib/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        ink: "#07111f",
        "ink-soft": "#52617a",
        "synapse-blue": "#2563eb",
        "synapse-red": "#ff4655",
        "surface-subtle": "#f4f7fb",
      },
      boxShadow: {
        "soft-card": "0 18px 60px rgba(15, 23, 42, 0.08)",
      },
    },
  },
  plugins: [],
};

export default config;
