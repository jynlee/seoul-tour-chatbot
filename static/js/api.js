// fetch 래퍼. 실패하면 화면에 그대로 보여줄 한국어 메시지를 담은 Error를 던진다.
const NETWORK_ERROR = '서버에 연결할 수 없어요. 잠시 후 다시 시도해 주세요.';
const GENERIC_ERROR = '답변을 가져오지 못했어요. 잠시 후 다시 시도해 주세요.';
const TIMEOUT_ERROR = '답변이 너무 오래 걸려요. 잠시 후 다시 시도해 주세요.';
// 채팅 한 턴 2~7초, 첫 Ollama 호출은 +13초까지 걸린다(팀원1 실측) → 넉넉히 90초
export const CHAT_TIMEOUT_MS = 90000;

export async function errorMessage(res) {
  try {
    const body = await res.json();
    if (typeof body.detail === 'string' && body.detail) return body.detail;
    if (res.status === 422) return '메시지는 1~500자로 입력해 주세요.';
  } catch { /* JSON이 아니면 기본 문구 */ }
  return GENERIC_ERROR;
}

async function request(url, options, fetchImpl, timeoutMs = CHAT_TIMEOUT_MS) {
  const ctrl = typeof AbortController === 'function' ? new AbortController() : null;
  let timedOut = false;
  const timer = ctrl ? setTimeout(() => { timedOut = true; ctrl.abort(); }, timeoutMs) : null;
  let res;
  try {
    res = await fetchImpl(url, ctrl ? { ...options, signal: ctrl.signal } : options);
  } catch {
    throw new Error(timedOut ? TIMEOUT_ERROR : NETWORK_ERROR);
  } finally {
    if (timer) clearTimeout(timer);
  }
  if (!res.ok) throw new Error(await errorMessage(res));
  return res.json();
}

export function sendChat({ sessionId = null, message, location = null, selectedPlaceId = null }, fetchImpl = fetch, timeoutMs = CHAT_TIMEOUT_MS) {
  return request('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      session_id: sessionId,
      message,
      location,
      selected_place_id: selectedPlaceId,
    }),
  }, fetchImpl, timeoutMs);
}

export function fetchHistory(sessionId, fetchImpl = fetch) {
  return request('/api/history/' + encodeURIComponent(sessionId), {}, fetchImpl, 15000);
}
