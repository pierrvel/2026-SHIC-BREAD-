import { initializeApp } from 'firebase/app';
import { getDatabase, onValue, ref, runTransaction } from 'firebase/database';
import { getAuth, onIdTokenChanged, signInWithEmailAndPassword, signOut } from 'firebase/auth';
import { freshMockData, MOCK_STORAGE_KEY, simulateThreshold } from './mockData';
import { stableStringify, validateConfig } from './config';
import { subscribeLocal, subscribeLocalAdmin, loginLocal, logoutLocal, saveLocalConfig, calibrateLocal, localRequest } from './local';

const env = import.meta.env;
export const isLocal = window.__BREAD_RUNTIME__?.mode === 'local';
export const isMock = !isLocal && (env.VITE_MOCK_MODE === 'true' || (env.DEV && env.VITE_MOCK_MODE !== 'false' && !env.VITE_FIREBASE_API_KEY));
export const isSample = isMock || (isLocal && window.__BREAD_RUNTIME__.sample === true);
const firebaseKeys = ['API_KEY', 'AUTH_DOMAIN', 'DATABASE_URL', 'PROJECT_ID', 'APP_ID'];
export const inventoryEnabled = isLocal || isMock || firebaseKeys.some((key) => !!env[`VITE_FIREBASE_${key}`]);
let database;
let auth;
let initializationError;

if (!isMock && !isLocal && inventoryEnabled) {
  if (firebaseKeys.some((key) => !env[`VITE_FIREBASE_${key}`])) {
    initializationError = new Error('재고 서비스 연결을 준비하고 있습니다. 잠시 후 다시 확인해 주세요.');
  } else {
    try {
      const app = initializeApp({
        apiKey: env.VITE_FIREBASE_API_KEY,
        authDomain: env.VITE_FIREBASE_AUTH_DOMAIN,
        databaseURL: env.VITE_FIREBASE_DATABASE_URL,
        projectId: env.VITE_FIREBASE_PROJECT_ID,
        appId: env.VITE_FIREBASE_APP_ID,
      });
      database = getDatabase(app);
      auth = getAuth(app);
    } catch {
      initializationError = new Error('Firebase 초기화에 실패했습니다. 프로젝트 설정을 확인해 주세요.');
    }
  }
}

let mockMemory = freshMockData();
let mockStorageAvailable = true;
const mockListeners = new Set();

function readMock() {
  if (!mockStorageAvailable) return structuredClone(mockMemory);
  try {
    const stored = localStorage.getItem(MOCK_STORAGE_KEY);
    if (stored) {
      const data = JSON.parse(stored);
      validateConfig(data.config);
      if (data.status && data.status.slots) return data;
    }
  } catch {
    // HTML previews can have an opaque origin and deny localStorage entirely.
    mockStorageAvailable = false;
  }
  return structuredClone(mockMemory);
}

function notifyMock() { mockListeners.forEach((listener) => listener()); }
if (isMock) window.addEventListener('storage', (event) => {
  if (event.key === MOCK_STORAGE_KEY || event.key === null) notifyMock();
});

export function subscribeNode(path, callback, onError) {
  if (!['config', 'status'].includes(path)) throw new Error('Unsupported database path');
  if (isLocal) return subscribeLocal(path, callback, onError);
  if (!inventoryEnabled) { callback(null); return () => {}; }
  if (isMock) {
    const listener = () => callback(readMock()[path]);
    mockListeners.add(listener);
    listener();
    return () => mockListeners.delete(listener);
  }
  if (initializationError) {
    onError?.(initializationError);
    return () => {};
  }
  return onValue(ref(database, path), (snapshot) => callback(snapshot.val()), () => {
    onError?.(new Error('데이터를 읽지 못했습니다. 연결 상태와 DB 권한을 확인해 주세요.'));
  });
}

export function subscribeConnection(callback) {
  if (isLocal) return subscribeLocal('connected', callback);
  if (!inventoryEnabled) { callback(false); return () => {}; }
  if (isMock) { callback(true); return () => {}; }
  if (initializationError) { callback(false); return () => {}; }
  return onValue(ref(database, '.info/connected'), (snapshot) => callback(snapshot.val() === true), () => callback(false));
}

export async function saveConfig(config, expectedConfig) {
  validateConfig(config);
  if (isLocal) return saveLocalConfig(config, expectedConfig);
  const conflict = '다른 관리자가 설정을 변경했습니다. 최신 설정을 불러온 뒤 다시 저장해 주세요.';
  if (isMock) {
    const data = readMock();
    if (stableStringify(data.config) !== stableStringify(expectedConfig)) throw new Error(conflict);
    data.config = structuredClone(config);
    simulateThreshold(data);
    let persisted = false;
    if (mockStorageAvailable) {
      try {
        localStorage.setItem(MOCK_STORAGE_KEY, JSON.stringify(data));
        persisted = true;
      } catch {
        mockStorageAvailable = false;
      }
    }
    mockMemory = data;
    notifyMock();
    return { persisted };
  }
  if (initializationError) throw initializationError;
  if (!auth.currentUser || !(await auth.currentUser.getIdTokenResult()).claims.admin) {
    throw new Error('관리자 계정으로 로그인해 주세요.');
  }
  const result = await runTransaction(ref(database, 'config'), (current) => {
    if (stableStringify(current) !== stableStringify(expectedConfig)) return undefined;
    return config;
  }, { applyLocally: false });
  if (!result.committed) throw new Error(conflict);
}

export function subscribeAdmin(callback) {
  if (isLocal) return subscribeLocalAdmin(callback);
  if (!inventoryEnabled) { callback({ ready: true, admin: false }); return () => {}; }
  if (isMock) { callback({ ready: true, admin: true, email: '로컬 데모 관리자' }); return () => {}; }
  if (initializationError) { callback({ ready: true, admin: false }); return () => {}; }
  let sequence = 0;
  const unsubscribe = onIdTokenChanged(auth, async (user) => {
    const current = ++sequence;
    try {
      const token = user ? await user.getIdTokenResult() : null;
      if (current === sequence) callback({ ready: true, admin: token?.claims.admin === true, email: user?.email });
    } catch {
      if (current === sequence) callback({ ready: true, admin: false });
    }
  });
  return () => { sequence += 1; unsubscribe(); };
}

export async function login(email, password) {
  if (isLocal) return loginLocal(password);
  if (initializationError) throw initializationError;
  await signInWithEmailAndPassword(auth, email, password);
}
export async function logout() {
  if (isLocal) return logoutLocal();
  if (auth) await signOut(auth);
}

export function subscribeHealth(callback) {
  if (isLocal) return subscribeLocal('meta', callback);
  callback(null);
  return () => {};
}

export async function calibrateEmpty() {
  if (!isLocal) throw new Error('파이 로컬 실행 모드에서 사용할 수 있습니다.');
  return calibrateLocal();
}

export async function captureNow() {
  if (!isLocal) throw new Error('파이 로컬 실행 모드에서 사용할 수 있습니다.');
  return localRequest('capture', {});
}

export function resetMock() {
  if (!isMock) return;
  try { localStorage.removeItem(MOCK_STORAGE_KEY); }
  catch { mockStorageAvailable = false; }
  mockMemory = freshMockData();
  notifyMock();
}
