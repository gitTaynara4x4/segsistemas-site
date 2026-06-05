(function () {
  'use strict';

  function initPasswordToggle() {
    const buttons = document.querySelectorAll('[data-toggle-password]');

    buttons.forEach(function (button) {
      button.addEventListener('click', function () {
        const wrap = button.closest('.input-wrap');
        if (!wrap) return;

        const input = wrap.querySelector('input');
        const eyeOpen = button.querySelector('.eye-open');
        const eyeClosed = button.querySelector('.eye-closed');

        if (!input) return;

        const showPassword = input.type === 'password';
        input.type = showPassword ? 'text' : 'password';

        button.setAttribute('aria-label', showPassword ? 'Ocultar senha' : 'Mostrar senha');
        button.setAttribute('title', showPassword ? 'Ocultar senha' : 'Mostrar senha');

        if (eyeOpen && eyeClosed) {
          eyeOpen.style.display = showPassword ? 'none' : 'block';
          eyeClosed.style.display = showPassword ? 'block' : 'none';
        }

        input.focus();
      });
    });
  }

  function initSubmitLoading() {
    const form = document.querySelector('[data-login-form]');
    const button = document.querySelector('[data-login-submit]');
    const text = document.querySelector('[data-submit-text]');

    if (!form || !button) return;

    form.addEventListener('submit', function () {
      if (!form.checkValidity()) return;

      button.disabled = true;
      button.classList.add('is-loading');

      if (text) {
        text.textContent = 'Entrando...';
      }
    });
  }

  function init() {
    initPasswordToggle();
    initSubmitLoading();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();