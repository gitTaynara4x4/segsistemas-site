(function () {
  'use strict';

  function closeGroups(except) {
    document.querySelectorAll('[data-segv-nav-group].open').forEach(function (group) {
      if (group !== except) group.classList.remove('open');
    });
  }

  function init() {
    var mobileButton = document.querySelector('[data-segv-mobile-menu]');
    var nav = document.querySelector('[data-segv-main-nav]');

    if (mobileButton && nav) {
      mobileButton.addEventListener('click', function () {
        var open = nav.classList.toggle('open');
        mobileButton.setAttribute('aria-expanded', open ? 'true' : 'false');
      });
    }

    document.querySelectorAll('[data-segv-nav-group]').forEach(function (group) {
      var trigger = group.querySelector('[data-segv-nav-trigger]');
      if (!trigger) return;

      trigger.addEventListener('click', function (event) {
        event.stopPropagation();
        var nextState = !group.classList.contains('open');
        closeGroups(group);
        group.classList.toggle('open', nextState);
      });
    });

    var user = document.querySelector('[data-segv-user]');
    var userButton = document.querySelector('[data-segv-user-button]');
    if (user && userButton) {
      userButton.addEventListener('click', function (event) {
        event.stopPropagation();
        var open = user.classList.toggle('open');
        userButton.setAttribute('aria-expanded', open ? 'true' : 'false');
        closeGroups();
      });
    }

    var refreshButton = document.querySelector('[data-segv-refresh]');
    if (refreshButton) {
      refreshButton.addEventListener('click', function () {
        window.location.reload();
      });
    }

    document.addEventListener('click', function () {
      closeGroups();
      if (user) user.classList.remove('open');
      if (userButton) userButton.setAttribute('aria-expanded', 'false');
    });

    document.addEventListener('keydown', function (event) {
      if (event.key !== 'Escape') return;
      closeGroups();
      if (user) user.classList.remove('open');
      if (nav) nav.classList.remove('open');
      if (mobileButton) mobileButton.setAttribute('aria-expanded', 'false');
      if (userButton) userButton.setAttribute('aria-expanded', 'false');
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
