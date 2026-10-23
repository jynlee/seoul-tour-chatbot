import { test } from 'node:test';
import assert from 'node:assert/strict';
import { sendChat, fetchHistory } from '../../static/js/api.js';

const json = (status, body) => async () => ({ ok: status < 400, status, json: async () => body });

test('요청 본문은 계약의 snake_case 필드', async () => {
  let seen;
  const fake = async (url, opt) => { seen = { url, opt }; return { ok: true, status: 200, json: async () => ({ ok: 1 }) }; };
  await sendChat({ sessionId: 's1', message: '광화문 맛집', location: { lat: 1, lng: 2 }, selectedPlaceId: 'p9' }, fake);
  assert.equal(seen.url, '/api/chat');
  assert.equal(seen.opt.method, 'POST');
  assert.deepEqual(JSON.parse(seen.opt.body), { session_id: 's1', message: '광화문 맛집', location: { lat: 1, lng: 2 }, selected_place_id: 'p9' });
});

test('503이면 detail 문구로 Error', async () => {
  const detail = '검색 서버에 연결할 수 없어요. 잠시 후 다시 시도해 주세요.';
  await assert.rejects(sendChat({ message: 'x' }, json(503, { detail })), { message: detail });
});

test('422면 길이 안내 문구', async () => {
  await assert.rejects(sendChat({ message: 'x' }, json(422, { detail: [{ msg: 'too long' }] })), /1~500자/);
});

test('네트워크 오류면 연결 안내 문구', async () => {
  await assert.rejects(sendChat({ message: 'x' }, async () => { throw new TypeError('Failed to fetch'); }), /서버에 연결할 수 없어요/);
});

test('history 조회', async () => {
  let url;
  const res = await fetchHistory('a b', async (u) => { url = u; return { ok: true, status: 200, json: async () => ({ messages: [] }) }; });
  assert.equal(url, '/api/history/a%20b');
  assert.deepEqual(res, { messages: [] });
});
