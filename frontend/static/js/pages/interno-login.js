(function () {
  'use strict';

  const core = window.SEGInternoCore;

  if (!core) {
    console.error('[SEG Interno] interno-base.js não foi carregado.');
    return;
  }

  core.onReady(function () {
    core.initPasswordToggle();
  });
})();