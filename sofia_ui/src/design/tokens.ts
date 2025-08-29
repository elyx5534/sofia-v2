/**
 * Design System Tokens for Sofia V2
 * Centralized design tokens for consistent UI
 */

export const spacing = {
  4: '0.25rem',   // 4px
  8: '0.5rem',    // 8px
  12: '0.75rem',  // 12px
  16: '1rem',     // 16px
  20: '1.25rem',  // 20px
  24: '1.5rem',   // 24px
  32: '2rem',     // 32px
} as const;

export const radius = {
  8: '0.5rem',    // 8px
  12: '0.75rem',  // 12px
  16: '1rem',     // 16px
} as const;

export const zIndex = {
  10: 10,  // Base elements
  20: 20,  // Overlays
  30: 30,  // Modals
  40: 40,  // Toasts
  50: 50,  // Top-level
} as const;

export const container = {
  max: '1200px',  // Max container width
  padding: spacing[16],
} as const;

export const colors = {
  background: '#0f172a',  // Dark background
  foreground: '#f8fafc',  // Light text
  primary: '#3b82f6',     // Blue
  secondary: '#8b5cf6',   // Purple
  success: '#10b981',     // Green
  warning: '#f59e0b',     // Yellow
  error: '#ef4444',       // Red
  muted: '#64748b',       // Gray
} as const;

export const typography = {
  fontFamily: {
    sans: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
    mono: 'ui-monospace, SFMono-Regular, "SF Mono", Menlo, Monaco, Consolas, monospace',
  },
  fontSize: {
    xs: '0.75rem',
    sm: '0.875rem',
    base: '1rem',
    lg: '1.125rem',
    xl: '1.25rem',
    '2xl': '1.5rem',
    '3xl': '1.875rem',
  },
  fontWeight: {
    normal: 400,
    medium: 500,
    semibold: 600,
    bold: 700,
  },
  lineHeight: {
    tight: 1.25,
    normal: 1.5,
    relaxed: 1.75,
  },
} as const;

export const animation = {
  duration: {
    fast: '150ms',
    normal: '300ms',
    slow: '500ms',
  },
  easing: {
    ease: 'cubic-bezier(0.4, 0, 0.2, 1)',
    easeIn: 'cubic-bezier(0.4, 0, 1, 1)',
    easeOut: 'cubic-bezier(0, 0, 0.2, 1)',
    easeInOut: 'cubic-bezier(0.4, 0, 0.2, 1)',
  },
} as const;

export const breakpoints = {
  sm: '640px',
  md: '768px',
  lg: '1024px',
  xl: '1280px',
  '2xl': '1536px',
} as const;