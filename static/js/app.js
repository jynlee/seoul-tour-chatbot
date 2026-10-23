// 화면 상태·이벤트
// 첫 화면(S2a) → 첫 전송 → 결과 화면(지도 펼침) ⇄ 지도 접힘(B안)
import { renderHome } from './home.js';
import { renderMap } from './map.js';
import { cardHtml, bubbleHtml, foldBarHtml, placeChipsHtml } from './view.js';
import { sendChat, fetchHistory } from './api.js';
import { requestLocation } from './geo.js';

const SESSION_KEY = 'stc.sessionId';
const $ = (sel) => document.querySelector(sel);

const state = {
  sessionId: loadSession(),
  center: null, // 마지막 추천의 기준점 {lat,lng,label,source}
  places: [], // 마지막 추천 장소 (새 추천이 오면 통째로 교체)
  me: null, // 내 위치 파란 점 (GPS 기준 추천일 때)
  selectedId: null, // 카드를 연 장소 → 다음 요청 selected_place_id
  cardOpen: false,
  mapOpen: true,
  pendingLocation: null, // 📍로 받은 좌표, 다음 전송에 한 번 실어 보냄 (F4)
  busy: false,
};

function loadSession() {
  try { return localStorage.getItem(SESSION_KEY); } catch { return null; }
}
function saveSession(id) {
  state.sessionId = id;
  try { localStorage.setItem(SESSION_KEY, id); } catch { /* 저장 못 해도 이번 화면에서는 계속 사용 */ }
}

// ---------- 결과 화면 뼈대 ----------
function buildResult() {
  $('#result').innerHTML = '<div class="top"><span class="brand">🗺️ 서울 여행 친구</span>'
    + '<button type="button" class="toggle" id="toggle" hidden>▾ 지도 접기</button></div>'
    + '<div class="map" id="map" hidden></div>'
    + '<button type="button" class="fold" id="fold" hidden></button>'
    + '<div class="chips" id="chips" hidden></div>'
    + '<div class="card" id="card" hidden></div>'
    + '<div class="chat" id="chat" aria-live="polite"></div>';
  $('#toggle').addEventListener('click', () => setMapOpen(!state.mapOpen));
  $('#fold').addEventListener('click', () => setMapOpen(true));
  $('#chips').addEventListener('click', (e) => {
    const chip = e.target.closest('.chip');
    if (chip) openCard(chip.dataset.id);
  });
}

function showResult() {
  if (!$('#result').hidden) return;
  $('#home').hidden = true;
  $('#result').hidden = false;
}

// ---------- 지도·요약 바·칩·카드 ----------
function renderPlaces() {
  const has = state.places.length > 0;
  $('#toggle').hidden = !has;
  $('#toggle').textContent = state.mapOpen ? '▾ 지도 접기' : '▴ 지도 펼치기';
  $('#map').hidden = !has || !state.mapOpen;
  $('#fold').hidden = !has || state.mapOpen;
  $('#chips').hidden = !has || state.mapOpen;
  if (!has) return;
  if (state.mapOpen) {
    renderMap($('#map'), {
      center: state.center,
      places: state.places,
      me: state.me,
      selectedId: state.cardOpen ? state.selectedId : null,
      onPinClick: openCard,
    });
  } else {
    $('#fold').innerHTML = foldBarHtml(state.center, state.places);
    $('#chips').innerHTML = placeChipsHtml(state.places, state.cardOpen ? state.selectedId : null);
  }
  renderCard();
}

function renderCard() {
  const card = $('#card');
  const place = state.cardOpen && state.places.find((p) => p.id === state.selectedId);
  if (!place) { card.hidden = true; card.innerHTML = ''; return; }
  card.innerHTML = cardHtml(place, { centerLabel: state.center && state.center.label });
  card.hidden = false;
  card.querySelector('.x').addEventListener('click', closeCard);
}

function openCard(id) {
  state.selectedId = id;
  state.cardOpen = true;
  renderPlaces();
}

function closeCard() {
  state.cardOpen = false; // selectedId는 남겨서 "거기 근처" 해석에 쓴다
  renderPlaces();
}

function setMapOpen(open) {
  state.mapOpen = open;
  renderPlaces();
}

