import { readFile, rename, writeFile } from 'node:fs/promises';

const marker = '<!-- Generated offline demo: npm --prefix web-dashboard run build:preview -->';
const target = new URL('../../index.html', import.meta.url);
const source = new URL('../dist-preview/index.html', import.meta.url);

try {
  const previous = await readFile(target, 'utf8');
  if (!previous.startsWith(marker)) {
    throw new Error('Root index.html is not a generated preview; preserving the existing user file.');
  }
} catch (error) {
  if (error.code !== 'ENOENT') throw error;
}

const html = await readFile(source, 'utf8');
if (/<script\b[^>]*\bsrc\s*=|<link\b[^>]*\brel=["']stylesheet/i.test(html)) {
  throw new Error('Preview still requires external scripts or styles.');
}
const temporary = new URL('../../index.html.tmp', import.meta.url);
await writeFile(temporary, `${marker}\n${html}`, 'utf8');
await rename(temporary, target);
console.log('Created standalone demo: /workspace/2026-SHIC-BREAD-/index.html');
