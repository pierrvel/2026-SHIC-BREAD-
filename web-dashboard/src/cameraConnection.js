const key = 'jaebbangso.camera.v1';
const legacyKeys = ['bread-salpim.camera.v1', 'breadCamStudentDashboard.v2'];

export function validateStreamUrl(value) {
  const text = value.trim();
  if (!text) return '';
  const url = new URL(text);
  const local = ['localhost', '127.0.0.1', '[::1]'].includes(url.hostname);
  const lan = window.__BREAD_RUNTIME__?.mode === 'local' && location.protocol === 'http:';
  if (url.username || url.password || !(url.protocol === 'https:' || (url.protocol === 'http:' && (lan || (local && location.protocol !== 'https:'))))) {
    throw new Error('공개 사이트에서는 비밀번호가 포함되지 않은 HTTPS 영상 주소를 입력해 주세요.');
  }
  return url.href;
}

export function defaultStreamUrl() {
  const fallback = import.meta.env.VITE_CAMERA_STREAM_URL || (window.__BREAD_RUNTIME__?.mode === 'local' ? `http://${location.hostname}:8081/stream.mjpg` : '');
  try { return validateStreamUrl(fallback); } catch { return ''; }
}

export function loadStreamUrl() {
  for (const storedKey of [key, ...legacyKeys]) {
    try {
      const value = localStorage.getItem(storedKey);
      if (value === null) continue;
      const url = storedKey === 'breadCamStudentDashboard.v2' ? JSON.parse(value).url : value;
      if (typeof url === 'string') return validateStreamUrl(url);
    } catch { /* Reject malformed legacy settings and tolerate blocked storage. */ }
  }
  return defaultStreamUrl();
}

export function saveStreamUrl(value) {
  const url = validateStreamUrl(value);
  let persisted = false;
  try { localStorage.setItem(key, url); persisted = true; } catch { /* Current-tab settings still work. */ }
  return { url, persisted };
}

export function resetStreamUrl() {
  let persisted = false;
  try {
    [key, ...legacyKeys].forEach((storedKey) => localStorage.removeItem(storedKey));
    persisted = true;
  } catch { /* The deployed URL still applies in this tab. */ }
  return { url: defaultStreamUrl(), persisted };
}
