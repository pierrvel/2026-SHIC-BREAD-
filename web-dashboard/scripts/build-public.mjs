import { readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';
import { loadEnv } from 'vite';

const root = fileURLToPath(new URL('../', import.meta.url));
const env = { ...loadEnv('production', root, 'VITE_'), ...process.env, VITE_MOCK_MODE: 'false' };
if (process.argv[2]) {
  const config = JSON.parse(await readFile(process.argv[2], 'utf8'));
  if (config.private_key || config.type === 'service_account') throw new Error('Use public Firebase web configuration, never a service account key.');
  for (const [field, name] of Object.entries({ apiKey: 'API_KEY', authDomain: 'AUTH_DOMAIN', projectId: 'PROJECT_ID', appId: 'APP_ID', databaseURL: 'DATABASE_URL' })) {
    if (config[field]) env[`VITE_FIREBASE_${name}`] = config[field];
  }
}
const keys = ['API_KEY', 'AUTH_DOMAIN', 'PROJECT_ID', 'APP_ID', 'DATABASE_URL'];
const inventory = keys.some((key) => !!env[`VITE_FIREBASE_${key}`]);
const missing = keys.filter((key) => !env[`VITE_FIREBASE_${key}`]);
if (inventory && missing.length) throw new Error(`Partial inventory configuration. Missing: ${missing.join(', ')}. Set all public Firebase fields or leave all empty for CCTV-only mode.`);
if (inventory) {
  if (env.VITE_FIREBASE_PROJECT_ID !== 'bread-notificator') throw new Error('The inventory project must match .firebaserc: bread-notificator.');
  const db = new URL(env.VITE_FIREBASE_DATABASE_URL);
  if (db.protocol !== 'https:' || !['firebaseio.com', 'firebasedatabase.app'].some((host) => db.hostname.endsWith('.' + host))) throw new Error('Use the HTTPS Realtime Database URL from the Firebase console.');
}
if (env.VITE_CAMERA_STREAM_URL) {
  const url = new URL(env.VITE_CAMERA_STREAM_URL);
  if (url.protocol !== 'https:' || url.username || url.password) throw new Error('Public camera URL must use HTTPS and contain no credentials.');
}
console.log(`Building Cloudflare Pages site with mock mode disabled; ${inventory ? 'Firebase inventory enabled' : 'slot map and CCTV mode'}.`);
if (!env.VITE_CAMERA_STREAM_URL) console.log('Public camera URL is not configured; viewers can enter an address in the camera page.');
const result = spawnSync('npm', ['run', 'build'], { cwd: root, env, stdio: 'inherit' });
if (result.status === 0) await writeFile(new URL('../dist/public-build.json', import.meta.url), JSON.stringify({ hosting: 'cloudflare-pages', mockMode: false, inventoryEnabled: inventory, cameraConfigured: !!env.VITE_CAMERA_STREAM_URL }));
process.exit(result.status ?? 1);
