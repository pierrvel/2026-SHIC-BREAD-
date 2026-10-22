import { useEffect, useState } from 'react';
import StudentView from './components/StudentView';
import AdminView from './components/AdminView';
import CameraView from './components/CameraView';
import { loadStreamUrl } from './cameraConnection';
import { isLocal, isSample, inventoryEnabled } from './firebase';
import { useVending } from './useVending';

export default function App() {
  const readView = () => ['camera', ...(inventoryEnabled ? ['admin'] : [])].includes(location.hash.slice(1)) ? location.hash.slice(1) : 'slots';
  const [view, setView] = useState(readView);
  const [selectedId, setSelectedId] = useState('slot_1');
  const [streamUrl, setStreamUrl] = useState(loadStreamUrl);
  const data = useVending();
  useEffect(() => { const update = () => setView(readView()); window.addEventListener('hashchange', update); return () => window.removeEventListener('hashchange', update); }, []);
  useEffect(() => { document.title = `빵살핌 | ${view === 'camera' ? '실시간 카메라' : view === 'admin' ? '관리자' : '자판기 슬롯 지도'}`; }, [view]);
  const navigate = (next) => { location.hash = next; setView(next); window.scrollTo(0, 0); };
  return <div className="app bread-site">
    <header className="top">
      <a className="brand" href="#slots" onClick={(event) => { event.preventDefault(); navigate('slots'); }} aria-label="빵살핌 슬롯 지도 홈"><span className="brandmark" aria-hidden="true">🍞</span><span><b>빵살핌</b><small>BREAD CAM</small></span></a>
      <nav className="top-nav" aria-label="화면 선택"><button aria-current={view === 'slots' ? 'page' : undefined} onClick={() => navigate('slots')}><span aria-hidden="true">▦</span> 슬롯 지도</button><button aria-current={view === 'camera' ? 'page' : undefined} onClick={() => navigate('camera')}><span aria-hidden="true">◉</span> 실시간 카메라</button>{inventoryEnabled && <button aria-current={view === 'admin' ? 'page' : undefined} onClick={() => navigate('admin')}>관리자</button>}</nav>
      <span className="header-status"><span className={`dot ${data.connected ? 'on' : inventoryEnabled ? 'wait' : ''}`} />{!inventoryEnabled ? '영상은 상세에서 확인' : isLocal ? (isSample ? '파이 샘플 모드' : '파이 카메라 모드') : isSample ? '샘플 모드' : data.connected ? '재고 연결됨' : '재고 연결 대기'}</span>
    </header>
    <main>{view === 'slots' ? <StudentView {...data} selectedId={selectedId} onSelect={setSelectedId} onCamera={() => navigate('camera')} /> : view === 'camera' ? <CameraView {...data} selectedId={selectedId} streamUrl={streamUrl} onStreamUrl={setStreamUrl} onBack={() => navigate('slots')} /> : <div className="admin-site"><AdminView {...data} /></div>}</main>
    <footer className="bread-footer"><span><strong>빵살핌</strong> · 우리의 쉬는 시간을 위한 작은 프로젝트</span><span>학교 자판기 · 슬롯 지도 · 실시간 카메라</span></footer>
  </div>;
}
