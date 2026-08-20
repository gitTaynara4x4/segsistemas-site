(function () {
  'use strict';

  const core = window.SEGInternoCore;
  if (!core) return;
  const { qs, escapeHtml, formatDateTime, apiFetch, onReady } = core;

  const groups = [
    ['ocorrencias', 'Ocorrências', 'fa-regular fa-clipboard'],
    ['funcionarios', 'Funcionários', 'fa-solid fa-users'],
    ['passagens', 'Passagens de plantão', 'fa-solid fa-right-left'],
    ['tarefas', 'Pendências / Tarefas', 'fa-solid fa-list-check'],
    ['documentos', 'Documentos', 'fa-regular fa-folder-open'],
  ];

  let timer = null;
  let controller = null;

  function resultMeta(item) {
    const meta = item.meta || {};
    const parts = [];
    if (meta.prioridade) parts.push(String(meta.prioridade).replaceAll('_', ' '));
    if (meta.status) parts.push(String(meta.status).replaceAll('_', ' '));
    if (meta.categoria) parts.push(meta.categoria);
    if (meta.tipo) parts.push(meta.tipo);
    if (meta.ativo === false) parts.push('inativo');
    return parts.filter(Boolean).join(' · ');
  }

  function resultDate(item) {
    if (!item.data) return '';
    return formatDateTime(item.data);
  }

  function renderGroup(key, title, icon, items) {
    const section = document.createElement('section');
    section.className = 'seg-search-group';
    section.innerHTML = `
      <div class="seg-search-group-head">
        <div class="seg-search-group-title">
          <span class="seg-search-group-icon"><i class="${icon}"></i></span>
          <strong>${escapeHtml(title)}</strong>
          <span>${items.length}</span>
        </div>
      </div>
      <div class="seg-search-list"></div>`;

    const list = section.querySelector('.seg-search-list');
    items.forEach(item => {
      const a = document.createElement('a');
      a.className = 'seg-search-result';
      a.href = item.url || '#';
      a.innerHTML = `
        <div class="seg-search-result-main">
          <strong>${escapeHtml(item.titulo || 'Sem título')}</strong>
          <span>${escapeHtml(item.subtitulo || '')}</span>
          ${item.detalhe ? `<small>${escapeHtml(item.detalhe)}</small>` : ''}
        </div>
        <div class="seg-search-result-side">
          ${resultMeta(item) ? `<span class="seg-search-meta">${escapeHtml(resultMeta(item))}</span>` : ''}
          ${resultDate(item) ? `<time>${escapeHtml(resultDate(item))}</time>` : ''}
          <i class="fa-solid fa-chevron-right"></i>
        </div>`;
      list.appendChild(a);
    });

    return section;
  }

  function showOnly(id) {
    ['search-empty', 'search-minimum', 'search-loading', 'search-no-results'].forEach(name => {
      const el = qs('#' + name);
      if (el) el.hidden = name !== id;
    });
  }

  function render(data) {
    const root = qs('#search-results');
    const toolbar = qs('#search-toolbar');
    const summary = qs('#search-summary');
    const queryLabel = qs('#search-query-label');
    if (!root) return;

    root.querySelectorAll('.seg-search-group').forEach(el => el.remove());

    const total = Number(data.total || 0);
    const q = data.q || '';
    toolbar.hidden = !q;
    if (summary) summary.textContent = `${total} ${total === 1 ? 'resultado' : 'resultados'}`;
    if (queryLabel) queryLabel.textContent = q ? `para “${q}”` : '';

    if (!total) {
      showOnly('search-no-results');
      return;
    }

    ['search-empty', 'search-minimum', 'search-loading', 'search-no-results'].forEach(name => {
      const el = qs('#' + name);
      if (el) el.hidden = true;
    });

    groups.forEach(([key, title, icon]) => {
      const items = (data.resultados || {})[key] || [];
      if (items.length) root.appendChild(renderGroup(key, title, icon, items));
    });
  }

  async function search(value, pushUrl) {
    const q = String(value || '').trim();
    const input = qs('#global-search-input');
    if (input && input.value !== q) input.value = q;

    if (q.length < 2) {
      if (controller) controller.abort();
      qs('#search-toolbar').hidden = true;
      showOnly(q.length ? 'search-minimum' : 'search-empty');
      qs('#search-results').querySelectorAll('.seg-search-group').forEach(el => el.remove());
      return;
    }

    if (controller) controller.abort();
    controller = new AbortController();
    showOnly('search-loading');
    qs('#search-results').querySelectorAll('.seg-search-group').forEach(el => el.remove());

    try {
      const data = await apiFetch('/api/interno/busca?q=' + encodeURIComponent(q), { signal: controller.signal });
      render(data);
      if (pushUrl) history.replaceState({}, '', '/interno/busca?q=' + encodeURIComponent(q));
    } catch (error) {
      if (error.name === 'AbortError') return;
      const no = qs('#search-no-results');
      if (no) {
        no.hidden = false;
        no.querySelector('strong').textContent = 'Não foi possível pesquisar';
        no.querySelector('span').textContent = error.message || 'Tente novamente.';
      }
    }
  }

  onReady(() => {
    const form = qs('#global-search-form');
    const input = qs('#global-search-input');
    const clear = qs('#search-clear');
    if (!form || !input) return;

    const initial = new URLSearchParams(window.location.search).get('q') || '';
    input.value = initial;
    if (initial) search(initial, false);
    else input.focus();

    form.addEventListener('submit', event => {
      event.preventDefault();
      search(input.value, true);
    });

    input.addEventListener('input', () => {
      clearTimeout(timer);
      const value = input.value;
      timer = setTimeout(() => search(value, true), value.trim().length >= 2 ? 220 : 0);
    });

    if (clear) {
      clear.addEventListener('click', () => {
        input.value = '';
        history.replaceState({}, '', '/interno/busca');
        qs('#search-toolbar').hidden = true;
        qs('#search-results').querySelectorAll('.seg-search-group').forEach(el => el.remove());
        showOnly('search-empty');
        input.focus();
      });
    }

    document.addEventListener('keydown', event => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        input.focus();
        input.select();
      }
    });
  });
})();
