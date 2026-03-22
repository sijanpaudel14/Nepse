/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: 'class',
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        // Premium Dark Theme - Institutional Finance Aesthetic
        // Inspired by Bloomberg Terminal + Modern Fintech
        background: '#09090b',        // Near black, not pure
        foreground: '#fafafa',        // Off-white for text
        card: {
          DEFAULT: '#141416',         // Slightly lifted from bg
          hover: '#1c1c1f',           // Subtle hover state
        },
        'card-hover': '#1c1c1f',
        border: '#27272a',
        
        // Primary: Emerald with proper contrast
        primary: {
          DEFAULT: '#10b981',         // Emerald-500 (better than bright green)
          foreground: '#022c22',      // Dark emerald for text on primary
          muted: '#064e3b',           // For backgrounds
          glow: 'rgba(16, 185, 129, 0.15)',
        },
        
        // Secondary: Cool blue-gray (not default blue)
        secondary: {
          DEFAULT: '#64748b',         // Slate-500
          foreground: '#f8fafc',
        },
        
        // Accent: Teal (unique, not purple)
        accent: {
          DEFAULT: '#14b8a6',         // Teal-500
          foreground: '#042f2e',
          muted: '#115e59',
        },
        
        // Destructive: Rich crimson (not bright red)
        destructive: {
          DEFAULT: '#dc2626',         // Red-600
          foreground: '#fef2f2',
          muted: '#7f1d1d',
        },
        
        // Warning: Amber (warmer than orange)
        warning: {
          DEFAULT: '#d97706',         // Amber-600
          foreground: '#1c1917',
        },
        
        // Info: Cyan for informational
        info: {
          DEFAULT: '#06b6d4',
          foreground: '#083344',
        },
        
        // Muted: Zinc tones
        muted: {
          DEFAULT: '#3f3f46',
          foreground: '#a1a1aa',
        },
        
        // Stock-specific colors with proper contrast
        bull: {
          DEFAULT: '#10b981',         // Emerald
          muted: '#064e3b',
          text: '#d1fae5',            // Readable on dark bg
        },
        bear: {
          DEFAULT: '#ef4444',         // Red-500
          muted: '#7f1d1d',
          text: '#fecaca',            // Readable on dark bg
        },
        neutral: {
          DEFAULT: '#fbbf24',         // Amber-400
          muted: '#78350f',
          text: '#fef3c7',
        },
        
        // Surface colors for layering
        surface: {
          0: '#09090b',               // Base
          1: '#141416',               // Cards
          2: '#1c1c1f',               // Elevated
          3: '#27272a',               // Borders/dividers
        },
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'SF Mono', 'Fira Code', 'Consolas', 'monospace'],
        sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
        display: ['Inter', 'system-ui', 'sans-serif'],
      },
      fontSize: {
        'xs': ['0.75rem', { lineHeight: '1rem' }],
        'sm': ['0.875rem', { lineHeight: '1.25rem' }],
        'base': ['1rem', { lineHeight: '1.5rem' }],
        'lg': ['1.125rem', { lineHeight: '1.75rem' }],
        'xl': ['1.25rem', { lineHeight: '1.75rem' }],
        '2xl': ['1.5rem', { lineHeight: '2rem' }],
        '3xl': ['1.875rem', { lineHeight: '2.25rem' }],
        '4xl': ['2.25rem', { lineHeight: '2.5rem', letterSpacing: '-0.02em' }],
        '5xl': ['3rem', { lineHeight: '1.1', letterSpacing: '-0.02em' }],
      },
      boxShadow: {
        'glow-sm': '0 0 10px rgba(16, 185, 129, 0.2)',
        'glow-md': '0 0 20px rgba(16, 185, 129, 0.25)',
        'glow-lg': '0 0 30px rgba(16, 185, 129, 0.3)',
        'glow-red': '0 0 20px rgba(239, 68, 68, 0.25)',
        'inner-glow': 'inset 0 1px 0 0 rgba(255, 255, 255, 0.05)',
        'card': '0 1px 3px rgba(0, 0, 0, 0.3), 0 1px 2px rgba(0, 0, 0, 0.4)',
        'card-hover': '0 10px 40px rgba(0, 0, 0, 0.4)',
      },
      borderRadius: {
        'sm': '0.25rem',
        'DEFAULT': '0.5rem',
        'md': '0.625rem',
        'lg': '0.75rem',
        'xl': '1rem',
        '2xl': '1.25rem',
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'glow': 'glow 2s ease-in-out infinite alternate',
        'slide-up': 'slideUp 0.3s ease-out',
        'fade-in': 'fadeIn 0.2s ease-out',
      },
      keyframes: {
        glow: {
          '0%': { boxShadow: '0 0 5px rgba(16, 185, 129, 0.3)' },
          '100%': { boxShadow: '0 0 25px rgba(16, 185, 129, 0.5)' },
        },
        slideUp: {
          '0%': { transform: 'translateY(10px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
      },
      backgroundImage: {
        'gradient-radial': 'radial-gradient(var(--tw-gradient-stops))',
        'noise': "url(\"data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.65' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)' opacity='0.03'/%3E%3C/svg%3E\")",
      },
    },
  },
  plugins: [],
};
