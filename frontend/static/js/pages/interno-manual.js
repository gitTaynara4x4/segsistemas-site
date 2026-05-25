(function () {
  'use strict';

  const core = window.SEGInternoCore;
  if (!core) {
    console.error('[SEG Interno] interno-base.js não foi carregado.');
    return;
  }

  const {
    state,
    qs,
    qsa,
    escapeHtml,
    normalize,
    apiFetch,
    initPasswordToggle,
    formatDateTime,
    onReady,
  } = core;

  function manualCardMatchesFilter(card, filtro) {
    if (!card) return false;

    const period = card.getAttribute('data-manual-period') || 'todos';
    const category = card.getAttribute('data-manual-category') || '';

    if (!filtro || filtro === 'todos') return true;

    if (filtro === 'horario-comercial') {
      return period === 'horario-comercial' || period === 'todos';
    }

    if (filtro === 'fora-horario') {
      return period === 'fora-horario' || period === 'todos';
    }

    if (filtro === 'falhas') {
      return category === 'falhas';
    }

    return true;
  }

  function manualCardMatchesSearch(card, busca) {
    if (!card) return false;

    const termo = normalize(busca);
    if (!termo) return true;

    const dataText = card.getAttribute('data-manual-search-text') || '';
    const visibleText = card.textContent || '';
    const haystack = normalize(dataText + ' ' + visibleText);

    return haystack.includes(termo);
  }

  function updateManualCount(visible, total) {
    const count = qs('[data-manual-count]');
    if (!count) return;

    const visibleSafe = Number(visible || 0);
    const totalSafe = Number(total || 0);

    if (visibleSafe === 1) {
      count.textContent = '1 procedimento visível';
      return;
    }

    if (visibleSafe === totalSafe) {
      count.textContent = visibleSafe + ' procedimentos visíveis';
      return;
    }

    count.textContent = visibleSafe + ' de ' + totalSafe + ' procedimentos visíveis';
  }

  function renderManualCards() {
    const page = qs('[data-manual-page]');
    if (!page) return;

    const cards = qsa('[data-manual-card]', page);
    const empty = qs('[data-manual-empty]', page);

    let visible = 0;

    cards.forEach(function (card) {
      const matchesFilter = manualCardMatchesFilter(card, state.manualFiltro);
      const matchesSearch = manualCardMatchesSearch(card, state.manualBusca);
      const show = matchesFilter && matchesSearch;

      card.hidden = !show;

      if (show) {
        visible += 1;
      }
    });

    updateManualCount(visible, cards.length);

    if (empty) {
      empty.classList.toggle('show', visible === 0);
    }
  }

  function setManualFilter(filtro) {
    state.manualFiltro = filtro || 'todos';

    qsa('[data-manual-filter]').forEach(function (btn) {
      const active = btn.getAttribute('data-manual-filter') === state.manualFiltro;
      btn.classList.toggle('active', active);
      btn.setAttribute('aria-pressed', active ? 'true' : 'false');
    });

    renderManualCards();
  }

  function bindManualPage() {
    const page = qs('[data-manual-page]');
    if (!page) return;

    const search = qs('[data-manual-search]', page);
    const filters = qsa('[data-manual-filter]', page);

    if (search) {
      search.addEventListener('input', function () {
        state.manualBusca = search.value || '';
        renderManualCards();
      });
    }

    filters.forEach(function (btn) {
      btn.addEventListener('click', function () {
        setManualFilter(btn.getAttribute('data-manual-filter') || 'todos');
      });
    });

    setManualFilter('todos');
    renderManualCards();
  }



  onReady(function () {
    bindManualPage();
  });
})();
