// 화면 상태·이벤트
// 첫 화면(S2a) → 첫 전송 → 결과 화면(지도 펼침) ⇄ 지도 접힘(B안)
import { renderHome } from './home.js';
import { renderMap } from './map.js';
import { cardHtml, bubbleHtml, foldBarHtml, placeChipsHtml, placesView } from './view.js';
import { sendChat, fetchHistory } from './api.js';
import { requestLocation } from './geo.js';
import { startFollower } from './follower.js';
import { pickBadge, badgeSvg, DEFAULT_BADGE } from './brand.js';

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
  badgeId: DEFAULT_BADGE, // 상단 배지 랜드마크 (center에서 가장 가까운 것)
};

// 배지 교체: Y축으로 살짝 뒤집히며 바뀜(0.4초). 같은 랜드마크면 그대로, 움직임 줄이기면 바로.
function setBadge(center) {
  const id = pickBadge(center, state.badgeId);
  if (id === state.badgeId) return;
  state.badgeId = id;
  const el = $('#badge');
  const swap = () => { el.innerHTML = badgeSvg(id); };
  const reduced = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (reduced || typeof el.animate !== 'function') { swap(); return; }
  el.getAnimations().forEach((a) => a.cancel());
  el.animate([{ transform: 'rotateY(0deg)' }, { transform: 'rotateY(90deg)' }], { duration: 200, easing: 'ease-in' })
    .onfinish = () => {
      swap();
      el.animate([{ transform: 'rotateY(-90deg)' }, { transform: 'rotateY(0deg)' }], { duration: 200, easing: 'ease-out' });
    };
}

function loadSession() {
  try { return localStorage.getItem(SESSION_KEY); } catch { return null; }
}
function saveSession(id) {
  state.sessionId = id;
  try { localStorage.setItem(SESSION_KEY, id); } catch { /* 저장 못 해도 이번 화면에서는 계속 사용 */ }
}

// ---------- 결과 화면 뼈대 ----------
function buildResult() {
  $('#result').innerHTML = '<div class="top"><span class="brand"><span class="badge" id="badge">' + badgeSvg(state.badgeId) + '</span>'
    + '<span class="brand-name"><span class="seoul">서울</span> 여행친구</span></span></div>'
    + '<div class="map" id="map" hidden></div>'
    + '<button type="button" class="handle" id="handle" aria-expanded="true" aria-controls="map" hidden>▴ 지도 접기</button>'
    + '<button type="button" class="fold" id="fold" aria-expanded="false" aria-controls="map" hidden></button>'
    + '<div class="chips" id="chips" hidden></div>'
    + '<div class="card" id="card" hidden></div>'
    + '<div class="chat" id="chat" aria-live="polite"></div>';
  // 누른 버튼이 숨으므로 키보드로 눌렀을 때는 포커스를 반대쪽 버튼으로 넘긴다
  const swap = (open, next) => (e) => {
    const kb = e.currentTarget.matches(':focus-visible');
    setMapOpen(open);
    if (kb) $(next).focus();
  };
  $('#handle').addEventListener('click', swap(false, '#fold'));
  $('#fold').addEventListener('click', swap(true, '#handle'));
  $('#chips').addEventListener('click', (e) => {
    const chip = e.target.closest('.chip');
    if (chip) openCard(chip.dataset.id);
  });
}

let stopFollower = null;

function showResult() {
  if (stopFollower) { stopFollower(); stopFollower = null; } // 🎒는 첫 화면에서만
  if (!$('#result').hidden) return;
  $('#home').hidden = true;
  $('#result').hidden = false;
}

// ---------- 지도·요약 바·칩·카드 ----------
function renderPlaces() {
  const has = state.places.length > 0;
  const show = placesView(has, state.mapOpen);
  $('#map').hidden = !show.map;
  $('#handle').hidden = !show.handle;
  $('#fold').hidden = !show.fold;
  $('#chips').hidden = !show.chips;
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
    setBadge(res.center);
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
  const lastCenter = [...msgs].reverse().find((m) => m.role !== 'user' && m.center);
  if (lastCenter) { // 복원은 애니메이션 없이 바로
    state.badgeId = pickBadge(lastCenter.center, state.badgeId);
    $('#badge').innerHTML = badgeSvg(state.badgeId);
  }
  const last = [...msgs].reverse().find((m) => m.role !== 'user' && m.places && m.places.length);
  if (last) {
    const me = last.center && last.center.source === 'gps' ? { lat: last.center.lat, lng: last.center.lng } : null;
    setPlaces(last.center, last.places, me);
  }
}

// ---------- 시작 ----------
buildResult();
renderHome($('#home'), { onChip });
stopFollower = startFollower();
$('#gps').addEventListener('click', onGpsButton);
$('#inp').addEventListener('submit', (e) => {
  e.preventDefault();
  const text = $('#msg').value;
  if (!text.trim() || state.busy) return;
  $('#msg').value = '';
  send(text);
});
restore();
