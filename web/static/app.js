/* ═══════════════════════════════════════════════════════════════════
   Job Aggregator — Frontend SPA
   ═══════════════════════════════════════════════════════════════════ */

"use strict";

// ── Estado global ─────────────────────────────────────────────────────
const state = {
  vagas: [],
  vagas_filtered: [],
  skills: [],
  selected_id: null,
  active_tab: "vagas",
  ai_active: false,
  cv: {
    file: null,
    tema: "classic",
    gerando: false,
  },
  filters: {
    q: "",
    status: "",
    modalidade: "",
    estado: "",
    fontes: new Set(["linkedin", "vagas.com", "infojobs"]),
  },
  scraping: false,
  sse: null,
};

// ── DOM refs ──────────────────────────────────────────────────────────
const $ = id => document.getElementById(id);

const els = {
  feedList:          $("feedList"),
  feedEmpty:         $("feedEmpty"),
  detailContent:     $("detailContent"),
  detailPlaceholder: $("detailPlaceholder"),
  numTotal:          $("numTotal"),
  numAplicadas:      $("numAplicadas"),
  numEntrevistas:    $("numEntrevistas"),
  statusDot:         $("statusDot"),
  statusLabel:       $("statusLabel"),
  progressBar:       $("progressBar"),
  inputBusca:        $("inputBusca"),
  scrapingLog:       $("scrapingLog"),
  logEntries:        $("logEntries"),
  logTitle:          $("logTitle"),
  skillsChips:       $("skillsChips"),
  btnIniciarBusca:   $("btnIniciarBusca"),
  skillsPanel:       $("skillsPanel"),
  toolbar:           $("toolbar"),
  vagasLayout:       $("vagasLayout"),
  cvLayout:          $("cvLayout"),
  headerSearch:      $("headerSearch"),
  cvLog:             $("cvLog"),
  btnExtrair:        $("btnExtrair"),
  btnGerar:          $("btnGerar"),
  yamlEditor:        $("yamlEditor"),
  uploadZone:        $("uploadZone"),
  uploadTitle:       $("uploadTitle"),
  aiToggle:          $("aiToggle"),
  aiToggleLabel:     $("aiToggleLabel"),
  btnConfigAI:       $("btnConfigAI"),
  inputGeminiKey:    $("inputGeminiKey"),
  aiTestResult:      $("aiTestResult"),
};

// ── Init ──────────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  setupFilterPills();
  setupSourceBtns();
  setupSearch();
  setupKeyboard();
  setupThemeBtns();
  loadSkills();
  loadStats();
  loadVagas();
  loadAIConfig();
});

// ── Tab switching ─────────────────────────────────────────────────────

function switchTab(tab) {
  state.active_tab = tab;

  document.querySelectorAll(".tab-btn").forEach(b => {
    b.classList.toggle("active", b.dataset.tab === tab);
  });

  if (tab === "vagas") {
    els.toolbar.style.display = "";
    els.vagasLayout.style.display = "";
    els.cvLayout.style.display = "none";
    els.headerSearch.style.display = "";
  } else {
    els.toolbar.style.display = "none";
    els.vagasLayout.style.display = "none";
    els.cvLayout.style.display = "";
    els.headerSearch.style.display = "none";
    // CV layout ocupa do header para baixo (sem toolbar)
    els.cvLayout.style.top = "var(--header-h)";
  }
}

// ── Filters ───────────────────────────────────────────────────────────

function setupFilterPills() {
  document.querySelectorAll("[data-filter]").forEach(btn => {
    btn.addEventListener("click", () => {
      const filter = btn.dataset.filter;
      const value  = btn.dataset.value;
      btn.parentElement.querySelectorAll("[data-filter]").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      state.filters[filter] = value;
      loadVagas();
    });
  });

  $("selEstado").addEventListener("change", e => {
    state.filters.estado = e.target.value;
    loadVagas();
  });
}

function setupSourceBtns() {
  document.querySelectorAll(".source-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const fonte = btn.dataset.fonte;
      btn.classList.toggle("active");
      if (btn.classList.contains("active")) state.filters.fontes.add(fonte);
      else state.filters.fontes.delete(fonte);
      applyFilters();
    });
  });
}

