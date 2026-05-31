/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        offwhite: {
          50:  '#FDFCFA',
          100: '#F8F5F0',
          200: '#F0EBE3',
          300: '#E5DDD3',
          400: '#D6CABF',
        },
        brand: {
          50:   '#FEF0ED',
          100:  '#FDE0D9',
          200:  '#FAB9AA',
          300:  '#F68F7A',
          400:  '#F06650',
          500:  '#DE3919',
          600:  '#C23015',
          700:  '#A02810',
          800:  '#7D1F0C',
          900:  '#5C1608',
          950:  '#3A0D04',
        },
        warm: {
          50:  '#FAFAF9',
          100: '#F5F5F4',
          200: '#E7E5E4',
          300: '#D6D3D1',
          400: '#A8A29E',
          500: '#78716C',
          600: '#57534E',
          700: '#44403C',
          800: '#292524',
          900: '#1C1917',
          950: '#0C0A09',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      boxShadow: {
        soft: '0 1px 3px 0 rgb(0 0 0 / 0.06), 0 1px 2px -1px rgb(0 0 0 / 0.06)',
        card: '0 4px 6px -1px rgb(0 0 0 / 0.07), 0 2px 4px -2px rgb(0 0 0 / 0.07)',
        elevated: '0 10px 15px -3px rgb(0 0 0 / 0.08), 0 4px 6px -4px rgb(0 0 0 / 0.08)',
      },
      borderRadius: {
        xl: '0.75rem',
        '2xl': '1rem',
        '3xl': '1.5rem',
      },
    },
  },
  plugins: [],
}
