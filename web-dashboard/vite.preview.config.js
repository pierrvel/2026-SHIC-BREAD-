import { defineConfig } from 'vite';
import { inlinePreviewAssets } from './scripts/inline-preview-plugin.mjs';

// Portable copy of the real storefront. An absent camera stays disconnected.
export default defineConfig({
  base: './',
  publicDir: false,
  envDir: false,
  envPrefix: 'BREAD_PREVIEW_',
  define: {
    'import.meta.env.VITE_MOCK_MODE': JSON.stringify('false'),
    'import.meta.env.VITE_CAMERA_STREAM_URL': JSON.stringify(''),
  },
  plugins: [{
    name: 'offline-system-fonts',
    transformIndexHtml: { order: 'pre', handler: (html) => html.replace(/<link\b[^>]*href="https:\/\/fonts\.[^"]*"[^>]*>/g, '') },
  }, inlinePreviewAssets()],
  build: {
    outDir: 'dist-preview',
    assetsInlineLimit: Number.MAX_SAFE_INTEGER,
    cssCodeSplit: false,
    modulePreload: false,
    rollupOptions: { output: { inlineDynamicImports: true } },
  },
});