function setupSearch() {
  els.inputBusca.addEventListener("input", e => {
    state.filters.q = e.target.value.toLowerCase();
    applyFilters();
  });

  document.addEventListener("keydown", e => {
    if (e.key === "/" && document.activeElement !== els.inputBusca &&
        !e.target.closest("input, textarea, select")) {
      e.preventDefault();
      els.inputBusca.focus();
      els.inputBusca.select();
    }
  });
}

function setupKeyboard() {
  document.addEventListener("keydown", e => {
    if (e.target.closest("input, textarea, select")) return;
    if (state.active_tab !== "vagas") return;

    if (e.key === "Escape") {
      state.selected_id = null;
      renderDetail(null);
    }
    if ((e.key === "j" || e.key === "ArrowDown") && !e.metaKey) {
      e.preventDefault();
      navigateCards(1);
    }
    if ((e.key === "k" || e.key === "ArrowUp") && !e.metaKey) {
      e.preventDefault();
      navigateCards(-1);
    }
    if (e.key === "Enter" && state.selected_id) {
      const vaga = state.vagas.find(v => v.id === state.selected_id);
      if (vaga?.link) window.open(vaga.link, "_blank");
    }
  });
}

function navigateCards(dir) {
  const ids = state.vagas_filtered.map(v => v.id);
  if (!ids.length) return;
  const cur  = ids.indexOf(state.selected_id);
  const next = Math.max(0, Math.min(ids.length - 1, cur + dir));
  selectVaga(ids[next]);
  document.querySelector(`.job-card[data-id="${ids[next]}"]`)?.scrollIntoView({ block: "nearest", behavior: "smooth" });
}

// ── Data loading ──────────────────────────────────────────────────────

async function loadVagas() {
  const params = new URLSearchParams();
  if (state.filters.status)     params.set("status",     state.filters.status);
  if (state.filters.estado)     params.set("estado",     state.filters.estado);
  if (state.filters.modalidade) params.set("modalidade", state.filters.modalidade);
  if (state.ai_active)          params.set("ai_filtrar", "1");

  try {
    const res = await fetch(`/api/vagas?${params}`);
    const data = await res.json();
    state.vagas = data;
    applyFilters();
    loadStats();
  } catch (err) {
    console.error("Erro ao carregar vagas:", err);
  }
}

