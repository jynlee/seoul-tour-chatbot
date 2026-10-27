// 6대 랜드마크 좌표와 SVG 일러스트.
// SVG 함수는 확정 시안 docs/superpowers/mockups/first-screen-s2a.html 에서 그대로 옮겼다.
// s = 그라데이션 id 접미사 (한 페이지에 SVG가 여러 개일 때 id 충돌 방지)

export function defs(s) {
  return '<defs>'
    + '<linearGradient id="gold' + s + '" x1="0" x2="1"><stop offset="0" stop-color="#f3c262"/><stop offset=".55" stop-color="#fbe3a6"/><stop offset="1" stop-color="#e9ad48"/></linearGradient>'
    + '<linearGradient id="silver' + s + '" x1="0" x2="1"><stop offset="0" stop-color="#b9c8dc"/><stop offset=".5" stop-color="#eef3fa"/><stop offset="1" stop-color="#a5b6cd"/></linearGradient>'
    + '<linearGradient id="roof' + s + '" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#5b6b78"/><stop offset="1" stop-color="#3f4b56"/></linearGradient>'
    + '<radialGradient id="hill' + s + '" cx=".5" cy=".3"><stop offset="0" stop-color="#cfe8b8"/><stop offset="1" stop-color="#a7d48f"/></radialGradient>'
    + '<linearGradient id="sky' + s + '" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ffe3ec"/><stop offset="1" stop-color="#fff3e2"/></linearGradient>'
    + '<linearGradient id="ddp' + s + '" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#f4f7fb"/><stop offset="1" stop-color="#bfcbdb"/></linearGradient>'
    + '<linearGradient id="river' + s + '" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#bfe6f8"/><stop offset="1" stop-color="#93cfee"/></linearGradient>'
    + '</defs>';
}

export function palace(x, y, k, s) {
  return '<g transform="translate(' + x + ',' + y + ') scale(' + k + ')">'
    + '<rect x="-44" y="18" width="88" height="7" rx="1.5" fill="#e4ddd0"/><rect x="-38" y="12" width="76" height="7" rx="1.5" fill="#efe9de"/>'
    + '<rect x="-6" y="12" width="12" height="13" fill="#d9d1c2"/><rect x="-32" y="-6" width="64" height="18" fill="#f6ead2"/>'
    + [-28, -17, -6, 5, 16, 27].map((px) => '<rect x="' + px + '" y="-6" width="3" height="18" fill="#c8483b"/>').join('')
    + '<rect x="-32" y="-9" width="64" height="4" fill="#5fae96"/><rect x="-32" y="-9" width="64" height="1.3" fill="#e9655a"/>'
    + '<path d="M-48,-11 Q-40,-9 -30,-12 L30,-12 Q40,-9 48,-11 Q42,-17 34,-21 L-34,-21 Q-42,-17 -48,-11Z" fill="url(#roof' + s + ')"/>'
    + '<rect x="-22" y="-30" width="44" height="10" fill="#f6ead2"/>'
    + [-19, -8, 3, 14].map((px) => '<rect x="' + px + '" y="-30" width="2.5" height="10" fill="#c8483b"/>').join('')
    + '<rect x="-22" y="-32" width="44" height="3" fill="#5fae96"/>'
    + '<path d="M-36,-32 Q-29,-30 -21,-33 L21,-33 Q29,-30 36,-32 Q30,-40 22,-44 L-22,-44 Q-30,-40 -36,-32Z" fill="url(#roof' + s + ')"/>'
    + '<path d="M-23,-44 L23,-44" stroke="#2f3a43" stroke-width="2.4" stroke-linecap="round"/>'
    + '</g>';
}

