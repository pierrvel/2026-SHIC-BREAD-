import { useState } from 'react';
import StudentView from './components/StudentView';
import AdminView from './components/AdminView';
import { isMock } from './firebase';
import { useVending } from './useVending';

export default function App() {
  const [view, setView] = useState('student');
  const data = useVending();
  return <div className="app-shell">
    <header className="site-header"><div className="header-inner">
      <a className="brand" href="#" onClick={(event) => { event.preventDefault(); setView('student'); }} aria-label="쉬는빵 학생 화면"><span className="brand-icon" aria-hidden="true">♧</span><span>쉬는빵<small>SCHOOL BREAD CLUB</small></span></a>
      <nav aria-label="화면 선택"><button className={view === 'student' ? 'active' : ''} aria-current={view === 'student' ? 'page' : undefined} onClick={() => setView('student')}>재고 확인</button><button className={view === 'admin' ? 'active' : ''} aria-current={view === 'admin' ? 'page' : undefined} onClick={() => setView('admin')}>관리자</button></nav>
      <span className={`header-status ${data.connected ? 'connected' : ''}`}><span className={`connection-dot ${data.connected ? 'online' : ''}`} />{isMock ? '데모 모드' : data.connected ? 'DB 연결됨' : '연결 확인 중'}</span>
    </div></header>
    <main className="main-content">{view === 'student' ? <StudentView {...data} /> : <AdminView {...data} />}</main>
    <footer className="site-footer"><div><span className="footer-brand">쉬는빵</span><span>우리의 쉬는 시간을 위한 작은 프로젝트.</span></div><span>MADE BY SCHOOL BREAD CLUB <span aria-hidden="true">↗</span></span></footer>
  </div>;
}