function applyFilters() {
  const { q, fontes } = state.filters;

  const filtered = state.vagas.filter(v => {
    if (fontes.size && !fontes.has(v.fonte)) return false;
    if (q) {
      const hay = `${v.titulo} ${v.empresa} ${v.localizacao} ${(v.skills||[]).join(" ")}`.toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });

  // Mais recentes no topo
  filtered.sort((a, b) => {
    const da = a.data_coleta || "";
    const db = b.data_coleta || "";
    return db.localeCompare(da);
  });

  state.vagas_filtered = filtered;
  renderFeed(filtered);
}

async function loadStats() {
  try {
    const res = await fetch("/api/stats");
    const s = await res.json();
    animateNum(els.numTotal,       s.total_vagas || 0);
    animateNum(els.numAplicadas,   s.aplicadas   || 0);
    animateNum(els.numEntrevistas, s.chamados    || 0);
  } catch {}
}

async function loadSkills() {
  try {
    const res = await fetch("/api/skills");
    state.skills = await res.json();
    renderSkillsPanel();
  } catch {}
}

// ── Render: Feed ──────────────────────────────────────────────────────

function renderFeed(vagas) {
  if (!vagas.length) {
    els.feedEmpty.classList.remove("hidden");
    els.feedList.innerHTML = "";
    return;
  }
  els.feedEmpty.classList.add("hidden");
  els.feedList.innerHTML = vagas.map((v, idx) => buildCardHTML(v, idx)).join("");
  els.feedList.querySelectorAll(".job-card").forEach(card => {
    card.addEventListener("click", () => selectVaga(+card.dataset.id));
  });
  if (state.selected_id) {
    document.querySelector(`.job-card[data-id="${state.selected_id}"]`)?.classList.add("selected");
  }
}

function buildCardHTML(v, idx) {
  const skills   = v.skills || [];
  const matchPct = v.match_score || 0;
  const matchCls = matchPct >= 70 ? "high" : matchPct >= 40 ? "mid" : "";
  const matchLabel = matchPct ? `${matchPct}%` : "—";

  const modal = (v.modalidade || "").toLowerCase();
  let modalBadge = "";
  if (modal.includes("remot"))      modalBadge = `<span class="card-modal-badge modal-remoto">Remoto</span>`;
  else if (modal.includes("hibrid")) modalBadge = `<span class="card-modal-badge modal-hibrido">Híbrido</span>`;
  else if (modal.includes("presenc")) modalBadge = `<span class="card-modal-badge modal-presencial">Presencial</span>`;

  const skillsHtml = skills.slice(0, 4).map(sk => {
    const isMatch = state.skills.map(s => s.toLowerCase()).includes(sk.toLowerCase());
    return `<span class="skill-chip ${isMatch ? "match" : ""}">${esc(sk)}</span>`;
  }).join("") + (skills.length > 4 ? `<span class="skill-chip">+${skills.length - 4}</span>` : "");

  const statusClass = v.resultado_entrevista && v.resultado_entrevista !== "pendente"
    ? `resultado-${v.resultado_entrevista}`
    : `status-${v.status || "nova"}`;

  const loc  = v.estado || (v.localizacao || "").split(",")[0] || "";
  const date = formatDate(v.data_coleta);

  return `
  <article class="job-card ${statusClass}" data-id="${v.id}"
           style="animation-delay:${Math.min(idx * 25, 300)}ms">
    <div class="card-accent"></div>
    <div class="card-body">
      <div class="card-top">
        <h3 class="card-title">${esc(v.titulo)}</h3>
        <span class="card-match ${matchCls}">${matchLabel}</span>
      </div>
      <div class="card-meta">
        <span class="card-company">${esc(v.empresa || "—")}</span>
        ${loc ? `<span class="meta-dot">·</span><span class="card-location">${esc(loc)}</span>` : ""}
        ${modalBadge ? `<span class="meta-dot">·</span>${modalBadge}` : ""}
      </div>
      <div class="card-bottom">
        <div class="card-skills">${skillsHtml}</div>
        <span class="card-date">${date}</span>
      </div>
    </div>
  </article>`;
}

// ── Render: Detail ────────────────────────────────────────────────────

function selectVaga(id) {
  document.querySelectorAll(".job-card.selected").forEach(c => c.classList.remove("selected"));
  state.selected_id = id;
  const vaga = state.vagas.find(v => v.id === id);
  if (!vaga) return;
  document.querySelector(`.job-card[data-id="${id}"]`)?.classList.add("selected");
  renderDetail(vaga);
}

function renderDetail(vaga) {
  if (!vaga) {
    els.detailPlaceholder.style.display = "";
    els.detailContent.style.display = "none";
    return;
  }

  els.detailPlaceholder.style.display = "none";
  els.detailContent.style.display = "";

  const skills  = vaga.skills || [];
  const matchPct = vaga.match_score || 0;
  const probPct  = vaga.prob_pct || 0;
  const skillsU  = state.skills.map(s => s.toLowerCase());

  const modal = (vaga.modalidade || "").toLowerCase();
  let modalLabel = "—";
  if (modal.includes("remot"))      modalLabel = "🏠 Remoto";
  else if (modal.includes("hibrid")) modalLabel = "🔀 Híbrido";
  else if (modal.includes("presenc")) modalLabel = "🏢 Presencial";
  else if (modal) modalLabel = modal;

  const resultadoMap = {
    chamado:     { label: "Chamado para entrevista", color: "var(--green)",  icon: "✅" },
    nao_chamado: { label: "Não chamado",             color: "var(--red)",    icon: "❌" },
    contratado:  { label: "Contratado! 🎉",          color: "var(--purple)", icon: "🏆" },
    pendente:    { label: "Aguardando feedback",     color: "var(--text-3)", icon: "⏳" },
  };
  const res = resultadoMap[vaga.resultado_entrevista] || resultadoMap.pendente;

  const statusMap = {
    nova:     { color: "var(--indigo-h)", label: "Nova" },
    favorita: { color: "var(--yellow)",   label: "Favorita" },
    aplicada: { color: "var(--green-h)",  label: "Aplicada" },
    ignorada: { color: "var(--text-3)",   label: "Ignorada" },
  };

  const detStatus = [
    { value: "nova",     icon: "🔄", label: "Nova" },
    { value: "favorita", icon: "⭐", label: "Favorita" },
    { value: "aplicada", icon: "✅", label: "Aplicada" },
    { value: "ignorada", icon: "🚫", label: "Ignorada" },
  ];

  const skillsHtml = skills.length
    ? skills.map(sk => {
        const match = skillsU.includes(sk.toLowerCase());
        return `<span class="det-skill ${match ? "match" : ""}">${esc(sk)}</span>`;
      }).join("")
    : `<span style="color:var(--text-3);font-size:12px">Nenhuma skill detectada</span>`;

  const desc = (vaga.descricao || "Sem descrição disponível.").trim();
  const link = (vaga.link || "").startsWith("http") ? vaga.link : vaga.link ? `https://${vaga.link}` : "";
  const dateStr = vaga.data_coleta ? `Coletada ${formatDate(vaga.data_coleta)}` : "";

  els.detailContent.innerHTML = `
    <div class="det-hero">
      <div class="det-fonte-badge">${esc(vaga.fonte || "")}${dateStr ? ` · ${dateStr}` : ""}</div>
      <h2 class="det-title">${esc(vaga.titulo)}</h2>
      <div class="det-company">${esc(vaga.empresa || "Empresa não informada")}</div>
      <div class="det-meta">
        ${vaga.localizacao ? `<span class="meta-chip">📍 ${esc(vaga.localizacao)}</span>` : ""}
        <span class="meta-chip">${modalLabel}</span>
        ${vaga.salario ? `<span class="meta-chip">💰 ${esc(vaga.salario)}</span>` : ""}
      </div>
    </div>

    <div class="det-scores">
      <div class="score-card">
        <div class="score-label">Match Skills</div>
        <div class="score-value" style="color:${matchPct >= 70 ? 'var(--green-h)' : matchPct >= 40 ? 'var(--yellow)' : 'var(--indigo-h)'}">${matchPct}%</div>
        <div class="score-bar"><div class="score-fill" style="width:${matchPct}%;background:${matchPct >= 70 ? 'var(--green)' : matchPct >= 40 ? 'var(--yellow)' : 'var(--indigo)'}"></div></div>
      </div>
      <div class="score-card">
        <div class="score-label">Chance</div>
        <div class="score-value" style="color:${probPct >= 50 ? 'var(--green-h)' : 'var(--yellow)'}">${probPct}%</div>
        <div class="score-bar"><div class="score-fill" style="width:${probPct}%;background:${probPct >= 50 ? 'var(--green)' : 'var(--yellow)'}"></div></div>
      </div>
    </div>

    <div class="det-section">
      <div class="det-section-title">Skills da Vaga</div>
      <div class="det-skills">${skillsHtml}</div>
    </div>

    <div class="det-section">
      <div class="det-section-title">Descrição</div>
      <div class="det-desc" id="detDesc">${esc(desc)}</div>
      <div class="det-desc-fade" id="detDescFade"></div>
      <button class="btn-expand" id="btnExpand" onclick="toggleDesc()">Ver mais</button>
    </div>

    ${link ? `<a href="${link}" target="_blank" rel="noopener" class="det-link-btn">
      <svg viewBox="0 0 20 20" fill="none" width="15" height="15">
        <path d="M10 13H7a4 4 0 010-8h3m3 8h3a4 4 0 000-8h-3m-6 4h8" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
      </svg>
      Abrir Vaga no Site
    </a>` : ""}

    <div class="det-section" style="margin-top:${link ? '16px' : '0'}">
      <div class="det-section-title">Candidatura</div>
      <div class="det-status-grid">
        ${detStatus.map(s => `
          <button class="det-status-btn ${vaga.status === s.value ? 'active' : ''}"
                  style="${vaga.status === s.value ? `color:${(statusMap[s.value]||{}).color||'var(--text)'}` : ''}"
                  onclick="setStatus(${vaga.id}, '${s.value}')">
            <span class="btn-icon">${s.icon}</span>${s.label}
          </button>`).join("")}
      </div>
    </div>

    <div class="det-section">
      <div class="det-section-title">Sistema de Aprendizado</div>
      <div class="resultado-badge" style="color:${res.color};border-color:${res.color}40;background:${res.color}12">
        ${res.icon} ${res.label}
      </div>
      <div class="det-feedback-grid">
        <button class="feedback-btn positive" onclick="sendFeedback(${vaga.id}, true)">
          <span>✅</span> Fui Chamado!
        </button>
        <button class="feedback-btn negative" onclick="sendFeedback(${vaga.id}, false)">
          <span>❌</span> Não Chamado
        </button>
        <button class="feedback-btn hired" onclick="sendFeedback(${vaga.id}, true, true)">
          <span>🏆</span> Fui Contratado!
        </button>
      </div>
    </div>
  `;
}

function toggleDesc() {
  const desc = $("detDesc");
  const btn  = $("btnExpand");
  desc.classList.toggle("expanded");
  btn.textContent = desc.classList.contains("expanded") ? "Ver menos" : "Ver mais";
}

// ── Actions ───────────────────────────────────────────────────────────

async function setStatus(vagaId, status) {
  try {
    await fetch(`/api/vagas/${vagaId}/status`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status }),
    });
    const v = state.vagas.find(v => v.id === vagaId);
    if (v) v.status = status;
    renderDetail(v);
    applyFilters();
  } catch(e) { console.error(e); }
}

