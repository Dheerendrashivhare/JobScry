/** @type {import('tailwindcss').Config} */
module.exports = {
  // Class strategy so the toolbar toggle can flip themes without a reload.
  darkMode: 'class',
  content: ['./src/**/*.{html,ts}'],
  theme: {
    extend: {},
  },
  // Angular Material ships its own reset; Tailwind's preflight would fight it.
  corePlugins: { preflight: false },
  plugins: [],
};
