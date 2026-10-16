import { after, before, beforeEach, test } from 'node:test';
import { readFile } from 'node:fs/promises';
import { assertFails, assertSucceeds, initializeTestEnvironment } from '@firebase/rules-unit-testing';
import { get, ref, remove, set, update } from 'firebase/database';

let environment;
const config = { threshold: 35, slots: { slot_1: { name: '1번 칸', x: 50, y: 50, w: 150, h: 180 } } };
const status = { updated_at: '2026-10-16 13:00:00', slots: { slot_1: { in_stock: true, hsv_score: 68.5, thumbnail: 'data:image/webp;base64,UklGRg==' } } };

before(async () => {
  if (!process.env.FIREBASE_DATABASE_EMULATOR_HOST) throw new Error('Run with firebase emulators:exec --only database. No production tests.');
  const [host, port] = process.env.FIREBASE_DATABASE_EMULATOR_HOST.split(':');
  environment = await initializeTestEnvironment({
    projectId: 'demo-school-bread',
    database: { host, port: Number(port), rules: await readFile(new URL('../../database.rules.json', import.meta.url), 'utf8') },
  });
});
beforeEach(async () => {
  await environment.clearDatabase();
  await environment.withSecurityRulesDisabled(async (context) => set(ref(context.database()), { config, status }));
});
after(async () => { await environment?.cleanup(); });

test('students can read config and status', async () => {
  const database = environment.unauthenticatedContext().database();
  await assertSucceeds(get(ref(database, 'config')));
  await assertSucceeds(get(ref(database, 'status')));
});
test('students cannot write config or status', async () => {
  const database = environment.unauthenticatedContext().database();
  await assertFails(set(ref(database, 'config'), config));
  await assertFails(set(ref(database, 'status'), status));
});
test('ordinary signed-in accounts cannot write config', async () => {
  await assertFails(update(ref(environment.authenticatedContext('student').database(), 'config'), { threshold: 20 }));
});
test('administrators can update config but cannot write browser status', async () => {
  const database = environment.authenticatedContext('admin', { admin: true }).database();
  await assertSucceeds(update(ref(database, 'config'), { threshold: 40 }));
  await assertFails(set(ref(database, 'status'), status));
});
test('malformed coordinates and schema extensions are rejected', async () => {
  const database = environment.authenticatedContext('admin', { admin: true }).database();
  for (const value of [-1, 0.5, '50', 9000]) {
    await assertFails(set(ref(database, 'config/slots/slot_1/x'), value));
  }
  await assertFails(set(ref(database, 'config/slots/slot_1/w'), 0));
  await assertFails(set(ref(database, 'config/threshold'), 256));
  await assertFails(set(ref(database, 'config/extra'), true));
  await assertFails(set(ref(database, 'config/slots/slot_1/extra'), true));
});
test('required fields and last slot cannot be deleted', async () => {
  const database = environment.authenticatedContext('admin', { admin: true }).database();
  await assertFails(remove(ref(database, 'config/slots/slot_1/name')));
  await assertFails(remove(ref(database, 'config/slots/slot_1')));
  await assertFails(remove(ref(database, 'config/threshold')));
  await assertFails(remove(ref(database, 'config')));
});
