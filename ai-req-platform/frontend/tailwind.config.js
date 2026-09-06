import type { Config } from 'tailwindcss';

const config: Config = {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        accent: {
          DEFAULT: '#4F46E5',
          hover: '#4338CA',
          active: '#3730A3',
          on: '#FFFFFF',
        },
        success: '#16A34A',
        warn: '#D97706',
        danger: '#DC2626',
        bg: '#FAFAFA',
        surface: '#FFFFFF',
        fg: '#111827',
        muted: '#6B7280',
        meta: '#9CA3AF',
        border: '#E5E7EB',
        'surface-warm': '#F3F4F6',
      },
      fontFamily: {
        sans: ['Inter', 'Noto Sans SC', '-apple-system', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      borderRadius: {
        sm: '8px',
        md: '12px',
        lg: '16px',
        pill: '9999px',
      },
      boxShadow: {
        sm: '0 1px 2px rgba(0,0,0,0.04), 0 4px 8px rgba(0,0,0,0.06)',
        md: '0 1px 3px rgba(0,0,0,0.06), 0 4px 12px rgba(0,0,0,0.08)',
        ring: '0 0 0 1px var(--border)',
      },
      transitionDuration: {
        fast: '150ms',
        base: '200ms',
      },
      transitionTimingFunction: {
        standard: 'cubic-bezier(0.2, 0, 0, 1)',
      },
    },
  },
  plugins: [],
};

export default config;
