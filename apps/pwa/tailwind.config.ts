import type { Config } from 'tailwindcss';

const config: Config = {
  darkMode: 'class',
  content: ['./app/**/*.{ts,tsx}', './components/**/*.{ts,tsx}', './lib/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // Primary palette is keyed to the active theme via CSS variables in
        // app/globals.css. Light = Classic Light blue (#2563eb), Dark =
        // Midnight Dark violet (#8b5cf6). Numbered shades remain static for
        // surfaces/borders that need a fixed tone.
        primary: {
          DEFAULT: 'var(--primary)',
          hover: 'var(--primary-hover)',
          soft: 'var(--primary-soft)',
          50: '#EEF2FF',
          100: '#E0E7FF',
          200: '#C7D2FE',
          500: '#6366F1',
          600: 'var(--primary)',
          700: 'var(--primary-hover)',
          900: '#1E1B4B',
        },
        // Theme-aware semantic tokens (use via bg-surface, text-fg, etc.).
        bg: 'var(--bg)',
        surface: {
          DEFAULT: 'var(--surface)',
          2: 'var(--surface-2)',
          hover: 'var(--surface-hover)',
        },
        fg: {
          DEFAULT: 'var(--text)',
          muted: 'var(--text-muted)',
          subtle: 'var(--text-subtle)',
        },
        accent: 'var(--accent)',
        urgent: { DEFAULT: '#EF4444', light: '#FEE2E2', dark: '#B91C1C' },
        success: { DEFAULT: '#10B981', light: '#D1FAE5' },
        warning: { DEFAULT: '#F59E0B', light: '#FEF3C7' },
      },
      fontFamily: {
        sans: ['var(--font-inter)', 'system-ui', 'sans-serif'],
      },
      animation: {
        'slide-in-right': 'slideInRight 0.3s ease-out',
        'fade-in': 'fadeIn 0.2s ease-out',
        'pulse-urgent': 'pulseUrgent 2s cubic-bezier(0.4, 0, 0.6, 1) infinite',
      },
      keyframes: {
        slideInRight: {
          '0%': { transform: 'translateX(100%)', opacity: '0' },
          '100%': { transform: 'translateX(0)', opacity: '1' },
        },
        fadeIn: {
          '0%': { opacity: '0', transform: 'translateY(4px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        pulseUrgent: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.6' },
        },
      },
    },
  },
  plugins: [],
};
export default config;
