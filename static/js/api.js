// fetch 래퍼. 실패하면 화면에 그대로 보여줄 한국어 메시지를 담은 Error를 던진다.
const NETWORK_ERROR = '서버에 연결할 수 없어요. 잠시 후 다시 시도해 주세요.';
const GENERIC_ERROR = '답변을 가져오지 못했어요. 잠시 후 다시 시도해 주세요.';

export async function errorMessage(res) {
  try {
    const body = await res.json();
    if (typeof body.detail === 'string' && body.detail) return body.detail;
    if (res.status === 422) return '메시지는 1~500자로 입력해 주세요.';
  } catch { /* JSON이 아니면 기본 문구 */ }
  return GENERIC_ERROR;
}

async function request(url, options, fetchImpl) {
  let res;
  try {
    res = await fetchImpl(url, options);
  } catch {
    throw new Error(NETWORK_ERROR);
  }
  if (!res.ok) throw new Error(await errorMessage(res));
  return res.json();
}

export function sendChat({ sessionId = null, message, location = null, selectedPlaceId = null }, fetchImpl = fetch) {
  return request('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      session_id: sessionId,
      message,
      location,
      selected_place_id: selectedPlaceId,
    }),
  }, fetchImpl);
}

export function fetchHistory(sessionId, fetchImpl = fetch) {
  return request('/api/history/' + encodeURIComponent(sessionId), {}, fetchImpl);
}
