(function () {
  'use strict';

  const core = window.SEGInternoCore;
  if (!core) return;

  const { qs, escapeHtml, normalize, apiFetch, onReady } = core;
  const state = {
    tarefas: [],
    funcionarios: [],
    carregando: false,
    salvando: false,
  };

  function setMessage(type, text) {
    const box = qs('#tarefas-message');
    if (!box) return;
    box.className = 'tarefas-message' + (type ? ' ' + type : '');
    box.textContent = text || '';
    box.hidden = !text;
  }

  function formatDate(value) {
    if (!value) return 'Sem prazo';
    const parts = String(value).split('-');
    if (parts.length !== 3) return value;
    return parts[2] + '/' + parts[1] + '/' + parts[0];
  }

  function updateStats(resumo) {
    const map = {
      '#tarefas-stat-abertas': resumo.abertas,
      '#tarefas-stat-atrasadas': resumo.atrasadas,
      '#tarefas-stat-hoje': resumo.vencem_hoje,
      '#tarefas-stat-minhas': resumo.minhas,
    };
    Object.keys(map).forEach(function (selector) {
      const el = qs(selector);
      if (el) el.textContent = Number(map[selector] || 0);
    });
  }

  function filteredTasks() {
    const busca = normalize(qs('#tarefas-busca')?.value);
    const status = normalize(qs('#tarefas-filtro-status')?.value);
    const prioridade = normalize(qs('#tarefas-filtro-prioridade')?.value);
    const responsavel = String(qs('#tarefas-filtro-responsavel')?.value || '');

    return state.tarefas.filter(function (item) {
      if (status && normalize(item.status) !== status) return false;
      if (prioridade && normalize(item.prioridade) !== prioridade) return false;
      if (responsavel && String(item.responsavel_id || '') !== responsavel) return false;
      if (!busca) return true;
      return normalize([item.titulo, item.descricao, item.responsavel_nome].join(' ')).includes(busca);
    });
  }

  function taskMeta(item) {
    const dueClass = item.atrasada ? ' is-overdue' : (item.vence_hoje ? ' is-today' : '');
    const dueIcon = item.atrasada ? 'fa-triangle-exclamation' : 'fa-calendar-day';
    const responsible = item.responsavel_nome || 'Sem responsável';
    return `
      <div class="tarefa-meta">
        <span><i class="fa-regular fa-user"></i>${escapeHtml(responsible)}</span>
        <span class="tarefa-due${dueClass}"><i class="fa-solid ${dueIcon}"></i>${escapeHtml(formatDate(item.prazo))}</span>
      </div>
    `;
  }

  function renderTasks() {
    const list = qs('#tarefas-list');
    const empty = qs('#tarefas-empty');
    if (!list || !empty) return;

    const tasks = filteredTasks();
    empty.hidden = tasks.length > 0;

    list.innerHTML = tasks.map(function (item) {
      const done = item.status === 'concluida';
      const canceled = item.status === 'cancelada';
      const open = !done && !canceled;
      const description = item.descricao ? `<p>${escapeHtml(item.descricao)}</p>` : '';
      const conclude = open ? `<button class="tarefa-action success" data-concluir="${item.id}"><i class="fa-solid fa-check"></i>Concluir</button>` : '';
      const reopen = (done || canceled) ? `<button class="tarefa-action" data-reabrir="${item.id}"><i class="fa-solid fa-rotate-left"></i>Reabrir</button>` : '';
      const cancel = open ? `<button class="tarefa-action danger" data-cancelar="${item.id}" title="Cancelar"><i class="fa-solid fa-ban"></i></button>` : '';

      return `
        <article class="tarefa-row priority-${escapeHtml(item.prioridade)}${item.atrasada ? ' is-overdue' : ''}${done ? ' is-done' : ''}">
          <div class="tarefa-main">
            <div class="tarefa-title-line">
              <h3>${escapeHtml(item.titulo)}</h3>
              <div class="tarefa-badges">
                <span class="tarefa-badge priority-${escapeHtml(item.prioridade)}">${escapeHtml(item.prioridade_label)}</span>
                <span class="tarefa-badge status-${escapeHtml(item.status)}">${escapeHtml(item.status_label)}</span>
              </div>
            </div>
            ${description}
            ${taskMeta(item)}
          </div>
          <div class="tarefa-actions">
            <button class="tarefa-action" data-editar="${item.id}"><i class="fa-solid fa-pen"></i>Editar</button>
            ${conclude}
            ${reopen}
            ${cancel}
          </div>
        </article>
      `;
    }).join('');
  }

  function resetForm(focus) {
    const form = qs('#tarefa-form');
    if (form) form.reset();
    if (qs('#tarefa-id')) qs('#tarefa-id').value = '';
    if (qs('#tarefa-prioridade')) qs('#tarefa-prioridade').value = 'media';
    if (qs('#tarefa-status')) qs('#tarefa-status').value = 'pendente';
    const title = qs('#tarefa-form-title');
    if (title) title.textContent = 'Nova tarefa';
    const btn = qs('#btn-salvar-tarefa');
    if (btn) btn.innerHTML = '<i class="fa-solid fa-floppy-disk"></i> Salvar tarefa';
    if (focus) qs('#tarefa-titulo')?.focus();
  }

  function editTask(id) {
    const item = state.tarefas.find(function (task) { return String(task.id) === String(id); });
    if (!item) return;

    qs('#tarefa-id').value = item.id || '';
    qs('#tarefa-titulo').value = item.titulo || '';
    qs('#tarefa-responsavel').value = item.responsavel_id || '';
    qs('#tarefa-prioridade').value = item.prioridade || 'media';
    qs('#tarefa-prazo').value = item.prazo || '';
    qs('#tarefa-status').value = item.status || 'pendente';
    qs('#tarefa-descricao').value = item.descricao || '';
    qs('#tarefa-form-title').textContent = 'Editar tarefa';
    qs('#btn-salvar-tarefa').innerHTML = '<i class="fa-solid fa-floppy-disk"></i> Salvar alterações';
    qs('#tarefa-form-panel')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    setTimeout(function () { qs('#tarefa-titulo')?.focus(); }, 250);
  }

  function formData() {
    const select = qs('#tarefa-responsavel');
    const selected = select && select.selectedOptions ? select.selectedOptions[0] : null;
    return {
      id: qs('#tarefa-id')?.value || '',
      titulo: qs('#tarefa-titulo')?.value.trim() || '',
      descricao: qs('#tarefa-descricao')?.value.trim() || '',
      responsavel_id: select?.value || null,
      responsavel_nome: selected && selected.value ? selected.textContent.trim() : '',
      prioridade: qs('#tarefa-prioridade')?.value || 'media',
      prazo: qs('#tarefa-prazo')?.value || '',
      status: qs('#tarefa-status')?.value || 'pendente',
    };
  }

  async function loadTasks() {
    if (state.carregando) return;
    state.carregando = true;
    const btn = qs('#btn-reload-tarefas');
    if (btn) btn.disabled = true;
    try {
      const data = await apiFetch('/api/interno/tarefas');
      state.tarefas = Array.isArray(data.tarefas) ? data.tarefas : [];
      state.funcionarios = Array.isArray(data.funcionarios) ? data.funcionarios : [];
      updateStats(data.resumo || {});
      renderTasks();
      setMessage('', '');
    } catch (error) {
      setMessage('error', error.message || 'Erro ao carregar tarefas.');
    } finally {
      state.carregando = false;
      if (btn) btn.disabled = false;
    }
  }

  async function saveTask(event) {
    event.preventDefault();
    if (state.salvando) return;
    const data = formData();
    if (!data.titulo) {
      setMessage('error', 'Informe o título da tarefa.');
      qs('#tarefa-titulo')?.focus();
      return;
    }

    state.salvando = true;
    const btn = qs('#btn-salvar-tarefa');
    if (btn) {
      btn.disabled = true;
      btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Salvando...';
    }

    try {
      const editing = Boolean(data.id);
      const url = editing ? '/api/interno/tarefas/' + encodeURIComponent(data.id) : '/api/interno/tarefas';
      await apiFetch(url, { method: editing ? 'PUT' : 'POST', body: JSON.stringify(data) });
      resetForm(false);
      await loadTasks();
      setMessage('success', editing ? 'Tarefa atualizada.' : 'Tarefa criada com sucesso.');
    } catch (error) {
      setMessage('error', error.message || 'Erro ao salvar tarefa.');
    } finally {
      state.salvando = false;
      if (btn) {
        btn.disabled = false;
        if (qs('#tarefa-id')?.value) btn.innerHTML = '<i class="fa-solid fa-floppy-disk"></i> Salvar alterações';
        else btn.innerHTML = '<i class="fa-solid fa-floppy-disk"></i> Salvar tarefa';
      }
    }
  }

  async function action(id, actionName, confirmText) {
    if (!id) return;
    if (confirmText && !window.confirm(confirmText)) return;
    try {
      await apiFetch('/api/interno/tarefas/' + encodeURIComponent(id) + '/' + actionName, { method: 'POST', body: '{}' });
      await loadTasks();
      setMessage('success', actionName === 'concluir' ? 'Tarefa concluída.' : actionName === 'reabrir' ? 'Tarefa reaberta.' : 'Tarefa cancelada.');
    } catch (error) {
      setMessage('error', error.message || 'Erro ao atualizar tarefa.');
    }
  }

  function bind() {
    if (!qs('#tarefas-page')) return;
    qs('#tarefa-form')?.addEventListener('submit', saveTask);
    qs('#btn-nova-tarefa')?.addEventListener('click', function () {
      resetForm(true);
      qs('#tarefa-form-panel')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
    qs('#btn-fechar-form')?.addEventListener('click', function () { resetForm(false); });
    qs('#btn-cancelar-edicao')?.addEventListener('click', function () { resetForm(false); });
    qs('#btn-reload-tarefas')?.addEventListener('click', loadTasks);

    ['#tarefas-busca', '#tarefas-filtro-status', '#tarefas-filtro-prioridade', '#tarefas-filtro-responsavel'].forEach(function (selector) {
      const el = qs(selector);
      if (!el) return;
      el.addEventListener(el.tagName === 'INPUT' ? 'input' : 'change', renderTasks);
    });

    qs('#tarefas-list')?.addEventListener('click', function (event) {
      const edit = event.target.closest('[data-editar]');
      const conclude = event.target.closest('[data-concluir]');
      const reopen = event.target.closest('[data-reabrir]');
      const cancel = event.target.closest('[data-cancelar]');
      if (edit) editTask(edit.dataset.editar);
      else if (conclude) action(conclude.dataset.concluir, 'concluir', 'Marcar esta tarefa como concluída?');
      else if (reopen) action(reopen.dataset.reabrir, 'reabrir', 'Reabrir esta tarefa?');
      else if (cancel) action(cancel.dataset.cancelar, 'cancelar', 'Cancelar esta tarefa?');
    });

    loadTasks();
  }

  onReady(bind);
})();
