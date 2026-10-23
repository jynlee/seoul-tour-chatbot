import { test } from 'node:test';
import assert from 'node:assert/strict';
import { stepFollow } from '../../static/js/follower.js';

test('한 프레임에 목표 쪽으로 일부만 움직인다 (늦게 따라옴)', () => {
  const n = stepFollow({ x: 0, y: 0 }, { x: 100, y: 50 });
  assert.ok(n.x > 0 && n.x < 100);
  assert.ok(n.y > 0 && n.y < 50);
});

test('계속 따라가면 목표에 수렴한다', () => {
  let p = { x: 0, y: 0 };
  for (let i = 0; i < 100; i++) p = stepFollow(p, { x: 100, y: 50 });
  assert.ok(Math.abs(p.x - 100) < 0.1 && Math.abs(p.y - 50) < 0.1);
});

test('기울기는 이동 방향을 따르고 12도를 넘지 않는다', () => {
  assert.equal(stepFollow({ x: 0, y: 0 }, { x: 500, y: 0 }).tilt, 12);
  assert.equal(stepFollow({ x: 500, y: 0 }, { x: 0, y: 0 }).tilt, -12);
  assert.ok(Math.abs(stepFollow({ x: 0, y: 0 }, { x: 4, y: 0 }).tilt) < 12);
});

test('움직임 줄이기 설정이면 바로 목표로, 기울기 0', () => {
  assert.deepEqual(stepFollow({ x: 0, y: 0 }, { x: 100, y: 50 }, { reduced: true }), { x: 100, y: 50, tilt: 0 });
});
