import { loadStreamUrl, saveStreamUrl, resetStreamUrl } from './cameraConnection';

const $ = (selector) => document.querySelector(selector);
const glass = $('#glass'), dialog = $('#settingsDialog'), pauseButton = $('#pauseBtn');
let image = $('#liveImg');
let streamUrl = loadStreamUrl();
let state = 'idle', autoPaused = false, connection = 0;
let frameTimer, slowTimer, timeoutTimer, healthTimer, swingTimer, controller;
let dimensions = null, health = null;
const signs = {
  idle: ['개업 준비중', '카메라 연결 전'], connecting: ['준비중', '영상 불러오는 중'],
  live: ['영업중', '지금 보고 있어요'], paused: ['잠시 외출', '영상을 멈춰 뒀어요'],
  error: ['잠깐 쉬어요', '영상이 끊겼어요'],
};
const shades = {
  idle: ['아직 개업 전이에요', '카메라 영상 주소가 연결되면 이 창문으로 자판기 앞이 보여요.', '카메라 설정', 'settings'],
  paused: ['잠시 외출 중이에요', '데이터를 아끼려고 영상을 멈춰 뒀어요.', '다시 보기', 'resume'],
  error: ['창문이 잠깐 흐려졌어요', '영상을 불러오지 못했어요. 잠시 뒤에 다시 연결해 주세요.', '다시 연결', 'retry'],
};
const pauseIcon = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><rect x="6" y="5" width="4" height="14" rx="1"/><rect x="14" y="5" width="4" height="14" rx="1"/></svg>';
const playIcon = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M7 5v14l11-7Z"/></svg>';

