(function () {
  'use strict';

  // AOS
  if (window.AOS) {
    AOS.init({
      once: true,
      offset: 100
    });
  }

  // Sticky Header
  const header = document.getElementById('header');
  function onScrollHeader() {
    if (!header) return;
    if (window.scrollY > 50) header.classList.add('scrolled');
    else header.classList.remove('scrolled');
  }
  window.addEventListener('scroll', onScrollHeader, { passive: true });
  onScrollHeader();

  // Menu Mobile
  const nav = document.getElementById('navLinks');
  const toggle = document.getElementById('mobileToggle');

  function toggleMenu() {
    if (!nav) return;
    nav.classList.toggle('active');
  }

  if (toggle) toggle.addEventListener('click', toggleMenu);

  // Fecha menu ao clicar em link (mobile)
  if (nav) {
    nav.addEventListener('click', (e) => {
      const a = e.target && e.target.closest ? e.target.closest('a') : null;
      if (!a) return;
      if (nav.classList.contains('active')) nav.classList.remove('active');
    });
  }
})();