export function gate(x, y, k, s) {
  let st = '';
  for (let r = 0; r < 3; r++) for (let c = 0; c < 7; c++) st += '<rect x="' + (-35 + c * 10 + (r % 2 ? 5 : 0)) + '" y="' + (4 + r * 6) + '" width="9" height="5" rx="1" fill="#e6dfd3"/>';
  return '<g transform="translate(' + x + ',' + y + ') scale(' + k + ')">'
    + '<rect x="-36" y="2" width="72" height="22" rx="2" fill="#d6cdbd"/>' + st
    + '<path d="M-8,24 L-8,14 A8,8 0 0 1 8,14 L8,24Z" fill="#6b5847"/>'
    + '<rect x="-26" y="-10" width="52" height="12" fill="#f6ead2"/>'
    + [-23, -12, -1, 10, 21].map((px) => '<rect x="' + px + '" y="-10" width="2.5" height="12" fill="#c8483b"/>').join('')
    + '<rect x="-26" y="-12" width="52" height="3" fill="#5fae96"/>'
    + '<path d="M-38,-12 Q-30,-10 -24,-13 L24,-13 Q30,-10 38,-12 Q32,-19 25,-22 L-25,-22 Q-32,-19 -38,-12Z" fill="url(#roof' + s + ')"/>'
    + '<rect x="-18" y="-29" width="36" height="8" fill="#f6ead2"/><rect x="-18" y="-31" width="36" height="2.5" fill="#5fae96"/>'
    + '<path d="M-28,-31 Q-22,-29 -17,-32 L17,-32 Q22,-29 28,-31 Q23,-37 17,-40 L-17,-40 Q-23,-37 -28,-31Z" fill="url(#roof' + s + ')"/>'
    + '</g>';
}

export function namsan(x, y, k, s) {
  return '<g transform="translate(' + x + ',' + y + ') scale(' + k + ')">'
    + '<path d="M-46,22 C-30,-2 -12,-8 0,-8 C14,-8 30,-2 46,22Z" fill="url(#hill' + s + ')"/>'
    + '<circle cx="-24" cy="12" r="5" fill="#8cc271"/><circle cx="-14" cy="6" r="6" fill="#8cc271"/><circle cx="18" cy="8" r="5.5" fill="#8cc271"/><circle cx="28" cy="14" r="4.5" fill="#8cc271"/>'
    + '<path d="M-7,-6 L-4,-14 L4,-14 L7,-6Z" fill="#f2efe9"/>'
    + '<rect x="-2.6" y="-60" width="5.2" height="47" fill="#fbfaf7" stroke="#d8d2c6" stroke-width=".8"/>'
    + '<ellipse cx="0" cy="-60" rx="11" ry="3" fill="#e9e4dc"/>'
    + '<rect x="-10" y="-70" width="20" height="10" rx="3" fill="#fff" stroke="#d8d2c6" stroke-width=".8"/><rect x="-10" y="-67" width="20" height="2.4" fill="#ffb3c1"/>'
    + '<rect x="-8.5" y="-77" width="17" height="7" rx="2.5" fill="#fff" stroke="#d8d2c6" stroke-width=".8"/><rect x="-8.5" y="-75" width="17" height="2" fill="#9fd1ec"/>'
    + '<rect x="-1.4" y="-104" width="2.8" height="27" fill="#fff"/>'
    + [0, 1, 2, 3].map((i) => '<rect x="-1.4" y="' + (-104 + i * 7) + '" width="2.8" height="3.5" fill="#ff7a8f"/>').join('')
    + '</g>';
}

export function ddp(x, y, k, s) {
  let d = '';
  for (let i = 0; i < 9; i++) d += '<path d="M' + (-30 + i * 7.5) + ',-2 Q' + (-28 + i * 7.5) + ',-12 ' + (-26 + i * 7.5) + ',-16" stroke="#a9b8cc" stroke-width=".8" fill="none"/>';
  return '<g transform="translate(' + x + ',' + y + ') scale(' + k + ')"><ellipse cx="0" cy="6" rx="42" ry="6" fill="#d7ecc4"/>'
    + '<path d="M-40,4 C-42,-10 -30,-22 -8,-22 C10,-22 18,-14 30,-16 C42,-18 44,-4 40,4Z" fill="url(#ddp' + s + ')" stroke="#a9b8cc" stroke-width="1"/>' + d
    + '<path d="M-24,-20 C-12,-26 4,-24 14,-18" stroke="#9fd083" stroke-width="4" fill="none" stroke-linecap="round"/></g>';
}

