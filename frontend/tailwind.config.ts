import type { Config } from "tailwindcss";



const config: Config = {

  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],

  theme: {

    extend: {

      colors: {

        bg: "#ffffff",

        panel: "#ffffff",

        panel2: "#f5f6f8",

        line: "#e5e7eb",

        text: "#1f2937",

        muted: "#6b7280",

        primary: "#FF7300",

        primaryDark: "#E0670A",

        success: "#16a34a",

        warning: "#f59e0b",

        danger: "#dc2626",

      },

      boxShadow: {

        glow: "0 0 24px rgba(255, 115, 0, 0.30)",

      },

    },

  },

  plugins: [],

};

export default config;

