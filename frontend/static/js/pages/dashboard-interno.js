(function () {
  'use strict';

  function qs(selector, root) {
    return (root || document).querySelector(selector);
  }

  function qsa(selector, root) {
    return Array.from((root || document).querySelectorAll(selector));
  }

  function pad(value) {
    return String(value).padStart(2, '0');
  }

  function formatNow() {
    const now = new Date();
    return (
      pad(now.getDate()) + '/' +
      pad(now.getMonth() + 1) + '/' +
      now.getFullYear() + ' ' +
      pad(now.getHours()) + ':' +
      pad(now.getMinutes())
    );
  }

  function updateClock() {
    const el = qs('#dash-current-time');
    if (!el) return;
    el.textContent = formatNow();
  }

  function markCurrentLink() {
    const current = (window.location.pathname || '/interno').replace(/\/$/, '') || '/interno';

    qsa('a[href]').forEach(function (link) {
      const href = link.getAttribute('href');
      if (!href || href.startsWith('#')) return;

      const normalized = href.replace(/\/$/, '') || '/interno';
      if (normalized === current) {
        link.classList.add('active');
      }
    });
  }

  function bindRefresh() {
    const btn = qs('#dash-refresh-btn');
    if (!btn) return;

    btn.addEventListener('click', function () {
      btn.disabled = true;
      btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i>';
      window.setTimeout(function () {
        window.location.reload();
      }, 180);
    });
  }

  function init() {
    if (!qs('#dashboard-page')) return;

    updateClock();
    window.setInterval(updateClock, 30000);

    markCurrentLink();
    bindRefresh();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
