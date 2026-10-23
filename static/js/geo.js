// GPS 현재 위치. 브라우저는 https 또는 localhost에서만 위치를 준다.
export const GEO_UNSUPPORTED = '이 브라우저에서는 위치를 쓸 수 없어요';
export const GEO_DENIED = '위치 권한이 없어서 현재 위치를 쓸 수 없어요';
export const GEO_FAILED = '현재 위치를 찾지 못했어요. 잠시 후 다시 시도해 주세요';
const TIMEOUT_MS = 8000;

export function requestLocation(geo = globalThis.navigator && globalThis.navigator.geolocation) {
  if (!geo || typeof geo.getCurrentPosition !== 'function') return Promise.resolve({ error: GEO_UNSUPPORTED });
  return new Promise((resolve) => {
    try {
      geo.getCurrentPosition(
        (pos) => resolve({ lat: pos.coords.latitude, lng: pos.coords.longitude }),
        (err) => resolve({ error: err && err.code === 1 ? GEO_DENIED : GEO_FAILED }),
        { enableHighAccuracy: false, timeout: TIMEOUT_MS, maximumAge: 60000 },
      );
    } catch {
      resolve({ error: GEO_FAILED });
    }
  });
}