async function sendFeedback(vagaId, chamado, contratado = false) {
  try {
    const res = await fetch(`/api/vagas/${vagaId}/feedback`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ chamado, contratado }),
    });
    const data = await res.json();
    const v = state.vagas.find(v => v.id === vagaId);
    if (v) {
      v.resultado_entrevista = data.resultado;
      if (contratado) v.status = "aplicada";
    }
    renderDetail(v);
    applyFilters();
    loadStats();
  } catch(e) { console.error(e); }
}

// ── Buscar Modal ──────────────────────────────────────────────────────

function openBuscarModal() {
  $("buscarOverlay").classList.add("open");
  setTimeout(() => $("inputCargo").focus(), 120);
}

function closeBuscarModal(e) {
  if (e && e.target !== $("buscarOverlay")) return;
  if (state.scraping) return;
  $("buscarOverlay").classList.remove("open");
  els.scrapingLog.style.display = "none";
  els.logEntries.innerHTML = "";
}

async function iniciarBusca() {
  const cargo = $("inputCargo").value.trim();
  if (!cargo || state.scraping) return;

  const estado = $("selEstadoBusca").value;
  const fonte  = $("selFonteBusca").value;

  state.scraping = true;
  els.btnIniciarBusca.disabled = true;
  els.scrapingLog.style.display = "";
  els.logEntries.innerHTML = "";
  els.logTitle.textContent = "Iniciando scraping…";

  setStatusIndicator("active", "Buscando…");
  showProgressBar(20);
  connectSSE();

  try {
    const res = await fetch("/api/buscar", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ cargo, estado, fonte }),
    });
    if (!res.ok) {
      const err = await res.json();
      addLogEntry(`Erro: ${err.error}`, "err");
      finishScraping();
    }
  } catch(e) {
    addLogEntry(`Erro de conexão: ${e}`, "err");
    finishScraping();
  }
}

