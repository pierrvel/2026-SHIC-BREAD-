import { useState } from 'react';
import { isSample } from '../firebase';

function Thumbnail({ source, name }) {
  const [failedSource, setFailedSource] = useState(null);
  const safe = typeof source === 'string' && source.startsWith('data:image/webp;base64,');
  return safe && failedSource !== source
    ? <img src={source} alt={`${name}에 놓인 상품 사진`} onError={() => setFailedSource(source)} />
    : <div className="missing-photo"><span aria-hidden="true">▧</span>사진 준비 중</div>;
}

export default function StudentView({ config, status, health, loading, error, connected }) {
  const [filter, setFilter] = useState('all');
  const slots = Object.entries(config?.slots || {}).sort(([a], [b]) => a.localeCompare(b, 'ko', { numeric: true }));
  const stocked = slots.filter(([id]) => status?.slots?.[id]?.in_stock === true).length;
  const soldOut = slots.filter(([id]) => status?.slots?.[id]?.in_stock === false).length;
  const visible = filter === 'stock' ? slots.filter(([id]) => status?.slots?.[id]?.in_stock === true) : slots;

  return <>
    <section className="hero">
      <div>
        <div className="eyebrow"><span className="small-line" /> OUR SCHOOL, LESS WAITING</div>
        <h1>헛걸음 없이,<br />쉬는 시간을 <em>더 길게.</em></h1>
        <p>지금 자판기에 어떤 빵이 있는지,<br className="mobile-break" /> 가기 전에 먼저 확인하세요.</p>
        <div className="hero-caption"><span aria-hidden="true">◷</span> 30초마다 촬영 · 변화가 있으면 재고 갱신</div>
      </div>
      <aside className="summary-card" aria-label="재고 요약">
        <div className="summary-top"><span>지금 고를 수 있는 칸</span><span className="round-arrow" aria-hidden="true">↗</span></div>
        <div className="summary-number">{loading ? '—' : stocked}<span> / {slots.length}칸</span></div>
        <div className="summary-bottom"><span className="stock-dot" /> 재고 있음 {stocked}<span className="summary-divider" /><span className="empty-dot" /> 품절 {soldOut}</div>
      </aside>
    </section>

    {isSample && <div className="demo-notice"><span className="notice-symbol">i</span><p><strong>샘플로 둘러보는 중이에요.</strong> 합성 사진을 사용한 데모이며, 실제 자판기 재고가 아닙니다.</p><span className="demo-label">DEMO</span></div>}
    {health?.message && <div className={`alert ${health.error ? 'error' : ''}`} role="status">{health.message}</div>}
    {error && <div className="alert error" role="alert">{error}</div>}
    {!connected && <div className="alert" role="status">연결이 끊겼습니다. 아래 사진은 마지막으로 수신한 정보이며, 현재 재고와 다를 수 있습니다.</div>}

    <section className="inventory" aria-labelledby="inventory-title">
      <div className="section-toolbar">
        <div><div className="section-kicker">VENDING MACHINE</div><h2 id="inventory-title">우리 학교 자판기 <span className="count-badge">{slots.length}</span></h2></div>
        <div className="filter-group" aria-label="재고 필터">
          <button className={filter === 'all' ? 'selected' : ''} aria-pressed={filter === 'all'} onClick={() => setFilter('all')}>전체 보기</button>
          <button className={filter === 'stock' ? 'selected' : ''} aria-pressed={filter === 'stock'} onClick={() => setFilter('stock')}>재고 있는 칸</button>
        </div>
      </div>
      <div className="update-row"><span className={`connection-dot ${connected ? 'online' : ''}`} /><span>{isSample ? '샘플 판별 시각' : '마지막 재고 판별'} <time>{status?.updated_at || '아직 없음'}</time> (한국 시간)</span></div>
      {loading ? <div className="empty-state" role="status">자판기 정보를 불러오고 있어요…</div>
        : slots.length === 0 ? <div className="empty-state">등록된 칸이 없습니다. 관리자 화면에서 초기 설정을 확인해 주세요.</div>
          : visible.length === 0 ? <div className="empty-state">현재 재고가 확인된 칸이 없어요. 다음 입고를 기다려 주세요.</div>
            : <div className="slot-grid">{visible.map(([id, slot]) => {
              const item = status?.slots?.[id];
              const state = typeof item?.in_stock === 'boolean' ? (item.in_stock ? 'stocked' : 'soldout') : 'unknown';
              return <article className={`slot-card ${state}`} key={id}>
                <div className="slot-photo">
                  <Thumbnail source={item?.thumbnail} name={slot.name} />
                  <span className="slot-number">{id.replace('slot_', '').padStart(2, '0')}</span>
                  {state === 'soldout' && <div className="soldout-overlay"><span>입고를 기다리고 있어요</span></div>}
                </div>
                <div className="slot-description"><div><h3>{slot.name}</h3><p>{state === 'stocked' ? '사진 속 상품을 확인하세요' : state === 'soldout' ? '현재 비어 있는 칸이에요' : '재고 정보를 기다리고 있어요'}</p></div>
                  <span className={`availability ${state}`}><span aria-hidden="true">{state === 'stocked' ? '●' : state === 'soldout' ? '×' : '?'}</span>{state === 'stocked' ? '재고 있음' : state === 'soldout' ? '품절' : '미확인'}</span></div>
              </article>;
            })}</div>}
    </section>
    <div className="student-note"><span aria-hidden="true">✳</span><p>수량 대신 칸이 비었는지 확인해요. <span>촬영 이후 상품이 판매될 수 있으니 참고해 주세요.</span></p></div>
  </>;
}
