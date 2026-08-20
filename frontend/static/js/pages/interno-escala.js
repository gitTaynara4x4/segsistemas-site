(function () {
  'use strict';
  const core = window.SEGInternoCore;
  if (!core) return;
  const { qs, escapeHtml, normalize, apiFetch, onReady } = core;

  const state = { escalas: [], podeGerenciar: false, carregando: false };

  function dateISO(d) {
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${y}-${m}-${day}`;
  }
  function brDate(value) {
    if (!value) return '-';
    const p = String(value).split('-');
    return p.length === 3 ? `${p[2]}/${p[1]}/${p[0]}` : value;
  }
  function dayLabel(value) {
    if (!value) return '';
    const d = new Date(`${value}T12:00:00`);
    return d.toLocaleDateString('pt-BR', { weekday: 'short' }).replace('.', '');
  }
  function setMessage(type, text) {
    const el = qs('#escala-message');
    if (!el) return;
    el.hidden = !text;
    el.className = `escala-message${type ? ' ' + type : ''}`;
    el.textContent = text || '';
  }
  function updateStats(r) {
    r = r || {};
    const map = {
      '#escala-stat-hoje': r.total_hoje,
      '#escala-stat-andamento': r.em_andamento,
      '#escala-stat-folgas': r.folgas,
      '#escala-stat-substituicoes': r.substituicoes,
    };
    Object.entries(map).forEach(([sel, val]) => { const el = qs(sel); if (el) el.textContent = Number(val || 0); });
    const next = qs('#escala-proximo-texto');
    if (next) {
      const item = r.proxima_escala;
      next.textContent = item
        ? `${brDate(item.data_escala)} · ${item.horario_inicio || '--:--'} às ${item.horario_fim || '--:--'}${item.tem_substituicao ? ' · substituição' : ''}`
        : 'Nenhum próximo plantão agendado';
    }
  }
  function statusClass(status) { return `status-${String(status || '').replace(/[^a-z_]/g, '')}`; }

  function render() {
    const list = qs('#escala-list');
    const empty = qs('#escala-empty');
    if (!list || !empty) return;
    const busca = normalize(qs('#escala-busca')?.value);
    const status = normalize(qs('#escala-filtro-status')?.value);
    const filtered = state.escalas.filter(item => {
      if (status && normalize(item.status) !== status) return false;
      if (!busca) return true;
      return normalize([item.funcionario_nome, item.substituto_nome, item.observacao].join(' ')).includes(busca);
    });
    empty.hidden = filtered.length > 0;

    let previousDate = '';
    list.innerHTML = filtered.map(item => {
      const dateHeader = item.data_escala !== previousDate
        ? `<div class="escala-day-divider"><strong>${escapeHtml(brDate(item.data_escala))}</strong><span>${escapeHtml(dayLabel(item.data_escala))}</span></div>` : '';
      previousDate = item.data_escala;
      const isFolga = item.status === 'folga';
      const efetivo = item.efetivo_nome || item.funcionario_nome || 'Funcionário';
      const substitution = item.tem_substituicao ? `
        <div class="escala-swap-note"><i class="fa-solid fa-right-left"></i><span><s>${escapeHtml(item.funcionario_nome)}</s> <strong>${escapeHtml(item.substituto_nome)}</strong>${item.motivo_substituicao ? ` · ${escapeHtml(item.motivo_substituicao)}` : ''}</span></div>` : '';
      const actions = state.podeGerenciar ? `
        <div class="escala-row-actions">
          <button type="button" data-edit="${item.id}"><i class="fa-regular fa-pen-to-square"></i> Editar</button>
          ${item.status !== 'cancelado' ? `<button type="button" class="danger" data-cancel="${item.id}" title="Cancelar"><i class="fa-solid fa-ban"></i></button>` : ''}
        </div>` : '';
      return `${dateHeader}
        <article class="escala-row ${statusClass(item.status)}">
          <div class="escala-time-box">
            ${isFolga ? '<i class="fa-regular fa-moon"></i><strong>Folga</strong>' : `<strong>${escapeHtml(item.horario_inicio || '--:--')}</strong><span>${escapeHtml(item.horario_fim || '--:--')}</span>`}
          </div>
          <div class="escala-person">
            <div class="escala-avatar">${escapeHtml((efetivo || 'F').slice(0,1).toUpperCase())}</div>
            <div>
              <strong>${escapeHtml(efetivo)}</strong>
              <small>${item.tem_substituicao ? 'Substituindo ' + escapeHtml(item.funcionario_nome) : (isFolga ? 'Folga programada' : 'Escala regular')}</small>
              ${substitution}
            </div>
          </div>
          <span class="escala-status ${statusClass(item.status)}">${escapeHtml(item.status_label || '')}</span>
          <div class="escala-integration">${item.plantao_id ? `<i class="fa-solid fa-link"></i> Plantão #${item.plantao_id}` : (isFolga ? '' : '<i class="fa-regular fa-clock"></i> aguardando plantão')}</div>
          ${actions}
        </article>`;
    }).join('');
  }

  function resetForm() {
    if (!state.podeGerenciar) return;
    qs('#escala-id').value = '';
    qs('#escala-form-title').textContent = 'Nova escala';
    qs('#escala-funcionario').value = '';
    qs('#escala-data').value = dateISO(new Date());
    qs('#escala-status').value = 'agendado';
    qs('#escala-inicio').value = '18:00';
    qs('#escala-fim').value = '06:00';
    qs('#escala-substituto').value = '';
    qs('#escala-motivo').value = '';
    qs('#escala-observacao').value = '';
    syncConditionalFields();
  }
  function syncConditionalFields() {
    if (!state.podeGerenciar) return;
    const folga = qs('#escala-status').value === 'folga';
    qs('#escala-horarios-wrap').hidden = folga;
    const temSub = Boolean(qs('#escala-substituto').value);
    qs('#escala-motivo-wrap').hidden = !temSub;
  }
  function edit(id) {
    const item = state.escalas.find(x => Number(x.id) === Number(id));
    if (!item || !state.podeGerenciar) return;
    qs('#escala-id').value = item.id;
    qs('#escala-form-title').textContent = 'Editar escala';
    qs('#escala-funcionario').value = item.funcionario_id || '';
    qs('#escala-data').value = item.data_escala || '';
    qs('#escala-status').value = item.status === 'cancelado' ? 'agendado' : item.status;
    qs('#escala-inicio').value = item.horario_inicio || '18:00';
    qs('#escala-fim').value = item.horario_fim || '06:00';
    qs('#escala-substituto').value = item.substituto_id || '';
    qs('#escala-motivo').value = item.motivo_substituicao || '';
    qs('#escala-observacao').value = item.observacao || '';
    syncConditionalFields();
    qs('#escala-form-panel')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  async function load() {
    if (state.carregando) return;
    state.carregando = true;
    try {
      const inicio = qs('#escala-filtro-inicio')?.value || '';
      const fim = qs('#escala-filtro-fim')?.value || '';
      const data = await apiFetch(`/api/interno/escala?inicio=${encodeURIComponent(inicio)}&fim=${encodeURIComponent(fim)}`);
      state.escalas = Array.isArray(data.escalas) ? data.escalas : [];
      state.podeGerenciar = Boolean(data.pode_gerenciar);
      updateStats(data.resumo || {});
      render();
      setMessage('', '');
    } catch (e) { setMessage('error', e.message || 'Erro ao carregar escala.'); }
    finally { state.carregando = false; }
  }

  async function save(event) {
    event.preventDefault();
    if (!state.podeGerenciar) return;
    const id = qs('#escala-id').value;
    const payload = {
      funcionario_id: qs('#escala-funcionario').value,
      data_escala: qs('#escala-data').value,
      status: qs('#escala-status').value,
      horario_inicio: qs('#escala-inicio').value,
      horario_fim: qs('#escala-fim').value,
      substituto_id: qs('#escala-substituto').value || null,
      motivo_substituicao: qs('#escala-motivo').value.trim(),
      observacao: qs('#escala-observacao').value.trim(),
    };
    const btn = qs('#btn-salvar-escala');
    if (btn) btn.disabled = true;
    try {
      await apiFetch(id ? `/api/interno/escala/${id}` : '/api/interno/escala', { method: id ? 'PUT' : 'POST', body: JSON.stringify(payload) });
      setMessage('success', id ? 'Escala atualizada.' : 'Escala criada.');
      resetForm();
      await load();
    } catch (e) { setMessage('error', e.message || 'Erro ao salvar escala.'); }
    finally { if (btn) btn.disabled = false; }
  }

  async function cancel(id) {
    if (!window.confirm('Cancelar esta escala?')) return;
    try {
      await apiFetch(`/api/interno/escala/${id}/cancelar`, { method: 'POST', body: '{}' });
      setMessage('success', 'Escala cancelada.');
      await load();
    } catch (e) { setMessage('error', e.message || 'Erro ao cancelar escala.'); }
  }

  function bind() {
    const page = qs('#escala-page');
    if (!page) return;
    state.podeGerenciar = page.dataset.canManage === '1';
    const today = new Date();
    const start = new Date(today); start.setDate(start.getDate() - 2);
    const end = new Date(today); end.setDate(end.getDate() + 14);
    qs('#escala-filtro-inicio').value = dateISO(start);
    qs('#escala-filtro-fim').value = dateISO(end);
    if (state.podeGerenciar) resetForm();

    qs('#escala-form')?.addEventListener('submit', save);
    qs('#btn-nova-escala')?.addEventListener('click', () => { resetForm(); qs('#escala-form-panel')?.scrollIntoView({ behavior: 'smooth' }); });
    qs('#btn-limpar-escala')?.addEventListener('click', resetForm);
    qs('#btn-cancelar-edicao')?.addEventListener('click', resetForm);
    qs('#escala-status')?.addEventListener('change', syncConditionalFields);
    qs('#escala-substituto')?.addEventListener('change', syncConditionalFields);
    qs('#btn-reload-escala')?.addEventListener('click', load);
    qs('#escala-filtro-inicio')?.addEventListener('change', load);
    qs('#escala-filtro-fim')?.addEventListener('change', load);
    qs('#escala-filtro-status')?.addEventListener('change', render);
    qs('#escala-busca')?.addEventListener('input', render);
    qs('#escala-list')?.addEventListener('click', e => {
      const editBtn = e.target.closest('[data-edit]');
      if (editBtn) return edit(editBtn.dataset.edit);
      const cancelBtn = e.target.closest('[data-cancel]');
      if (cancelBtn) return cancel(cancelBtn.dataset.cancel);
    });
    load();
  }
  onReady(bind);
})();
