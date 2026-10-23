// 첫 화면에서 포인터(마우스·터치)를 살짝 늦게 따라다니는 🎒
// position:fixed + pointer-events:none 이라 칩·입력창 클릭을 막지 않는다.
const OFFSET_X = 14; // 커서 오른쪽 아래로 살짝 떨어뜨림
const OFFSET_Y = 16;
const EASE = 0.18; // 프레임당 따라가는 비율 (lerp)
const MAX_TILT = 12; // 도

// 한 프레임 이동. reduced(움직임 줄이기)면 바로 목표로, 기울기 없음.
export function stepFollow(pos, target, { reduced = false } = {}) {
  if (reduced) return { x: target.x, y: target.y, tilt: 0 };
  const x = pos.x + (target.x - pos.x) * EASE;
  const y = pos.y + (target.y - pos.y) * EASE;
  const tilt = Math.max(-MAX_TILT, Math.min(MAX_TILT, (target.x - pos.x) * 0.5));
  return { x, y, tilt };
}

// 시작하고, 멈추는 함수를 돌려준다.
export function startFollower(doc = document, win = window, emoji = '🎒') {
  const el = doc.createElement('div');
  el.className = 'follower';
  el.setAttribute('aria-hidden', 'true');
  el.textContent = emoji;
  doc.body.appendChild(el);

  const mq = win.matchMedia ? win.matchMedia('(prefers-reduced-motion: reduce)') : null;
  let pos = null;
  let target = null;
  let tilt = 0;
  let raf = 0;

  const paint = () => {
    el.style.transform = 'translate3d(' + pos.x.toFixed(1) + 'px,' + pos.y.toFixed(1) + 'px,0) rotate(' + tilt.toFixed(1) + 'deg)';
  };
  const frame = () => {
    raf = 0;
    const next = stepFollow(pos, target, { reduced: !!(mq && mq.matches) });
    const done = Math.abs(next.x - target.x) < 0.3 && Math.abs(next.y - target.y) < 0.3;
    pos = done ? { x: target.x, y: target.y } : { x: next.x, y: next.y };
    tilt = done ? 0 : next.tilt;
    paint();
    if (!done) raf = win.requestAnimationFrame(frame);
  };
  const moveTo = (clientX, clientY) => {
    target = { x: clientX + OFFSET_X, y: clientY + OFFSET_Y };
    if (!pos) { pos = { ...target }; paint(); }
    el.classList.add('show');
    if (!raf) raf = win.requestAnimationFrame(frame);
  };
  const onPointer = (e) => moveTo(e.clientX, e.clientY);
  const onTouch = (e) => { const t = e.touches && e.touches[0]; if (t) moveTo(t.clientX, t.clientY); };
  const onLeave = (e) => { if (!e.relatedTarget) el.classList.remove('show'); };
  const onBlur = () => el.classList.remove('show');

  doc.addEventListener('pointermove', onPointer, { passive: true });
  doc.addEventListener('pointerdown', onPointer, { passive: true });
  doc.addEventListener('touchmove', onTouch, { passive: true }); // 스크롤 중 pointercancel 대비
  doc.addEventListener('pointerout', onLeave, { passive: true });
  win.addEventListener('blur', onBlur);

  return function stop() {
    doc.removeEventListener('pointermove', onPointer);
    doc.removeEventListener('pointerdown', onPointer);
    doc.removeEventListener('touchmove', onTouch);
    doc.removeEventListener('pointerout', onLeave);
    win.removeEventListener('blur', onBlur);
    if (raf) win.cancelAnimationFrame(raf);
    el.remove();
  };
}