function connectSSE() {
  if (state.sse) { state.sse.close(); }
  state.sse = new EventSource("/api/buscar/stream");

  state.sse.addEventListener("progress", e => {
    const d = JSON.parse(e.data);
    els.logTitle.textContent = d.msg;
    addLogEntry(`⏳ ${d.msg}`, "");
    showProgressBar(30);
  });

  state.sse.addEventListener("fonte_ok", e => {
    const d = JSON.parse(e.data);
    const duplicatas = d.coletadas - d.novas;
    const dupeMsg = duplicatas > 0 ? `, ${duplicatas} já existiam` : "";
    addLogEntry(`✓ ${d.fonte}: ${d.novas} novas${dupeMsg}`, "ok");
    showProgressBar(Math.min(30 + d.total * 2, 80));
    loadVagas();
  });

  state.sse.addEventListener("fonte_erro", e => {
    const d = JSON.parse(e.data);
    addLogEntry(`✗ ${d.fonte}: ${d.error}`, "err");
  });

  state.sse.addEventListener("ai_scoring", e => {
    const d = JSON.parse(e.data);
    addLogEntry(`✦ IA: avaliando ${d.total} vagas com Gemini…`, "");
    els.logTitle.textContent = "Filtrando com IA…";
    showProgressBar(85);
  });

  state.sse.addEventListener("ai_done", e => {
    const d = JSON.parse(e.data);
    addLogEntry(`✦ IA: ${d.total_analisadas} avaliadas, ${d.irrelevantes} filtradas`, "ok");
    loadVagas();
  });

  state.sse.addEventListener("ai_erro", e => {
    const d = JSON.parse(e.data);
    addLogEntry(`✦ IA: erro — ${d.error}`, "err");
  });

  state.sse.addEventListener("done", e => {
    const d = JSON.parse(e.data);
    els.logTitle.textContent = `✅ Concluído — ${d.total} novas vagas`;
    addLogEntry(`✅ Busca por "${d.cargo}" finalizada · ${d.total} novas inseridas`, "ok");
    showProgressBar(100);
    setTimeout(() => { finishScraping(); loadVagas(); loadStats(); }, 800);
  });

  state.sse.addEventListener("error", e => {
    if (e.data) {
      try { addLogEntry(`Erro: ${JSON.parse(e.data).error}`, "err"); } catch {}
    }
    finishScraping();
  });

  state.sse.onerror = () => { state.sse?.close(); state.sse = null; };
}