export function b63(x, y, k, s) {
  let r = '';
  for (let i = 0; i < 12; i++) r += '<path d="M' + (-11 + i * 0.25) + ',' + (-4 - i * 5.6) + ' L' + (11 - i * 0.25) + ',' + (-4 - i * 5.6) + '" stroke="#e2a443" stroke-width=".7" opacity=".7"/>';
  return '<g transform="translate(' + x + ',' + y + ') scale(' + k + ')"><ellipse cx="0" cy="2" rx="20" ry="4" fill="#cfe8b8"/>'
    + '<path d="M-12,0 L-8.5,-68 Q0,-74 8.5,-68 L12,0Z" fill="url(#gold' + s + ')"/>' + r
    + '<path d="M-3,-66 L-1,-4" stroke="#fff" stroke-width="2" opacity=".55"/><rect x="-14" y="-4" width="28" height="5" rx="1" fill="#e6c48a"/></g>';
}

export function lotte(x, y, k, s) {
  return '<g transform="translate(' + x + ',' + y + ') scale(' + k + ')"><ellipse cx="0" cy="2" rx="18" ry="4" fill="#cfe8b8"/>'
    + '<path d="M-9,0 C-8,-40 -4,-80 -1.5,-104 L-.3,-96 L.3,-96 L1.5,-104 C4,-80 8,-40 9,0Z" fill="url(#silver' + s + ')"/>'
    + '<path d="M0,-94 L0,0" stroke="#fff" stroke-width="1.4" opacity=".6"/><rect x="-12" y="-2" width="24" height="4" rx="1" fill="#c9d6e8"/></g>';
}

export function tree(x, y, r) {
  return '<circle cx="' + x + '" cy="' + y + '" r="' + r + '" fill="#9fd083"/>';
}

export function cloud(x, y) {
  return '<g fill="#fff" opacity=".9"><ellipse cx="' + x + '" cy="' + y + '" rx="18" ry="6"/><ellipse cx="' + (x + 11) + '" cy="' + (y - 5) + '" rx="10" ry="6"/></g>';
}

export function badge(x, y, r, inner, col) {
  return '<g><circle cx="' + x + '" cy="' + (y + 3) + '" r="' + r + '" fill="#000" opacity=".08"/><circle cx="' + x + '" cy="' + y + '" r="' + r + '" fill="#fff"/>'
    + '<circle cx="' + x + '" cy="' + y + '" r="' + (r - 4) + '" fill="' + col + '"/>'
    + '<circle cx="' + x + '" cy="' + y + '" r="' + (r - 1.5) + '" fill="none" stroke="' + col + '" stroke-width="1" stroke-dasharray="2 3"/>' + inner + '</g>';
}

// 배지 안 그림 배치 (첫 화면 배지 링 시안 값): dy = 배지 가운데에서 건물 바닥까지, k = 배율, col = 배지 안쪽 색
export const BADGE_ART = {
  gyeongbokgung: { dy: 6, k: 0.5, col: '#fff3d9' },
  ddp: { dy: 4, k: 0.6, col: '#e9f1fb' },
  lotte: { dy: 26, k: 0.48, col: '#e9f1fb' },
  b63: { dy: 22, k: 0.58, col: '#fff3d9' },
  sungnyemun: { dy: 4, k: 0.55, col: '#fbe9e1' },
  namsan: { dy: 20, k: 0.44, col: '#e6f4da' },
};

// draw(x, y, k, s): (x, y)는 건물 바닥 가운데. 지도에서 쓸 때 기준점이 바닥이 되도록 bottom 값을 둔다.
export const LANDMARKS = [
  { id: 'gyeongbokgung', name: '경복궁', lat: 37.5796, lng: 126.9770, draw: palace },
  { id: 'sungnyemun', name: '숭례문', lat: 37.5600, lng: 126.9753, draw: gate },
  { id: 'namsan', name: '남산서울타워', lat: 37.5512, lng: 126.9882, draw: namsan },
  { id: 'ddp', name: 'DDP', lat: 37.5665, lng: 127.0092, draw: ddp },
  { id: 'b63', name: '63빌딩', lat: 37.5198, lng: 126.9402, draw: b63 },
  { id: 'lotte', name: '롯데월드타워', lat: 37.5126, lng: 127.1025, draw: lotte },
];
