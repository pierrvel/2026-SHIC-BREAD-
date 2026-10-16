import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: { rollupOptions: { output: { manualChunks(id) {
    if (id.includes('/node_modules/@firebase/') || id.includes('/node_modules/firebase/')) return 'firebase';
    if (id.includes('/node_modules/react')) return 'react';
  } } } },
});
