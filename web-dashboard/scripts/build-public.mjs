import { writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';
import { loadEnv } from 'vite';

const root = fileURLToPath(new URL('../', import.meta.url));
const env = { ...loadEnv('camera', root, 'VITE_'), ...process.env, VITE_MOCK_MODE: 'false' };
if (process.argv.length > 2) throw new Error('The public camera site needs no Firebase configuration file. Set VITE_CAMERA_STREAM_URL instead.');
if (env.VITE_CAMERA_STREAM_URL) {
  const url = new URL(env.VITE_CAMERA_STREAM_URL);
  if (url.protocol !== 'https:' || url.username || url.password) throw new Error('Public camera URL must use HTTPS and contain no credentials.');
}
console.log('Building the camera-only Cloudflare Pages site: no Firebase, inventory, or mock data.');
if (!env.VITE_CAMERA_STREAM_URL) console.log('Public camera URL is not configured; viewers can enter an address in the camera page.');
const result = spawnSync('npm', ['run', 'build', '--', '--mode', 'camera'], { cwd: root, env, stdio: 'inherit' });
if (result.status === 0) await writeFile(new URL('../dist/public-build.json', import.meta.url), JSON.stringify({ hosting: 'cloudflare-pages', mode: 'camera', mockMode: false, inventoryEnabled: false, cameraConfigured: !!env.VITE_CAMERA_STREAM_URL }));
process.exit(result.status ?? 1);