function finishScraping() {
  state.scraping = false;
  els.btnIniciarBusca.disabled = false;
  setStatusIndicator("ok", "Concluído");
  setTimeout(() => setStatusIndicator("idle", "Aguardando"), 4000);
  setTimeout(() => hideProgressBar(), 1200);
  if (state.sse) { state.sse.close(); state.sse = null; }
}

function addLogEntry(msg, cls) {
  const el = document.createElement("div");
  el.className = `log-entry ${cls}`;
  el.textContent = msg;
  els.logEntries.appendChild(el);
  els.logEntries.scrollTop = els.logEntries.scrollHeight;
}

// ── CV Tab ────────────────────────────────────────────────────────────

function setupThemeBtns() {
  document.querySelectorAll(".theme-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".theme-btn").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      state.cv.tema = btn.dataset.tema;
    });
  });

  // Habilita "Gerar PDF" sempre que o editor tiver conteúdo — inclusive ao colar YAML
  els.yamlEditor.addEventListener("input", () => {
    els.btnGerar.disabled = els.yamlEditor.value.trim().length === 0;
  });
}

function handleFileSelect(input) {
  const file = input.files[0];
  if (file) setCV_File(file);
}

function handleDrop(e) {
  e.preventDefault();
  els.uploadZone.classList.remove("drag");
  const file = e.dataTransfer.files[0];
  if (file) setCV_File(file);
}

function setCV_File(file) {
  const ext = file.name.split(".").pop().toLowerCase();
  if (!["pdf", "docx"].includes(ext)) {
    cvLog(`Formato não suportado: .${ext} — use .pdf ou .docx`, "err");
    return;
  }
  state.cv.file = file;
  els.uploadZone.classList.add("has-file");
  els.uploadTitle.textContent = `📎 ${file.name}`;
  els.btnExtrair.disabled = false;
  cvLog(`Arquivo selecionado: ${file.name}`, "info");
}

async function extrairYAML() {
  if (!state.cv.file) return;

  els.btnExtrair.disabled = true;
  cvLog("Extraindo texto do arquivo…", "info");

  const form = new FormData();
  form.append("file", state.cv.file);

  try {
    const res = await fetch("/api/cv/extrair", { method: "POST", body: form });
    const data = await res.json();

    if (data.error) {
      cvLog(`Erro: ${data.error}`, "err");
      els.btnExtrair.disabled = false;
      return;
    }

    els.yamlEditor.value = data.yaml;
    els.btnGerar.disabled = false;
    cvLog(`✅ YAML gerado (${data.chars} caracteres extraídos) — edite se necessário`, "ok");
  } catch(e) {
    cvLog(`Erro de conexão: ${e}`, "err");
  } finally {
    els.btnExtrair.disabled = false;
  }
}

