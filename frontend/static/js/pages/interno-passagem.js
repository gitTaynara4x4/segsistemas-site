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

  function setPassagemMessage(type, text) {
    const box = qs('#passagem-message');
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

  function updatePassagemStats(resumo) {
    const safe = resumo || {};
    qsa('[data-passagem-stat]').forEach(function (el) {
      const key = el.getAttribute('data-passagem-stat');
      el.textContent = String(safe[key] || (key === 'data' ? '-' : 0));
    });
  }

  function passagemResumoCurto(passagem) {
    if (!passagem) return 'Sem detalhes informados.';

    const campos = [
      passagem.pendencias,
      passagem.clientes_observacao,
      passagem.falhas_sistema,
      passagem.ocorrencias_importantes,
      passagem.recado_proximo,
    ].filter(Boolean);

    if (!campos.length) return 'Sem detalhes informados.';

    const texto = campos.join(' • ');
    return texto.length > 180 ? texto.slice(0, 180) + '...' : texto;
  }

  function renderPassagemPendente() {
    const box = qs('#passagem-pendente-card');
    if (!box) return;

    const passagem = state.passagemPendente;
    if (!passagem) {
      box.hidden = true;
      box.innerHTML = '';
      return;
    }

    box.hidden = false;
    box.innerHTML = `
      <h3><i class="fa-solid fa-triangle-exclamation"></i> Existe passagem pendente</h3>
      <p>
        ${escapeHtml(passagem.passado_por_nome || 'Funcionário')} deixou uma passagem em
        ${escapeHtml(formatDateTime(passagem.passado_em))}. Leia o histórico e confirme que assumiu.
      </p>
      <p><strong>Resumo:</strong> ${escapeHtml(passagemResumoCurto(passagem))}</p>
      <button type="button" class="btn-small success" data-assumir-passagem="${escapeHtml(passagem.id)}">
        <i class="fa-solid fa-check"></i>
        Li e assumo o plantão
      </button>
    `;
  }

  function passagemSection(label, value) {
    if (!value) return '';
    return `
      <div class="passagem-section">
        <strong>${escapeHtml(label)}</strong>
        <span>${escapeHtml(value)}</span>
      </div>
    `;
  }

  function renderPassagensHoje() {
    const list = qs('#passagem-list');
    const empty = qs('#passagem-empty');
    if (!list || !empty) return;

    const passagens = Array.isArray(state.passagensHoje) ? state.passagensHoje : [];
    empty.hidden = passagens.length > 0;

    list.innerHTML = passagens.map(function (passagem) {
      const pendente = passagem.status === 'pendente';
      const statusTag = pendente
        ? '<span class="tag warn">Pendente</span>'
        : '<span class="tag">Recebida</span>';

      const recebeu = passagem.recebido_por_nome
        ? `<span><i class="fa-solid fa-user-check"></i> Recebida por ${escapeHtml(passagem.recebido_por_nome)} em ${escapeHtml(formatDateTime(passagem.recebido_em))}</span>`
        : '<span><i class="fa-solid fa-hourglass-half"></i> Aguardando próximo plantonista</span>';

      const assumirBtn = pendente ? `
        <button type="button" class="btn-small success" data-assumir-passagem="${escapeHtml(passagem.id)}">
          <i class="fa-solid fa-check"></i>
          Li e assumo
        </button>
      ` : '';

      return `
        <article class="passagem-card ${pendente ? 'pendente' : 'recebida'}">
          <div class="passagem-card-header">
            <div>
              <h3>Passagem deixada por ${escapeHtml(passagem.passado_por_nome || 'Funcionário')}</h3>
              <p>@${escapeHtml(passagem.passado_por_usuario || '-')} • ${escapeHtml(formatDateTime(passagem.passado_em))}</p>
            </div>
            ${statusTag}
          </div>

          <div class="passagem-section-list">
            ${passagemSection('Pendências', passagem.pendencias)}
            ${passagemSection('Clientes em observação', passagem.clientes_observacao)}
            ${passagemSection('Falhas de sistema', passagem.falhas_sistema)}
            ${passagemSection('Ocorrências importantes', passagem.ocorrencias_importantes)}
            ${passagemSection('Recado para o próximo plantonista', passagem.recado_proximo)}
          </div>

          <div class="passagem-footer">
            <span><i class="fa-solid fa-user-shield"></i> Registrada por ${escapeHtml(passagem.passado_por_nome || '-')}</span>
            ${recebeu}
          </div>

          ${assumirBtn ? `<div class="form-actions" style="margin-top: 12px;">${assumirBtn}</div>` : ''}
        </article>
      `;
    }).join('');
  }

  async function loadPassagens() {
    const page = qs('#passagem-page');
    if (!page || state.passagemCarregando) return;

    const reloadBtn = qs('#btn-reload-passagem');
    state.passagemCarregando = true;
    if (reloadBtn) reloadBtn.disabled = true;

    try {
      const data = await apiFetch('/api/interno/passagens/status');
      state.passagensHoje = Array.isArray(data.passagens_hoje) ? data.passagens_hoje : [];
      state.passagemPendente = data.ultima_pendente || null;
      updatePassagemStats(data.resumo || {});
      renderPassagemPendente();
      renderPassagensHoje();
      setPassagemMessage('', '');
    } catch (error) {
      setPassagemMessage('error', error.message || 'Erro ao carregar passagem de plantão.');
    } finally {
      state.passagemCarregando = false;
      if (reloadBtn) reloadBtn.disabled = false;
    }
  }

  function limparPassagemForm() {
    ['#passagem-pendencias', '#passagem-clientes', '#passagem-falhas', '#passagem-ocorrencias', '#passagem-recado'].forEach(function (selector) {
      const el = qs(selector);
      if (el) el.value = '';
    });

    const confirm = qs('#passagem-confirmacao');
    if (confirm) confirm.checked = false;
  }

  async function submitPassagem(event) {
    event.preventDefault();

    const btn = qs('#btn-passagem-save');
    const confirm = qs('#passagem-confirmacao');

    if (!confirm || !confirm.checked) {
      setPassagemMessage('error', 'Confirme que você está registrando esta passagem de plantão.');
      return;
    }

    const payload = {
      pendencias: qs('#passagem-pendencias') ? qs('#passagem-pendencias').value.trim() : '',
      clientes_observacao: qs('#passagem-clientes') ? qs('#passagem-clientes').value.trim() : '',
      falhas_sistema: qs('#passagem-falhas') ? qs('#passagem-falhas').value.trim() : '',
      ocorrencias_importantes: qs('#passagem-ocorrencias') ? qs('#passagem-ocorrencias').value.trim() : '',
      recado_proximo: qs('#passagem-recado') ? qs('#passagem-recado').value.trim() : '',
      confirmacao: true,
    };

    if (!payload.pendencias && !payload.clientes_observacao && !payload.falhas_sistema && !payload.ocorrencias_importantes && !payload.recado_proximo) {
      setPassagemMessage('error', 'Preencha pelo menos um campo da passagem.');
      return;
    }

    if (btn) {
      btn.disabled = true;
      btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Salvando...';
    }

    try {
      await apiFetch('/api/interno/passagens', {
        method: 'POST',
        body: JSON.stringify(payload),
      });
      limparPassagemForm();
      await loadPassagens();
      setPassagemMessage('success', 'Passagem de plantão salva com sucesso.');
    } catch (error) {
      setPassagemMessage('error', error.message || 'Erro ao salvar passagem.');
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = '<i class="fa-solid fa-floppy-disk"></i> Salvar passagem';
      }
    }
  }

  async function assumirPassagem(id) {
    if (!id) return;

    const confirma = window.confirm('Confirmar que você leu esta passagem e está assumindo o plantão?');
    if (!confirma) return;

    try {
      await apiFetch('/api/interno/passagens/' + encodeURIComponent(id) + '/assumir', {
        method: 'POST',
        body: JSON.stringify({ confirmacao: true }),
      });
      await loadPassagens();
      setPassagemMessage('success', 'Passagem recebida e assumida com sucesso.');
    } catch (error) {
      setPassagemMessage('error', error.message || 'Erro ao assumir passagem.');
    }
  }

  function bindPassagemPage() {
    const page = qs('#passagem-page');
    if (!page) return;

    const form = qs('#passagem-form');
    if (form) form.addEventListener('submit', submitPassagem);

    const btnReload = qs('#btn-reload-passagem');
    if (btnReload) btnReload.addEventListener('click', loadPassagens);

    page.addEventListener('click', function (event) {
      const btn = event.target.closest('[data-assumir-passagem]');
      if (!btn) return;
      assumirPassagem(btn.getAttribute('data-assumir-passagem'));
    });

    loadPassagens();
  }



  onReady(function () {
    bindPassagemPage();
  });
})();
