// 화면 상태·이벤트 (F1: 첫 화면만)
import { renderHome } from './home.js';

const $ = (sel) => document.querySelector(sel);

function send(message) {
  // F3에서 실제 전송으로 교체
  console.log('send', message);
}

renderHome($('#home'), {
  onChip: (chip) => send(chip.message),
});

$('#inp').addEventListener('submit', (e) => {
  e.preventDefault();
  const text = $('#msg').value.trim();
  if (!text) return;
  $('#msg').value = '';
  send(text);
});
