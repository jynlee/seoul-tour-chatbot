// 세션 ID 저장과 화면 상태 초기값 (DOM 없이 테스트하려고 app.js에서 뺌)
// 세션 ID는 sessionStorage: 같은 탭 새로고침은 복원, 새 탭·브라우저 재시작은 첫 화면.
import { DEFAULT_BADGE } from './brand.js';

export const SESSION_KEY = 'stc.sessionId';

// 예전 버전이 localStorage에 남긴 값은 지운다(남아 있으면 새 탭에서도 복원돼서)
export function loadSession(tab, legacy) {
  try { legacy.removeItem(SESSION_KEY); } catch { /* 못 지워도 읽지는 않음 */ }
  try { return tab.getItem(SESSION_KEY); } catch { return null; }
}

export function saveSession(id, tab) {
  try { tab.setItem(SESSION_KEY, id); } catch { /* 저장 못 해도 이번 화면에서는 계속 사용 */ }
}

export function clearSession(tab) {
  try { tab.removeItem(SESSION_KEY); } catch { /* 지우지 못해도 이번 화면은 새 세션 */ }
}

export function freshState() {
  return {
    sessionId: null,
    center: null, // 마지막 추천의 기준점 {lat,lng,label,source}
    places: [], // 마지막 추천 장소 (새 추천이 오면 통째로 교체)
    me: null, // 내 위치 파란 점 (GPS 기준 추천일 때)
    selectedId: null, // 카드를 연 장소 → 다음 요청 selected_place_id
    cardOpen: false,
    mapOpen: true,
    pendingLocation: null, // 📍로 받은 좌표, 다음 전송에 한 번 실어 보냄 (F4)
    busy: false,
    badgeId: DEFAULT_BADGE, // 상단 배지 랜드마크 (center에서 가장 가까운 것)
  };
}
