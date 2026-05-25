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

  function setOcorrenciaMessage(type, text) {
    const box = qs('#ocorrencia-message');
    if (!box) return;

    if (!text) {
      box.className = 'oc-message';
      box.textContent = '';
      return;
    }

    box.className = 'oc-message show ' + (type || 'success');
    box.textContent = text;
  }

  function updateOcorrenciaStats(resumo) {
    const safe = resumo || {};
    qsa('[data-ocorrencia-stat]').forEach(function (el) {
      const key = el.getAttribute('data-ocorrencia-stat');
      el.textContent = String(safe[key] || 0);
    });
  }

  function getOcorrenciaFormData() {
    return {
      id: qs('#ocorrencia-id') ? qs('#ocorrencia-id').value : '',
      titulo: qs('#ocorrencia-titulo') ? qs('#ocorrencia-titulo').value.trim() : '',
      tipo: qs('#ocorrencia-tipo') ? qs('#ocorrencia-tipo').value : 'outro',
      prioridade: qs('#ocorrencia-prioridade') ? qs('#ocorrencia-prioridade').value : 'media',
      status: qs('#ocorrencia-status') ? qs('#ocorrencia-status').value : 'aberta',
      responsavel: qs('#ocorrencia-responsavel') ? qs('#ocorrencia-responsavel').value.trim() : '',
      cliente_nome: qs('#ocorrencia-cliente') ? qs('#ocorrencia-cliente').value.trim() : '',
      local: qs('#ocorrencia-local') ? qs('#ocorrencia-local').value.trim() : '',
      descricao: qs('#ocorrencia-descricao') ? qs('#ocorrencia-descricao').value.trim() : '',
      providencia: qs('#ocorrencia-providencia') ? qs('#ocorrencia-providencia').value.trim() : '',
      solucao: qs('#ocorrencia-solucao') ? qs('#ocorrencia-solucao').value.trim() : '',
    };
  }

  function setSelectValue(selector, value, fallback) {
    const select = qs(selector);
    if (!select) return;

    const wanted = String(value || fallback || '');
    const exists = Array.from(select.options).some(function (option) {
      return option.value === wanted;
    });

    select.value = exists ? wanted : (fallback || '');
  }

  function resetOcorrenciaForm() {
    const form = qs('#ocorrencia-form');
    if (form) form.reset();

    const id = qs('#ocorrencia-id');
    if (id) id.value = '';

    const title = qs('#ocorrencia-form-title');
    if (title) title.textContent = 'Nova ocorrência';

    setSelectValue('#ocorrencia-tipo', 'cliente', 'outro');
    setSelectValue('#ocorrencia-prioridade', 'media', 'media');
    setSelectValue('#ocorrencia-status', 'aberta', 'aberta');

    const solucaoWrap = qs('#ocorrencia-solucao-wrap');
    if (solucaoWrap) solucaoWrap.hidden = true;

    const solucao = qs('#ocorrencia-solucao');
    if (solucao) solucao.value = '';

    const cancel = qs('#btn-cancel-ocorrencia');
    if (cancel) cancel.hidden = true;

    const btn = qs('#btn-save-ocorrencia');
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = '<i class="fa-solid fa-floppy-disk"></i> Salvar ocorrência';
    }

    setOcorrenciaMessage('', '');
  }

  function fillOcorrenciaForm(ocorrencia) {
    if (!ocorrencia) return;

    const id = qs('#ocorrencia-id');
    const titulo = qs('#ocorrencia-titulo');
    const responsavel = qs('#ocorrencia-responsavel');
    const cliente = qs('#ocorrencia-cliente');
    const local = qs('#ocorrencia-local');
    const descricao = qs('#ocorrencia-descricao');
    const providencia = qs('#ocorrencia-providencia');
    const solucao = qs('#ocorrencia-solucao');

    if (id) id.value = ocorrencia.id || '';
    if (titulo) titulo.value = ocorrencia.titulo || '';
    if (responsavel) responsavel.value = ocorrencia.responsavel || '';
    if (cliente) cliente.value = ocorrencia.cliente_nome || '';
    if (local) local.value = ocorrencia.local || '';
    if (descricao) descricao.value = ocorrencia.descricao || '';
    if (providencia) providencia.value = ocorrencia.providencia || '';
    if (solucao) solucao.value = ocorrencia.solucao || '';

    setSelectValue('#ocorrencia-tipo', ocorrencia.tipo, 'outro');
    setSelectValue('#ocorrencia-prioridade', ocorrencia.prioridade, 'media');
    setSelectValue('#ocorrencia-status', ocorrencia.status, 'aberta');

    const title = qs('#ocorrencia-form-title');
    if (title) title.textContent = 'Editar ocorrência';

    const solucaoWrap = qs('#ocorrencia-solucao-wrap');
    if (solucaoWrap) {
      solucaoWrap.hidden = ocorrencia.status !== 'resolvida';
    }

    const cancel = qs('#btn-cancel-ocorrencia');
    if (cancel) cancel.hidden = false;

    setOcorrenciaMessage('', '');

    const page = qs('#ocorrencias-page');
    if (page) {
      page.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }

  function ocorrenciaStatusClass(status) {
    return String(status || 'aberta').replace(/\s+/g, '_');
  }

  function ocorrenciaResumoCurto(value, limit) {
    const text = String(value || '').trim();
    const max = Number(limit || 220);

    if (!text) return '';
    if (text.length <= max) return text;

    return text.slice(0, max).trim() + '...';
  }

  function filteredOcorrencias() {
    const busca = normalize(state.ocorrenciaBusca);
    const status = normalize(state.ocorrenciaStatus);
    const tipo = normalize(state.ocorrenciaTipo);
    const prioridade = normalize(state.ocorrenciaPrioridade);

    return state.ocorrencias.filter(function (ocorrencia) {
      if (status && normalize(ocorrencia.status) !== status) return false;
      if (tipo && normalize(ocorrencia.tipo) !== tipo) return false;
      if (prioridade && normalize(ocorrencia.prioridade) !== prioridade) return false;

      if (!busca) return true;

      const haystack = normalize([
        ocorrencia.titulo,
        ocorrencia.tipo_label,
        ocorrencia.prioridade_label,
        ocorrencia.status_label,
        ocorrencia.cliente_nome,
        ocorrencia.local,
        ocorrencia.descricao,
        ocorrencia.providencia,
        ocorrencia.responsavel,
        ocorrencia.criado_por_nome,
        ocorrencia.criado_por_usuario,
        ocorrencia.solucao,
      ].join(' '));

      return haystack.includes(busca);
    });
  }

  function renderOcorrencias() {
    const list = qs('#ocorrencias-list');
    const empty = qs('#ocorrencias-empty');
    if (!list || !empty) return;

    const ocorrencias = filteredOcorrencias();
    empty.classList.toggle('show', ocorrencias.length === 0);

    list.innerHTML = ocorrencias.map(function (ocorrencia) {
      const status = ocorrencia.status || 'aberta';
      const prioridade = ocorrencia.prioridade || 'media';
      const statusClass = ocorrenciaStatusClass(status);
      const resolvida = status === 'resolvida';
      const cancelada = status === 'cancelada';

      const clienteLocal = [ocorrencia.cliente_nome, ocorrencia.local].filter(Boolean).join(' • ');
      const responsavel = ocorrencia.responsavel || 'Sem responsável definido';

      const providencia = ocorrencia.providencia ? `
        <div class="oc-extra-item">
          <strong>Providência / encaminhamento</strong>
          ${escapeHtml(ocorrencia.providencia)}
        </div>
      ` : '';

      const solucao = ocorrencia.solucao ? `
        <div class="oc-extra-item">
          <strong>Solução</strong>
          ${escapeHtml(ocorrencia.solucao)}
        </div>
      ` : '';

      const resolverBtn = (!resolvida && !cancelada) ? `
        <button type="button" class="oc-small-btn success" data-resolver-ocorrencia="${escapeHtml(ocorrencia.id)}">
          <i class="fa-solid fa-check"></i>
          Resolver
        </button>
      ` : '';

      const reabrirBtn = (resolvida || cancelada) ? `
        <button type="button" class="oc-small-btn" data-reabrir-ocorrencia="${escapeHtml(ocorrencia.id)}">
          <i class="fa-solid fa-rotate-left"></i>
          Reabrir
        </button>
      ` : '';

      return `
        <article class="oc-card priority-${escapeHtml(prioridade)} ${escapeHtml(statusClass)}" data-ocorrencia-id="${escapeHtml(ocorrencia.id)}">
          <div class="oc-card-header">
            <div class="oc-card-title">
              <h3>${escapeHtml(ocorrencia.titulo || 'Ocorrência sem título')}</h3>
              <p>
                ${escapeHtml(clienteLocal || 'Sem cliente/local informado')}
              </p>
            </div>

            <div class="oc-tags">
              <span class="oc-tag status-${escapeHtml(statusClass)}">${escapeHtml(ocorrencia.status_label || status)}</span>
              <span class="oc-tag priority-${escapeHtml(prioridade)}">${escapeHtml(ocorrencia.prioridade_label || prioridade)}</span>
              <span class="oc-tag">${escapeHtml(ocorrencia.tipo_label || ocorrencia.tipo || 'Outro')}</span>
            </div>
          </div>

          <p class="oc-description">${escapeHtml(ocorrenciaResumoCurto(ocorrencia.descricao, 260))}</p>

          <div class="oc-extra">
            ${providencia}
            ${solucao}
          </div>

          <div class="oc-card-footer">
            <div class="oc-card-meta">
              <span><i class="fa-regular fa-user"></i> ${escapeHtml(ocorrencia.criado_por_nome || ocorrencia.criado_por_usuario || 'Usuário')}</span>
              <span><i class="fa-regular fa-clock"></i> ${escapeHtml(formatDateTime(ocorrencia.criado_em))}</span>
              <span><i class="fa-solid fa-user-shield"></i> ${escapeHtml(responsavel)}</span>
              ${ocorrencia.resolvido_em ? `<span><i class="fa-solid fa-check"></i> Resolvida em ${escapeHtml(formatDateTime(ocorrencia.resolvido_em))}</span>` : ''}
            </div>

            <div class="oc-card-actions">
              <button type="button" class="oc-small-btn" data-edit-ocorrencia="${escapeHtml(ocorrencia.id)}">
                <i class="fa-solid fa-pen"></i>
                Editar
              </button>
              ${resolverBtn}
              ${reabrirBtn}
            </div>
          </div>
        </article>
      `;
    }).join('');
  }

  async function loadOcorrencias() {
    const page = qs('#ocorrencias-page');
    if (!page || state.ocorrenciasCarregando) return;

    const reloadBtn = qs('#btn-reload-ocorrencias');
    state.ocorrenciasCarregando = true;
    if (reloadBtn) reloadBtn.disabled = true;

    try {
      const data = await apiFetch('/api/interno/ocorrencias');
      state.ocorrencias = Array.isArray(data.ocorrencias) ? data.ocorrencias : [];
      updateOcorrenciaStats(data.resumo || {});
      renderOcorrencias();
      setOcorrenciaMessage('', '');
    } catch (error) {
      setOcorrenciaMessage('error', error.message || 'Erro ao carregar ocorrências.');
    } finally {
      state.ocorrenciasCarregando = false;
      if (reloadBtn) reloadBtn.disabled = false;
    }
  }

  async function saveOcorrencia(event) {
    event.preventDefault();

    if (state.ocorrenciaSalvando) return;

    const dados = getOcorrenciaFormData();
    const editando = Boolean(dados.id);
    const btn = qs('#btn-save-ocorrencia');

    if (!dados.titulo) {
      setOcorrenciaMessage('error', 'Informe o título da ocorrência.');
      return;
    }

    if (!dados.descricao) {
      setOcorrenciaMessage('error', 'Descreva a ocorrência.');
      return;
    }

    if (dados.status === 'resolvida' && !dados.solucao && !dados.providencia) {
      setOcorrenciaMessage('error', 'Para marcar como resolvida, informe a solução ou a providência tomada.');
      return;
    }

    state.ocorrenciaSalvando = true;

    if (btn) {
      btn.disabled = true;
      btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Salvando...';
    }

    try {
      const url = editando
        ? '/api/interno/ocorrencias/' + encodeURIComponent(dados.id)
        : '/api/interno/ocorrencias';

      const method = editando ? 'PUT' : 'POST';

      await apiFetch(url, {
        method,
        body: JSON.stringify(dados),
      });

      resetOcorrenciaForm();
      await loadOcorrencias();
      setOcorrenciaMessage('success', editando ? 'Ocorrência atualizada com sucesso.' : 'Ocorrência registrada com sucesso.');
    } catch (error) {
      setOcorrenciaMessage('error', error.message || 'Erro ao salvar ocorrência.');
    } finally {
      state.ocorrenciaSalvando = false;
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = '<i class="fa-solid fa-floppy-disk"></i> Salvar ocorrência';
      }
    }
  }

  async function resolverOcorrencia(id) {
    if (!id) return;

    const solucao = window.prompt('Informe a solução da ocorrência:');
    if (solucao === null) return;

    const texto = solucao.trim();
    if (!texto) {
      setOcorrenciaMessage('error', 'Informe a solução da ocorrência.');
      return;
    }

    try {
      await apiFetch('/api/interno/ocorrencias/' + encodeURIComponent(id) + '/resolver', {
        method: 'POST',
        body: JSON.stringify({ solucao: texto }),
      });

      await loadOcorrencias();
      setOcorrenciaMessage('success', 'Ocorrência resolvida com sucesso.');
    } catch (error) {
      setOcorrenciaMessage('error', error.message || 'Erro ao resolver ocorrência.');
    }
  }

  async function reabrirOcorrencia(id) {
    if (!id) return;

    const confirma = window.confirm('Deseja reabrir esta ocorrência?');
    if (!confirma) return;

    try {
      await apiFetch('/api/interno/ocorrencias/' + encodeURIComponent(id) + '/reabrir', {
        method: 'POST',
        body: JSON.stringify({}),
      });

      await loadOcorrencias();
      setOcorrenciaMessage('success', 'Ocorrência reaberta com sucesso.');
    } catch (error) {
      setOcorrenciaMessage('error', error.message || 'Erro ao reabrir ocorrência.');
    }
  }

  function handleOcorrenciaStatusChange() {
    const status = qs('#ocorrencia-status');
    const solucaoWrap = qs('#ocorrencia-solucao-wrap');

    if (!status || !solucaoWrap) return;

    solucaoWrap.hidden = status.value !== 'resolvida';
  }

  function bindOcorrenciasPage() {
    const page = qs('#ocorrencias-page');
    if (!page) return;

    const form = qs('#ocorrencia-form');
    if (form) form.addEventListener('submit', saveOcorrencia);

    const btnCancel = qs('#btn-cancel-ocorrencia');
    if (btnCancel) btnCancel.addEventListener('click', resetOcorrenciaForm);

    const btnReload = qs('#btn-reload-ocorrencias');
    if (btnReload) btnReload.addEventListener('click', loadOcorrencias);

    const btnScrollForm = qs('[data-scroll-ocorrencia-form]');
    if (btnScrollForm) {
      btnScrollForm.addEventListener('click', function () {
        const titleInput = qs('#ocorrencia-titulo');
        const formEl = qs('#ocorrencia-form');

        if (formEl) {
          formEl.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }

        if (titleInput) {
          setTimeout(function () {
            titleInput.focus();
          }, 220);
        }
      });
    }

    const search = qs('#ocorrencia-search');
    if (search) {
      search.addEventListener('input', function () {
        state.ocorrenciaBusca = search.value || '';
        renderOcorrencias();
      });
    }

    const filterStatus = qs('#ocorrencia-filter-status');
    if (filterStatus) {
      filterStatus.addEventListener('change', function () {
        state.ocorrenciaStatus = filterStatus.value || '';
        renderOcorrencias();
      });
    }

    const filterTipo = qs('#ocorrencia-filter-tipo');
    if (filterTipo) {
      filterTipo.addEventListener('change', function () {
        state.ocorrenciaTipo = filterTipo.value || '';
        renderOcorrencias();
      });
    }

    const filterPrioridade = qs('#ocorrencia-filter-prioridade');
    if (filterPrioridade) {
      filterPrioridade.addEventListener('change', function () {
        state.ocorrenciaPrioridade = filterPrioridade.value || '';
        renderOcorrencias();
      });
    }

    const statusSelect = qs('#ocorrencia-status');
    if (statusSelect) {
      statusSelect.addEventListener('change', handleOcorrenciaStatusChange);
    }

    page.addEventListener('click', function (event) {
      const editBtn = event.target.closest('[data-edit-ocorrencia]');
      if (editBtn) {
        const id = Number(editBtn.getAttribute('data-edit-ocorrencia'));
        const ocorrencia = state.ocorrencias.find(function (item) {
          return Number(item.id) === id;
        });
        fillOcorrenciaForm(ocorrencia);
        return;
      }

      const resolverBtn = event.target.closest('[data-resolver-ocorrencia]');
      if (resolverBtn) {
        resolverOcorrencia(resolverBtn.getAttribute('data-resolver-ocorrencia'));
        return;
      }

      const reabrirBtn = event.target.closest('[data-reabrir-ocorrencia]');
      if (reabrirBtn) {
        reabrirOcorrencia(reabrirBtn.getAttribute('data-reabrir-ocorrencia'));
      }
    });

    resetOcorrenciaForm();
    loadOcorrencias();
  }



  onReady(function () {
    bindOcorrenciasPage();
  });
})();
