/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./index.html",
    "./src/**/*.{ts,tsx,js,jsx,html}",
    "./sofia_ui/templates/**/*.html",
    "./sofia_ui/**/*.jinja",
    "./src/**/*.py"
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#faf5ff",
          100: "#f3e8ff", 
          200: "#e9d5ff",
          300: "#d8b4fe",
          400: "#c084fc",
          500: "#a855f7",
          600: "#9333ea",
          700: "#7e22ce",
          800: "#6b21a8",
          900: "#581c87"
        },
        surface: "#0f0b1a",
        text: "#e6edf3", 
        muted: "#9aa4b2"
      },
      borderRadius: {
        '2xl': '16px'
      }
    }
  },
  safelist: [
    {
      pattern: /(bg|text|ring|from|to|via)-(brand)-(50|100|200|300|400|500|600|700|800|900)/
    },
    {
      pattern: /(hover:bg|focus:ring)-(brand)-(400|500|600|700)/
    }
  ],
  plugins: []
}