// Shared polling connection for the optional on-Pi runtime. Firebase continues
// to use its SDK listeners; this adapter is activated only by the Pi server.
const subscribers = new Set();
const adminSubscribers = new Set();
let timer, pending = null, state = null, connected = false;
let session = { ready: false, admin: false };

function notifyAdmin(value) {
  session = value;
  adminSubscribers.forEach((callback) => callback(value));
}

export async function localRequest(path, body) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 15000);
  try {
    const response = await fetch(`/api/${path}`, {
      method: body === undefined ? 'GET' : 'POST',
      credentials: 'same-origin', cache: 'no-store', signal: controller.signal,
      ...(body === undefined ? {} : { headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }),
    });
    const value = await response.json();
    if (!response.ok) {
      if (response.status === 401 && path !== 'login') notifyAdmin({ ready: true, admin: false });
      throw new Error(value.error || '파이 요청에 실패했습니다.');
    }
    return value;
  } finally { clearTimeout(timeout); }
}

async function fetchState() {
  try {
    const next = await localRequest('state');
    for (const subscriber of subscribers) {
      const value = subscriber.key === 'connected' ? true : next[subscriber.key];
      if (JSON.stringify(value) !== subscriber.previous) {
        subscriber.previous = JSON.stringify(value);
        subscriber.callback(value);
      }
    }
    state = next;
    connected = true;
  } catch {
    connected = false;
    for (const subscriber of subscribers) {
      subscriber.previous = undefined; // Re-emit unchanged values after recovery to clear errors.
      if (subscriber.key === 'connected') subscriber.callback(false);
      else subscriber.onError?.(new Error('파이에 연결하지 못했습니다. 같은 네트워크와 파이 실행 상태를 확인해 주세요.'));
    }
  }
}

function poll() {
  if (pending) return pending;
  if (!subscribers.size) return Promise.resolve();
  pending = fetchState().finally(() => { pending = null; });
  return pending;
}

async function refreshAfterWrite() {
  if (pending) await pending;
  await poll();
}

export function subscribeLocal(key, callback, onError) {
  const subscriber = { key, callback, onError };
  subscribers.add(subscriber);
  if (key === 'connected') callback(connected);
  else if (state) {
    subscriber.previous = JSON.stringify(state[key]);
    callback(state[key]);
  }
  if (!timer) timer = setInterval(poll, 1000);
  poll();
  return () => {
    subscribers.delete(subscriber);
    if (!subscribers.size) { clearInterval(timer); timer = null; }
  };
}

export function subscribeLocalAdmin(callback) {
  adminSubscribers.add(callback);
  callback(session);
  localRequest('session').then(notifyAdmin).catch(() => notifyAdmin({ ready: true, admin: false }));
  return () => adminSubscribers.delete(callback);
}

export async function loginLocal(password) {
  await localRequest('login', { password });
  notifyAdmin(await localRequest('session'));
}

export async function logoutLocal() {
  await localRequest('logout', {});
  notifyAdmin({ ready: true, admin: false });
}

export async function saveLocalConfig(config, expectedConfig) {
  await localRequest('config', { config, expectedConfig });
  await refreshAfterWrite();
}

export async function calibrateLocal() {
  await localRequest('calibrate', { confirmEmpty: true });
  await refreshAfterWrite();
}
