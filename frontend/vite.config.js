import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  base: './',
  plugins: [
    react(),
    {
      name: 'interview-app-entry',
      transformIndexHtml: {
        order: 'pre',
        handler(html) {
          return html
            .replace('<html lang="en">', '<html lang="en" data-vite-app>')
            .replace('<!-- VITE_APP_ENTRY -->', '<script type="module" src="/src/main.jsx"></script>');
        },
      },
    },
  ],
  server: { host: '127.0.0.1', port: 5173, strictPort: true },
});
