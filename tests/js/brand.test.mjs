import { test } from 'node:test';
import assert from 'node:assert/strict';
import { pickBadge, badgeSvg, DEFAULT_BADGE } from '../../static/js/brand.js';
import { homeSvg } from '../../static/js/home.js';

// 좌표는 백엔드 app/geo.py 인기 지역 이름표·카탈로그 값
test('가장 가까운 랜드마크 배지', () => {
  assert.equal(pickBadge({ lat: 37.5219, lng: 126.9245 }), 'b63'); // 여의도
  assert.equal(pickBadge({ lat: 37.5512, lng: 126.9882 }), 'namsan'); // 남산
  assert.equal(pickBadge({ lat: 37.5133, lng: 127.1 }), 'lotte'); // 잠실
  assert.equal(pickBadge({ lat: 37.5759, lng: 126.9769 }), 'gyeongbokgung'); // 광화문
  assert.equal(pickBadge({ lat: 37.5665, lng: 127.0092 }), 'ddp'); // 동대문
  assert.equal(pickBadge({ lat: 37.5446, lng: 127.0559 }), 'ddp'); // 성수 — 거리 제한 없음 (DDP 4.6km)
});

test('명동은 거리상 숭례문이 가장 가깝다(0.8km, 남산타워 1.4km)', () => {
  assert.equal(pickBadge({ lat: 37.5636, lng: 126.9827 }), 'sungnyemun');
});

test('center가 없으면 직전 배지, 직전도 없으면 광화문', () => {
  assert.equal(pickBadge(null, 'b63'), 'b63');
  assert.equal(pickBadge(null), DEFAULT_BADGE);
  assert.equal(DEFAULT_BADGE, 'gyeongbokgung');
  assert.equal(pickBadge({ lat: 0, lng: 0 }, 'lotte'), 'lotte');
});

test('배지 SVG는 40px, 글자 없음', () => {
  const svg = badgeSvg('b63');
  assert.match(svg, /width="40" height="40"/);
  assert.doesNotMatch(svg, /<text/);
});

test('첫 화면 원 안 로고: 상단 워드마크와 같은 Jua 두 색', () => {
  const svg = homeSvg();
  assert.match(svg, /<text class="home-logo"[^>]*font-family="Jua/);
  assert.match(svg, /<tspan fill="#ff6f8d">서울<\/tspan><tspan fill="#5a4632"> 여행친구<\/tspan>/);
});
