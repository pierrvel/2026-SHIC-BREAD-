import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import { inlinePreviewAssets } from './scripts/inline-preview-plugin.mjs';

// The desktop app opens HTML files without a Vite server. Bundle everything,
// including the administrator's full-frame image, into a portable demo file.
// Live Firebase configuration must never influence this offline demo artifact.
export default defineConfig({
  base: './',
  publicDir: false,
  envDir: false,
  envPrefix: 'BREAD_PREVIEW_',
  define: {
    'import.meta.env': JSON.stringify({
      VITE_MOCK_MODE: 'true', MODE: 'preview', PROD: true, DEV: false, BASE_URL: './',
    }),
  },
  plugins: [react(), tailwindcss(), inlinePreviewAssets()],
  build: {
    outDir: 'dist-preview',
    assetsInlineLimit: Number.MAX_SAFE_INTEGER,
    cssCodeSplit: false,
    modulePreload: false,
    rollupOptions: { output: { inlineDynamicImports: true } },
  },
});
