(function () {
  'use strict';

  const config = window.SEG_AREA_CLIENTE || {};
  const API_BASE = String(config.apiBase || '').replace(/\/$/, '');

  const state = {
    acesso: '',
    sessionToken: '',
    linkStatus: null,
    cliente: null,
    dados: null,
    loading: false,
  };

  const fields = [
    'tipo_pessoa',
    'nome_completo',
    'cpf',
    'rg',
    'nacionalidade',
    'profissao',
    'estado_civil',
    'data_nascimento',
    'email_pessoal',
    'telefone_pessoal',
    'razao_social',
    'cnpj',
    'email_empresa',
    'telefone_whatsapp_empresa',
    'representante_nome',
    'representante_cpf',
    'representante_rg',
    'representante_nacionalidade',
    'representante_profissao',
    'representante_estado_civil',
    'representante_data_nascimento',
    'representante_email_pessoal',
    'representante_telefone_pessoal',
    'imovel_rua',
    'imovel_numero',
    'imovel_bairro',
    'imovel_cidade',
    'imovel_uf',
    'imovel_cep',
    'observacoes_contrato',
  ];

  const dom = {};

  function byId(id) {
    return document.getElementById(id);
  }

  function initDom() {
    dom.alert = byId('portalAlert');
    dom.tokenCard = byId('tokenCard');
    dom.tokenStatusText = byId('tokenStatusText');
    dom.statusPill = byId('statusPill');
    dom.tokenInfo = byId('tokenInfo');
    dom.tokenHint = byId('tokenHint');
    dom.tokenExpires = byId('tokenExpires');
    dom.authForm = byId('authForm');
    dom.senha = byId('senha_provisoria');
    dom.toggleSenha = byId('toggleSenha');
    dom.btnEntrar = byId('btnEntrar');

    dom.clienteCard = byId('clienteCard');
    dom.clienteNome = byId('clienteNome');
    dom.clienteResumo = byId('clienteResumo');
    dom.clienteCodigo = byId('clienteCodigo');

    dom.dadosForm = byId('dadosForm');
    dom.tipoPessoa = byId('tipo_pessoa');
    dom.pjSection = byId('pjSection');
    dom.btnSalvarRascunho = byId('btnSalvarRascunho');
    dom.btnFinalizar = byId('btnFinalizar');
    dom.successCard = byId('successCard');
  }

  function setLoading(isLoading, text) {
    state.loading = isLoading;

    if (dom.btnEntrar) {
      dom.btnEntrar.disabled = isLoading;
      dom.btnEntrar.innerHTML = isLoading
        ? '<i class="fas fa-spinner fa-spin"></i> Aguarde...'
        : '<i class="fas fa-unlock-keyhole"></i> Entrar na Área do Cliente';
    }

    if (dom.btnSalvarRascunho) dom.btnSalvarRascunho.disabled = isLoading;
    if (dom.btnFinalizar) dom.btnFinalizar.disabled = isLoading;

    if (text) showAlert(text, 'info');
  }

  function apiUrl(path) {
    return `${API_BASE}${path}`;
  }

  async function apiJson(path, options = {}) {
    const response = await fetch(apiUrl(path), {
      ...options,
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
      throw new Error(detail || `Erro HTTP ${response.status}.`);
    }

    return data;
  }

  function showAlert(message, type = 'info') {
    if (!dom.alert) return;

    const text = String(message || '').trim();
    if (!text) {
      dom.alert.hidden = true;
      dom.alert.textContent = '';
      dom.alert.className = 'portal-alert';
      return;
    }

    dom.alert.hidden = false;
    dom.alert.textContent = text;
    dom.alert.className = `portal-alert ${type}`;
  }

  function formatDateTime(value) {
    if (!value) return '---';

    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return String(value);

    return new Intl.DateTimeFormat('pt-BR', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    }).format(date);
  }

  function firstFilled() {
    for (let i = 0; i < arguments.length; i += 1) {
      const text = String(arguments[i] || '').trim();
      if (text) return text;
    }
    return '';
  }

  function getTokenFromUrl() {
    const params = new URLSearchParams(window.location.search);
    return String(params.get('acesso') || params.get('token') || '').trim();
  }

  function updateSteps(stepNumber) {
    document.querySelectorAll('.step-item').forEach((item) => {
      const step = Number(item.dataset.step || 0);
      item.classList.toggle('is-active', step === Number(stepNumber));
    });
  }

  function setStatusPill(text, mode) {
    dom.statusPill.textContent = text;
    dom.statusPill.className = `status-pill ${mode || ''}`.trim();
  }

  async function verificarToken() {
    state.acesso = getTokenFromUrl();

    if (!state.acesso) {
      setStatusPill('Sem token', 'invalid');
      dom.tokenStatusText.textContent = 'Nenhum token de acesso foi encontrado no link.';
      dom.authForm.hidden = true;
      showAlert('Link inválido. Use o link enviado pela equipe SEG ou solicite um novo acesso.', 'error');
      return;
    }

    setStatusPill('Verificando', '');
    dom.tokenStatusText.textContent = 'Verificando o link recebido...';
    showAlert('', 'info');

    try {
      const data = await apiJson(`/api/area-cliente-publica/status?acesso=${encodeURIComponent(state.acesso)}`);
      state.linkStatus = data;

      dom.tokenInfo.hidden = false;
      dom.tokenHint.textContent = data.token_hint || '---';
      dom.tokenExpires.textContent = formatDateTime(data.expira_em);

      if (!data.valido) {
        setStatusPill(data.status || 'Indisponível', 'invalid');
        dom.tokenStatusText.textContent = data.mensagem || 'Este acesso não está disponível.';
        dom.authForm.hidden = true;
        showAlert(data.mensagem || 'Este link não está disponível. Solicite um novo acesso à equipe SEG.', 'error');
        return;
      }

      setStatusPill('Válido', 'valid');
      dom.tokenStatusText.textContent = data.mensagem || 'Acesso válido. Informe sua senha provisória.';
      dom.authForm.hidden = false;
      showAlert('Digite a senha provisória enviada junto com o link.', 'info');
    } catch (error) {
      console.error('[Área do Cliente] erro ao validar token:', error);
      setStatusPill('Erro', 'invalid');
      dom.authForm.hidden = true;
      dom.tokenStatusText.textContent = 'Não foi possível validar o link.';
      showAlert(error.message || 'Não foi possível validar o acesso.', 'error');
    }
  }

  async function autenticar(event) {
    event.preventDefault();

    if (state.loading) return;

    const senha = String(dom.senha.value || '').trim();

    if (!state.acesso) {
      showAlert('Token de acesso não encontrado no link.', 'error');
      return;
    }

    if (!senha) {
      showAlert('Digite a senha provisória para continuar.', 'error');
      dom.senha.focus();
      return;
    }

    setLoading(true, 'Validando senha provisória...');

    try {
      const data = await apiJson('/api/area-cliente-publica/autenticar', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          acesso: state.acesso,
          senha_provisoria: senha,
        }),
      });

      state.sessionToken = data.session_token || '';
      state.cliente = data.cliente || null;
      state.dados = data.dados || null;

      renderCliente();
      preencherFormulario(state.dados || {});
      mostrarFormulario();
      updateSteps(2);
      showAlert('Acesso validado. Confira e complete seus dados.', 'success');
    } catch (error) {
      console.error('[Área do Cliente] erro ao autenticar:', error);
      showAlert(error.message || 'Senha provisória inválida.', 'error');
    } finally {
      setLoading(false);
    }
  }

  function mostrarFormulario() {
    dom.clienteCard.hidden = false;
    dom.dadosForm.hidden = false;
    dom.successCard.hidden = true;
    dom.tokenCard.hidden = true;

    setTimeout(() => {
      dom.clienteCard.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 80);
  }

  function renderCliente() {
    const cliente = state.cliente || {};
    const nome = firstFilled(cliente.nome, 'Cliente SEG');
    const documento = firstFilled(cliente.documento, 'Documento não informado');
    const email = firstFilled(cliente.email, 'E-mail não informado');
    const telefone = firstFilled(cliente.telefone, 'Telefone não informado');

    dom.clienteNome.textContent = nome;
    dom.clienteCodigo.textContent = cliente.codigo || '---';
    dom.clienteResumo.textContent = `${documento} • ${email} • ${telefone}`;
  }

  function preencherFormulario(dados) {
    fields.forEach((field) => {
      const el = byId(field);
      if (!el) return;

      const value = dados[field];
      el.value = value === null || value === undefined ? '' : String(value);
    });

    if (!dom.tipoPessoa.value) dom.tipoPessoa.value = 'PF';
    atualizarTipoPessoa();
  }

  function coletarFormulario(finalizar) {
    const payload = {
      session_token: state.sessionToken,
      finalizar: Boolean(finalizar),
    };

    fields.forEach((field) => {
      const el = byId(field);
      if (!el) return;
      payload[field] = String(el.value || '').trim() || null;
    });

    payload.tipo_pessoa = payload.tipo_pessoa || 'PF';
    return payload;
  }

  function atualizarTipoPessoa() {
    const tipo = String(dom.tipoPessoa.value || 'PF').toUpperCase();
    dom.pjSection.hidden = tipo !== 'PJ';
  }

  function fieldValue(id) {
    const el = byId(id);
    return String((el && el.value) || '').trim();
  }

  function validarObrigatorios(finalizar) {
    if (!finalizar) return true;

    const tipo = String(dom.tipoPessoa.value || 'PF').toUpperCase();

    const base = [
      ['imovel_rua', 'Rua do imóvel'],
      ['imovel_numero', 'Número do imóvel'],
      ['imovel_bairro', 'Bairro do imóvel'],
      ['imovel_cidade', 'Cidade do imóvel'],
      ['imovel_uf', 'UF do imóvel'],
      ['imovel_cep', 'CEP do imóvel'],
    ];

    const pf = [
      ['nome_completo', 'Nome completo'],
      ['cpf', 'CPF'],
      ['rg', 'RG'],
      ['email_pessoal', 'E-mail pessoal'],
      ['telefone_pessoal', 'Telefone pessoal'],
    ];

    const pj = [
      ['razao_social', 'Razão social'],
      ['cnpj', 'CNPJ'],
      ['email_empresa', 'E-mail da empresa'],
      ['telefone_whatsapp_empresa', 'WhatsApp da empresa'],
      ['representante_nome', 'Nome do representante'],
      ['representante_cpf', 'CPF do representante'],
    ];

    const required = tipo === 'PJ' ? base.concat(pj) : base.concat(pf);

    for (const item of required) {
      const id = item[0];
      const label = item[1];
      if (!fieldValue(id)) {
        showAlert(`Preencha o campo obrigatório: ${label}.`, 'error');
        const el = byId(id);
        if (el) {
          el.focus();
          el.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
        return false;
      }
    }

    return true;
  }

  async function salvarDados(finalizar) {
    if (state.loading) return;

    if (!state.sessionToken) {
      showAlert('Sessão não encontrada. Acesse novamente pelo link enviado.', 'error');
      return;
    }

    if (!validarObrigatorios(finalizar)) return;

    if (finalizar) {
      const ok = window.confirm('Finalizar e enviar seus dados para análise? Depois disso, este acesso provisório não poderá ser usado novamente.');
      if (!ok) return;
    }

    setLoading(true, finalizar ? 'Enviando dados para análise...' : 'Salvando rascunho...');

    try {
      const data = await apiJson('/api/area-cliente-publica/dados', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(coletarFormulario(finalizar)),
      });

      state.dados = data.dados || state.dados;

      if (data.finalizado) {
        updateSteps(3);
        dom.dadosForm.hidden = true;
        dom.clienteCard.hidden = true;
        dom.successCard.hidden = false;
        showAlert('Dados enviados com sucesso.', 'success');
        dom.successCard.scrollIntoView({ behavior: 'smooth', block: 'center' });
        return;
      }

      preencherFormulario(state.dados || {});
      showAlert('Rascunho salvo com sucesso.', 'success');
    } catch (error) {
      console.error('[Área do Cliente] erro ao salvar dados:', error);
      showAlert(error.message || 'Não foi possível salvar os dados.', 'error');
    } finally {
      setLoading(false);
    }
  }

  function bindEvents() {
    dom.authForm.addEventListener('submit', autenticar);

    dom.toggleSenha.addEventListener('click', () => {
      const isPassword = dom.senha.type === 'password';
      dom.senha.type = isPassword ? 'text' : 'password';
      dom.toggleSenha.innerHTML = isPassword
        ? '<i class="fas fa-eye-slash"></i>'
        : '<i class="fas fa-eye"></i>';
    });

    dom.tipoPessoa.addEventListener('change', atualizarTipoPessoa);

    dom.btnSalvarRascunho.addEventListener('click', () => salvarDados(false));
    dom.btnFinalizar.addEventListener('click', () => salvarDados(true));
  }

  function boot() {
    initDom();
    bindEvents();
    updateSteps(1);
    verificarToken();
  }

  document.addEventListener('DOMContentLoaded', boot);
})();