function notice(message = '') {
  $('#connectionNotice').textContent = message;
  $('#connectionNotice').hidden = !message;
}
function showDetails() {
  const details = [];
  if (dimensions) details.push(`영상 ${dimensions.width} × ${dimensions.height}`);
  if (health && Number.isFinite(health.fps)) details.push(`카메라 처리 출력 ${health.fps} FPS`);
  if (health && Number.isFinite(health.target_fps)) details.push(`목표 ${health.target_fps} FPS`);
  if (health?.sample) details.push('합성 테스트 영상 · 실제 카메라 아님');
  $('#cameraDetails').hidden = details.length === 0;
  $('#cameraDetails').textContent = details.join(' · ');
  $('#sampleBadge').hidden = health?.sample !== true;
  if (state === 'live' && health?.sample) {
    $('#signTitle').textContent = '테스트중';
    $('#signSub').textContent = '합성 영상이에요';
  }
}
function setState(next) {
  const changed = next !== state;
  state = next;
  glass.dataset.state = next;
  if (next !== 'live') glass.style.aspectRatio = '';
  const [title, subtitle] = signs[next];
  $('#signTitle').textContent = title;
  $('#signSub').textContent = subtitle;
  if (changed) {
    clearTimeout(swingTimer);
    $('#signBoard').classList.add('swing');
    swingTimer = setTimeout(() => $('#signBoard').classList.remove('swing'), 260);
  }
  const shade = shades[next];
  if (shade) {
    $('#shadeTitle').textContent = shade[0]; $('#shadeText').textContent = shade[1];
    $('#shadeBtn').textContent = shade[2]; $('#shadeBtn').dataset.action = shade[3];
  }
  if (next === 'connecting') $('#dimText').textContent = '영상 불러오는 중…';
  pauseButton.disabled = next === 'idle' || next === 'error';
  pauseButton.innerHTML = next === 'paused' ? playIcon + '다시 보기' : pauseIcon + '잠깐 멈추기';
  showDetails();
}
function stopStream() {
  connection += 1;
  clearInterval(frameTimer); clearInterval(healthTimer);
  clearTimeout(slowTimer); clearTimeout(timeoutTimer);
  controller?.abort();
  image.onload = null; image.onerror = null;
  // Replacing src first cancels an in-flight MJPEG request in Chromium too.
  image.src = 'data:,';
  image.removeAttribute('src');
}
function fail(message = '') {
  stopStream();
  dimensions = null;
  setState('error');
  notice(message);
}
function connect() {
  stopStream();
  autoPaused = false; health = null; dimensions = null; notice();
  if (!streamUrl) { setState('idle'); return; }
  if (document.hidden) { autoPaused = true; setState('paused'); return; }
  // A new image cannot report the previous connection's cached naturalWidth.
  const fresh = image.cloneNode(false);
  image.replaceWith(fresh); image = fresh;
  const current = connection;
  setState('connecting');
  function firstFrame() {
    if (current !== connection || !image.naturalWidth || !image.naturalHeight) return;
    dimensions = { width: image.naturalWidth, height: image.naturalHeight };
    clearTimeout(slowTimer); clearTimeout(timeoutTimer);
    if (state !== 'live') setState('live');
    glass.style.aspectRatio = `${dimensions.width} / ${dimensions.height}`;
    showDetails();
  }
  image.onload = firstFrame;
  image.onerror = () => { if (current === connection) fail(); };
  image.src = streamUrl;
  frameTimer = setInterval(firstFrame, 500);
  slowTimer = setTimeout(() => {
    if (current === connection && state === 'connecting') {
      $('#dimText').textContent = '응답이 조금 늦어요… 계속 연결하는 중';
      $('#signSub').textContent = '조금만 기다려 주세요';
    }
  }, 12000);
  timeoutTimer = setTimeout(() => {
    if (current === connection && state === 'connecting') fail('카메라가 응답하지 않아요. 다시 연결하거나 영상 주소를 확인해 주세요.');
  }, 30000);

  // Our Pi endpoint reports capture freshness; other MJPEG servers need no API.
  if (!new URL(streamUrl).pathname.endsWith('/stream.mjpg')) return;
  let supported = false, missed = 0, stale = 0, version;
  async function checkHealth() {
    const requestController = new AbortController();
    controller = requestController;
    const timeout = setTimeout(() => requestController.abort(), 2500);
    try {
      const response = await fetch(new URL('/api/health', streamUrl), { signal: requestController.signal, cache: 'no-store', credentials: 'omit' });
      if (!response.ok) throw new Error('health unavailable');
      const value = await response.json();
      if (current !== connection || typeof value.live !== 'boolean') return;
      supported = true; missed = 0; health = value;
      if (version !== undefined && value.stream_version !== undefined && version !== value.stream_version) { connect(); return; }
      version = value.stream_version;
      stale = value.live ? 0 : stale + 1;
      if (stale >= 2) { fail('카메라의 새 영상이 도착하지 않아요. 파이 연결을 확인한 뒤 다시 연결해 주세요.'); return; }
      showDetails();
    } catch {
      if (current === connection && supported && ++missed >= 2) fail('카메라와 연결이 끊겼어요. 잠시 뒤에 다시 연결해 주세요.');
    } finally { clearTimeout(timeout); }
  }
  checkHealth(); healthTimer = setInterval(checkHealth, 3000);
}
function pause(automatic = false) {
  stopStream(); autoPaused = automatic; setState('paused');
}
function openSettings() {
  $('#streamUrl').value = streamUrl; $('#validation').textContent = '';
  if (!dialog.open) dialog.showModal();
}
$('#shadeBtn').addEventListener('click', () => $('#shadeBtn').dataset.action === 'settings' ? openSettings() : connect());
$('#refreshBtn').addEventListener('click', () => streamUrl ? connect() : openSettings());
pauseButton.addEventListener('click', () => state === 'paused' ? connect() : pause());
document.addEventListener('visibilitychange', () => {
  if (document.hidden && (state === 'live' || state === 'connecting')) pause(true);
  else if (!document.hidden && autoPaused && state === 'paused') connect();
});
window.addEventListener('pagehide', () => {
  if (state === 'live' || state === 'connecting') pause(true);
  else stopStream();
});
window.addEventListener('pageshow', () => { if (!document.hidden && autoPaused && state === 'paused') connect(); });
$('#fullscreenBtn').addEventListener('click', async () => {
  try {
    if (document.fullscreenElement) await document.exitFullscreen();
    else if (glass.requestFullscreen) await glass.requestFullscreen();
    else notice('이 브라우저에서는 크게 보기를 지원하지 않아요.');
  } catch { notice('크게 보기로 전환할 수 없어요. 브라우저에서 다시 시도해 주세요.'); }
});
document.addEventListener('fullscreenchange', () => {
  $('#fullscreenLabel').textContent = document.fullscreenElement ? '작게 보기' : '크게 보기';
});
document.querySelectorAll('[data-open-settings]').forEach((button) => button.addEventListener('click', openSettings));
$('#closeDialog').addEventListener('click', () => dialog.close());
dialog.addEventListener('click', (event) => { if (event.target === dialog) dialog.close(); });
function saveSettings(event) {
  event.preventDefault();
  try {
    const result = saveStreamUrl($('#streamUrl').value);
    streamUrl = result.url; dialog.close(); connect();
    if (!result.persisted) notice('브라우저에 주소를 저장할 수 없어 현재 창에만 적용했어요.');
  } catch { $('#validation').textContent = '유효한 HTTPS 주소를 입력해 주세요. 비밀번호나 API 토큰을 포함하지 마세요.'; }
}
$('#settingsForm').addEventListener('submit', saveSettings);
// Sandboxed file previews can run scripts while blocking native form submits.
$('#settingsForm button[type="submit"]').addEventListener('click', saveSettings);
$('#streamUrl').addEventListener('keydown', (event) => { if (event.key === 'Enter') saveSettings(event); });
$('#clearBtn').addEventListener('click', () => {
  const result = resetStreamUrl(); streamUrl = result.url;
  dialog.close(); connect();
  if (!result.persisted) notice('현재 창에서 기본 주소로 돌아왔어요. 이 브라우저에서는 저장소를 사용할 수 없어요.');
});
setState('idle'); connect();
