const key = 'bread-salpim.camera.v1';

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

export function loadStreamUrl() {
  const fallback = import.meta.env.VITE_CAMERA_STREAM_URL || (window.__BREAD_RUNTIME__?.mode === 'local' ? `http://${location.hostname}:8081/stream.mjpg` : '');
  try { return validateStreamUrl(localStorage.getItem(key) ?? fallback); }
  catch { try { return validateStreamUrl(fallback); } catch { return ''; } }
}

export function saveStreamUrl(value) {
  const url = validateStreamUrl(value);
  let persisted = false;
  try { localStorage.setItem(key, url); persisted = true; } catch { /* Current-tab settings still work. */ }
  return { url, persisted };
}