async function gerarPDF() {
  const yaml_content = els.yamlEditor.value.trim();
  if (!yaml_content || state.cv.gerando) return;

  state.cv.gerando = true;
  els.btnGerar.disabled = true;
  cvLog(`Gerando PDF com tema "${state.cv.tema}"…`, "info");

  try {
    const res = await fetch("/api/cv/gerar", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ yaml_content, tema_id: state.cv.tema }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ error: res.statusText }));
      // Extrai só a primeira linha relevante do erro (evita dump completo do rendercv)
      const msg = (err.error || "Erro desconhecido").split("\n")
        .filter(l => l.trim() && !l.includes("---") && !l.includes("http") && !l.includes("RenderCV") && !l.includes("Welcome"))
        .slice(0, 3).join(" ") || err.error;
      cvLog(`Erro: ${msg}`, "err");
      return;
    }

    // Trigger browser download
    const blob = await res.blob();
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement("a");
    a.href     = url;
    a.download = "curriculo.pdf";
    a.click();
    URL.revokeObjectURL(url);
    cvLog("✅ PDF gerado e baixado com sucesso!", "ok");
  } catch(e) {
    cvLog(`Erro: ${e}`, "err");
  } finally {
    state.cv.gerando = false;
    els.btnGerar.disabled = false;
  }
}

async function normalizarYAMLcomIA() {
  const yaml_content = els.yamlEditor.value.trim();
  if (!yaml_content) { cvLog("Editor vazio.", "err"); return; }

  const btn = $("btnNormalizarIA");
  btn.disabled = true;
  btn.textContent = "✦ Corrigindo…";
  cvLog("✦ Gemini analisando e corrigindo estrutura do YAML…", "info");

  try {
    const res = await fetch("/api/cv/normalizar-ia", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ yaml_content }),
    });
    const data = await res.json();

    if (data.error) {
      cvLog(`Erro: ${data.error}`, "err");
      return;
    }

    els.yamlEditor.value = data.yaml;
    els.btnGerar.disabled = false;
    cvLog("✅ Estrutura corrigida pela IA — revise e clique em Gerar PDF.", "ok");
  } catch(e) {
    cvLog(`Erro de conexão: ${e}`, "err");
  } finally {
    btn.disabled = false;
    btn.innerHTML = `<svg viewBox="0 0 16 16" width="12" height="12" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M8 1l1.5 3.5L13 6l-3.5 1.5L8 11l-1.5-3.5L3 6l3.5-1.5z" stroke-linejoin="round"/></svg> Corrigir com IA`;
  }
}

function clearEditor() {
  if (!els.yamlEditor.value || confirm("Limpar o editor?")) {
    els.yamlEditor.value = "";
    els.btnGerar.disabled = true;
  }
}

function copyYAML() {
  if (!els.yamlEditor.value) return;
  navigator.clipboard.writeText(els.yamlEditor.value)
    .then(() => cvLog("YAML copiado para a área de transferência", "info"))
    .catch(() => cvLog("Não foi possível copiar", "err"));
}

function cvLog(msg, cls = "") {
  const el = document.createElement("div");
  el.className = `cv-log-entry ${cls}`;
  el.textContent = `${new Date().toLocaleTimeString("pt-BR", {hour:"2-digit",minute:"2-digit"})} ${msg}`;
  els.cvLog.appendChild(el);
  els.cvLog.scrollTop = els.cvLog.scrollHeight;
}

// ── Skills Panel ──────────────────────────────────────────────────────

function toggleSkillsPanel() {
  els.skillsPanel.classList.toggle("open");
  if (els.skillsPanel.classList.contains("open")) $("inputSkill").focus();
}

async function addSkill() {
  const raw = $("inputSkill").value.trim();
  if (!raw) return;
  try {
    const res = await fetch("/api/skills", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ skill: raw }),
    });
    state.skills = await res.json();
    $("inputSkill").value = "";
    renderSkillsPanel();
    applyFilters();
  } catch(e) { console.error(e); }
}

async function deleteSkill(skill) {
  try {
    const res = await fetch(`/api/skills/${encodeURIComponent(skill)}`, { method: "DELETE" });
    state.skills = await res.json();
    renderSkillsPanel();
    applyFilters();
  } catch(e) { console.error(e); }
}

function renderSkillsPanel() {
  els.skillsChips.innerHTML = state.skills.length
    ? state.skills.map(sk => `
        <span class="skill-tag">
          ${esc(sk)}
          <button class="skill-del" onclick="deleteSkill('${esc(sk)}')" title="Remover">×</button>
        </span>`).join("")
    : `<span style="color:var(--text-3);font-size:11px">Nenhuma skill. Adicione acima.</span>`;
}

