// 첫 그리기 전에 테마를 정한다(깜빡임 방지). 저장한 선택이 있으면 그것, 없으면 시스템 설정.
(function () {
  var root = document.documentElement;
  root.classList.add('js');
  var saved = null;
  try {
    saved = window.localStorage.getItem('symbolon-theme');
  } catch (e) {
    saved = null;
  }
  if (saved !== 'light' && saved !== 'dark') {
    saved = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }
  root.setAttribute('data-theme', saved);
})();
