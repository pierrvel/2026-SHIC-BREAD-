import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig(({ mode }) => ({
  plugins: [react(), tailwindcss(), {
    name: 'public-camera-entry',
    transformIndexHtml: {
      order: 'pre',
      handler(html) {
        return mode === 'camera' ? html.replace('/src/main.jsx', '/src/public-main.jsx') : html;
      },
    },
  }],
  build: { rollupOptions: { output: { manualChunks(id) {
    if (id.includes('/node_modules/@firebase/') || id.includes('/node_modules/firebase/')) return 'firebase';
    if (id.includes('/node_modules/react')) return 'react';
  } } } },
}));
