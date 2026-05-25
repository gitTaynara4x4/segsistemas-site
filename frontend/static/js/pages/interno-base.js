(function () {
  'use strict';

  const state = {
    funcionarios: [],
    filtro: '',
    salvando: false,
    plantao: null,
    plantoesHoje: [],
    plantaoCarregando: false,
    passagensHoje: [],
    passagemPendente: null,
    passagemCarregando: false,
    manualFiltro: 'todos',
    manualBusca: '',
    ocorrencias: [],
    ocorrenciaBusca: '',
    ocorrenciaStatus: '',
    ocorrenciaTipo: '',
    ocorrenciaPrioridade: '',
    ocorrenciasCarregando: false,
    ocorrenciaSalvando: false,
    pontoAtual: null,
    pontosHoje: [],
    pontoCarregando: false,
    pontoAcaoSalvando: false,
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

  function onReady(callback) {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', callback);
    } else {
      callback();
    }
  }

  window.SEGInternoCore = {
    state,
    qs,
    qsa,
    escapeHtml,
    normalize,
    apiFetch,
    initPasswordToggle,
    formatDateTime,
    onReady,
  };
})();
