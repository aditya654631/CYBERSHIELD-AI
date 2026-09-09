/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        cyber: {
          bg: '#060913',
          card: '#0c1222',
          cardHover: '#111a33',
          border: '#1b2a4a',
          cyan: '#00d8ff',
          blue: '#2563eb',
          purple: '#8b5cf6',
          critical: '#ef4444',
          high: '#f59e0b',
          medium: '#3b82f6',
          safe: '#10b981',
          textMuted: '#94a3b8',
        }
      },
      animation: {
        'pulse-subtle': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'glow-cyan': 'glowCyan 2s ease-in-out infinite alternate',
      },
      keyframes: {
        glowCyan: {
          '0%': { boxShadow: '0 0 5px rgba(0, 216, 255, 0.2)' },
          '100%': { boxShadow: '0 0 20px rgba(0, 216, 255, 0.6)' },
        }
      }
    },
  },
  plugins: [],
}