// ── UI helpers ────────────────────────────────────────────────────────

function setStatusIndicator(st, label) {
  const dot = els.statusDot;
  dot.className = "status-dot";
  if (st === "active") dot.classList.add("active");
  if (st === "ok")     dot.classList.add("ok");
  if (st === "error")  dot.classList.add("error");
  els.statusLabel.textContent = label;
}

function showProgressBar(pct) {
  els.progressBar.classList.add("active");
  els.progressBar.style.width = `${pct}%`;
}

function hideProgressBar() {
  els.progressBar.style.width = "0%";
  setTimeout(() => els.progressBar.classList.remove("active"), 600);
}

function animateNum(el, target) {
  const start = parseInt(el.textContent) || 0;
  if (start === target) return;
  const diff  = target - start;
  const steps = 20;
  let i = 0;
  const tick = () => {
    i++;
    el.textContent = Math.round(i === steps ? target : start + diff * (i / steps));
    if (i < steps) requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
}

// ── Date formatting ───────────────────────────────────────────────────

function formatDate(dateStr) {
  if (!dateStr) return "";
  try {
    const d    = new Date(dateStr.replace(" ", "T"));
    const now  = new Date();
    const diff = Math.floor((now - d) / (1000 * 60 * 60 * 24));
    if (diff === 0)  return "hoje";
    if (diff === 1)  return "ontem";
    if (diff < 7)    return `há ${diff}d`;
    if (diff < 30)   return `há ${Math.floor(diff / 7)}sem`;
    if (diff < 365)  return `há ${Math.floor(diff / 30)}m`;
    return `há ${Math.floor(diff / 365)}a`;
  } catch { return ""; }
}

// ── Gemini AI ─────────────────────────────────────────────────────────

async function loadAIConfig() {
  try {
    const res = await fetch("/api/config");
    const cfg = await res.json();
    const hasKey = !!cfg.gemini_configurado;
    els.btnConfigAI.classList.toggle("configured", hasKey);
    els.btnConfigAI.title = hasKey ? "Gemini configurado ✓" : "Configurar Gemini API Key";
  } catch {}
}

function toggleAI() {
  state.ai_active = !state.ai_active;
  els.aiToggle.classList.toggle("active", state.ai_active);
  els.aiToggleLabel.textContent = state.ai_active ? "IA ✦" : "IA";
  loadVagas();
}

function openAIConfig() {
  els.inputGeminiKey.value = "";
  els.aiTestResult.style.display = "none";
  $("aiConfigOverlay").classList.add("open");
  setTimeout(() => els.inputGeminiKey.focus(), 120);
}

function closeAIConfig(e) {
  if (e && e.target !== $("aiConfigOverlay")) return;
  $("aiConfigOverlay").classList.remove("open");
}

async function testarChaveAI() {
  const key = els.inputGeminiKey.value.trim();
  if (!key) {
    showAITestResult("Digite uma API key primeiro", false);
    return;
  }

  const btn = $("btnTestarAI");
  btn.disabled = true;
  btn.textContent = "Testando…";
  els.aiTestResult.style.display = "none";

  try {
    const res = await fetch("/api/ai/testar", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ api_key: key }),
    });
    const data = await res.json();
    showAITestResult(data.mensagem || (data.ok ? "Conexão OK!" : "Falha"), data.ok);
  } catch(e) {
    showAITestResult(`Erro: ${e}`, false);
  } finally {
    btn.disabled = false;
    btn.textContent = "Testar conexão";
  }
}

function showAITestResult(msg, ok) {
  els.aiTestResult.style.display = "";
  els.aiTestResult.style.color = ok ? "var(--green-h)" : "var(--red)";
  els.aiTestResult.textContent = (ok ? "✓ " : "✗ ") + msg;
}

async function salvarChaveAI() {
  const key = els.inputGeminiKey.value.trim();
  try {
    await fetch("/api/config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ gemini_api_key: key }),
    });
    $("aiConfigOverlay").classList.remove("open");
    await loadAIConfig();
  } catch(e) {
    showAITestResult(`Erro ao salvar: ${e}`, false);
  }
}

// ── Escape ────────────────────────────────────────────────────────────

function esc(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}
