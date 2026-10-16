export function stableStringify(value) {
  if (value === null || typeof value !== 'object') return JSON.stringify(value);
  if (Array.isArray(value)) return `[${value.map(stableStringify).join(',')}]`;
  return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${stableStringify(value[key])}`).join(',')}}`;
}

export function validateConfig(config, dimensions) {
  if (!config || !Number.isFinite(config.threshold) || config.threshold < 0 || config.threshold > 255) {
    throw new Error('판별 기준값은 0~255 사이의 숫자로 입력해 주세요.');
  }
  const entries = Object.entries(config.slots || {});
  if (entries.length < 1 || entries.length > 60) throw new Error('칸은 1~60개여야 합니다.');
  for (const [id, slot] of entries) {
    if (!/^slot_[A-Za-z0-9_-]+$/.test(id) || !slot || typeof slot.name !== 'string' || !slot.name.trim() || slot.name.length > 60) {
      throw new Error('칸 이름은 1~60자로 입력해 주세요.');
    }
    for (const key of ['x', 'y', 'w', 'h']) {
      if (!Number.isInteger(slot[key]) || slot[key] < (['w', 'h'].includes(key) ? 1 : 0) || slot[key] > 8192) {
        throw new Error(`${slot.name}: 좌표는 0 이상, 크기는 1 이상의 정수여야 합니다 (최대 8192).`);
      }
    }
    if (dimensions && (slot.x + slot.w > dimensions.width || slot.y + slot.h > dimensions.height)) {
      throw new Error(`${slot.name}: 선택 영역이 사진 바깥으로 나갑니다.`);
    }
  }
}
