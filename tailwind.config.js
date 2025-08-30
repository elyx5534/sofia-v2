/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./sofia_ui/templates/**/*.html",
    "./src/**/*.py",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        primary: '#3b82f6',
        secondary: '#8b5cf6',
        success: '#10b981',
        danger: '#ef4444',
        warning: '#f59e0b',
        dark: '#0f172a'
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'float': 'float 6s ease-in-out infinite',
        'glow': 'glow 2s ease-in-out infinite alternate'
      },
      zIndex: {
        '100': '100'
      }
    }
  },
  plugins: [],
}