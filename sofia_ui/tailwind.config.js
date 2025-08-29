/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./templates/**/*.html",
    "./static/**/*.{js,css}",
    "../src/**/*.{ts,tsx,js,jsx,html}",
    "../**/*.jinja",
    "./**/*.py"
  ],
  safelist: [
    // Purple brand color safelist
    'bg-brand-50', 'bg-brand-100', 'bg-brand-200', 'bg-brand-300', 'bg-brand-400',
    'bg-brand-500', 'bg-brand-600', 'bg-brand-700', 'bg-brand-800', 'bg-brand-900',
    'text-brand-50', 'text-brand-100', 'text-brand-200', 'text-brand-300', 'text-brand-400',
    'text-brand-500', 'text-brand-600', 'text-brand-700', 'text-brand-800', 'text-brand-900',
    'border-brand-50', 'border-brand-100', 'border-brand-200', 'border-brand-300', 'border-brand-400',
    'border-brand-500', 'border-brand-600', 'border-brand-700', 'border-brand-800', 'border-brand-900',
    'hover:bg-brand-500', 'hover:bg-brand-600', 'hover:bg-brand-700',
    'focus:ring-brand-400', 'focus:ring-brand-500', 'focus:border-brand-500',
    // Trading specific colors
    'text-price-up', 'text-price-down', 'bg-price-up', 'bg-price-down'
  ],
  theme: {
    extend: {
      colors: {
        // Sofia V2 Purple Brand Colors (Mor Tema)
        brand: {
          50: '#faf5ff',
          100: '#f3e8ff',
          200: '#e9d5ff',
          300: '#d8b4fe',
          400: '#c084fc',
          500: '#a855f7',
          600: '#9333ea',
          700: '#7c3aed',
          800: '#6b21a8',
          900: '#581c87',
        },
        primary: {
          50: '#faf5ff',
          100: '#f3e8ff', 
          500: '#a855f7',
          600: '#9333ea',
          700: '#7c3aed',
          900: '#581c87',
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