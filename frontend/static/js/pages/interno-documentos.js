(function () {
  'use strict';

  const grid = document.getElementById('documentos-grid');
  if (!grid) return;

  const state = {
    documentos: [],
    categorias: [],
    tipo: 'todos',
    categoria: 'Todos',
    busca: '',
    podeGerenciar: false,
    editingId: null,
  };

  const $ = (id) => document.getElementById(id);
  const busca = $('documentos-busca');
  const empty = $('documentos-empty');
  const total = $('documentos-total');
  const catList = $('documentos-categorias-list');
  const listTitle = $('documentos-list-title');
  const listSubtitle = $('documentos-list-subtitle');
  const formModal = $('documentos-modal');
  const viewModal = $('documentos-view-modal');
  const form = $('documentos-form');
  const typeField = $('documento-tipo');
  const contentField = document.querySelector('[data-field-content]');
  const contactFields = document.querySelector('[data-field-contact]');
  const fileField = document.querySelector('[data-field-file]');
  const fileCurrent = $('documento-arquivo-atual');
  const formMessage = $('documentos-form-message');
  const newButton = $('btn-novo-documento');

  function esc(value) {
    return String(value ?? '').replace(/[&<>'"]/g, (char) => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
    })[char]);
  }

  function formatDate(value) {
    if (!value) return '';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return '';
    return date.toLocaleDateString('pt-BR');
  }

  function iconFor(tipo) {
    if (tipo === 'pdf') return 'fa-solid fa-file-pdf';
    if (tipo === 'manual') return 'fa-solid fa-book';
    if (tipo === 'contato') return 'fa-solid fa-address-book';
    return 'fa-solid fa-list-check';
  }

  function filtered() {
    const term = state.busca.trim().toLowerCase();
    return state.documentos.filter((item) => {
      if (state.tipo !== 'todos' && item.tipo !== state.tipo) return false;
      if (state.categoria !== 'Todos' && item.categoria !== state.categoria) return false;
      if (!term) return true;
      return [item.titulo, item.descricao, item.conteudo, item.categoria, item.contato_nome, item.telefone, item.email]
        .some((field) => String(field || '').toLowerCase().includes(term));
    });
  }

  function renderCategories() {
    const categories = [...new Set(state.categorias.filter(Boolean))];
    const datalist = $('documentos-categorias-datalist');
    if (datalist) datalist.innerHTML = categories.map((category) => `<option value="${esc(category)}"></option>`).join('');
    catList.innerHTML = categories.map((category) => `
      <button type="button" class="${state.categoria === category ? 'is-active' : ''}" data-categoria="${esc(category)}">${esc(category)}</button>
    `).join('');

    document.querySelectorAll('.documentos-categorias [data-categoria]').forEach((button) => {
      button.addEventListener('click', () => {
        state.categoria = button.dataset.categoria || 'Todos';
        document.querySelectorAll('.documentos-categorias [data-categoria]').forEach((item) => item.classList.toggle('is-active', item === button));
        if (state.categoria === 'Todos') document.querySelector('.documentos-categorias>button[data-categoria="Todos"]')?.classList.add('is-active');
        render();
      });
    });
  }

  function render() {
    const items = filtered();
    total.textContent = String(state.documentos.length);
    listTitle.textContent = state.categoria === 'Todos' ? 'Todos os documentos' : state.categoria;
    listSubtitle.textContent = `${items.length} item${items.length === 1 ? '' : 'ns'} disponível${items.length === 1 ? '' : 'is'} para a equipe.`;
    empty.hidden = items.length > 0;

    grid.innerHTML = items.map((item) => {
      const isContact = item.tipo === 'contato';
      const actions = [];
      if (item.tipo === 'pdf' && item.arquivo_url) {
        actions.push(`<a href="${esc(item.arquivo_url)}" target="_blank" rel="noopener"><i class="fa-regular fa-eye"></i> Abrir PDF</a>`);
      } else {
        actions.push(`<button type="button" data-view="${item.id}"><i class="fa-regular fa-eye"></i> Abrir</button>`);
      }
      if (state.podeGerenciar) {
        actions.push(`<button type="button" data-edit="${item.id}"><i class="fa-solid fa-pen"></i></button>`);
        actions.push(`<button type="button" class="danger" data-delete="${item.id}"><i class="fa-regular fa-trash-can"></i></button>`);
      }

      return `
        <article class="documento-card">
          <div class="documento-card-top">
            <div class="documento-icon"><i class="${iconFor(item.tipo)}"></i></div>
            <span class="documento-kind">${esc(item.tipo_label)}</span>
          </div>
          <h3>${esc(item.titulo)}</h3>
          <p>${esc(item.descricao || (item.tipo === 'pdf' ? item.arquivo_nome : item.conteudo) || 'Sem descrição.')}</p>
          ${isContact ? `
            <div class="documento-contact">
              ${item.contato_nome ? `<div class="documento-contact-line"><i class="fa-regular fa-user"></i><span>${esc(item.contato_nome)}</span></div>` : ''}
              ${item.telefone ? `<div class="documento-contact-line"><i class="fa-solid fa-phone"></i><span>${esc(item.telefone)}</span></div>` : ''}
              ${item.email ? `<div class="documento-contact-line"><i class="fa-regular fa-envelope"></i><span>${esc(item.email)}</span></div>` : ''}
            </div>` : ''}
          <span class="documento-category">${esc(item.categoria)}</span>
          <div class="documento-footer">
            <span class="documento-meta">${esc(item.criado_por_nome || 'Administração')} · ${esc(formatDate(item.criado_em))}</span>
            <div class="documento-actions">${actions.join('')}</div>
          </div>
        </article>`;
    }).join('');

    grid.querySelectorAll('[data-view]').forEach((button) => button.addEventListener('click', () => openView(Number(button.dataset.view))));
    grid.querySelectorAll('[data-edit]').forEach((button) => button.addEventListener('click', () => openEdit(Number(button.dataset.edit))));
    grid.querySelectorAll('[data-delete]').forEach((button) => button.addEventListener('click', () => deleteDocument(Number(button.dataset.delete))));
  }

  function updateFields() {
    const type = typeField.value;
    contentField.hidden = type === 'pdf' || type === 'contato';
    contactFields.hidden = type !== 'contato';
    fileField.hidden = type !== 'pdf';
    if (type !== 'pdf') $('documento-arquivo').value = '';
  }

  function openModal() {
    formModal.hidden = false;
    document.body.style.overflow = 'hidden';
    $('documento-titulo').focus();
  }

  function closeModal() {
    formModal.hidden = true;
    document.body.style.overflow = '';
    form.reset();
    $('documento-id').value = '';
    state.editingId = null;
    $('documentos-modal-title').textContent = 'Novo documento';
    $('documentos-modal-kicker').textContent = 'Documento';
    fileCurrent.textContent = 'Máximo de 15 MB.';
    formMessage.textContent = '';
    updateFields();
  }

  function openView(id) {
    const item = state.documentos.find((doc) => doc.id === id);
    if (!item) return;
    $('documentos-view-title').textContent = item.titulo;
    $('documentos-view-type').textContent = `${item.tipo_label} · ${item.categoria}`;
    $('documentos-view-meta').innerHTML = [item.descricao, item.contato_nome, item.telefone, item.email, item.observacao]
      .filter(Boolean).map((value) => `<span>${esc(value)}</span>`).join('');
    let body = '';
    if (item.tipo === 'pdf' && item.arquivo_url) {
      body = `<p>Arquivo: <strong>${esc(item.arquivo_nome || 'PDF')}</strong></p><p><a href="${esc(item.arquivo_url)}" target="_blank" rel="noopener">Abrir PDF em uma nova aba</a></p>`;
    } else if (item.tipo === 'contato') {
      body = `<p>${esc(item.conteudo || 'Contato útil da SEG.')}</p>`;
      if (item.telefone) body += `<p><strong>Telefone:</strong> ${esc(item.telefone)}</p>`;
      if (item.email) body += `<p><strong>E-mail:</strong> ${esc(item.email)}</p>`;
    } else {
      body = `<div>${esc(item.conteudo || item.descricao || 'Sem conteúdo cadastrado.')}</div>`;
    }
    $('documentos-view-body').innerHTML = body;
    viewModal.hidden = false;
    document.body.style.overflow = 'hidden';
  }

  function closeView() {
    viewModal.hidden = true;
    document.body.style.overflow = '';
  }

  function openEdit(id) {
    const item = state.documentos.find((doc) => doc.id === id);
    if (!item) return;
    state.editingId = id;
    $('documentos-modal-title').textContent = 'Editar documento';
    $('documentos-modal-kicker').textContent = item.tipo_label;
    $('documento-id').value = item.id;
    $('documento-titulo').value = item.titulo || '';
    $('documento-categoria').value = item.categoria || 'Geral';
    $('documento-tipo').value = item.tipo || 'procedimento';
    $('documento-descricao').value = item.descricao || '';
    $('documento-conteudo').value = item.conteudo || '';
    $('documento-contato-nome').value = item.contato_nome || '';
    $('documento-telefone').value = item.telefone || '';
    $('documento-email').value = item.email || '';
    $('documento-observacao').value = item.observacao || '';
    fileCurrent.textContent = item.arquivo_nome ? `Atual: ${item.arquivo_nome}. Selecione outro PDF para substituir.` : 'Máximo de 15 MB.';
    updateFields();
    openModal();
  }

  async function load() {
    grid.innerHTML = '<div class="documentos-empty"><div class="documentos-empty-icon"><i class="fa-solid fa-spinner fa-spin"></i></div><strong>Carregando documentos...</strong></div>';
    try {
      const response = await fetch('/api/interno/documentos', { headers: { 'Accept': 'application/json' } });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || 'Não foi possível carregar os documentos.');
      state.documentos = data.documentos || [];
      state.categorias = data.categorias || [];
      state.podeGerenciar = Boolean(data.pode_gerenciar);
      newButton.hidden = !state.podeGerenciar;
      renderCategories();
      render();
    } catch (error) {
      grid.innerHTML = '';
      empty.hidden = false;
      empty.querySelector('strong').textContent = error.message || 'Não foi possível carregar os documentos.';
      empty.querySelector('span').textContent = 'Atualize a página e tente novamente.';
    }
  }

  async function submitForm(event) {
    event.preventDefault();
    const button = $('btn-salvar-documento');
    button.disabled = true;
    formMessage.textContent = 'Salvando...';
    try {
      const data = new FormData(form);
      const id = state.editingId;
      const response = await fetch(id ? `/api/interno/documentos/${id}` : '/api/interno/documentos', {
        method: id ? 'PUT' : 'POST',
        body: data,
        headers: { 'Accept': 'application/json' },
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload.detail || 'Não foi possível salvar o documento.');
      closeModal();
      await load();
    } catch (error) {
      formMessage.textContent = error.message || 'Não foi possível salvar.';
      button.disabled = false;
    }
  }

  async function deleteDocument(id) {
    const item = state.documentos.find((doc) => doc.id === id);
    if (!item || !window.confirm(`Excluir "${item.titulo}"?`)) return;
    try {
      const response = await fetch(`/api/interno/documentos/${id}`, { method: 'DELETE', headers: { 'Accept': 'application/json' } });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || 'Não foi possível excluir.');
      await load();
    } catch (error) {
      window.alert(error.message || 'Não foi possível excluir o documento.');
    }
  }

  newButton?.addEventListener('click', openModal);
  $('btn-reload-documentos')?.addEventListener('click', load);
  busca?.addEventListener('input', () => { state.busca = busca.value; render(); });
  typeField?.addEventListener('change', updateFields);
  form?.addEventListener('submit', submitForm);
  document.querySelectorAll('[data-close-modal]').forEach((item) => item.addEventListener('click', closeModal));
  document.querySelectorAll('[data-close-view]').forEach((item) => item.addEventListener('click', closeView));
  document.querySelectorAll('.documentos-type-tabs [data-tipo]').forEach((button) => {
    button.addEventListener('click', () => {
      state.tipo = button.dataset.tipo || 'todos';
      document.querySelectorAll('.documentos-type-tabs button').forEach((item) => item.classList.toggle('is-active', item === button));
      render();
    });
  });
  document.querySelector('.documentos-categorias>button[data-categoria="Todos"]')?.addEventListener('click', (event) => {
    state.categoria = 'Todos';
    document.querySelectorAll('.documentos-categorias [data-categoria]').forEach((item) => item.classList.toggle('is-active', item === event.currentTarget));
    render();
  });

  updateFields();
  load();
})();
