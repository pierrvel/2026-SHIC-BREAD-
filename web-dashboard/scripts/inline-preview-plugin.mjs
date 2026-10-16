// Vite emits one JS entry and one stylesheet for the offline preview. Embed
// those generated assets so a sandboxed HTML viewer never needs a web server.
export function inlinePreviewAssets() {
  return {
    name: 'school-bread:inline-preview',
    enforce: 'post',
    generateBundle(_options, bundle) {
      const entry = bundle['index.html'];
      if (!entry || entry.type !== 'asset') throw new Error('Missing HTML preview entry');
      let html = String(entry.source);
      html = html.replace(/<script\b[^>]*\bsrc="([^"]+)"[^>]*><\/script>/g, (_tag, source) => {
        const filename = source.replace(/^\.\//, '');
        const script = bundle[filename];
        if (!script || script.type !== 'chunk') throw new Error(`Missing preview script: ${filename}`);
        delete bundle[filename];
        return `<script type="module">${script.code.replace(/<\/script/gi, '<\\/script')}</script>`;
      });
      html = html.replace(/<link\b[^>]*\brel="stylesheet"[^>]*>/g, (tag) => {
        const filename = tag.match(/\bhref="([^"]+)"/)?.[1].replace(/^\.\//, '');
        const stylesheet = bundle[filename];
        if (!stylesheet || stylesheet.type !== 'asset') throw new Error(`Missing preview stylesheet: ${filename}`);
        delete bundle[filename];
        return `<style>${String(stylesheet.source).replace(/<\/style/gi, '<\\/style')}</style>`;
      });
      entry.source = html;
    },
  };
}
