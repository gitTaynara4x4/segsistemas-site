(function () {
      "use strict";

      const state = {
        pontoAtual: null,
        pontosHoje: [],
        pontosRelatorio: [],
        pontosMesPorData: {},
        funcionarios: [],
        selectedDay: "",
        carregando: false,
        salvando: false,
      };

      function qs(selector, root) {
        return (root || document).querySelector(selector);
      }

      function qsa(selector, root) {
        return Array.from((root || document).querySelectorAll(selector));
      }

      function escapeHtml(value) {
        return String(value || "")
          .replaceAll("&", "&amp;")
          .replaceAll("<", "&lt;")
          .replaceAll(">", "&gt;")
          .replaceAll('"', "&quot;")
          .replaceAll("'", "&#039;");
      }

      function normalize(value) {
        return String(value || "")
          .toLowerCase()
          .normalize("NFD")
          .replace(/[\u0300-\u036f]/g, "")
          .trim();
      }

      function todayIso() {
        const now = new Date();
        const offset = now.getTimezoneOffset();
        const local = new Date(now.getTime() - offset * 60000);
        return local.toISOString().slice(0, 10);
      }

      function currentMonthIso() {
        return todayIso().slice(0, 7);
      }

      function parseDateIso(value) {
        if (!value) return null;

        const parts = String(value).split("-");
        if (parts.length !== 3) return null;

        const year = Number(parts[0]);
        const month = Number(parts[1]);
        const day = Number(parts[2]);

        if (!year || !month || !day) return null;

        return new Date(year, month - 1, day);
      }

      function dateToIso(date) {
        const y = date.getFullYear();
        const m = String(date.getMonth() + 1).padStart(2, "0");
        const d = String(date.getDate()).padStart(2, "0");
        return `${y}-${m}-${d}`;
      }

      function monthLabel(monthIso) {
        const parts = String(monthIso || "").split("-");
        if (parts.length !== 2) return "Calendário";

        const year = Number(parts[0]);
        const month = Number(parts[1]);

        if (!year || !month) return "Calendário";

        return new Date(year, month - 1, 1).toLocaleDateString("pt-BR", {
          month: "long",
          year: "numeric",
        });
      }

      function dateRange(startIso, endIso) {
        const start = parseDateIso(startIso);
        const end = parseDateIso(endIso);

        if (!start || !end || start > end) return [];

        const days = [];
        const current = new Date(start.getTime());

        while (current <= end && days.length <= 62) {
          days.push(dateToIso(current));
          current.setDate(current.getDate() + 1);
        }

        return days;
      }

      function monthDays(monthIso) {
        const parts = String(monthIso || "").split("-");
        const year = Number(parts[0]);
        const month = Number(parts[1]);

        if (!year || !month) return [];

        const first = new Date(year, month - 1, 1);
        const last = new Date(year, month, 0);
        const start = new Date(first.getTime());
        const end = new Date(last.getTime());

        start.setDate(start.getDate() - start.getDay());
        end.setDate(end.getDate() + (6 - end.getDay()));

        const days = [];
        const current = new Date(start.getTime());

        while (current <= end) {
          days.push({
            iso: dateToIso(current),
            day: current.getDate(),
            inMonth: current.getMonth() === first.getMonth(),
          });
          current.setDate(current.getDate() + 1);
        }

        return days;
      }

      async function apiFetch(url, options) {
        const response = await fetch(url, {
          credentials: "same-origin",
          headers: {
            Accept: "application/json",
            "Content-Type": "application/json",
            ...(options && options.headers ? options.headers : {}),
          },
          ...(options || {}),
        });

        let data = null;

        try {
          data = await response.json();
        } catch (error) {
          data = { ok: false, detail: "Resposta inválida do servidor." };
        }

        if (response.status === 401) {
          window.location.href = "/interno/login?next=" + encodeURIComponent(window.location.pathname);
          return Promise.reject(new Error("Não autenticado."));
        }

        if (!response.ok || data.ok === false) {
          throw new Error(data.detail || "Não foi possível concluir a ação.");
        }

        return data;
      }

      async function tryPost(endpoints, payload) {
        let lastError = null;

        for (const endpoint of endpoints) {
          try {
            return await apiFetch(endpoint, {
              method: "POST",
              body: JSON.stringify(payload || {}),
            });
          } catch (error) {
            lastError = error;
          }
        }

        throw lastError || new Error("Não foi possível concluir a ação.");
      }

      function setMessage(type, text) {
        const box = qs("#ponto-message");
        if (!box) return;

        if (!text) {
          box.className = "ponto-message";
          box.textContent = "";
          return;
        }

        box.className = "ponto-message show " + (type || "success");
        box.textContent = text;
      }

      function formatDateTime(value) {
        if (!value) return "-";

        const date = new Date(value);
        if (Number.isNaN(date.getTime())) return "-";

        return date.toLocaleString("pt-BR", {
          timeZone: "America/Sao_Paulo",
          day: "2-digit",
          month: "2-digit",
          year: "numeric",
          hour: "2-digit",
          minute: "2-digit",
        });
      }

      function formatTimeOnly(value) {
        if (!value) return "-";

        const date = new Date(value);
        if (Number.isNaN(date.getTime())) return "-";

        return date.toLocaleTimeString("pt-BR", {
          timeZone: "America/Sao_Paulo",
          hour: "2-digit",
          minute: "2-digit",
        });
      }

      function secondsToLabel(seconds) {
        const safe = Math.max(Number(seconds || 0), 0);
        const hours = Math.floor(safe / 3600);
        const minutes = Math.floor((safe % 3600) / 60);

        if (hours <= 0 && minutes <= 0) return "0 min";
        if (hours <= 0) return `${minutes} min`;

        return `${hours}h ${String(minutes).padStart(2, "0")}min`;
      }

      function normalizeStatus(status) {
        const safe = normalize(status);

        if (safe === "em_pausa") return "pausado";
        if (safe === "pausa") return "pausado";
        if (safe === "aberto") return "aberto";
        if (safe === "finalizado") return "finalizado";

        return safe || "";
      }

      function statusLabel(status) {
        const safe = normalizeStatus(status);

        if (safe === "aberto") return "Trabalhando";
        if (safe === "pausado") return "Em pausa";
        if (safe === "finalizado") return "Finalizado";

        return "Sem ponto aberto";
      }

      function statusTagClass(status) {
        const safe = normalizeStatus(status);

        if (safe === "aberto") return "green";
        if (safe === "pausado") return "orange";
        if (safe === "finalizado") return "blue";

        return "blue";
      }

      function statusIcon(status) {
        const safe = normalizeStatus(status);

        if (safe === "aberto") {
          return { cls: "", icon: "fa-solid fa-user-check" };
        }

        if (safe === "pausado") {
          return { cls: "pause", icon: "fa-solid fa-mug-hot" };
        }

        return { cls: "closed", icon: "fa-regular fa-clock" };
      }

      function pontoTotalSeconds(ponto) {
        return Number(
          ponto && (
            ponto.duracao_total_segundos ||
            ponto.duracao_segundos ||
            ponto.total_segundos ||
            0
          )
        );
      }

      function pontoPausasSeconds(ponto) {
        return Number(
          ponto && (
            ponto.duracao_pausas_segundos ||
            ponto.pausa_total_segundos ||
            ponto.total_pausa_segundos ||
            0
          )
        );
      }

      function pontoLiquidoSeconds(ponto) {
        const explicit = Number(
          ponto && (
            ponto.duracao_liquida_segundos ||
            ponto.tempo_trabalhado_segundos ||
            ponto.total_trabalhado_segundos ||
            0
          )
        );

        if (explicit > 0) return explicit;

        const bruto = pontoTotalSeconds(ponto);
        const pausas = pontoPausasSeconds(ponto);

        return Math.max(bruto - pausas, 0);
      }

      function pontoTotalLabel(ponto) {
        return ponto && (
          ponto.duracao_total_label ||
          ponto.duracao_label ||
          secondsToLabel(pontoTotalSeconds(ponto))
        );
      }

      function pontoPausasLabel(ponto) {
        return ponto && (
          ponto.duracao_pausas_label ||
          ponto.pausa_total_label ||
          ponto.total_pausa_label ||
          secondsToLabel(pontoPausasSeconds(ponto))
        );
      }

      function pontoLiquidoLabel(ponto) {
        return ponto && (
          ponto.duracao_liquida_label ||
          ponto.tempo_trabalhado_label ||
          ponto.total_trabalhado_label ||
          secondsToLabel(pontoLiquidoSeconds(ponto))
        );
      }

      function getPausas(ponto) {
        if (!ponto) return [];
        if (Array.isArray(ponto.pausas)) return ponto.pausas;
        if (Array.isArray(ponto.intervalos)) return ponto.intervalos;
        return [];
      }

      function ultimaPausaAberta(ponto) {
        const pausas = getPausas(ponto);

        for (let i = pausas.length - 1; i >= 0; i -= 1) {
          const pausa = pausas[i];
          if (pausa && (pausa.inicio_em || pausa.iniciado_em) && !(pausa.fim_em || pausa.finalizado_em)) {
            return pausa;
          }
        }

        if (ponto && (ponto.pausa_iniciada_em || ponto.ultima_pausa_inicio)) {
          return {
            inicio_em: ponto.pausa_iniciada_em || ponto.ultima_pausa_inicio,
            fim_em: "",
          };
        }

        return null;
      }

      function pontoObservacaoResumo(ponto) {
        if (!ponto) return "";

        const pausas = getPausas(ponto);
        const obsPausas = pausas.flatMap(function (pausa, index) {
          const n = index + 1;
          return [
            pausa.observacao_inicio ? `Pausa ${n}: ${pausa.observacao_inicio}` : "",
            pausa.observacao_fim ? `Retorno ${n}: ${pausa.observacao_fim}` : "",
          ];
        });

        const campos = [
          ponto.observacao_entrada ? "Entrada: " + ponto.observacao_entrada : "",
          ...obsPausas,
          ponto.observacao_saida ? "Saída: " + ponto.observacao_saida : "",
          ponto.observacao ? ponto.observacao : "",
        ].filter(Boolean);

        return campos.join("\n");
      }

      function updateStats(resumo) {
        const safe = resumo || {};

        qsa("[data-ponto-stat]").forEach(function (el) {
          const key = el.getAttribute("data-ponto-stat");
          const fallbackKey = key === "ativos_agora" ? "presentes" : key;
          el.textContent = String(safe[key] || safe[fallbackKey] || 0);
        });
      }

      function updateButtons() {
        const entrada = qs("#btn-ponto-entrada");
        const pausa = qs("#btn-ponto-pausa");
        const retorno = qs("#btn-ponto-retorno");
        const saida = qs("#btn-ponto-saida");

        const ponto = state.pontoAtual;
        const status = normalizeStatus(ponto ? ponto.status : "");

        if (entrada) entrada.disabled = Boolean(ponto) || state.salvando;
        if (pausa) pausa.disabled = !ponto || status !== "aberto" || state.salvando;
        if (retorno) retorno.disabled = !ponto || status !== "pausado" || state.salvando;
        if (saida) saida.disabled = !ponto || status === "finalizado" || state.salvando;
      }

      function renderStatus() {
        const card = qs("#ponto-status-card");
        const title = qs("#ponto-status-title");
        const confirm = qs("#ponto-confirmacao");
        const labelConfirm = qs("#ponto-confirmacao-label");

        if (!card) return;

        const ponto = state.pontoAtual;
        const status = normalizeStatus(ponto ? ponto.status : "");
        const icon = statusIcon(status);

        if (title) {
          title.textContent = ponto ? "Ponto em andamento" : "Nenhum ponto aberto";
        }

        if (confirm) confirm.checked = false;

        if (labelConfirm) {
          if (!ponto) {
            labelConfirm.textContent = "Confirmo que estou batendo minha entrada no ponto online.";
          } else if (status === "pausado") {
            labelConfirm.textContent = "Confirmo que estou retornando da pausa ou finalizando meu ponto.";
          } else {
            labelConfirm.textContent = "Confirmo que estou registrando esta ação no ponto online.";
          }
        }

        if (!ponto) {
          card.innerHTML = `
            <div class="ponto-status-big">
              <span class="ponto-status-icon closed">
                <i class="fa-regular fa-clock"></i>
              </span>

              <div class="ponto-status-info">
                <strong>Você ainda não bateu entrada hoje.</strong>
                <p>Clique em Entrada para iniciar sua jornada do dia.</p>

                <div class="ponto-status-tags">
                  <span class="ponto-tag blue">
                    <i class="fa-regular fa-circle"></i>
                    Sem ponto aberto
                  </span>
                </div>
              </div>
            </div>
          `;

          updateButtons();
          return;
        }

        const entrada = ponto.entrada_em || ponto.iniciado_em || ponto.criado_em || "";
        const saida = ponto.saida_em || ponto.finalizado_em || "";
        const pausaAberta = ultimaPausaAberta(ponto);
        const pausaInicio = pausaAberta ? (pausaAberta.inicio_em || pausaAberta.iniciado_em || "") : "";

        card.innerHTML = `
          <div class="ponto-status-big">
            <span class="ponto-status-icon ${escapeHtml(icon.cls)}">
              <i class="${escapeHtml(icon.icon)}"></i>
            </span>

            <div class="ponto-status-info">
              <strong>${escapeHtml(statusLabel(status))}</strong>
              <p>
                Entrada registrada em ${escapeHtml(formatDateTime(entrada))}.
                ${status === "pausado" ? "Você está em pausa neste momento." : "Sua jornada está em acompanhamento."}
              </p>

              <div class="ponto-status-tags">
                <span class="ponto-tag ${escapeHtml(statusTagClass(status))}">
                  <i class="fa-solid fa-circle"></i>
                  ${escapeHtml(statusLabel(status))}
                </span>

                <span class="ponto-tag">
                  <i class="fa-regular fa-clock"></i>
                  Líquido: ${escapeHtml(pontoLiquidoLabel(ponto))}
                </span>

                <span class="ponto-tag">
                  <i class="fa-solid fa-mug-hot"></i>
                  Pausas: ${escapeHtml(pontoPausasLabel(ponto))}
                </span>
              </div>

              <div class="ponto-status-tags">
                <span class="ponto-tag">Entrada: ${escapeHtml(formatTimeOnly(entrada))}</span>
                <span class="ponto-tag">Pausa aberta: ${escapeHtml(formatTimeOnly(pausaInicio))}</span>
                <span class="ponto-tag">Saída: ${escapeHtml(formatTimeOnly(saida))}</span>
              </div>
            </div>
          </div>
        `;

        updateButtons();
      }

      function renderPontosHoje() {
        const list = qs("#ponto-list");
        const empty = qs("#ponto-empty");

        if (!list || !empty) return;

        const pontos = Array.isArray(state.pontosHoje) ? state.pontosHoje : [];
        empty.classList.toggle("show", pontos.length === 0);
        list.innerHTML = pontos.map(renderPontoCard).join("");
      }

      function renderPontoCard(ponto) {
        const status = normalizeStatus(ponto.status || "aberto");
        const entrada = ponto.entrada_em || ponto.iniciado_em || ponto.criado_em || "";
        const saida = ponto.saida_em || ponto.finalizado_em || "";
        const pausas = getPausas(ponto);
        const primeiraPausa = pausas[0] || {};
        const ultimaPausa = pausas[pausas.length - 1] || {};
        const primeiraPausaInicio = primeiraPausa.inicio_em || primeiraPausa.iniciado_em || ponto.pausa_iniciada_em || ponto.ultima_pausa_inicio || "";
        const ultimaPausaFim = ultimaPausa.fim_em || ultimaPausa.finalizado_em || ponto.ultimo_retorno_em || ponto.retorno_em || "";
        const observacao = pontoObservacaoResumo(ponto);

        const note = observacao ? `
          <div class="ponto-note">
            <strong>Observações / justificativas:</strong>
            ${escapeHtml(observacao)}
          </div>
        ` : "";

        return `
          <article class="ponto-card ${escapeHtml(status)}">
            <div class="ponto-card-header">
              <div class="ponto-card-title">
                <h3>${escapeHtml(ponto.funcionario_nome || ponto.nome || "Funcionário")}</h3>
                <p>@${escapeHtml(ponto.usuario || "-")} • ${escapeHtml(statusLabel(status))}</p>
              </div>

              <span class="ponto-tag ${escapeHtml(statusTagClass(status))}">
                ${escapeHtml(ponto.status_label || statusLabel(status))}
              </span>
            </div>

            <div class="ponto-times">
              <div class="ponto-time-box">
                <small>Entrada</small>
                <strong>${escapeHtml(formatDateTime(entrada))}</strong>
              </div>

              <div class="ponto-time-box">
                <small>1ª pausa</small>
                <strong>${escapeHtml(formatDateTime(primeiraPausaInicio))}</strong>
              </div>

              <div class="ponto-time-box">
                <small>Último retorno</small>
                <strong>${escapeHtml(formatDateTime(ultimaPausaFim))}</strong>
              </div>

              <div class="ponto-time-box">
                <small>Saída</small>
                <strong>${escapeHtml(formatDateTime(saida))}</strong>
              </div>
            </div>

            <div class="ponto-times">
              <div class="ponto-time-box">
                <small>Total bruto</small>
                <strong>${escapeHtml(pontoTotalLabel(ponto))}</strong>
              </div>

              <div class="ponto-time-box">
                <small>Total pausas</small>
                <strong>${escapeHtml(pontoPausasLabel(ponto))}</strong>
              </div>

              <div class="ponto-time-box">
                <small>Total líquido</small>
                <strong>${escapeHtml(pontoLiquidoLabel(ponto))}</strong>
              </div>

              <div class="ponto-time-box">
                <small>Data</small>
                <strong>${escapeHtml(ponto.data_ponto || "-")}</strong>
              </div>
            </div>

            ${note}
          </article>
        `;
      }

      async function loadFuncionarios() {
        try {
          const data = await apiFetch("/api/interno/funcionarios");
          state.funcionarios = Array.isArray(data.funcionarios)
            ? data.funcionarios.filter(function (funcionario) {
                return funcionario && funcionario.ativo !== false;
              })
            : [];
        } catch (error) {
          state.funcionarios = [];
        }
      }

      async function loadPonto() {
        const page = qs("#ponto-page");

        if (!page || state.carregando) return;

        const btn = qs("#btn-reload-ponto");

        state.carregando = true;

        if (btn) btn.disabled = true;

        try {
          const data = await apiFetch("/api/interno/ponto/status");

          state.pontoAtual = data.ponto_aberto || data.ponto_atual || null;
          state.pontosHoje = Array.isArray(data.pontos_hoje) ? data.pontos_hoje : [];

          updateStats(data.resumo || {});
          renderStatus();
          renderPontosHoje();
          renderAlertas(data.resumo || {}, state.pontosHoje);
          setMessage("", "");
        } catch (error) {
          setMessage("error", error.message || "Erro ao carregar ponto online.");
        } finally {
          state.carregando = false;

          if (btn) btn.disabled = false;

          updateButtons();
        }
      }

      function clearAcao() {
        const observacao = qs("#ponto-observacao");
        const confirm = qs("#ponto-confirmacao");

        if (observacao) observacao.value = "";
        if (confirm) confirm.checked = false;
      }

      async function executarAcao(acao) {
        if (state.salvando) return;

        const confirm = qs("#ponto-confirmacao");
        const observacao = qs("#ponto-observacao");
        const confirmacao = confirm ? confirm.checked : false;

        if (!confirmacao) {
          setMessage("error", "Confirme a ação antes de registrar o ponto.");
          return;
        }

        const endpoints = {
          entrada: ["/api/interno/ponto/entrada"],
          pausa: ["/api/interno/ponto/pausa/iniciar", "/api/interno/ponto/pausa"],
          retorno: ["/api/interno/ponto/pausa/finalizar", "/api/interno/ponto/retorno"],
          saida: ["/api/interno/ponto/saida"],
        };

        const labels = {
          entrada: "Entrada registrada com sucesso.",
          pausa: "Pausa iniciada com sucesso.",
          retorno: "Retorno registrado com sucesso.",
          saida: "Saída registrada com sucesso.",
        };

        const buttons = {
          entrada: qs("#btn-ponto-entrada"),
          pausa: qs("#btn-ponto-pausa"),
          retorno: qs("#btn-ponto-retorno"),
          saida: qs("#btn-ponto-saida"),
        };

        const endpointList = endpoints[acao];
        const btn = buttons[acao];

        if (!endpointList) return;

        const original = btn ? btn.innerHTML : "";

        state.salvando = true;
        updateButtons();

        if (btn) {
          btn.disabled = true;
          btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Salvando...';
        }

        try {
          await tryPost(endpointList, {
            confirmacao: true,
            observacao: observacao ? observacao.value.trim() : "",
          });

          clearAcao();
          await loadPonto();
          setMessage("success", labels[acao] || "Ponto atualizado com sucesso.");
        } catch (error) {
          setMessage("error", error.message || "Erro ao registrar ponto.");
        } finally {
          state.salvando = false;

          if (btn) btn.innerHTML = original;

          updateButtons();
        }
      }

      async function carregarPontosData(dataIso) {
        const params = new URLSearchParams();
        params.set("data", dataIso);
        params.set("limite", "300");

        const data = await apiFetch("/api/interno/pontos?" + params.toString());

        if (Array.isArray(data.pontos)) return data.pontos;
        if (Array.isArray(data.pontos_hoje)) return data.pontos_hoje;

        return [];
      }

      function getRelFilters() {
        return {
          inicio: qs("#rel-data-inicio") ? qs("#rel-data-inicio").value : "",
          fim: qs("#rel-data-fim") ? qs("#rel-data-fim").value : "",
          funcionario: qs("#rel-funcionario") ? qs("#rel-funcionario").value : "",
          status: qs("#rel-status") ? qs("#rel-status").value : "",
          busca: qs("#rel-busca") ? qs("#rel-busca").value : "",
        };
      }

      function filtrarRelatorio(pontos) {
        const filters = getRelFilters();
        const funcionario = normalize(filters.funcionario);
        const status = normalizeStatus(filters.status);
        const busca = normalize(filters.busca);

        return pontos.filter(function (ponto) {
          if (status && normalizeStatus(ponto.status) !== status) return false;

          if (funcionario) {
            const funcHay = normalize([ponto.funcionario_nome, ponto.nome, ponto.usuario].join(" "));
            if (!funcHay.includes(funcionario)) return false;
          }

          if (busca) {
            const haystack = normalize([
              ponto.data_ponto,
              ponto.funcionario_nome,
              ponto.nome,
              ponto.usuario,
              ponto.status_label,
              pontoObservacaoResumo(ponto),
            ].join(" "));

            if (!haystack.includes(busca)) return false;
          }

          return true;
        });
      }

      async function carregarRelatorio() {
        const btn = qs("#btn-rel-carregar");
        const filters = getRelFilters();

        const inicio = filters.inicio || todayIso();
        const fim = filters.fim || inicio;
        const dias = dateRange(inicio, fim);

        if (!dias.length) {
          alert("Informe um período válido.");
          return;
        }

        if (btn) {
          btn.disabled = true;
          btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Carregando...';
        }

        try {
          const chunks = [];

          for (const dia of dias) {
            const pontos = await carregarPontosData(dia);
            chunks.push(...pontos);
          }

          state.pontosRelatorio = filtrarRelatorio(chunks);
          renderRelatorio();
        } catch (error) {
          alert(error.message || "Erro ao carregar relatório.");
        } finally {
          if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<i class="fa-solid fa-magnifying-glass"></i> Carregar relatório';
          }
        }
      }

      function funcionarioKeyFromPonto(ponto) {
        const id = ponto.funcionario_id || "";
        const usuario = normalize(ponto.usuario || "");
        const nome = normalize(ponto.funcionario_nome || ponto.nome || "");

        if (id) return `id:${id}`;
        if (usuario) return `u:${usuario}`;
        if (nome) return `n:${nome}`;

        return "";
      }

      function uniqueFuncionarios(pontos) {
        const map = new Map();

        pontos.forEach(function (ponto) {
          const key = funcionarioKeyFromPonto(ponto);

          if (!key) return;

          if (!map.has(key)) {
            map.set(key, {
              key,
              nome: ponto.funcionario_nome || ponto.nome || "Funcionário",
              usuario: ponto.usuario || "",
            });
          }
        });

        return Array.from(map.values());
      }

      function updateReportDashboard(pontos) {
        const safePontos = Array.isArray(pontos) ? pontos : [];
        const pessoas = uniqueFuncionarios(safePontos);

        const trabalhando = safePontos.filter(function (ponto) {
          const status = normalizeStatus(ponto.status);
          return status === "aberto" || status === "pausado";
        });

        const finalizados = safePontos.filter(function (ponto) {
          return normalizeStatus(ponto.status) === "finalizado";
        });

        const diasSet = new Set();
        let liquido = 0;
        let pausas = 0;

        safePontos.forEach(function (ponto) {
          if (ponto.data_ponto) diasSet.add(ponto.data_ponto);
          liquido += pontoLiquidoSeconds(ponto);
          pausas += pontoPausasSeconds(ponto);
        });

        const media = diasSet.size ? Math.round(safePontos.length / diasSet.size) : 0;

        const refs = {
          total: qs("#dash-total-registros"),
          pessoas: qs("#dash-total-pessoas"),
          trabalhando: qs("#dash-trabalhando"),
          finalizados: qs("#dash-finalizados"),
          horas: qs("#dash-horas-liquidas"),
          pausas: qs("#dash-pausas"),
          dias: qs("#dash-dias-com-ponto"),
          media: qs("#dash-media-dia"),
        };

        if (refs.total) refs.total.textContent = String(safePontos.length);
        if (refs.pessoas) refs.pessoas.textContent = String(pessoas.length);
        if (refs.trabalhando) refs.trabalhando.textContent = String(trabalhando.length);
        if (refs.finalizados) refs.finalizados.textContent = String(finalizados.length);
        if (refs.horas) refs.horas.textContent = secondsToLabel(liquido);
        if (refs.pausas) refs.pausas.textContent = secondsToLabel(pausas);
        if (refs.dias) refs.dias.textContent = String(diasSet.size);
        if (refs.media) refs.media.textContent = String(media);
      }

      function renderRelatorio() {
        const tbody = qs("#rel-table-body");
        const empty = qs("#rel-empty");

        if (!tbody || !empty) return;

        const pontos = Array.isArray(state.pontosRelatorio) ? state.pontosRelatorio : [];
        empty.classList.toggle("show", pontos.length === 0);

        updateReportDashboard(pontos);

        tbody.innerHTML = pontos.map(function (ponto) {
          const pausas = getPausas(ponto);

          const pausasText = pausas.length
            ? pausas.map(function (pausa, index) {
                const inicio = pausa.inicio_em || pausa.iniciado_em || "";
                const fim = pausa.fim_em || pausa.finalizado_em || "";
                return `${index + 1}) ${formatTimeOnly(inicio)} até ${formatTimeOnly(fim)}`;
              }).join("<br>")
            : "-";

          return `
            <tr>
              <td>${escapeHtml(ponto.data_ponto || "-")}</td>
              <td>
                <strong>${escapeHtml(ponto.funcionario_nome || ponto.nome || "Funcionário")}</strong><br>
                <small>@${escapeHtml(ponto.usuario || "-")}</small>
              </td>
              <td>
                <span class="ponto-tag ${escapeHtml(statusTagClass(ponto.status))}">
                  ${escapeHtml(ponto.status_label || statusLabel(ponto.status))}
                </span>
              </td>
              <td>${escapeHtml(formatDateTime(ponto.entrada_em || ponto.iniciado_em || ponto.criado_em))}</td>
              <td>${pausasText}</td>
              <td>${escapeHtml(formatDateTime(ponto.saida_em || ponto.finalizado_em))}</td>
              <td>
                <strong>${escapeHtml(pontoLiquidoLabel(ponto))}</strong><br>
                <small>Bruto: ${escapeHtml(pontoTotalLabel(ponto))} • Pausas: ${escapeHtml(pontoPausasLabel(ponto))}</small>
              </td>
              <td>${escapeHtml(pontoObservacaoResumo(ponto) || "-")}</td>
            </tr>
          `;
        }).join("");
      }

      function limparRelatorio() {
        const hoje = todayIso();

        if (qs("#rel-data-inicio")) qs("#rel-data-inicio").value = hoje;
        if (qs("#rel-data-fim")) qs("#rel-data-fim").value = hoje;
        if (qs("#rel-funcionario")) qs("#rel-funcionario").value = "";
        if (qs("#rel-status")) qs("#rel-status").value = "";
        if (qs("#rel-busca")) qs("#rel-busca").value = "";

        state.pontosRelatorio = [];
        renderRelatorio();
      }

      function csvEscape(value) {
        const text = String(value || "").replaceAll('"', '""');
        return `"${text}"`;
      }

      function exportarCsv() {
        const pontos = Array.isArray(state.pontosRelatorio) ? state.pontosRelatorio : [];

        if (!pontos.length) {
          alert("Carregue o relatório antes de exportar.");
          return;
        }

        const header = [
          "Data",
          "Funcionário",
          "Usuário",
          "Status",
          "Entrada",
          "Saída",
          "Total bruto",
          "Total pausas",
          "Total líquido",
          "Observações",
        ];

        const rows = pontos.map(function (ponto) {
          return [
            ponto.data_ponto || "",
            ponto.funcionario_nome || ponto.nome || "",
            ponto.usuario || "",
            ponto.status_label || statusLabel(ponto.status),
            formatDateTime(ponto.entrada_em || ponto.iniciado_em || ponto.criado_em),
            formatDateTime(ponto.saida_em || ponto.finalizado_em),
            pontoTotalLabel(ponto),
            pontoPausasLabel(ponto),
            pontoLiquidoLabel(ponto),
            pontoObservacaoResumo(ponto),
          ];
        });

        const csv = [header, ...rows]
          .map(function (row) {
            return row.map(csvEscape).join(";");
          })
          .join("\n");

        const blob = new Blob(["\ufeff" + csv], { type: "text/csv;charset=utf-8" });
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");

        link.href = url;
        link.download = "relatorio-ponto-seg.csv";
        document.body.appendChild(link);
        link.click();
        link.remove();

        URL.revokeObjectURL(url);
      }

      async function carregarCalendarioMes() {
        const input = qs("#calendar-month");
        const title = qs("#calendar-title");
        const monthIso = input && input.value ? input.value : currentMonthIso();

        if (title) title.textContent = "Calendário — " + monthLabel(monthIso);

        const [yearRaw, monthRaw] = monthIso.split("-");
        const year = Number(yearRaw);
        const month = Number(monthRaw);

        if (!year || !month) return;

        const first = new Date(year, month - 1, 1);
        const last = new Date(year, month, 0);
        const days = dateRange(dateToIso(first), dateToIso(last));

        state.pontosMesPorData = {};

        const btn = qs("#btn-cal-load");

        if (btn) {
          btn.disabled = true;
          btn.textContent = "Carregando...";
        }

        try {
          for (const dia of days) {
            state.pontosMesPorData[dia] = await carregarPontosData(dia);
          }

          if (!state.selectedDay || !state.selectedDay.startsWith(monthIso)) {
            state.selectedDay = todayIso().startsWith(monthIso) ? todayIso() : dateToIso(first);
          }

          renderCalendario();
          renderDiaSelecionado(state.selectedDay);
        } catch (error) {
          alert(error.message || "Erro ao carregar calendário de ponto.");
        } finally {
          if (btn) {
            btn.disabled = false;
            btn.textContent = "Atualizar";
          }
        }
      }

      function renderCalendario() {
        const grid = qs("#ponto-calendar-grid");
        const input = qs("#calendar-month");

        if (!grid || !input) return;

        const monthIso = input.value || currentMonthIso();
        const days = monthDays(monthIso);
        const today = todayIso();

        grid.innerHTML = days.map(function (day) {
          const pontos = state.pontosMesPorData[day.iso] || [];
          const pessoas = uniqueFuncionarios(pontos);

          const names = pessoas.slice(0, 3).map(function (pessoa) {
            return `<span class="ponto-day-name">${escapeHtml(pessoa.nome)}</span>`;
          }).join("");

          const more = pessoas.length > 3
            ? `<span class="ponto-day-more">+${pessoas.length - 3} pessoa(s)</span>`
            : "";

          const classes = [
            "ponto-day",
            day.inMonth ? "" : "out",
            day.iso === today ? "today" : "",
            day.iso === state.selectedDay ? "selected" : "",
          ].filter(Boolean).join(" ");

          return `
            <button type="button" class="${classes}" data-calendar-day="${escapeHtml(day.iso)}">
              <span class="ponto-day-number">
                <strong>${escapeHtml(day.day)}</strong>
                <span>${escapeHtml(pessoas.length)}</span>
              </span>

              <span class="ponto-day-names">
                ${names}
                ${more}
              </span>
            </button>
          `;
        }).join("");
      }

      function funcionariosAusentesNoDia(pontosDia) {
        const funcionarios = Array.isArray(state.funcionarios) ? state.funcionarios : [];

        if (!funcionarios.length) return [];

        const presentesKeys = new Set(
          uniqueFuncionarios(pontosDia).map(function (pessoa) {
            return pessoa.key;
          })
        );

        return funcionarios.filter(function (funcionario) {
          const id = funcionario.id ? `id:${funcionario.id}` : "";
          const usuario = funcionario.usuario ? `u:${normalize(funcionario.usuario)}` : "";
          const nome = funcionario.nome ? `n:${normalize(funcionario.nome)}` : "";

          if (id && presentesKeys.has(id)) return false;
          if (usuario && presentesKeys.has(usuario)) return false;
          if (nome && presentesKeys.has(nome)) return false;

          return true;
        });
      }

      function renderDiaSelecionado(dayIso) {
        state.selectedDay = dayIso;

        const title = qs("#day-detail-title");
        const subtitle = qs("#day-detail-subtitle");
        const list = qs("#day-present-list");
        const empty = qs("#day-empty");
        const totalPresentes = qs("#day-total-presentes");
        const totalAusentes = qs("#day-total-ausentes");

        const pontos = state.pontosMesPorData[dayIso] || [];
        const pessoas = uniqueFuncionarios(pontos);
        const ausentes = funcionariosAusentesNoDia(pontos);

        if (title) {
          title.textContent = "Ponto em " + dayIso.split("-").reverse().join("/");
        }

        if (subtitle) {
          subtitle.textContent = pessoas.length
            ? pessoas.length + " pessoa(s) bateram ponto neste dia."
            : "Nenhum funcionário bateu ponto neste dia.";
        }

        if (totalPresentes) totalPresentes.textContent = String(pessoas.length);
        if (totalAusentes) totalAusentes.textContent = state.funcionarios.length ? String(ausentes.length) : "-";

        if (empty) empty.classList.toggle("show", pessoas.length === 0);

        if (!list) return;

        const rowsPresentes = pontos.map(function (ponto) {
          const status = normalizeStatus(ponto.status);

          return `
            <div class="ponto-person-row">
              <div>
                <strong>${escapeHtml(ponto.funcionario_nome || ponto.nome || "Funcionário")}</strong>
                <small>
                  @${escapeHtml(ponto.usuario || "-")} •
                  Entrada ${escapeHtml(formatTimeOnly(ponto.entrada_em || ponto.iniciado_em || ponto.criado_em))} •
                  Saída ${escapeHtml(formatTimeOnly(ponto.saida_em || ponto.finalizado_em))}
                </small>
              </div>

              <span class="ponto-tag ${escapeHtml(statusTagClass(status))}">
                ${escapeHtml(ponto.status_label || statusLabel(status))}
              </span>
            </div>
          `;
        }).join("");

        const rowsAusentes = ausentes.length ? `
          <div class="ponto-note">
            <strong>Sem registro neste dia:</strong>
            ${escapeHtml(ausentes.map(function (funcionario) {
              return funcionario.nome || funcionario.usuario || "Funcionário";
            }).join(", "))}
          </div>
        ` : "";

        list.innerHTML = rowsPresentes + rowsAusentes;

        renderCalendario();
      }

      function changeMonth(delta) {
        const input = qs("#calendar-month");

        if (!input) return;

        const current = input.value || currentMonthIso();
        const parts = current.split("-");
        const year = Number(parts[0]);
        const month = Number(parts[1]);

        if (!year || !month) return;

        const next = new Date(year, month - 1 + delta, 1);
        input.value = `${next.getFullYear()}-${String(next.getMonth() + 1).padStart(2, "0")}`;

        carregarCalendarioMes();
      }

      function renderAlertas(resumo, pontos) {
        const safeResumo = resumo || {};
        const safePontos = Array.isArray(pontos) ? pontos : [];

        const trabalhando = safePontos.filter(function (p) {
          return normalizeStatus(p.status) === "aberto";
        });

        const pausados = safePontos.filter(function (p) {
          return normalizeStatus(p.status) === "pausado";
        });

        const finalizados = safePontos.filter(function (p) {
          return normalizeStatus(p.status) === "finalizado";
        });

        const agora = Date.now();

        const pausasLongas = pausados.filter(function (ponto) {
          const pausa = ultimaPausaAberta(ponto);

          if (!pausa) return false;

          const inicioValue = pausa.inicio_em || pausa.iniciado_em || "";
          const inicio = new Date(inicioValue).getTime();

          if (Number.isNaN(inicio)) return false;

          return (agora - inicio) >= 60 * 60 * 1000;
        });

        const els = {
          trabalhando: qs("#alert-trabalhando"),
          pausados: qs("#alert-pausados"),
          pontoAberto: qs("#alert-ponto-aberto"),
          finalizados: qs("#alert-finalizados"),
          horas: qs("#alert-horas"),
          pausasLongas: qs("#alert-pausas-longas"),
        };

        if (els.trabalhando) els.trabalhando.textContent = String(trabalhando.length);
        if (els.pausados) els.pausados.textContent = String(pausados.length);
        if (els.pontoAberto) els.pontoAberto.textContent = String(trabalhando.length + pausados.length);
        if (els.finalizados) els.finalizados.textContent = String(finalizados.length);
        if (els.horas) els.horas.textContent = safeResumo.horas_liquidas_label || secondsToLabel(safeResumo.horas_liquidas_segundos || 0);
        if (els.pausasLongas) els.pausasLongas.textContent = String(pausasLongas.length);

        const alertList = qs("#alert-list");
        const alertEmpty = qs("#alert-empty");

        if (!alertList || !alertEmpty) return;

        const alertas = [];

        trabalhando.forEach(function (ponto) {
          alertas.push({
            tipo: "green",
            titulo: "Ponto aberto",
            texto: `${ponto.funcionario_nome || ponto.nome || ponto.usuario || "Funcionário"} está trabalhando desde ${formatTimeOnly(ponto.entrada_em || ponto.iniciado_em || ponto.criado_em)}.`,
          });
        });

        pausados.forEach(function (ponto) {
          const pausa = ultimaPausaAberta(ponto);
          const inicio = pausa ? (pausa.inicio_em || pausa.iniciado_em || "") : "";

          alertas.push({
            tipo: pausasLongas.includes(ponto) ? "red" : "orange",
            titulo: pausasLongas.includes(ponto) ? "Pausa longa" : "Funcionário em pausa",
            texto: `${ponto.funcionario_nome || ponto.nome || ponto.usuario || "Funcionário"} está em pausa desde ${formatTimeOnly(inicio)}.`,
          });
        });

        alertEmpty.classList.toggle("show", alertas.length === 0);

        alertList.innerHTML = alertas.map(function (item) {
          return `
            <article class="ponto-card ${item.tipo === "red" ? "finalizado" : item.tipo === "orange" ? "pausado" : "aberto"}">
              <div class="ponto-card-header">
                <div class="ponto-card-title">
                  <h3>${escapeHtml(item.titulo)}</h3>
                  <p>${escapeHtml(item.texto)}</p>
                </div>

                <span class="ponto-tag ${escapeHtml(item.tipo)}">
                  ${item.tipo === "red" ? "Atenção" : "Monitorar"}
                </span>
              </div>
            </article>
          `;
        }).join("");
      }

      function bindTabs() {
        qsa("[data-ponto-tab]").forEach(function (btn) {
          btn.addEventListener("click", function () {
            const tab = btn.getAttribute("data-ponto-tab");

            qsa("[data-ponto-tab]").forEach(function (item) {
              item.classList.toggle("active", item === btn);
            });

            qsa("[data-ponto-panel]").forEach(function (panel) {
              panel.classList.toggle("active", panel.getAttribute("data-ponto-panel") === tab);
            });

            if (tab === "relatorio") {
              carregarRelatorio();
            }

            if (tab === "calendario") {
              carregarCalendarioMes();
            }

            if (tab === "alertas") {
              renderAlertas({}, state.pontosHoje);
              loadPonto();
            }
          });
        });
      }

      function bindActions() {
        const reload = qs("#btn-reload-ponto");

        if (reload) {
          reload.addEventListener("click", function () {
            loadPonto();
            carregarRelatorio();
            carregarCalendarioMes();
          });
        }

        const entrada = qs("#btn-ponto-entrada");
        if (entrada) entrada.addEventListener("click", function () { executarAcao("entrada"); });

        const pausa = qs("#btn-ponto-pausa");
        if (pausa) pausa.addEventListener("click", function () { executarAcao("pausa"); });

        const retorno = qs("#btn-ponto-retorno");
        if (retorno) retorno.addEventListener("click", function () { executarAcao("retorno"); });

        const saida = qs("#btn-ponto-saida");
        if (saida) saida.addEventListener("click", function () { executarAcao("saida"); });

        const btnRel = qs("#btn-rel-carregar");
        if (btnRel) btnRel.addEventListener("click", carregarRelatorio);

        const btnLimpar = qs("#btn-rel-limpar");
        if (btnLimpar) btnLimpar.addEventListener("click", limparRelatorio);

        const btnCsv = qs("#btn-rel-csv");
        if (btnCsv) btnCsv.addEventListener("click", exportarCsv);

        const btnPrint = qs("#btn-rel-print");
        if (btnPrint) btnPrint.addEventListener("click", function () {
          window.print();
        });

        const calPrev = qs("#btn-cal-prev");
        if (calPrev) calPrev.addEventListener("click", function () {
          changeMonth(-1);
        });

        const calNext = qs("#btn-cal-next");
        if (calNext) calNext.addEventListener("click", function () {
          changeMonth(1);
        });

        const calLoad = qs("#btn-cal-load");
        if (calLoad) calLoad.addEventListener("click", carregarCalendarioMes);

        const calMonth = qs("#calendar-month");
        if (calMonth) calMonth.addEventListener("change", carregarCalendarioMes);

        const calGrid = qs("#ponto-calendar-grid");

        if (calGrid) {
          calGrid.addEventListener("click", function (event) {
            const btn = event.target.closest("[data-calendar-day]");
            if (!btn) return;
            renderDiaSelecionado(btn.getAttribute("data-calendar-day"));
          });
        }
      }

      function initDates() {
        const hoje = todayIso();

        const inicio = qs("#rel-data-inicio");
        const fim = qs("#rel-data-fim");
        const month = qs("#calendar-month");

        if (inicio && !inicio.value) inicio.value = hoje;
        if (fim && !fim.value) fim.value = hoje;
        if (month && !month.value) month.value = currentMonthIso();

        state.selectedDay = hoje;
      }

      async function init() {
        const page = qs("#ponto-page");

        if (!page) return;

        bindTabs();
        bindActions();
        initDates();
        renderStatus();
        renderRelatorio();

        await loadFuncionarios();
        await loadPonto();
      }

      if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
      } else {
        init();
      }
    })();
