// 화면 상태·이벤트
// 첫 화면(S2a) → 첫 전송 → 결과 화면(지도 펼침) ⇄ 지도 접힘(B안)
import { renderHome } from './home.js';
import { renderMap } from './map.js';
import { cardHtml, bubbleHtml, foldBarHtml, placeChipsHtml, placesView } from './view.js';
import { sendChat, fetchHistory } from './api.js';
import { requestLocation } from './geo.js';
import { startFollower } from './follower.js';
import { pickBadge, badgeSvg } from './brand.js';
import { loadSession, saveSession, clearSession, freshState } from './session.js';

const $ = (sel) => document.querySelector(sel);
// 저장소 접근 자체가 막힌 브라우저도 있어서 감싼다 (null이면 session.js에서 조용히 무시)
const storage = (name) => { try { return window[name]; } catch { return null; } };
const tabStore = storage('sessionStorage');

const state = { ...freshState(), sessionId: loadSession(tabStore, storage('localStorage')) };

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

// ---------- 결과 화면 뼈대 ----------
function buildResult() {
  $('#result').innerHTML = '<div class="top"><span class="brand"><span class="badge" id="badge">' + badgeSvg(state.badgeId) + '</span>'
    + '<span class="brand-name"><span class="seoul">서울</span> 여행친구</span></span>'
    + '<button type="button" class="newchat" id="newchat">↺ 새 대화</button></div>'
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
  $('#newchat').addEventListener('click', newChat);
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

// "새 대화": 서버 기록은 그대로 두고, 새 세션으로 첫 화면(S2a)부터 다시
function newChat() {
  if (state.busy) return;
  clearSession(tabStore);
  restoreGen++; // 아직 끝나지 않은 복원이 있으면 버린다
  Object.assign(state, freshState());
  $('#chat').innerHTML = '';
  $('#badge').innerHTML = badgeSvg(state.badgeId);
  renderPlaces(); // 장소가 없으니 지도·손잡이·요약 바·칩 숨김
  renderCard();
  clearPendingLocation();
  $('#msg').value = '';
  $('#result').hidden = true;
  $('#home').hidden = false;
  if (!stopFollower) stopFollower = startFollower();
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
  const index = state.places.indexOf(place);
  card.innerHTML = cardHtml(place, { centerLabel: state.center && state.center.label, index, prev: index > 0 ? state.places[index - 1] : null });
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
function addBubble(role, text, names) {
  const chat = $('#chat');
  chat.insertAdjacentHTML('beforeend', bubbleHtml(role, text, names));
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
  setBusy(true);
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
    if (res.session_id) { state.sessionId = res.session_id; saveSession(res.session_id, tabStore); }
    typing.remove();
    // 장소 이름 굵게: 새 목록이면 그 장소들, 정보 답처럼 목록이 없으면 지금 지도에 있는 장소들
    const shown = res.places && res.places.length ? res.places : state.places;
    addBubble('assistant', res.answer, (shown || []).map((p) => p.title));
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
    setBusy(false);
  }
}

// 응답 기다리는 동안은 "새 대화"를 잠근다
function setBusy(on) {
  state.busy = on;
  $('#newchat').disabled = on;
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
let restoreGen = 0;

async function restore() {
  if (!state.sessionId) return;
  const gen = restoreGen;
  let hist;
  try {
    hist = await fetchHistory(state.sessionId);
  } catch {
    return; // 복원 실패 시 첫 화면 그대로
  }
  if (gen !== restoreGen) return; // 그 사이 "새 대화"를 눌렀음
  const msgs = (hist && hist.messages) || [];
  if (!msgs.length) return;
  showResult();
  let shownTitles = []; // 그 답 시점에 지도에 있던 장소 이름 (정보 답은 설명한 장소도)
  for (const m of msgs) {
    if (m.role === 'user') { addBubble('user', m.message); continue; }
    if (m.places && m.places.length) shownTitles = m.places.map((p) => p.title);
    const focus = !(m.places && m.places.length) && m.center && m.center.source === 'place' ? [m.center.label] : [];
    addBubble('assistant', m.message, [...shownTitles, ...focus]);
  }
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
