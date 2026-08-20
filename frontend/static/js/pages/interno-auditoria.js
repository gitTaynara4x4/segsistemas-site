(function () {
  'use strict';
  const core = window.SEGInternoCore;
  if (!core) return;
  const { qs, escapeHtml, formatDateTime, apiFetch, onReady } = core;

  function labelAction(acao) {
    const map = { CRIAR:'Criou', ALTERAR:'Alterou', ENCERRAR:'Encerrou', RESOLVER:'Resolveu', ASSUMIR:'Assumiu', ATIVAR:'Ativou', INATIVAR:'Inativou' };
    return map[acao] || String(acao || '').replaceAll('_',' ');
  }
  function load() {
    const params = new URLSearchParams();
    [['busca','#audit-busca'],['modulo','#audit-modulo'],['acao','#audit-acao'],['data_inicio','#audit-inicio'],['data_fim','#audit-fim']].forEach(([key,sel]) => { const el=qs(sel); if(el&&el.value) params.set(key,el.value); });
    apiFetch('/api/interno/auditoria?' + params.toString()).then(data => {
      const rows = qs('#audit-list');
      const empty = qs('#audit-vazio');
      const items = data.auditoria || [];
      if (qs('#audit-total')) qs('#audit-total').textContent = data.resumo?.total || 0;
      if (qs('#audit-hoje')) qs('#audit-hoje').textContent = data.resumo?.hoje || 0;
      if (!items.length) { rows.innerHTML=''; empty.hidden=false; return; }
      empty.hidden=true;
      rows.innerHTML = items.map(item => `
        <tr>
          <td><span class="audit-time">${escapeHtml(formatDateTime(item.criado_em))}</span></td>
          <td><strong>${escapeHtml(item.usuario_nome || item.usuario || 'Sistema')}</strong><small>${escapeHtml(item.usuario || '')}</small></td>
          <td><span class="audit-action audit-${escapeHtml(String(item.acao || '').toLowerCase())}">${escapeHtml(labelAction(item.acao))}</span></td>
          <td>${escapeHtml(item.modulo || '-')}</td>
          <td>${escapeHtml(item.entidade || '-')}${item.entidade_id ? ' #' + escapeHtml(item.entidade_id) : ''}</td>
          <td>${escapeHtml(item.descricao || '-')}</td>
        </tr>`).join('');
    }).catch(err => {
      const empty=qs('#audit-vazio'); if(empty){empty.hidden=false; empty.textContent=err.message || 'Não foi possível carregar o histórico.';}
    });
  }
  onReady(() => {
    ['#audit-busca','#audit-modulo','#audit-acao','#audit-inicio','#audit-fim'].forEach(sel => { const el=qs(sel); if(el) el.addEventListener(el.tagName==='INPUT'&&el.type==='search'?'input':'change', load); });
    const clear=qs('#audit-limpar'); if(clear) clear.addEventListener('click',()=>{['#audit-busca','#audit-modulo','#audit-acao','#audit-inicio','#audit-fim'].forEach(sel=>{const el=qs(sel);if(el)el.value='';});load();});
    const refresh=qs('#audit-atualizar'); if(refresh) refresh.addEventListener('click', load);
    load();
  });
})();
