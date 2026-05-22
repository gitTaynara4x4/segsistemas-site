(function () {
  'use strict';

  const state = {
    funcionarios: [],
    filtro: '',
    salvando: false,
    plantao: null,
    plantoesHoje: [],
    plantaoCarregando: false,
  };

  function qs(selector, root) {
    return (root || document).querySelector(selector);
  }

  function qsa(selector, root) {
    return Array.from((root || document).querySelectorAll(selector));
  }

  function escapeHtml(value) {
    return String(value || '')
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#039;');
  }

  function normalize(value) {
    return String(value || '')
      .toLowerCase()
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .trim();
  }

  async function apiFetch(url, options) {
    const response = await fetch(url, {
      credentials: 'same-origin',
      headers: {
        Accept: 'application/json',
        'Content-Type': 'application/json',
        ...(options && options.headers ? options.headers : {}),
      },
      ...(options || {}),
    });

    let data = null;
    try {
      data = await response.json();
    } catch (error) {
      data = { ok: false, detail: 'Resposta inválida do servidor.' };
    }

    if (response.status === 401) {
      window.location.href = '/interno/login?next=' + encodeURIComponent(window.location.pathname);
      return Promise.reject(new Error('Não autenticado.'));
    }

    if (!response.ok || data.ok === false) {
      throw new Error(data.detail || 'Não foi possível concluir a ação.');
    }

    return data;
  }

  function initPasswordToggle() {
    const legacyBtn = qs('[data-toggle-password]');
    const legacyInput = qs('#senha');

    if (legacyBtn && legacyInput) {
      legacyBtn.addEventListener('click', function () {
        const showing = legacyInput.type === 'text';
        legacyInput.type = showing ? 'password' : 'text';
        legacyBtn.setAttribute('aria-label', showing ? 'Mostrar senha' : 'Ocultar senha');
        legacyBtn.innerHTML = showing
          ? '<i class="fa-solid fa-eye"></i>'
          : '<i class="fa-solid fa-eye-slash"></i>';
      });
    }

    qsa('[data-toggle-target]').forEach(function (btn) {
      const targetId = btn.getAttribute('data-toggle-target');
      const input = targetId ? document.getElementById(targetId) : null;
      if (!input) return;

      btn.addEventListener('click', function () {
        const showing = input.type === 'text';
        input.type = showing ? 'password' : 'text';
        btn.setAttribute('aria-label', showing ? 'Mostrar senha' : 'Ocultar senha');
        btn.innerHTML = showing
          ? '<i class="fa-solid fa-eye"></i>'
          : '<i class="fa-solid fa-eye-slash"></i>';
      });
    });
  }

  function setMessage(type, text) {
    const box = qs('#func-form-message');
    if (!box) return;

    if (!text) {
      box.hidden = true;
      box.className = 'form-message';
      box.textContent = '';
      return;
    }

    box.hidden = false;
    box.className = 'form-message ' + (type || 'success');
    box.textContent = text;
  }

  function getFormData() {
    return {
      id: qs('#funcionario-id') ? qs('#funcionario-id').value : '',
      nome: qs('#func-nome') ? qs('#func-nome').value.trim() : '',
      telefone: qs('#func-telefone') ? qs('#func-telefone').value.trim() : '',
      email: qs('#func-email') ? qs('#func-email').value.trim() : '',
      cargo: qs('#func-cargo') ? qs('#func-cargo').value.trim() : '',
      tipo: qs('#func-tipo') ? qs('#func-tipo').value : 'plantonista',
      usuario: qs('#func-usuario') ? qs('#func-usuario').value.trim().toLowerCase().replace(/\s+/g, '') : '',
      permissao: qs('#func-permissao') ? qs('#func-permissao').value : 'operador',
      senha: qs('#func-senha') ? qs('#func-senha').value : '',
      ativo: qs('#func-ativo') ? qs('#func-ativo').checked : true,
    };
  }

  function resetForm() {
    const form = qs('#funcionario-form');
    if (form) form.reset();

    const id = qs('#funcionario-id');
    if (id) id.value = '';

    const ativo = qs('#func-ativo');
    if (ativo) ativo.checked = true;

    const title = qs('#func-form-title');
    if (title) title.textContent = 'Novo funcionário';

    const btnCancel = qs('#btn-cancel-edit');
    if (btnCancel) btnCancel.hidden = true;

    const senhaHelp = qs('#senha-help');
    if (senhaHelp) senhaHelp.textContent = '*';

    const senha = qs('#func-senha');
    if (senha) {
      senha.required = true;
      senha.placeholder = 'Senha de acesso ao painel';
      senha.value = '';
    }

    setMessage('', '');
  }

  function fillForm(funcionario) {
    if (!funcionario) return;

    qs('#funcionario-id').value = funcionario.id || '';
    qs('#func-nome').value = funcionario.nome || '';
    qs('#func-telefone').value = funcionario.telefone || '';
    qs('#func-email').value = funcionario.email || '';
    qs('#func-cargo').value = funcionario.cargo || '';
    qs('#func-tipo').value = funcionario.tipo || 'plantonista';
    qs('#func-usuario').value = funcionario.usuario || '';
    qs('#func-permissao').value = funcionario.permissao || 'operador';
    qs('#func-ativo').checked = Boolean(funcionario.ativo);

    const senha = qs('#func-senha');
    if (senha) {
      senha.required = false;
      senha.value = '';
      senha.placeholder = 'Deixe vazio para manter a senha atual';
    }

    const senhaHelp = qs('#senha-help');
    if (senhaHelp) senhaHelp.textContent = '(opcional na edição)';

    const title = qs('#func-form-title');
    if (title) title.textContent = 'Editar funcionário';

    const btnCancel = qs('#btn-cancel-edit');
    if (btnCancel) btnCancel.hidden = false;

    setMessage('', '');
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  function updateStats(resumo) {
    const safe = resumo || {};
    qsa('[data-func-stat]').forEach(function (el) {
      const key = el.getAttribute('data-func-stat');
      el.textContent = String(safe[key] || 0);
    });
  }

  function filteredFuncionarios() {
    const filtro = normalize(state.filtro);
    if (!filtro) return state.funcionarios.slice();

    return state.funcionarios.filter(function (funcionario) {
      const haystack = normalize([
        funcionario.nome,
        funcionario.usuario,
        funcionario.telefone,
        funcionario.email,
        funcionario.cargo,
        funcionario.tipo_label,
        funcionario.permissao_label,
        funcionario.ativo ? 'ativo' : 'inativo',
      ].join(' '));

      return haystack.includes(filtro);
    });
  }

  function renderFuncionarios() {
    const list = qs('#funcionarios-list');
    const empty = qs('#func-empty');
    if (!list || !empty) return;

    const funcionarios = filteredFuncionarios();
    empty.hidden = funcionarios.length > 0;

    list.innerHTML = funcionarios.map(function (funcionario) {
      const ativo = Boolean(funcionario.ativo);
      const statusTag = ativo
        ? '<span class="tag">Ativo</span>'
        : '<span class="tag danger">Inativo</span>';

      const contato = [funcionario.telefone, funcionario.email].filter(Boolean).join(' • ');
      const cargo = funcionario.cargo || 'Cargo não informado';
      const letra = escapeHtml((funcionario.nome || funcionario.usuario || 'S').slice(0, 1).toUpperCase());

      return `
        <article class="func-card ${ativo ? '' : 'inativo'}" data-id="${escapeHtml(funcionario.id)}">
          <div class="func-main">
            <span class="func-avatar">${letra}</span>
            <div class="func-info">
              <h3>${escapeHtml(funcionario.nome)}</h3>
              <p>
                <strong>@${escapeHtml(funcionario.usuario)}</strong>
                ${cargo ? ' • ' + escapeHtml(cargo) : ''}
              </p>
              ${contato ? `<p>${escapeHtml(contato)}</p>` : '<p>Sem telefone/e-mail informado</p>'}
              <div class="func-tags">
                ${statusTag}
                <span class="tag neutral">${escapeHtml(funcionario.tipo_label || funcionario.tipo)}</span>
                <span class="tag warn">${escapeHtml(funcionario.permissao_label || funcionario.permissao)}</span>
              </div>
            </div>
          </div>

          <div class="func-actions">
            <button type="button" class="btn-small" data-edit-func="${escapeHtml(funcionario.id)}">
              <i class="fa-solid fa-pen"></i>
              Editar
            </button>
            <button type="button" class="btn-small ${ativo ? 'danger' : 'success'}" data-toggle-func="${escapeHtml(funcionario.id)}" data-ativo="${ativo ? '1' : '0'}">
              <i class="fa-solid ${ativo ? 'fa-user-slash' : 'fa-user-check'}"></i>
              ${ativo ? 'Inativar' : 'Ativar'}
            </button>
          </div>
        </article>
      `;
    }).join('');
  }

  async function loadFuncionarios() {
    const reloadBtn = qs('#btn-reload-func');
    if (reloadBtn) reloadBtn.disabled = true;

    try {
      const data = await apiFetch('/api/interno/funcionarios');
      state.funcionarios = Array.isArray(data.funcionarios) ? data.funcionarios : [];
      updateStats(data.resumo || {});
      renderFuncionarios();
    } catch (error) {
      setMessage('error', error.message || 'Erro ao carregar funcionários.');
    } finally {
      if (reloadBtn) reloadBtn.disabled = false;
    }
  }

  async function saveFuncionario(event) {
    event.preventDefault();
    if (state.salvando) return;

    const btn = qs('#btn-save-func');
    const dados = getFormData();
    const editando = Boolean(dados.id);

    if (!dados.nome) {
      setMessage('error', 'Informe o nome do funcionário.');
      return;
    }

    if (!dados.usuario) {
      setMessage('error', 'Informe o usuário de login.');
      return;
    }

    if (!editando && !dados.senha) {
      setMessage('error', 'Informe uma senha para o funcionário.');
      return;
    }

    state.salvando = true;
    if (btn) {
      btn.disabled = true;
      btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Salvando...';
    }

    try {
      const url = editando
        ? '/api/interno/funcionarios/' + encodeURIComponent(dados.id)
        : '/api/interno/funcionarios';

      const method = editando ? 'PUT' : 'POST';

      await apiFetch(url, {
        method,
        body: JSON.stringify(dados),
      });

      resetForm();
      await loadFuncionarios();
      setMessage('success', editando ? 'Funcionário atualizado com sucesso.' : 'Funcionário cadastrado com sucesso.');
    } catch (error) {
      setMessage('error', error.message || 'Erro ao salvar funcionário.');
    } finally {
      state.salvando = false;
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = '<i class="fa-solid fa-floppy-disk"></i> Salvar funcionário';
      }
    }
  }

  async function toggleFuncionario(id, ativoAtual) {
    const acao = ativoAtual ? 'inativar' : 'ativar';
    const confirma = ativoAtual
      ? 'Deseja inativar este funcionário? Ele não conseguirá acessar o painel.'
      : 'Deseja ativar este funcionário novamente?';

    if (!window.confirm(confirma)) return;

    try {
      await apiFetch('/api/interno/funcionarios/' + encodeURIComponent(id) + '/' + acao, {
        method: 'POST',
        body: JSON.stringify({}),
      });
      await loadFuncionarios();
      setMessage('success', ativoAtual ? 'Funcionário inativado.' : 'Funcionário ativado.');
    } catch (error) {
      setMessage('error', error.message || 'Erro ao alterar status do funcionário.');
    }
  }

  function bindFuncionariosPage() {
    const page = qs('#funcionarios-page');
    if (!page) return;

    const form = qs('#funcionario-form');
    if (form) form.addEventListener('submit', saveFuncionario);

    const btnCancel = qs('#btn-cancel-edit');
    if (btnCancel) btnCancel.addEventListener('click', resetForm);

    const btnReload = qs('#btn-reload-func');
    if (btnReload) btnReload.addEventListener('click', loadFuncionarios);

    const search = qs('#func-search');
    if (search) {
      search.addEventListener('input', function () {
        state.filtro = search.value;
        renderFuncionarios();
      });
    }

    page.addEventListener('click', function (event) {
      const editBtn = event.target.closest('[data-edit-func]');
      if (editBtn) {
        const id = Number(editBtn.getAttribute('data-edit-func'));
        const funcionario = state.funcionarios.find(function (item) {
          return Number(item.id) === id;
        });
        fillForm(funcionario);
        return;
      }

      const toggleBtn = event.target.closest('[data-toggle-func]');
      if (toggleBtn) {
        const id = Number(toggleBtn.getAttribute('data-toggle-func'));
        const ativoAtual = toggleBtn.getAttribute('data-ativo') === '1';
        toggleFuncionario(id, ativoAtual);
      }
    });

    resetForm();
    loadFuncionarios();
  }

  function setPlantaoMessage(type, text) {
    const box = qs('#plantao-message');
    if (!box) return;

    if (!text) {
      box.hidden = true;
      box.className = 'message-box';
      box.textContent = '';
      return;
    }

    box.hidden = false;
    box.className = 'message-box ' + (type || 'success');
    box.textContent = text;
  }

  function formatDateTime(value) {
    if (!value) return '-';

    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return '-';

    return date.toLocaleString('pt-BR', {
      timeZone: 'America/Sao_Paulo',
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  }

  function updatePlantaoStats(resumo) {
    const safe = resumo || {};
    qsa('[data-plantao-stat]').forEach(function (el) {
      const key = el.getAttribute('data-plantao-stat');
      el.textContent = String(safe[key] || (key === 'data' ? '-' : 0));
    });
  }

  function renderPlantaoStatus() {
    const title = qs('#plantao-status-title');
    const card = qs('#plantao-status-card');
    const btn = qs('#btn-plantao-action');
    const observacao = qs('#plantao-observacao');
    const labelObs = qs('#plantao-observacao-label');
    const labelConfirm = qs('#plantao-confirmacao-label');
    const confirm = qs('#plantao-confirmacao');

    if (!card || !btn) return;

    const plantao = state.plantao;

    if (plantao) {
      if (title) title.textContent = 'Plantão em andamento';
      card.innerHTML = `
        <div class="status-big">
          <i class="fa-solid fa-user-shield"></i>
          <div>
            <strong>${escapeHtml(plantao.funcionario_nome || 'Funcionário')}</strong>
            <p>Plantão iniciado em ${escapeHtml(formatDateTime(plantao.iniciado_em))}. Tempo atual: ${escapeHtml(plantao.duracao_label || '-')}.</p>
            <div class="status-meta">
              <span><i class="fa-solid fa-circle-play"></i> Em andamento</span>
              <span><i class="fa-regular fa-clock"></i> ${escapeHtml(plantao.duracao_label || '-')}</span>
            </div>
          </div>
        </div>
      `;

      if (labelObs) labelObs.textContent = 'Observação do encerramento';
      if (labelConfirm) labelConfirm.textContent = 'Confirmo que estou finalizando este plantão.';
      if (observacao) observacao.placeholder = 'Ex: Encerrando plantão. Sem pendências ou deixar recado para o próximo plantonista.';
      if (confirm) confirm.checked = false;
      btn.classList.add('danger-action');
      btn.innerHTML = '<i class="fa-solid fa-stop"></i> Finalizar plantão';
      return;
    }

    if (title) title.textContent = 'Nenhum plantão em andamento';
    card.innerHTML = `
      <div class="status-big closed">
        <i class="fa-solid fa-circle-check"></i>
        <div>
          <strong>Você ainda não iniciou plantão.</strong>
          <p>Clique em iniciar para registrar sua entrada e assumir responsabilidade pelo turno atual.</p>
        </div>
      </div>
    `;

    if (labelObs) labelObs.textContent = 'Observação do início';
    if (labelConfirm) labelConfirm.textContent = 'Confirmo que estou assumindo este plantão.';
    if (observacao) observacao.placeholder = 'Ex: Assumindo plantão do monitoramento. Sem pendências no momento.';
    if (confirm) confirm.checked = false;
    btn.classList.remove('danger-action');
    btn.innerHTML = '<i class="fa-solid fa-play"></i> Iniciar plantão';
  }

  function renderPlantoesHoje() {
    const list = qs('#plantao-list');
    const empty = qs('#plantao-empty');
    if (!list || !empty) return;

    const plantoes = Array.isArray(state.plantoesHoje) ? state.plantoesHoje : [];
    empty.hidden = plantoes.length > 0;

    list.innerHTML = plantoes.map(function (plantao) {
      const aberto = plantao.status === 'aberto';
      const statusTag = aberto
        ? '<span class="tag">Em andamento</span>'
        : '<span class="tag neutral">Finalizado</span>';
      const obsInicio = plantao.observacao_inicio ? `
        <div class="plantao-note"><strong>Início:</strong> ${escapeHtml(plantao.observacao_inicio)}</div>
      ` : '';
      const obsFim = plantao.observacao_fim ? `
        <div class="plantao-note"><strong>Finalização:</strong> ${escapeHtml(plantao.observacao_fim)}</div>
      ` : '';

      return `
        <article class="plantao-card ${aberto ? 'aberto' : 'finalizado'}">
          <div class="plantao-card-header">
            <div>
              <h3>${escapeHtml(plantao.funcionario_nome || 'Funcionário')}</h3>
              <p>@${escapeHtml(plantao.usuario || '-')} • ${escapeHtml(plantao.status_label || '')}</p>
            </div>
            ${statusTag}
          </div>

          <div class="plantao-times">
            <div class="plantao-time-box">
              <small>Entrada</small>
              <strong>${escapeHtml(formatDateTime(plantao.iniciado_em))}</strong>
            </div>
            <div class="plantao-time-box">
              <small>Saída</small>
              <strong>${escapeHtml(plantao.finalizado_em ? formatDateTime(plantao.finalizado_em) : 'Em andamento')}</strong>
            </div>
            <div class="plantao-time-box">
              <small>Duração</small>
              <strong>${escapeHtml(plantao.duracao_label || '-')}</strong>
            </div>
          </div>

          ${obsInicio}
          ${obsFim}
        </article>
      `;
    }).join('');
  }

  async function loadPlantao() {
    const page = qs('#plantao-page');
    if (!page || state.plantaoCarregando) return;

    const reloadBtn = qs('#btn-reload-plantao');
    state.plantaoCarregando = true;
    if (reloadBtn) reloadBtn.disabled = true;

    try {
      const data = await apiFetch('/api/interno/plantao/status');
      state.plantao = data.plantao_aberto || null;
      state.plantoesHoje = Array.isArray(data.plantoes_hoje) ? data.plantoes_hoje : [];
      updatePlantaoStats(data.resumo || {});
      renderPlantaoStatus();
      renderPlantoesHoje();
      setPlantaoMessage('', '');
    } catch (error) {
      setPlantaoMessage('error', error.message || 'Erro ao carregar plantão.');
    } finally {
      state.plantaoCarregando = false;
      if (reloadBtn) reloadBtn.disabled = false;
    }
  }

  async function submitPlantao(event) {
    event.preventDefault();

    const btn = qs('#btn-plantao-action');
    const observacao = qs('#plantao-observacao');
    const confirm = qs('#plantao-confirmacao');
    const confirmacao = confirm ? confirm.checked : false;

    if (!confirmacao) {
      setPlantaoMessage('error', state.plantao
        ? 'Confirme que você está finalizando o plantão.'
        : 'Confirme que você está assumindo o plantão.');
      return;
    }

    const url = state.plantao
      ? '/api/interno/plantao/finalizar'
      : '/api/interno/plantao/iniciar';

    if (btn) {
      btn.disabled = true;
      btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Salvando...';
    }

    try {
      await apiFetch(url, {
        method: 'POST',
        body: JSON.stringify({
          confirmacao: true,
          observacao: observacao ? observacao.value.trim() : '',
        }),
      });

      if (observacao) observacao.value = '';
      if (confirm) confirm.checked = false;
      await loadPlantao();
      setPlantaoMessage('success', state.plantao ? 'Plantão iniciado com sucesso.' : 'Plantão finalizado com sucesso.');
    } catch (error) {
      setPlantaoMessage('error', error.message || 'Erro ao salvar plantão.');
      renderPlantaoStatus();
    } finally {
      if (btn) btn.disabled = false;
    }
  }

  function bindPlantaoPage() {
    const page = qs('#plantao-page');
    if (!page) return;

    const form = qs('#plantao-form');
    if (form) form.addEventListener('submit', submitPlantao);

    const btnReload = qs('#btn-reload-plantao');
    if (btnReload) btnReload.addEventListener('click', loadPlantao);

    loadPlantao();
  }

  function init() {
    initPasswordToggle();
    bindFuncionariosPage();
    bindPlantaoPage();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
