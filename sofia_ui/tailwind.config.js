/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./templates/**/*.html",
    "./static/**/*.{js,css}",
    "../src/**/*.{ts,tsx,js,jsx,html}",
    "../**/*.jinja",
    "./**/*.py"
  ],
  theme: {
    extend: {
      colors: {
        // Sofia V2 Brand Colors
        primary: {
          50: '#eff6ff',
          100: '#dbeafe', 
          500: '#3b82f6',
          600: '#2563eb',
          700: '#1d4ed8',
          900: '#1e3a8a',
        },
        surface: {
          DEFAULT: '#ffffff',
          dark: '#111827',
          card: '#f9fafb',
          'card-dark': '#1f2937',
        },
        success: {
          DEFAULT: '#10b981',
          dark: '#059669',
        },
        danger: {
          DEFAULT: '#ef4444', 
          dark: '#dc2626',
        },
        warning: {
          DEFAULT: '#f59e0b',
          dark: '#d97706',
        }
      },
      spacing: {
        '18': '4.5rem',
        '88': '22rem',
      },
      borderRadius: {
        'xl': '0.75rem',
        '2xl': '1rem',
      },
      zIndex: {
        'modal': '1000',
        'tooltip': '1001',
        'navbar': '50',
      },
      fontFamily: {
        'mono': ['JetBrains Mono', 'Consolas', 'Monaco', 'monospace'],
      },
      boxShadow: {
        'glass': '0 8px 32px 0 rgba(31, 38, 135, 0.37)',
        'card': '0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06)',
        'card-hover': '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)',
      }
    },
  },
  plugins: [
    require('@tailwindcss/forms'),
    require('@tailwindcss/typography'),
  ],
  darkMode: 'class',
}