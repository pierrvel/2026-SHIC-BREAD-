import { useEffect, useRef, useState } from 'react';
import { isMock, login, logout, resetMock, saveConfig, subscribeAdmin } from '../firebase';
import { stableStringify, validateConfig } from '../config';
import { freshMockData } from '../mockData';
import sampleVendingPhoto from '../assets/sample_vending.jpg';

export default function AdminView({ config, loading, error: dataError }) {
  const [session, setSession] = useState({ ready: false, admin: false });
  const [draft, setDraft] = useState(null);
  const [baseline, setBaseline] = useState(null);
  const [selectedId, setSelectedId] = useState('slot_1');
  const [preview, setPreview] = useState(isMock ? sampleVendingPhoto : null);
  const [dimensions, setDimensions] = useState(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const uploadUrl = useRef(null);
  const dirty = !!draft && stableStringify(draft) !== stableStringify(baseline);
  const remoteChanged = baseline && stableStringify(config) !== stableStringify(baseline);

  useEffect(() => subscribeAdmin(setSession), []);
  useEffect(() => () => { if (uploadUrl.current) URL.revokeObjectURL(uploadUrl.current); }, []);
  useEffect(() => {
    if (!dirty) {
      setDraft(config ? structuredClone(config) : null);
      setBaseline(config ? structuredClone(config) : null);
    }
  }, [config, dirty]);

  function loadLatest() {
    setDraft(structuredClone(config));
    setBaseline(structuredClone(config));
    setError(''); setMessage('최신 설정을 불러왔습니다.');
  }

  async function submit(event) {
    event.preventDefault();
    setError(''); setMessage('');
    try {
      if (!dimensions) throw new Error('촬영 해상도의 전체 사진을 먼저 불러와 주세요.');
      validateConfig(draft, dimensions);
      setBusy(true);
      const result = await saveConfig(draft, baseline);
      setBaseline(structuredClone(draft));
      setMessage(isMock ? (result?.persisted
        ? '이 브라우저에 저장했습니다. 샘플 점수에 새 기준값을 적용했습니다.'
        : '이 미리보기에 적용했습니다. 브라우저 저장소를 사용할 수 없어 창을 닫으면 초기화됩니다.')
        : '설정이 저장되었습니다. 파이가 다음 촬영 주기에 새 설정을 적용합니다.');
    } catch (cause) {
      setError(cause.code ? '저장에 실패했습니다. 네트워크와 관리자 쓰기 권한을 확인해 주세요.' : cause.message);
    } finally { setBusy(false); }
  }

  function saveClick(event) {
    // Some HTML viewers allow scripts but block native form submission before
    // onSubmit fires. Keep native validation and handle the save from the click.
    event.preventDefault();
    if (event.currentTarget.form.reportValidity()) submit(event);
  }

  async function signIn(event) {
    event.preventDefault();
    setBusy(true); setError('');
    try { await login(email, password); setPassword(''); }
    catch { setError('로그인에 실패했습니다. 계정 정보와 로그인 제공자 설정을 확인해 주세요.'); }
    finally { setBusy(false); }
  }

  function changePhoto(event) {
    const file = event.target.files?.[0];
    if (!file) return;
    if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type) || file.size > 10 * 1024 * 1024) {
      setError('10MB 이하의 JPG, PNG, WebP 사진을 선택해 주세요.'); return;
    }
    if (uploadUrl.current) URL.revokeObjectURL(uploadUrl.current);
    uploadUrl.current = URL.createObjectURL(file);
    setPreview(uploadUrl.current); setDimensions(null); setError('');
  }

  function updateSlot(key, value) {
    setMessage('');
    setDraft((old) => ({ ...old, slots: { ...old.slots, [selectedId]: { ...old.slots[selectedId], [key]: value } } }));
  }

  function exportConfig() {
    try {
      validateConfig(draft, dimensions);
      const url = URL.createObjectURL(new Blob([JSON.stringify(draft, null, 2)], { type: 'application/json' }));
      const link = document.createElement('a'); link.href = url; link.download = 'vending-config.json'; link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (cause) { setError(cause.message); }
  }

  if (!session.ready) return <div className="empty-state">관리자 권한을 확인하는 중…</div>;
  if (!session.admin) return <section className="login-panel">
    <div className="section-kicker">ADMIN ACCESS</div><h1>관리자 로그인</h1>
    <p>칸 위치와 판별 기준값은 관리자 계정으로 수정할 수 있어요.</p>
    {session.email && <div className="alert">이 계정에는 관리자 권한이 없습니다. 담당자에게 권한을 요청해 주세요.</div>}
    {error && <div className="alert error" role="alert">{error}</div>}
    <form onSubmit={signIn} className="login-form">
      <label>이메일<input type="email" autoComplete="username" required value={email} onChange={(event) => setEmail(event.target.value)} /></label>
      <label>비밀번호<input type="password" autoComplete="current-password" required value={password} onChange={(event) => setPassword(event.target.value)} /></label>
      <button className="primary-button" disabled={busy}>{busy ? '로그인 중…' : '로그인'}</button>
    </form>
    {session.email && <button className="text-button" onClick={() => logout().catch(() => setError('로그아웃에 실패했습니다.'))}>현재 계정 로그아웃</button>}
  </section>;

  const selected = draft?.slots?.[selectedId];
  return <section className="admin-view">
    <div className="admin-heading"><div><div className="section-kicker">MACHINE SETTINGS</div><h1>자판기 설정</h1><p>사진 위에서 칸을 선택하고, 촬영 원본 기준의 좌표를 입력하세요.</p></div>
      <div className="admin-account"><span>{session.email}</span>{!isMock && <button className="text-button" onClick={() => logout().catch(() => setError('로그아웃에 실패했습니다.'))}>로그아웃</button>}</div></div>
    {isMock && <div className="demo-notice"><span className="notice-symbol">i</span><p>로컬 데모 설정입니다. 기준값은 샘플 점수에 적용되며, ROI 변경에 따른 사진 재분석은 Python에서 실행하세요.</p></div>}
    {(error || dataError) && <div className="alert error" role="alert">{error || dataError}</div>}
    {message && <div className="alert success" role="status">{message}</div>}
    {remoteChanged && dirty && <div className="alert">새 원격 설정이 있습니다. 현재 편집 내용과 충돌할 수 있습니다. <button type="button" className="text-button" onClick={loadLatest}>최신 설정 불러오기</button></div>}
    {loading ? <div className="empty-state">설정을 불러오는 중…</div> : !draft ? <div className="empty-state">
      <p>DB에 초기 설정이 없습니다. 기본 6칸 설정을 만든 뒤 실제 촬영 사진에 맞춰 조정하세요.</p>
      <button className="primary-button" onClick={() => { setDraft(freshMockData().config); setBaseline(null); }}>기본 설정 만들기</button>
    </div> : <form onSubmit={submit}>
      <div className="admin-layout"><div className="editor-photo-panel">
        <div className="panel-heading"><h2>칸 위치 미리보기</h2><label className="upload-button">사진 불러오기<input type="file" accept="image/jpeg,image/png,image/webp" onChange={changePhoto} /></label></div>
        <div className="roi-preview">
          {preview ? <>
            <img src={preview} alt="자판기 전체 사진과 칸별 선택 영역" onLoad={(event) => setDimensions({ width: event.currentTarget.naturalWidth, height: event.currentTarget.naturalHeight })} onError={() => { setDimensions(null); setError('사진을 읽지 못했습니다. 다른 사진을 선택해 주세요.'); }} />
            {dimensions && <svg viewBox={`0 0 ${dimensions.width} ${dimensions.height}`} aria-label="칸 선택 영역">
              {Object.entries(draft.slots).map(([id, slot]) => <g key={id} role="button" tabIndex={0} aria-label={`${slot.name} 선택`} aria-pressed={selectedId === id} onClick={() => setSelectedId(id)} onKeyDown={(event) => { if (['Enter', ' '].includes(event.key)) { event.preventDefault(); setSelectedId(id); } }}>
                <rect x={slot.x} y={slot.y} width={Math.max(0, slot.w || 0)} height={Math.max(0, slot.h || 0)} className={selectedId === id ? 'roi selected-roi' : 'roi'} />
                <text x={slot.x + 8} y={slot.y + 24} fontSize={Math.max(14, dimensions.width / 36)} fill="white" paintOrder="stroke" stroke="#174a38" strokeWidth="3">{slot.name}</text>
              </g>)}
            </svg>}
          </> : <div className="empty-photo">현장 카메라로 촬영한 전체 사진을 불러오세요.</div>}
        </div>
        <p className="photo-caption">{dimensions ? `원본 ${dimensions.width} × ${dimensions.height}px · ` : ''}사진은 이 기기에서만 사용되며 DB에 업로드되지 않습니다.</p>
      </div>
      <div className="editor-controls"><div className="panel-heading"><h2>판별 설정</h2><span className="edited-badge">{dirty ? '저장 전' : '저장됨'}</span></div>
        <label>편집할 칸<select value={selectedId} onChange={(event) => setSelectedId(event.target.value)}>{Object.entries(draft.slots).map(([id, slot]) => <option key={id} value={id}>{slot.name}</option>)}</select></label>
        {selected ? <>
          <label>칸 이름<input value={selected.name} maxLength={60} required onChange={(event) => updateSlot('name', event.target.value)} /></label>
          <div className="coordinate-grid">{[['x', 'X 좌표'], ['y', 'Y 좌표'], ['w', '너비 (W)'], ['h', '높이 (H)']].map(([key, label]) => <label key={key}>{label}<div className="input-unit"><input type="number" min={['w', 'h'].includes(key) ? 1 : 0} max="8192" step="1" required value={selected[key] ?? ''} onChange={(event) => updateSlot(key, event.target.value === '' ? '' : Number(event.target.value))} /><span>px</span></div></label>)}</div>
        </> : <p>편집할 칸을 선택해 주세요.</p>}
        <div className="threshold-field"><label>재고 판별 기준값 <span>{draft.threshold}</span><input type="range" min="0" max="255" step="1" value={draft.threshold} onChange={(event) => { setMessage(''); setDraft({ ...draft, threshold: Number(event.target.value) }); }} /></label><p>빈 칸 대비 평균 채도 차이가 이 값보다 크면 재고 있음으로 판별합니다.</p></div>
        <button type="submit" className="primary-button" disabled={busy || !dirty} onClick={saveClick}>{busy ? '저장 중…' : '설정 저장하기'}</button>
        <button type="button" className="secondary-button" onClick={exportConfig}>설정 JSON 내려받기</button>
        {dirty && <button type="button" className="text-button" onClick={loadLatest}>편집 취소 · 최신 설정 불러오기</button>}
      </div></div>
    </form>}
    {isMock && <button type="button" className="text-button reset-demo" onClick={() => { resetMock(); setDraft(null); setBaseline(null); setError(''); setMessage('샘플 설정을 초기화했습니다.'); }}>데모 설정 초기화</button>}
  </section>;
}
