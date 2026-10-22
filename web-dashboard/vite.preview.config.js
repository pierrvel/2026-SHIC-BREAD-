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
    // Vite constructs the complete env object itself. Define individual keys so
    // the portable demo is explicitly mock even when production has no fallback.
    'import.meta.env.VITE_MOCK_MODE': JSON.stringify('true'),
    'import.meta.env.VITE_CAMERA_STREAM_URL': JSON.stringify(''),
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
