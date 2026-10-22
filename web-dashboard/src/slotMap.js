// Derive the visual map from existing ROI coordinates without changing the DB schema.
export function mapSlots(config) {
  const ordered = Object.entries(config?.slots || {}).sort(([, a], [, b]) => a.y - b.y || a.x - b.x);
  const rows = [];
  for (const [id, slot] of ordered) {
    const center = slot.y + slot.h / 2;
    let row = rows.find((candidate) => Math.abs(candidate.center - center) < Math.min(candidate.height, slot.h) * .5);
    if (!row) { row = { center, height: slot.h, items: [] }; rows.push(row); }
    row.items.push({ id, ...slot });
  }
  return rows.flatMap((row, index) => row.items.sort((a, b) => a.x - b.x).map((slot, col) => ({
    ...slot, row: index + 1, column: col + 1, label: `${String.fromCharCode(65 + index)}${col + 1}`,
  })));
}

export function inventoryState(item) {
  return typeof item?.in_stock === 'boolean' ? (item.in_stock ? 'stocked' : 'soldout') : 'unknown';
}
export const stateLabel = { stocked: '재고 있음', soldout: '품절', unknown: '미확인' };
