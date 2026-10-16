import snapshot from './mockSnapshot.json';

export const freshMockData = () => structuredClone(snapshot);
export const MOCK_STORAGE_KEY = 'school-bread:mock:v1';

export function simulateThreshold(data) {
  for (const slot of Object.values(data.status.slots)) {
    slot.in_stock = slot.hsv_score > data.config.threshold;
  }
  data.status.updated_at = new Intl.DateTimeFormat('sv-SE', {
    timeZone: 'Asia/Seoul', year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false,
  }).format(new Date());
  return data;
}
