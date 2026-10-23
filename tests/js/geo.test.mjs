import { test } from 'node:test';
import assert from 'node:assert/strict';
import { requestLocation, GEO_DENIED, GEO_UNSUPPORTED, GEO_FAILED } from '../../static/js/geo.js';

const fakeGeo = (fn) => ({ getCurrentPosition: (ok, fail, opts) => fn(ok, fail, opts) });

test('성공하면 좌표', async () => {
  let opts;
  const geo = fakeGeo((ok, _f, o) => { opts = o; ok({ coords: { latitude: 37.5759, longitude: 126.9769 } }); });
  assert.deepEqual(await requestLocation(geo), { lat: 37.5759, lng: 126.9769 });
  assert.equal(opts.timeout, 8000);
});

test('권한 거부(code 1)면 거부 문구', async () => {
  const geo = fakeGeo((_ok, fail) => fail({ code: 1, PERMISSION_DENIED: 1 }));
  assert.deepEqual(await requestLocation(geo), { error: GEO_DENIED });
  assert.equal(GEO_DENIED, '위치 권한이 없어서 현재 위치를 쓸 수 없어요');
});

test('geo 없으면 미지원 문구', async () => {
  assert.deepEqual(await requestLocation(undefined), { error: GEO_UNSUPPORTED });
  assert.deepEqual(await requestLocation(null), { error: GEO_UNSUPPORTED });
  assert.equal(GEO_UNSUPPORTED, '이 브라우저에서는 위치를 쓸 수 없어요');
});

test('시간 초과·위치 못 찾음이면 실패 문구', async () => {
  assert.deepEqual(await requestLocation(fakeGeo((_ok, fail) => fail({ code: 3 }))), { error: GEO_FAILED });
  assert.deepEqual(await requestLocation(fakeGeo((_ok, fail) => fail({ code: 2 }))), { error: GEO_FAILED });
});

test('getCurrentPosition이 예외를 던져도 실패 문구', async () => {
  assert.deepEqual(await requestLocation(fakeGeo(() => { throw new Error('x'); })), { error: GEO_FAILED });
});