function setPlaces(center, places, me = null) {
  state.center = center || null;
  state.places = places;
  state.me = me;
  state.selectedId = null;
  state.cardOpen = false;
  renderPlaces();
}

// ---------- 대화 ----------
function addBubble(role, text) {
  const chat = $('#chat');
  chat.insertAdjacentHTML('beforeend', bubbleHtml(role, text));
  chat.scrollTop = chat.scrollHeight;
  return chat.lastElementChild;
}

function botNotice(text) {
  showResult();
  addBubble('assistant', text);
}

async function send(message) {
  const text = (message || '').trim();
  if (!text || state.busy) return;
  state.busy = true;
  showResult();
  addBubble('user', text);
  const typing = addBubble('typing');
  const location = state.pendingLocation;
  clearPendingLocation();
  try {
    const res = await sendChat({
      sessionId: state.sessionId,
      message: text,
      location,
      selectedPlaceId: state.selectedId,
    });
    if (res.session_id) saveSession(res.session_id);
    typing.remove();
    addBubble('assistant', res.answer);
    // 장소가 있는 답변만 지도를 바꾼다 (인사·감사 등은 지도 유지)
    if (res.places && res.places.length) {
      const me = res.center && res.center.source === 'gps' ? { lat: res.center.lat, lng: res.center.lng } : null;
      setPlaces(res.center, res.places, me);
    }
  } catch (err) {
    typing.remove();
    addBubble('error', err.message || '답변을 가져오지 못했어요. 잠시 후 다시 시도해 주세요.');
  } finally {
    state.busy = false;
  }
}

// ---------- 위치 (📍 버튼 / "📍 내 주변 맛집" 칩) ----------
const PLACEHOLDER = '메시지 입력…';
const PLACEHOLDER_GPS = '📍 현재 위치 사용 중';

function setPendingLocation(loc) {
  state.pendingLocation = loc;
  $('#gps').classList.toggle('on', !!loc);
  $('#gps').setAttribute('aria-pressed', loc ? 'true' : 'false');
  $('#msg').placeholder = loc ? PLACEHOLDER_GPS : PLACEHOLDER;
}

function clearPendingLocation() {
  setPendingLocation(null);
}

// 위치를 받아 pendingLocation에 둔다. 실패하면 봇 말풍선으로 알리고 null.
async function locate() {
  const btn = $('#gps');
  btn.classList.add('wait');
  btn.disabled = true;
  try {
    const res = await requestLocation();
    if (res.error) {
      clearPendingLocation();
      botNotice(res.error);
      return null;
    }
    setPendingLocation(res);
    return res;
  } finally {
    btn.classList.remove('wait');
    btn.disabled = false;
  }
}

async function onGpsButton() {
  if (state.pendingLocation) { clearPendingLocation(); return; } // 한 번 더 누르면 취소
  await locate();
  $('#msg').focus();
}

async function onChip(chip) {
  if (state.busy) return;
  if (chip.gps) await locate(); // 실패해도 location: null로 전송
  send(chip.message);
}

// ---------- 새로고침 복원 ----------
async function restore() {
  if (!state.sessionId) return;
  let hist;
  try {
    hist = await fetchHistory(state.sessionId);
  } catch {
    return; // 복원 실패 시 첫 화면 그대로
  }
  const msgs = (hist && hist.messages) || [];
  if (!msgs.length) return;
  showResult();
  for (const m of msgs) addBubble(m.role === 'user' ? 'user' : 'assistant', m.message);
  const last = [...msgs].reverse().find((m) => m.role !== 'user' && m.places && m.places.length);
  if (last) {
    const me = last.center && last.center.source === 'gps' ? { lat: last.center.lat, lng: last.center.lng } : null;
    setPlaces(last.center, last.places, me);
  }
}

// ---------- 시작 ----------
buildResult();
renderHome($('#home'), { onChip });
$('#gps').addEventListener('click', onGpsButton);
$('#inp').addEventListener('submit', (e) => {
  e.preventDefault();
  const text = $('#msg').value;
  if (!text.trim() || state.busy) return;
  $('#msg').value = '';
  send(text);
});
restore();
