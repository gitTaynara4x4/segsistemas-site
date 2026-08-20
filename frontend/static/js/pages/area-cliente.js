(function () {
  'use strict';

  const config = window.SEG_AREA_CLIENTE || {};
  const API_BASE = String(config.apiBase || '').replace(/\/$/, '');

  const state = {
    portal: null,
    loading: false,
    authMode: 'login',
    toastTimer: null,
  };

  const dom = {};

  function byId(id) {
    return document.getElementById(id);
  }

  function apiUrl(path) {
    return `${API_BASE}${path}`;
  }


  function text(value, fallback = '---') {
    if (value === null || value === undefined) return fallback;
    const normalized = String(value).trim();
    if (!normalized || ['null', 'undefined', 'none'].includes(normalized.toLowerCase())) return fallback;
    return normalized;
  }

  function lower(value) {
    return text(value, '').toLowerCase();
  }

  function firstFilled() {
    for (let i = 0; i < arguments.length; i += 1) {
      const value = text(arguments[i], '');
      if (value) return value;
    }
    return '';
  }

  function setText(id, value, fallback = '---') {
    const el = byId(id);
    if (el) el.textContent = text(value, fallback);
  }

  function escapeHtml(value) {
    return String(value ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function safeUrl(value) {
    const raw = text(value, '');
    if (!raw) return '';
    try {
      const parsed = new URL(raw, window.location.origin);
      if (parsed.protocol === 'https:' || parsed.protocol === 'http:') return parsed.href;
    } catch (_) {
      return '';
    }
    return '';
  }

  function formatDate(value, fallback = '---') {
    const raw = text(value, '');
    if (!raw) return fallback;

    const dateOnly = raw.match(/^(\d{4})-(\d{2})-(\d{2})$/);
    if (dateOnly) return `${dateOnly[3]}/${dateOnly[2]}/${dateOnly[1]}`;

    const date = new Date(raw);
    if (Number.isNaN(date.getTime())) return raw;
    return new Intl.DateTimeFormat('pt-BR', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
    }).format(date);
  }

  function formatDateTime(value, fallback = '---') {
    const raw = text(value, '');
    if (!raw) return fallback;
    const date = new Date(raw);
    if (Number.isNaN(date.getTime())) return raw;
    return new Intl.DateTimeFormat('pt-BR', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    }).format(date);
  }

  function formatMoney(value) {
    const normalized = String(value ?? '0').replace(',', '.');
    const number = Number(normalized);
    const safe = Number.isFinite(number) ? number : 0;
    return new Intl.NumberFormat('pt-BR', {
      style: 'currency',
      currency: 'BRL',
    }).format(safe);
  }

  async function apiJson(path, options = {}) {
    const response = await fetch(apiUrl(path), {
      ...options,
      credentials: 'same-origin',
      cache: 'no-store',
      headers: {
        Accept: 'application/json',
        ...(options.headers || {}),
      },
    });

    const contentType = response.headers.get('content-type') || '';
    const data = contentType.includes('application/json')
      ? await response.json().catch(() => null)
      : await response.text().catch(() => '');

    if (!response.ok) {
      const detail = data && typeof data === 'object' ? data.detail : data;
      const error = new Error(detail || `Erro HTTP ${response.status}.`);
      error.status = response.status;
      error.payload = data;
      throw error;
    }

    return data;
  }

  function showToast(message, type = '') {
    if (!dom.toast) return;
    window.clearTimeout(state.toastTimer);
    dom.toast.textContent = text(message, '');
    dom.toast.className = `portal-toast${type ? ` is-${type}` : ''}`;
    dom.toast.hidden = false;
    state.toastTimer = window.setTimeout(() => {
      dom.toast.hidden = true;
    }, 4200);
  }

  function setAccessMessage(message, type = 'error') {
    if (!dom.accessMessage) return;
    const value = text(message, '');
    dom.accessMessage.hidden = !value;
    dom.accessMessage.textContent = value;
    dom.accessMessage.className = `access-message${type === 'info' ? ' is-info' : ''}`;
  }

  function setAuthLoading(loading, mode = state.authMode) {
    state.loading = loading;

    if (dom.btnEntrar) {
      dom.btnEntrar.disabled = loading;
      dom.btnEntrar.innerHTML = loading && mode === 'login'
        ? '<i class="fa-solid fa-spinner fa-spin"></i> Entrando...'
        : 'Entrar na Área do Cliente <i class="fa-solid fa-arrow-right"></i>';
    }

    if (dom.btnPrimeiroAcesso) {
      dom.btnPrimeiroAcesso.disabled = loading;
      dom.btnPrimeiroAcesso.innerHTML = loading && mode === 'first'
        ? '<i class="fa-solid fa-spinner fa-spin"></i> Criando acesso...'
        : 'Criar acesso <i class="fa-solid fa-check"></i>';
    }
  }

  function initDom() {
    dom.toast = byId('portalToast');
    dom.accessShell = byId('accessShell');
    dom.accessTitle = byId('accessTitle');
    dom.accessStatusText = byId('accessStatusText');
    dom.accessMessage = byId('accessMessage');

    dom.loginTab = byId('loginTab');
    dom.firstAccessTab = byId('firstAccessTab');
    dom.loginForm = byId('loginForm');
    dom.firstAccessForm = byId('firstAccessForm');
    dom.loginIdentifier = byId('loginIdentifier');
    dom.loginPassword = byId('loginPassword');
    dom.firstIdentifier = byId('firstIdentifier');
    dom.firstVerification = byId('firstVerification');
    dom.newPassword = byId('newPassword');
    dom.confirmPassword = byId('confirmPassword');
    dom.toggleLoginPassword = byId('toggleLoginPassword');
    dom.toggleNewPassword = byId('toggleNewPassword');
    dom.toggleConfirmPassword = byId('toggleConfirmPassword');
    dom.btnEntrar = byId('btnEntrar');
    dom.btnPrimeiroAcesso = byId('btnPrimeiroAcesso');
    dom.goFirstAccess = byId('goFirstAccess');
    dom.backToLogin = byId('backToLogin');

    dom.portalApp = byId('portalApp');
    dom.portalSidebar = byId('portalSidebar');
    dom.mobileMenuButton = byId('mobileMenuButton');
    dom.mobileSidebarOverlay = byId('mobileSidebarOverlay');
    dom.refreshPortalButton = byId('refreshPortalButton');
    dom.logoutButton = byId('logoutButton');
    dom.financialBlockWarning = byId('financialBlockWarning');
    dom.financeNavCounter = byId('financeNavCounter');
  }

  function closeMobileMenu() {
    dom.portalSidebar?.classList.remove('is-open');
    if (dom.mobileSidebarOverlay) dom.mobileSidebarOverlay.hidden = true;
  }

  function openMobileMenu() {
    dom.portalSidebar?.classList.add('is-open');
    if (dom.mobileSidebarOverlay) dom.mobileSidebarOverlay.hidden = false;
  }

  function showView(viewName) {
    const target = text(viewName, 'dashboard');
    document.querySelectorAll('[data-view]').forEach((section) => {
      section.classList.toggle('is-active', section.dataset.view === target);
    });
    document.querySelectorAll('.portal-nav-item[data-view-target]').forEach((item) => {
      item.classList.toggle('is-active', item.dataset.viewTarget === target);
    });
    closeMobileMenu();
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  function monitorMode(status) {
    const normalized = lower(status);
    if (normalized === 'ativo') return 'active';
    if (normalized === 'bloqueio financeiro') return 'warning';
    if (normalized === 'inativo') return 'inactive';
    return '';
  }

  function monitorLabel(status) {
    const raw = text(status, 'Não informado');
    if (lower(raw) === 'ativo') return 'Ativo';
    if (lower(raw) === 'bloqueio financeiro') return 'Bloqueio financeiro';
    if (lower(raw) === 'inativo') return 'Inativo';
    return raw;
  }

  function financeStatus(status) {
    const normalized = lower(status);
    const map = {
      aberto: { label: 'Em aberto', cls: 'is-open' },
      parcial: { label: 'Parcial', cls: 'is-partial' },
      vencido: { label: 'Vencido', cls: 'is-overdue' },
      recebido: { label: 'Pago', cls: 'is-paid' },
      cancelado: { label: 'Cancelado', cls: 'is-cancelled' },
    };
    return map[normalized] || { label: text(status, 'Não informado'), cls: '' };
  }

  function buildAddress(endereco) {
    const street = text(endereco?.logradouro, '');
    const number = text(endereco?.numero, '');
    const complement = text(endereco?.complemento, '');
    const district = text(endereco?.bairro, '');
    const city = text(endereco?.cidade, '');
    const stateName = text(endereco?.uf, '');

    const line1 = [street, number].filter(Boolean).join(', ') || 'Endereço não informado';
    const extras = [complement, district].filter(Boolean).join(' • ');
    const line2 = [extras, [city, stateName].filter(Boolean).join(' / ')].filter(Boolean).join(' • ') || '---';
    return { line1, line2 };
  }

  function renderIdentity(data) {
    const cliente = data.cliente || {};
    const name = text(cliente.nome_razao_social, 'Cliente SEG');
    const trade = text(cliente.nome_fantasia, 'Não informado');
    const code = text(cliente.codigo, text(data.acesso?.codigo_cliente, '---'));
    const type = text(cliente.tipo_cliente, 'Não informado');

    setText('accountName', name, 'Cliente SEG');
    setText('accountCode', `Código ${code}`, 'Código ---');
    setText('dataLegalName', name, 'Cliente SEG');
    setText('dataTradeName', trade, 'Não informado');
    setText('dataClientCode', code, '---');
    setText('dataClientType', type, 'Não informado');

    const avatar = byId('accountAvatar');
    if (avatar) avatar.textContent = name.charAt(0).toUpperCase() || 'S';

    const greeting = byId('dashboardGreeting');
    if (greeting) greeting.textContent = 'Bem-vindo à sua Área do Cliente.';
    setText('dashboardSubtitle', name, 'Cliente SEG');
  }

  function renderMonitoramento(data) {
    const monitoramento = data.monitoramento || {};
    const status = monitorLabel(monitoramento.status);
    const mode = monitorMode(monitoramento.status);

    setText('summaryMonitorStatus', status, 'Não informado');
    setText('summaryAccount', monitoramento.conta_monit24hs, 'Não informado');
    setText('monitorStatusText', status, 'Não informado');
    setText('monitorStatusBadge', status, 'Não informado');
    setText('monitorAccount', monitoramento.conta_monit24hs, 'Não informado');
    setText('monitorContract', monitoramento.tipo_contrato, 'Não informado');
    setText('monitorProperty', monitoramento.tipo_imovel, 'Não informado');
    setText('monitorSegment', monitoramento.segmento, 'Não informado');
    setText('dashboardContractType', monitoramento.tipo_contrato, 'Não informado');
    setText('dashboardPropertyType', monitoramento.tipo_imovel, 'Não informado');
    setText('dashboardSegment', monitoramento.segmento, 'Não informado');

    const dot = byId('summaryMonitorDot');
    if (dot) dot.className = `status-dot${mode ? ` is-${mode}` : ''}`;

    const panel = byId('monitorStatusPanel');
    if (panel) panel.className = `monitor-status-panel${mode ? ` is-${mode}` : ''}`;

    if (dom.financialBlockWarning) {
      dom.financialBlockWarning.hidden = lower(monitoramento.status) !== 'bloqueio financeiro';
    }
  }

  function renderEndereco(data) {
    const endereco = data.endereco || {};
    const preview = buildAddress(endereco);

    setText('dashboardAddressLine', preview.line1, 'Endereço não informado');
    setText('dashboardAddressCity', preview.line2, '---');
    setText('addressStreet', endereco.logradouro, 'Não informado');
    setText('addressNumber', endereco.numero, 'Não informado');
    setText('addressComplement', endereco.complemento, 'Não informado');
    setText('addressDistrict', endereco.bairro, 'Não informado');
    setText('addressCity', endereco.cidade, 'Não informado');
    setText('addressState', endereco.uf, 'Não informado');
    setText('addressZip', endereco.cep, 'Não informado');
  }

  function renderContatos(data) {
    const contatos = data.contatos || {};
    setText('contactMainPhone', contatos.telefone_principal_whatsapp, 'Não informado');
    setText('contactEmail', contatos.email, 'Não informado');
    setText('contactPerson', contatos.pessoa_contato, 'Não informado');
    setText('contactPhone', contatos.telefone_contato_whatsapp, 'Não informado');
    setText('contactResponsible', contatos.pessoa_responsavel, 'Não informado');
  }

  function renderRecentFinance(titulos) {
    const root = byId('dashboardFinanceList');
    if (!root) return;

    const priority = (Array.isArray(titulos) ? titulos : [])
      .filter((item) => ['vencido', 'aberto', 'parcial'].includes(lower(item.status)))
      .slice(0, 4);

    if (!priority.length) {
      root.innerHTML = '<div class="empty-inline">Nenhum título pendente no momento.</div>';
      return;
    }

    root.innerHTML = priority.map((item) => {
      const status = financeStatus(item.status);
      const title = firstFilled(item.descricao, item.documento, `Título #${item.id}`);
      return `
        <div class="recent-finance-item">
          <div class="recent-finance-main">
            <strong>${escapeHtml(title)}</strong>
            <span>Vencimento ${escapeHtml(formatDate(item.data_vencimento))}</span>
          </div>
          <span class="finance-status ${escapeHtml(status.cls)}">${escapeHtml(status.label)}</span>
          <strong class="recent-finance-value">${escapeHtml(formatMoney(item.saldo_aberto || item.valor_total))}</strong>
        </div>
      `;
    }).join('');
  }

  function financeActions(item) {
    const boleto = item?.boleto || {};
    const actions = [];
    const pdfUrl = safeUrl(boleto.pdf_url);

    if (pdfUrl) {
      actions.push(`<a class="finance-action" href="${escapeHtml(pdfUrl)}" target="_blank" rel="noopener noreferrer">Ver boleto</a>`);
    }
    if (text(boleto.linha_digitavel, '')) {
      actions.push(`<button class="finance-action" type="button" data-copy-value="${escapeHtml(boleto.linha_digitavel)}">Copiar linha</button>`);
    }
    if (text(boleto.pix_copia_cola, '')) {
      actions.push(`<button class="finance-action" type="button" data-copy-value="${escapeHtml(boleto.pix_copia_cola)}">Copiar Pix</button>`);
    }

    if (!actions.length) return '<span class="finance-status">—</span>';
    return `<div class="finance-actions">${actions.join('')}</div>`;
  }

  function renderFinanceiro(data) {
    const financeiro = data.financeiro || {};
    const resumo = financeiro.resumo || {};
    const titulos = Array.isArray(financeiro.titulos) ? financeiro.titulos : [];

    setText('summaryOpenBalance', formatMoney(resumo.saldo_em_aberto || 0), 'R$ 0,00');
    setText(
      'summaryOpenTitles',
      Number(resumo.em_aberto || 0) + Number(resumo.vencidos || 0) > 0
        ? `${Number(resumo.em_aberto || 0) + Number(resumo.vencidos || 0)} título(s) pendente(s)`
        : 'Nenhum título pendente',
      'Nenhum título pendente'
    );
    setText('summaryNextDue', resumo.proximo_vencimento ? formatDate(resumo.proximo_vencimento) : 'Nenhum', 'Nenhum');

    setText('financeOpenBalance', formatMoney(resumo.saldo_em_aberto || 0), 'R$ 0,00');
    setText('financeOpenCount', resumo.em_aberto || 0, '0');
    setText('financeOverdueCount', resumo.vencidos || 0, '0');
    setText('financePaidCount', resumo.recebidos || 0, '0');

    const pendingCount = Number(resumo.em_aberto || 0) + Number(resumo.vencidos || 0);
    if (dom.financeNavCounter) {
      dom.financeNavCounter.hidden = pendingCount <= 0;
      dom.financeNavCounter.textContent = String(pendingCount);
    }

    renderRecentFinance(titulos);

    const unavailable = byId('financeUnavailable');
    const wrap = byId('financeTableWrap');
    const tbody = byId('financeTableBody');

    if (!financeiro.disponivel) {
      if (unavailable) {
        unavailable.hidden = false;
        unavailable.querySelector('strong').textContent = 'Financeiro indisponível';
        unavailable.querySelector('span').textContent = 'Não há uma base financeira disponível para este cadastro no momento.';
      }
      if (wrap) wrap.hidden = true;
      return;
    }

    if (!titulos.length) {
      if (unavailable) {
        unavailable.hidden = false;
        unavailable.querySelector('strong').textContent = 'Nenhum título encontrado';
        unavailable.querySelector('span').textContent = 'Não há movimentações financeiras registradas para este cliente.';
      }
      if (wrap) wrap.hidden = true;
      return;
    }

    if (unavailable) unavailable.hidden = true;
    if (wrap) wrap.hidden = false;

    if (tbody) {
      tbody.innerHTML = titulos.map((item) => {
        const status = financeStatus(item.status);
        const title = firstFilled(item.descricao, item.documento, `Título #${item.id}`);
        const subtitle = [
          text(item.competencia, ''),
          text(item.forma_cobranca?.nome, ''),
        ].filter(Boolean).join(' • ');

        return `
          <tr>
            <td>
              <div class="finance-title-cell">
                <strong>${escapeHtml(title)}</strong>
                <span>${escapeHtml(subtitle || `Título #${item.id}`)}</span>
              </div>
            </td>
            <td>${escapeHtml(formatDate(item.data_vencimento))}</td>
            <td>${escapeHtml(formatMoney(item.valor_total))}</td>
            <td><span class="finance-status ${escapeHtml(status.cls)}">${escapeHtml(status.label)}</span></td>
            <td>${financeActions(item)}</td>
          </tr>
        `;
      }).join('');
    }
  }

  function renderPortal(data) {
    state.portal = data;
    renderIdentity(data);
    renderMonitoramento(data);
    renderEndereco(data);
    renderContatos(data);
    renderFinanceiro(data);

    setText('lastSyncText', data.consulta_em ? `Atualizado em ${formatDateTime(data.consulta_em)}` : 'Atualizado agora', 'Atualizado agora');
  }

  function showPortal() {
    if (dom.accessShell) dom.accessShell.hidden = true;
    if (dom.portalApp) dom.portalApp.hidden = false;
    showView('dashboard');
  }

  function showAccess() {
    if (dom.portalApp) dom.portalApp.hidden = true;
    if (dom.accessShell) dom.accessShell.hidden = false;
  }

  function setAuthMode(mode) {
    const first = mode === 'first';
    state.authMode = first ? 'first' : 'login';
    setAccessMessage('');

    if (dom.loginForm) dom.loginForm.hidden = first;
    if (dom.firstAccessForm) dom.firstAccessForm.hidden = !first;
    dom.loginTab?.classList.toggle('is-active', !first);
    dom.firstAccessTab?.classList.toggle('is-active', first);
    dom.loginTab?.setAttribute('aria-selected', String(!first));
    dom.firstAccessTab?.setAttribute('aria-selected', String(first));

    if (first) {
      if (dom.accessTitle) dom.accessTitle.textContent = 'Criar meu acesso';
      if (dom.accessStatusText) dom.accessStatusText.textContent = 'Confirme um dado do seu cadastro e crie sua senha.';
      if (dom.firstIdentifier && !dom.firstIdentifier.value && dom.loginIdentifier?.value) {
        dom.firstIdentifier.value = dom.loginIdentifier.value;
      }
      window.setTimeout(() => dom.firstIdentifier?.focus(), 0);
    } else {
      if (dom.accessTitle) dom.accessTitle.textContent = 'Acessar minha conta';
      if (dom.accessStatusText) dom.accessStatusText.textContent = 'Entre com seu código, Conta Monit24hs, CPF ou CNPJ.';
      if (dom.loginIdentifier && !dom.loginIdentifier.value && dom.firstIdentifier?.value) {
        dom.loginIdentifier.value = dom.firstIdentifier.value;
      }
      window.setTimeout(() => dom.loginIdentifier?.focus(), 0);
    }
  }

  function togglePassword(input, button) {
    if (!input || !button) return;
    const revealing = input.type === 'password';
    input.type = revealing ? 'text' : 'password';
    button.innerHTML = revealing
      ? '<i class="fa-regular fa-eye-slash"></i>'
      : '<i class="fa-regular fa-eye"></i>';
  }

  async function loadPortal(options = {}) {
    if (dom.refreshPortalButton) {
      dom.refreshPortalButton.disabled = true;
      dom.refreshPortalButton.querySelector('i')?.classList.add('fa-spin');
    }

    try {
      const data = await apiJson('/api/area-cliente-publica/portal');
      if (!data || data.ok !== true) throw new Error('O portal retornou uma resposta inválida.');
      renderPortal(data);
      showPortal();
      if (options.notify) showToast('Dados atualizados com sucesso.', 'success');
      return data;
    } finally {
      if (dom.refreshPortalButton) {
        dom.refreshPortalButton.disabled = false;
        dom.refreshPortalButton.querySelector('i')?.classList.remove('fa-spin');
      }
    }
  }

  async function checkExistingSession() {
    showAccess();
    setAuthMode('login');

    try {
      const session = await apiJson('/api/area-cliente-publica/sessao');
      if (session?.autenticado) {
        await loadPortal();
        return;
      }
    } catch (error) {
      if (error.status !== 401) {
        console.warn('[Área do Cliente] Não foi possível verificar a sessão:', error);
      }
    }

    showAccess();
  }

  async function authenticateLogin(event) {
    event.preventDefault();
    if (state.loading) return;

    const identificador = text(dom.loginIdentifier?.value, '');
    const senha = String(dom.loginPassword?.value || '');
    if (!identificador || !senha) {
      setAccessMessage('Informe seu código/conta e sua senha.');
      return;
    }

    setAuthLoading(true, 'login');
    setAccessMessage('');

    try {
      await apiJson('/api/area-cliente-publica/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ identificador, senha }),
      });
      if (dom.loginPassword) dom.loginPassword.value = '';
      await loadPortal();
    } catch (error) {
      console.error('[Área do Cliente] Falha no login:', error);
      if (error.payload?.primeiro_acesso_necessario) {
        if (dom.firstIdentifier) dom.firstIdentifier.value = identificador;
        setAuthMode('first');
        setAccessMessage('Este cliente ainda não criou uma senha. Confirme seus dados para fazer o primeiro acesso.', 'info');
      } else {
        setAccessMessage(error.message || 'Não foi possível entrar na sua conta.');
      }
    } finally {
      setAuthLoading(false, 'login');
    }
  }

  async function createFirstAccess(event) {
    event.preventDefault();
    if (state.loading) return;

    const identificador = text(dom.firstIdentifier?.value, '');
    const verificacao = text(dom.firstVerification?.value, '');
    const senha = String(dom.newPassword?.value || '');
    const confirmarSenha = String(dom.confirmPassword?.value || '');

    if (!identificador || !verificacao) {
      setAccessMessage('Informe seu código/conta e o CPF/CNPJ ou telefone cadastrado.');
      return;
    }
    if (senha !== confirmarSenha) {
      setAccessMessage('As senhas informadas não conferem.');
      return;
    }
    if (senha.length < 8 || !/[A-Za-zÀ-ÿ]/.test(senha) || !/\d/.test(senha)) {
      setAccessMessage('Sua senha precisa ter pelo menos 8 caracteres, com letras e números.');
      return;
    }

    setAuthLoading(true, 'first');
    setAccessMessage('');

    try {
      await apiJson('/api/area-cliente-publica/primeiro-acesso', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          identificador,
          verificacao,
          senha,
          confirmar_senha: confirmarSenha,
        }),
      });
      if (dom.newPassword) dom.newPassword.value = '';
      if (dom.confirmPassword) dom.confirmPassword.value = '';
      if (dom.firstVerification) dom.firstVerification.value = '';
      showToast('Acesso criado com sucesso.', 'success');
      await loadPortal();
    } catch (error) {
      console.error('[Área do Cliente] Falha no primeiro acesso:', error);
      if (error.status === 409) {
        if (dom.loginIdentifier) dom.loginIdentifier.value = identificador;
        setAuthMode('login');
        setAccessMessage('Este cliente já possui uma senha. Entre normalmente.', 'info');
      } else {
        setAccessMessage(error.message || 'Não foi possível criar seu acesso.');
      }
    } finally {
      setAuthLoading(false, 'first');
    }
  }

  async function copyValue(value) {
    const raw = text(value, '');
    if (!raw) return;
    try {
      await navigator.clipboard.writeText(raw);
      showToast('Copiado para a área de transferência.', 'success');
    } catch (_) {
      const textarea = document.createElement('textarea');
      textarea.value = raw;
      textarea.style.position = 'fixed';
      textarea.style.opacity = '0';
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand('copy');
      textarea.remove();
      showToast('Copiado para a área de transferência.', 'success');
    }
  }

  async function logout() {
    state.portal = null;
    closeMobileMenu();
    try {
      await apiJson('/api/area-cliente-publica/logout', { method: 'POST' });
    } catch (_) {
      // Mesmo se o servidor estiver indisponível, volta para a tela de entrada.
    }
    if (dom.loginPassword) dom.loginPassword.value = '';
    showAccess();
    setAuthMode('login');
  }

  function bindEvents() {
    dom.loginForm?.addEventListener('submit', authenticateLogin);
    dom.firstAccessForm?.addEventListener('submit', createFirstAccess);

    document.querySelectorAll('[data-auth-mode]').forEach((button) => {
      button.addEventListener('click', () => setAuthMode(button.dataset.authMode));
    });
    dom.goFirstAccess?.addEventListener('click', () => setAuthMode('first'));
    dom.backToLogin?.addEventListener('click', () => setAuthMode('login'));

    dom.toggleLoginPassword?.addEventListener('click', () => togglePassword(dom.loginPassword, dom.toggleLoginPassword));
    dom.toggleNewPassword?.addEventListener('click', () => togglePassword(dom.newPassword, dom.toggleNewPassword));
    dom.toggleConfirmPassword?.addEventListener('click', () => togglePassword(dom.confirmPassword, dom.toggleConfirmPassword));

    dom.mobileMenuButton?.addEventListener('click', () => {
      if (dom.portalSidebar?.classList.contains('is-open')) closeMobileMenu();
      else openMobileMenu();
    });

    dom.mobileSidebarOverlay?.addEventListener('click', closeMobileMenu);
    dom.logoutButton?.addEventListener('click', logout);

    dom.refreshPortalButton?.addEventListener('click', async () => {
      try {
        await loadPortal({ notify: true });
      } catch (error) {
        if (error.status === 401) {
          showAccess();
          setAuthMode('login');
          setAccessMessage('Sua sessão expirou. Entre novamente.');
        } else {
          showToast(error.message || 'Não foi possível atualizar os dados.', 'error');
        }
      }
    });

    document.addEventListener('click', (event) => {
      const viewTarget = event.target.closest('[data-view-target]');
      if (viewTarget) {
        event.preventDefault();
        showView(viewTarget.dataset.viewTarget);
        return;
      }

      const copyButton = event.target.closest('[data-copy-value]');
      if (copyButton) {
        event.preventDefault();
        copyValue(copyButton.dataset.copyValue || '');
      }
    });

    window.addEventListener('resize', () => {
      if (window.innerWidth > 860) closeMobileMenu();
    });
  }

  function cleanupLegacyAccessParams() {
    try {
      const url = new URL(window.location.href);
      if (url.searchParams.has('acesso') || url.searchParams.has('token')) {
        url.searchParams.delete('acesso');
        url.searchParams.delete('token');
        window.history.replaceState({}, document.title, `${url.pathname}${url.search}${url.hash}`);
      }
    } catch (_) {
      // Sem ação: limpeza de URL é apenas uma proteção adicional.
    }
  }

  function boot() {
    cleanupLegacyAccessParams();
    initDom();
    bindEvents();
    checkExistingSession();
  }

  document.addEventListener('DOMContentLoaded', boot);
})();
