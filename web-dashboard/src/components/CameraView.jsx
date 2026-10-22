import { useEffect, useRef, useState } from 'react';
import { freshMockData } from '../mockData';
import { inventoryState, mapSlots, stateLabel } from '../slotMap';
import { saveStreamUrl } from '../cameraConnection';
import { inventoryEnabled } from '../firebase';

const fallback = freshMockData().config;

export default function CameraView({ config, status, selectedId, streamUrl, onStreamUrl, onBack }) {
  const selected = mapSlots(config || fallback).find((slot) => slot.id === selectedId) || mapSlots(config || fallback)[0];
  const [attempt, setAttempt] = useState(0);
  const [state, setState] = useState('offline');
  const [dimensions, setDimensions] = useState(null);
  const [health, setHealth] = useState(null);
  const [draft, setDraft] = useState(streamUrl);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const image = useRef(null);
  const viewport = useRef(null);
  const dialog = useRef(null);

  useEffect(() => {
    setDimensions(null); setState(streamUrl ? 'waiting' : 'offline');
    const target = image.current;
    if (!streamUrl || !target) return;
    target.src = streamUrl;
    const timer = setInterval(() => {
      if (target.naturalWidth > 0) {
        setDimensions({ width: target.naturalWidth, height: target.naturalHeight });
        setState((previous) => previous === 'error' ? previous : 'online');
      }
    }, 500);
    return () => { clearInterval(timer); target.src = 'data:,'; target.removeAttribute('src'); };
  }, [streamUrl, attempt]);

  useEffect(() => {
    setHealth(null);
    if (!streamUrl || !new URL(streamUrl).pathname.endsWith('/stream.mjpg')) return;
    const url = new URL('/api/health', streamUrl).href;
    let active = true, controller;
    async function poll() {
      controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 2500);
      try {
        const response = await fetch(url, { signal: controller.signal, cache: 'no-store', credentials: 'omit' });
        if (response.ok) {
          const value = await response.json();
          if (active && typeof value.live === 'boolean') setHealth(value);
        }
      } catch { /* Standard MJPEG providers may not expose this optional API. */ }
      finally { clearTimeout(timeout); }
    }
    poll(); const timer = setInterval(poll, 3000);
    return () => { active = false; clearInterval(timer); controller?.abort(); };
  }, [streamUrl, attempt]);

  function openSettings() { setDraft(streamUrl); setError(''); dialog.current.showModal(); }
  function save(event) {
    event.preventDefault();
    try {
      const result = saveStreamUrl(draft);
      onStreamUrl(result.url); setAttempt((value) => value + 1);
      setNotice(result.persisted ? '이 브라우저에 영상 주소를 저장했습니다.' : '현재 창에 영상 주소를 적용했습니다.');
      dialog.current.close();
    } catch (cause) { setError(cause.message || '영상 주소를 확인해 주세요.'); }
  }
  async function fullscreen() {
    try { await viewport.current.requestFullscreen(); }
    catch { setNotice('이 브라우저에서는 전체 화면을 사용할 수 없습니다.'); }
  }

  return <section className="page" aria-labelledby="cameraTitle">
    <div className="hero"><div><div className="eyebrow">LIVE CAMERA / DETAIL VIEW</div><h1 id="cameraTitle">실시간 자판기 카메라 📷</h1><p>영상에서 원하는 빵이 남아 있는지 직접 확인하세요.</p></div><span className="hero-note">FHD 우선 · 목표 60 FPS</span></div>
    <div className="camera-layout"><article className="panel camera-panel">
      <div className="section-head"><div className="head-title"><span className="head-icon" aria-hidden="true">◉</span><div><h2>자판기 실시간 화면</h2><p>MJPEG 영상 · 카메라가 지원하는 실제 속도로 표시됩니다.</p></div></div><span className="mode-pill">{state === 'online' ? '영상 표시 중' : state === 'error' ? '연결 오류' : state === 'waiting' ? '연결 중' : '연결 대기'}</span></div>
      <div ref={viewport} className={`viewport ${streamUrl ? 'is-streaming' : ''} ${state === 'error' ? 'has-error' : ''}`} aria-label="자판기 실시간 영상">
        {!streamUrl && <div className="camera-placeholder"><span aria-hidden="true">🍞</span><strong>카메라 연결을 준비하고 있어요</strong><p>공개 HTTPS 영상 주소를 연결하면 실제 영상이 표시됩니다.</p><small>현재 실제 카메라 영상은 재생되지 않습니다.</small></div>}
        {streamUrl && <img className="live-img" ref={image} alt="학교 자판기 실시간 카메라 영상" onError={() => { setState('error'); setDimensions(null); }} />}
        <div className="video-ribbon" role="status"><span className={`dot ${state === 'online' ? 'on' : state === 'error' ? 'fail' : 'wait'}`} />{state === 'online' ? `영상 표시 중 · ${dimensions?.width} × ${dimensions?.height}` : state === 'error' ? '영상 연결이 끊겼습니다' : state === 'waiting' ? '영상에 연결하고 있습니다…' : '공개 영상 주소 미설정'}</div>
        {state === 'error' && <div className="overlay-error" role="alert">영상 주소 또는 파이 연결 상태를 확인한 뒤 다시 연결하세요.</div>}
      </div>
      <div className="action-row"><button className="btn primary" onClick={openSettings}>⚙ 영상 연결 설정</button><button className="btn" onClick={() => streamUrl ? setAttempt((value) => value + 1) : openSettings()}>↻ 다시 연결</button><span className="spacer" /><button className="btn" onClick={fullscreen}>⛶ 전체 화면</button></div>
      {dimensions && (dimensions.width !== 1920 || dimensions.height !== 1080) && <div className="alert" role="status">실제 영상은 {dimensions.width} × {dimensions.height}입니다. FHD 지원 여부와 파이의 카메라 설정을 확인하세요.</div>}
      {notice && <p className="stream-note" role="status">{notice}</p>}
      {health && <p className="stream-note" role="status">{health.sample ? '합성 테스트 영상 · 실제 카메라 아님 · ' : ''}{health.live ? `카메라 처리 출력 ${health.fps} FPS · 목표 ${health.target_fps} FPS` : '카메라의 새 프레임을 기다리고 있습니다.'}</p>}
      <p className="stream-note">영상은 상세 화면에서만 연결됩니다. 화질·FPS 변경은 파이의 관리자용 카메라 설정 화면에서 적용합니다.</p>
    </article><aside className="camera-side"><article className="panel camera-info"><span className="overline">YOUR SELECTED SLOT</span><span className="info-badge">선택한 위치 <strong>{selected?.label || '—'}</strong></span><h3>{selected?.name || '선택한 칸'}</h3><p>{selected ? `${selected.row}행 · ${selected.column}열 위치를 영상에서 찾아보세요.` : '슬롯 지도에서 칸을 선택해 주세요.'}</p>{inventoryEnabled && <span className={`availability ${inventoryState(status?.slots?.[selected?.id])}`}>{stateLabel[inventoryState(status?.slots?.[selected?.id])]}</span>}<p className="minor">슬롯 위치를 영상에서 찾아 실제 상품을 확인하세요. 촬영과 네트워크 지연으로 현재 상태와 차이가 있을 수 있습니다.</p><button className="btn linklike" onClick={onBack}>← 슬롯 지도로 돌아가기</button></article><div className="camera-hint"><strong>💡 카메라 사용 안내</strong>지도로 돌아가면 영상 연결을 종료해 불필요한 데이터 사용을 줄입니다. 실제 FPS와 선명도는 카메라·조명·네트워크에 따라 달라집니다.</div></aside></div>
    <dialog ref={dialog} aria-labelledby="stream-dialog-title"><form className="dialog-content" onSubmit={save}><div className="dialog-head"><div><h2 id="stream-dialog-title">영상 연결 설정</h2><p>이 브라우저에서 사용할 영상 주소입니다.</p></div><button className="close" type="button" aria-label="설정 닫기" onClick={() => dialog.current.close()}>×</button></div><div className="field"><label htmlFor="stream-url">MJPEG 스트리밍 HTTPS 주소</label><input id="stream-url" type="url" value={draft} onChange={(event) => setDraft(event.target.value)} placeholder="https://camera.example.org/stream.mjpg" spellCheck="false" /><small>공개 영상 주소만 입력하세요. 비밀번호나 API 토큰을 포함하지 마세요.</small></div>{error && <p className="validation" role="alert">{error}</p>}<div className="dialog-actions"><button className="btn" type="button" onClick={() => setDraft('')}>주소 지우기</button><button className="btn primary" type="submit">설정 저장</button></div></form></dialog>
  </section>;
}
