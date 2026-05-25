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
    const estavaComPlantaoAberto = Boolean(state.plantao);

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
      setPlantaoMessage('success', estavaComPlantaoAberto ? 'Plantão finalizado com sucesso.' : 'Plantão iniciado com sucesso.');
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



  onReady(function () {
    bindPlantaoPage();
  });
})();
