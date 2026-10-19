/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        diff: {
          add: '#22c55e',
          addBg: '#dcfce7',
          remove: '#ef4444',
          removeBg: '#fee2e2',
          unchanged: '#6b7280',
        },
      },
    },
  },
  plugins: [],
};
