import { useState } from 'react';
import { siteLayout } from '../siteLayout';
import { inventoryState, mapSlots, stateLabel } from '../slotMap';
import ProductPhoto from './ProductPhoto';

export default function StudentView({ config, status, health, loading, error, connected, selectedId, onSelect, onCamera, inventoryEnabled = false, isSample = false }) {
  const [filter, setFilter] = useState('all');
  const slots = mapSlots(config || siteLayout);
  const selected = slots.find((slot) => slot.id === selectedId) || slots[0];
  const stocked = slots.filter((slot) => status?.slots?.[slot.id]?.in_stock === true).length;
  const visible = filter === 'stock' ? slots.filter((slot) => status?.slots?.[slot.id]?.in_stock === true) : slots;
  const item = status?.slots?.[selected?.id];
  const selectedState = inventoryState(item);
  const columns = Math.max(1, ...slots.map((slot) => slot.column));

  return <section className="page student-map" aria-labelledby="slotsTitle">
    <div className="hero"><div><div className="eyebrow">SCHOOL BREAD STATION</div><h1 id="slotsTitle">우리 학교 빵 자판기, 한눈에 보기 🥐</h1><p>{inventoryEnabled ? '궁금한 칸을 선택하고 상품 사진과 재고를 확인하세요. 실시간 카메라는 상세 화면에서 볼 수 있어요.' : '궁금한 슬롯을 선택한 다음, 실시간 카메라에서 빵이 남아 있는지 직접 확인해요.'}</p></div><span className="hero-note">📍 학교 자판기 · {slots.length}칸</span></div>
    {isSample && <div className="alert demo-notice"><strong>샘플로 둘러보는 중이에요.</strong> 합성 사진을 사용하며 실제 자판기 재고가 아닙니다.</div>}
    {health?.message && <div className={`alert ${health.error ? 'error' : ''}`} role="status">{health.message}</div>}
    {error && <div className="alert error" role="alert">{error}</div>}
    {inventoryEnabled && !connected && <div className="alert" role="status">재고 연결을 확인하고 있습니다. 표시된 마지막 정보는 현재 재고와 다를 수 있습니다.</div>}
    <div className="map-layout">
      <article className="panel map-panel">
        <div className="section-head"><div className="head-title"><span className="head-icon green" aria-hidden="true">▦</span><div><h2>자판기 슬롯 지도</h2><p>확인하고 싶은 칸을 터치하거나 클릭하세요.</p></div></div><span className="tag">{inventoryEnabled ? `재고 있음 ${stocked} / ${slots.length}` : '위치 안내용 · 재고는 영상에서 확인'}</span></div>
        {inventoryEnabled && <div className="stock-toolbar"><div className="filter-group" aria-label="재고 필터"><button className={filter === 'all' ? 'selected' : ''} aria-pressed={filter === 'all'} onClick={() => setFilter('all')}>전체 보기</button><button className={filter === 'stock' ? 'selected' : ''} aria-pressed={filter === 'stock'} onClick={() => setFilter('stock')}>재고 있는 칸</button></div><span>{status?.updated_at ? `마지막 판별 ${status.updated_at} (한국 시간)` : '재고 판별 대기 중'}</span></div>}
        <div className="map-stage"><div className="machine-shell"><div className="machine-top"><strong>BREAD STATION</strong><span>SELECT A SLOT</span></div>
          <div className="slot-scroller" role="region" aria-label="자판기 슬롯 지도"><div className="slot-grid" style={{ '--cols': columns }} role="group" aria-label="자판기 칸 선택">
            {loading ? <p className="map-empty" role="status">자판기 정보를 불러오고 있어요…</p> : visible.length ? visible.map((slot) => {
              const product = status?.slots?.[slot.id];
              const state = inventoryState(product);
              return <button type="button" className={`slot slot-card ${state}`} key={slot.id} aria-label={`${slot.label} ${slot.name} 선택`} aria-pressed={selected?.id === slot.id} onClick={() => onSelect(slot.id)}>
                <span className="slot-label">{slot.label}</span><span className="map-slot-photo">{inventoryEnabled ? <ProductPhoto source={product?.thumbnail} name={slot.name} /> : <span className="photo-waiting" aria-hidden="true">▤</span>}</span><strong>{slot.name}</strong><span className={`map-stock ${state}`}>{inventoryEnabled ? stateLabel[state] : selected?.id === slot.id ? '선택됨' : '위치 선택'}</span>
              </button>;
            }) : <p className="map-empty">현재 재고가 확인된 칸이 없어요.</p>}
          </div></div><div className="machine-base" /></div><div className="map-footer"><span className="legend"><i className="legend-square" />선택한 칸</span><span>{config ? '설정된 칸 위치 기준' : '기본 슬롯 배치'}</span></div></div>
        <p className="map-footnote">{inventoryEnabled ? 'ⓘ 수량 대신 칸이 비었는지 확인해요. 촬영 이후 상품이 판매될 수 있습니다.' : 'ⓘ 이 지도는 위치 안내용입니다. 실제 빵과 재고는 실시간 영상에서 직접 확인하세요.'}</p>
      </article>
      <aside className="map-sidebar"><article className="panel selected-panel" aria-live="polite"><div className="overline">SELECTED SLOT / 선택한 칸</div><div className="selected-number">{selected?.label || '—'}</div><h3>{selected?.name || '칸을 선택해 주세요'}</h3>
        {inventoryEnabled && <><span className={`availability ${selectedState}`}>{stateLabel[selectedState]}</span><div className="selected-photo"><ProductPhoto source={item?.thumbnail} name={selected?.name || '선택한 칸'} /></div></>}
        <p>{selected ? `${selected.row}행 · ${selected.column}열 위치입니다. ` : ''}{inventoryEnabled ? '상품 사진을 확인하거나 실시간 카메라에서 직접 살펴보세요.' : '실시간 카메라 화면에서 같은 위치를 찾아 남아 있는 빵을 직접 확인하세요.'}</p>
        <div className="selection-actions"><button className="btn primary" onClick={onCamera}>실시간 카메라에서 확인 →</button><span className="minor">카메라 상세를 열 때 영상에 연결하고, 지도로 돌아오면 연결을 멈춥니다.</span></div>
      </article><article className="panel help-panel"><h3>🧭 이렇게 이용해요</h3><div className="help-list"><div className="help-item"><b>01</b> 지도에서 궁금한 칸 선택</div><div className="help-item"><b>02</b> {inventoryEnabled ? '상품 사진과 재고 확인' : '실시간 카메라 열기'}</div><div className="help-item"><b>03</b> {inventoryEnabled ? '필요하면 실시간 카메라 열기' : '선택한 위치에서 빵 직접 확인'}</div></div></article></aside>
    </div>
  </section>;
}
