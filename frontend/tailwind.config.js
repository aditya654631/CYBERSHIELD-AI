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
        gov: {
          bg: '#F6F8FC',
          surface: '#FFFFFF',
          surfaceMuted: '#EFF6FF',
          border: '#DCE5F0',
          borderDark: '#CBD5E1',
          navy: '#173A63',
          navyLight: '#1E4A7D',
          navyMuted: '#475569',
          blue: '#2563EB',
          blueHover: '#1D4ED8',
          blueSubtle: '#EFF6FF',
          critical: '#DC2626',
          criticalBg: '#FEF2F2',
          criticalBorder: '#FECACA',
          warning: '#D97706',
          warningBg: '#FFFBEB',
          warningBorder: '#FDE68A',
          success: '#16A34A',
          successBg: '#F0FDF4',
          successBorder: '#BBF7D0',
          info: '#2563EB',
          infoBg: '#EFF6FF',
          infoBorder: '#BFDBFE',
          textPrimary: '#1E293B',
          textSecondary: '#64748B',
          textMuted: '#94A3B8',
        },
        // Backward-compatibility aliases mapped to restrained palette
        cyber: {
          bg: '#F6F8FC',
          card: '#FFFFFF',
          cardHover: '#F8FAFC',
          border: '#DCE5F0',
          cyan: '#0284C7',
          blue: '#2563EB',
          purple: '#6366F1',
          critical: '#DC2626',
          high: '#D97706',
          medium: '#2563EB',
          safe: '#16A34A',
          textMuted: '#64748B',
        }
      },
      boxShadow: {
        'gov-sm': '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
        'gov': '0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px -1px rgba(0, 0, 0, 0.1)',
        'gov-md': '0 4px 6px -1px rgba(0, 0, 0, 0.08), 0 2px 4px -2px rgba(0, 0, 0, 0.05)',
        'gov-lg': '0 10px 15px -3px rgba(0, 0, 0, 0.08), 0 4px 6px -4px rgba(0, 0, 0, 0.03)',
      },
      borderRadius: {
        'gov-sm': '6px',
        'gov': '8px',
        'gov-lg': '12px',
      }
    },
  },
  plugins: [],
}
