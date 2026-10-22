import { useState } from 'react';

export default function ProductPhoto({ source, name }) {
  const [failed, setFailed] = useState(null);
  return typeof source === 'string' && source.startsWith('data:image/webp;base64,') && failed !== source
    ? <img src={source} alt={`${name}에 놓인 상품 사진`} onError={() => setFailed(source)} />
    : <span className="photo-waiting" aria-label="상품 사진 준비 중">▧</span>;
}
