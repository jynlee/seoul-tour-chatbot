import { test } from 'node:test';
import assert from 'node:assert/strict';
import { SESSION_KEY, loadSession, saveSession, clearSession, freshState } from '../../static/js/session.js';
import { DEFAULT_BADGE } from '../../static/js/brand.js';

// Storage 흉내 (getItem/setItem/removeItem)
function fakeStore(init = {}) {
  const m = new Map(Object.entries(init));
  return {
    getItem: (k) => (m.has(k) ? m.get(k) : null),
    setItem: (k, v) => { m.set(k, String(v)); },
    removeItem: (k) => { m.delete(k); },
    has: (k) => m.has(k),
  };
}
const broken = { getItem() { throw new Error('막힘'); }, setItem() { throw new Error('막힘'); }, removeItem() { throw new Error('막힘'); } };

test('세션 ID는 sessionStorage에 저장하고 같은 탭에서 다시 읽힘(새로고침 복원)', () => {
  const tab = fakeStore();
  saveSession('abc', tab);
  assert.equal(tab.getItem(SESSION_KEY), 'abc');
  assert.equal(loadSession(tab, fakeStore()), 'abc');
});

test('새 탭(빈 sessionStorage)이면 null → 첫 화면', () => {
  assert.equal(loadSession(fakeStore(), fakeStore()), null);
});

test('예전 localStorage 값은 지우고 복원에 쓰지 않음', () => {
  const legacy = fakeStore({ [SESSION_KEY]: 'old' });
  assert.equal(loadSession(fakeStore(), legacy), null);
  assert.equal(legacy.has(SESSION_KEY), false);
});

test('저장소가 막혀도 오류 없이 동작', () => {
  assert.equal(loadSession(broken, broken), null);
  assert.doesNotThrow(() => saveSession('abc', broken));
  assert.doesNotThrow(() => clearSession(broken));
});

test('새 대화: 세션 ID 지우기', () => {
  const tab = fakeStore({ [SESSION_KEY]: 'abc' });
  clearSession(tab);
  assert.equal(loadSession(tab, fakeStore()), null);
});

test('초기 상태: 장소·선택·위치 비움, 지도 펼침, 기본 배지', () => {
  assert.deepEqual(freshState(), {
    sessionId: null, center: null, places: [], me: null, selectedId: null, cardOpen: false,
    mapOpen: true, pendingLocation: null, busy: false, badgeId: DEFAULT_BADGE,
  });
  assert.notEqual(freshState().places, freshState().places); // 매번 새 배열
});
