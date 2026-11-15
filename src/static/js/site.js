// 테마 전환과 모바일 메뉴. 외부 의존성 없음.
(function () {
  'use strict';
  var root = document.documentElement;
  var KEY = 'symbolon-theme';

  function current() {
    return root.getAttribute('data-theme') === 'dark' ? 'dark' : 'light';
  }

  function syncToggle(btn) {
    var dark = current() === 'dark';
    var en = (root.getAttribute('lang') || '').indexOf('en') === 0;
    var toLight = en ? 'Switch to light theme' : '밝은 테마로 바꾸기';
    var toDark = en ? 'Switch to dark theme' : '어두운 테마로 바꾸기';
    btn.setAttribute('aria-label', dark ? toLight : toDark);
    btn.setAttribute('aria-pressed', dark ? 'true' : 'false');
  }

  var themeBtn = document.querySelector('.theme-toggle');
  if (themeBtn) {
    syncToggle(themeBtn);
    themeBtn.addEventListener('click', function () {
      var next = current() === 'dark' ? 'light' : 'dark';
      root.setAttribute('data-theme', next);
      try {
        window.localStorage.setItem(KEY, next);
      } catch (e) {
        /* 저장할 수 없어도 이번 페이지에서는 바뀐다 */
      }
      syncToggle(themeBtn);
    });
  }

  // 저장한 선택이 없을 때만 시스템 설정 변경을 따른다.
  if (window.matchMedia) {
    var mq = window.matchMedia('(prefers-color-scheme: dark)');
    var onChange = function (ev) {
      var saved = null;
      try {
        saved = window.localStorage.getItem(KEY);
      } catch (e) {
        saved = null;
      }
      if (saved) return;
      root.setAttribute('data-theme', ev.matches ? 'dark' : 'light');
      if (themeBtn) syncToggle(themeBtn);
    };
    if (mq.addEventListener) mq.addEventListener('change', onChange);
  }

  var navBtn = document.querySelector('.nav-toggle');
  var nav = document.getElementById('site-nav');
  if (navBtn && nav) {
    var setOpen = function (open) {
      navBtn.setAttribute('aria-expanded', open ? 'true' : 'false');
      root.classList.toggle('nav-open', open);
    };
    navBtn.addEventListener('click', function () {
      setOpen(navBtn.getAttribute('aria-expanded') !== 'true');
    });
    document.addEventListener('keydown', function (ev) {
      if (ev.key === 'Escape' && navBtn.getAttribute('aria-expanded') === 'true') {
        setOpen(false);
        navBtn.focus();
      }
    });
    nav.addEventListener('click', function (ev) {
      if (ev.target && ev.target.closest && ev.target.closest('a')) setOpen(false);
    });
    window.addEventListener('resize', function () {
      if (window.innerWidth > 1080) setOpen(false);
    });
  }
  // 스크롤에 맞춰 나타나기(.reveal)와 히어로 그림의 느린 시차. 움직임을 줄인 환경에서는 하지 않는다(CSS도 끈다).
  var still = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var items = document.querySelectorAll('.reveal, .tilt');
  if (!still && 'IntersectionObserver' in window) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) {
          e.target.classList.add('is-in');
          io.unobserve(e.target);
        }
      });
    }, { rootMargin: '0px 0px -8% 0px', threshold: 0.12 });
    items.forEach(function (el) { io.observe(el); });
  } else {
    items.forEach(function (el) { el.classList.add('is-in'); });
  }

  var art = document.querySelector('.token-art');
  if (art && !still) {
    var ticking = false;
    window.addEventListener('scroll', function () {
      if (ticking) return;
      ticking = true;
      window.requestAnimationFrame(function () {
        var y = Math.min(window.scrollY, 900);
        art.style.setProperty('--py', String(Math.round(y * 0.12)));
        ticking = false;
      });
    }, { passive: true });
  }
})();
