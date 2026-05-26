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
    onReady,
  } = core;

  const ACESSOS_OPERACAO = [
    'dashboard',
    'ponto',
    'plantao',
    'passagem',
    'ocorrencias',
    'manual',
  ];

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

  function getAcessoChecks() {
    return Array.from(qsa('[data-acesso-check]') || []);
  }

  function getTodosAcessosDisponiveis() {
    return getAcessoChecks()
      .map(function (check) {
        return String(check.value || '').trim();
      })
      .filter(Boolean);
  }

  function normalizarListaAcessos(valor) {
    if (!valor) return [];

    if (Array.isArray(valor)) {
      return valor
        .map(function (item) {
          return String(item || '').trim();
        })
        .filter(Boolean);
    }

    if (typeof valor === 'string') {
      const raw = valor.trim();
      if (!raw) return [];

      try {
        const parsed = JSON.parse(raw);
        if (Array.isArray(parsed)) {
          return parsed
            .map(function (item) {
              return String(item || '').trim();
            })
            .filter(Boolean);
        }
      } catch (error) {
        // Se não for JSON, tenta separado por vírgula.
      }

      return raw
        .split(',')
        .map(function (item) {
          return String(item || '').trim();
        })
        .filter(Boolean);
    }

    return [];
  }

  function getAcessosSelecionados() {
    return getAcessoChecks()
      .filter(function (check) {
        return Boolean(check.checked);
      })
      .map(function (check) {
        return String(check.value || '').trim();
      })
      .filter(Boolean);
  }

  function setAcessosSelecionados(acessos) {
    const lista = normalizarListaAcessos(acessos);
    const set = new Set(lista);

    getAcessoChecks().forEach(function (check) {
      check.checked = set.has(String(check.value || '').trim());
    });
  }

  function selecionarAcessosOperacao() {
    const disponiveis = new Set(getTodosAcessosDisponiveis());
    const operacao = ACESSOS_OPERACAO.filter(function (key) {
      return disponiveis.has(key);
    });

    setAcessosSelecionados(operacao);
  }

  function selecionarTodosAcessos() {
    setAcessosSelecionados(getTodosAcessosDisponiveis());
  }

  function limparAcessos() {
    setAcessosSelecionados([]);
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
      acessos: getAcessosSelecionados(),
    };
  }

  function resetForm() {
    const form = qs('#funcionario-form');
    if (form) form.reset();

    const id = qs('#funcionario-id');
    if (id) id.value = '';

    const ativo = qs('#func-ativo');
    if (ativo) ativo.checked = true;

    const permissao = qs('#func-permissao');
    if (permissao) permissao.value = 'operador';

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

    selecionarAcessosOperacao();
    setMessage('', '');
  }

  function fillForm(funcionario) {
    if (!funcionario) return;

    const id = qs('#funcionario-id');
    const nome = qs('#func-nome');
    const telefone = qs('#func-telefone');
    const email = qs('#func-email');
    const cargo = qs('#func-cargo');
    const tipo = qs('#func-tipo');
    const usuario = qs('#func-usuario');
    const permissao = qs('#func-permissao');
    const ativo = qs('#func-ativo');

    if (id) id.value = funcionario.id || '';
    if (nome) nome.value = funcionario.nome || '';
    if (telefone) telefone.value = funcionario.telefone || '';
    if (email) email.value = funcionario.email || '';
    if (cargo) cargo.value = funcionario.cargo || '';
    if (tipo) tipo.value = funcionario.tipo || 'plantonista';
    if (usuario) usuario.value = funcionario.usuario || '';
    if (permissao) permissao.value = funcionario.permissao || 'operador';
    if (ativo) ativo.checked = Boolean(funcionario.ativo);

    const acessos = funcionario.acessos || funcionario.acessos_lista || [];
    const acessosNormalizados = normalizarListaAcessos(acessos);

    if (acessosNormalizados.length) {
      setAcessosSelecionados(acessosNormalizados);
    } else if ((funcionario.permissao || '') === 'admin') {
      selecionarTodosAcessos();
    } else {
      selecionarAcessosOperacao();
    }

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

  function labelAcesso(key) {
    const check = getAcessoChecks().find(function (item) {
      return item.value === key;
    });

    if (!check) return key;

    const label = check.closest('label');
    if (!label) return key;

    const span = label.querySelector('span');
    if (!span) return key;

    return String(span.childNodes[0] ? span.childNodes[0].textContent : span.textContent || key).trim();
  }

  function acessoResumoHtml(funcionario) {
    const acessos = normalizarListaAcessos(funcionario.acessos || funcionario.acessos_lista || []);

    if (!acessos.length) {
      return '<div class="func-access-summary"><span class="tag neutral">Sem módulos definidos</span></div>';
    }

    const visiveis = acessos.slice(0, 4);
    const restante = acessos.length - visiveis.length;

    return `
      <div class="func-access-summary">
        ${visiveis.map(function (key) {
          return '<span class="tag access">' + escapeHtml(labelAcesso(key)) + '</span>';
        }).join('')}
        ${restante > 0 ? '<span class="tag neutral">+' + restante + '</span>' : ''}
      </div>
    `;
  }

  function filteredFuncionarios() {
    const filtro = normalize(state.filtro);
    if (!filtro) return state.funcionarios.slice();

    return state.funcionarios.filter(function (funcionario) {
      const acessos = normalizarListaAcessos(funcionario.acessos || funcionario.acessos_lista || [])
        .map(labelAcesso)
        .join(' ');

      const haystack = normalize([
        funcionario.nome,
        funcionario.usuario,
        funcionario.telefone,
        funcionario.email,
        funcionario.cargo,
        funcionario.tipo_label,
        funcionario.permissao_label,
        funcionario.ativo ? 'ativo' : 'inativo',
        acessos,
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
              <h3>${escapeHtml(funcionario.nome || 'Sem nome')}</h3>

              <p>
                <strong>@${escapeHtml(funcionario.usuario || 'sem_usuario')}</strong>
                ${cargo ? ' • ' + escapeHtml(cargo) : ''}
              </p>

              ${contato ? `<p>${escapeHtml(contato)}</p>` : '<p>Sem telefone/e-mail informado</p>'}

              <div class="func-tags">
                ${statusTag}
                <span class="tag neutral">${escapeHtml(funcionario.tipo_label || funcionario.tipo || 'Tipo')}</span>
                <span class="tag warn">${escapeHtml(funcionario.permissao_label || funcionario.permissao || 'Permissão')}</span>
              </div>

              ${acessoResumoHtml(funcionario)}
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

    if (!Array.isArray(dados.acessos) || !dados.acessos.length) {
      setMessage('error', 'Marque pelo menos uma tela que esse funcionário pode acessar.');
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
        headers: {
          'Content-Type': 'application/json',
        },
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
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({}),
      });

      await loadFuncionarios();
      setMessage('success', ativoAtual ? 'Funcionário inativado.' : 'Funcionário ativado.');
    } catch (error) {
      setMessage('error', error.message || 'Erro ao alterar status do funcionário.');
    }
  }

  function bindAcessosButtons() {
    const btnOperacao = qs('#btn-acessos-operacao');
    const btnTodos = qs('#btn-acessos-todos');
    const btnLimpar = qs('#btn-acessos-limpar');
    const permissao = qs('#func-permissao');

    if (btnOperacao) {
      btnOperacao.addEventListener('click', function () {
        selecionarAcessosOperacao();
      });
    }

    if (btnTodos) {
      btnTodos.addEventListener('click', function () {
        selecionarTodosAcessos();
      });
    }

    if (btnLimpar) {
      btnLimpar.addEventListener('click', function () {
        limparAcessos();
      });
    }

    if (permissao) {
      permissao.addEventListener('change', function () {
        if (permissao.value === 'admin') {
          selecionarTodosAcessos();
        } else if (!getAcessosSelecionados().length) {
          selecionarAcessosOperacao();
        }
      });
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

    bindAcessosButtons();
    resetForm();
    loadFuncionarios();
  }

  function bindFuncionariosFormLayout() {
    const btnOpen = qs('#btn-open-form');
    const btnClose = qs('#btn-close-form');
    const formCard = qs('#form-container');
    const listCard = qs('#list-container');
    const list = qs('#funcionarios-list');

    if (!formCard || !listCard) return;

    function showForm() {
      formCard.classList.add('is-open');
      listCard.classList.add('is-shrunk');
    }

    function hideForm() {
      formCard.classList.remove('is-open');
      listCard.classList.remove('is-shrunk');
    }

    if (btnOpen) {
      btnOpen.addEventListener('click', function () {
        resetForm();
        showForm();
      });
    }

    if (btnClose) {
      btnClose.addEventListener('click', function () {
        hideForm();
      });
    }

    document.addEventListener('click', function (event) {
      if (event.target.closest('#btn-cancel-edit')) {
        hideForm();
      }
    });

    if (list) {
      list.addEventListener('click', function (event) {
        const editBtn = event.target.closest('[data-edit-func]');
        if (editBtn) showForm();
      });
    }
  }

  onReady(function () {
    initPasswordToggle();
    bindFuncionariosPage();
    bindFuncionariosFormLayout();
  });
})();