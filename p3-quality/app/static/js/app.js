document.addEventListener("DOMContentLoaded", () => {
  loadHealth();
  document.getElementById("ask-form").addEventListener("submit", handleAsk);
});

async function loadHealth() {
  const dot = document.getElementById("status-dot");
  const label = document.getElementById("status-label");
  try {
    const res = await fetch("/health");
    if (!res.ok) throw new Error();
    const data = await res.json();
    const ok = data.status === "healthy";
    dot.className = "status-dot " + (ok ? "online" : "degraded");
    label.textContent = ok ? "Online" : "Degraded";
    label.style.color = ok ? "var(--green)" : "var(--yellow)";
  } catch {
    dot.className = "status-dot offline";
    label.textContent = "Offline";
    label.style.color = "var(--red)";
  }
}

async function handleAsk(e) {
  e.preventDefault();
  const question = document.getElementById("question").value.trim();
  if (!question) return;

  const mode = document.querySelector('input[name="mode"]:checked').value;
  const btn = document.getElementById("ask-btn");
  const loading = document.getElementById("loading");

  btn.disabled = true;
  loading.classList.remove("hidden");
  hideAll();

  try {
    const res = await fetch("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, mode, top_k: 5 }),
    });

    loading.classList.add("hidden");

    if (!res.ok) {
      const err = await res.json().catch(() => null);
      throw new Error(err?.detail?.message || `Request failed (${res.status})`);
    }

    const data = await res.json();
    renderFlow(data);
    renderAnswer(data);
    renderQuality(data);
    renderCorrections(data);
  } catch (err) {
    loading.classList.add("hidden");
    const ep = document.getElementById("error-panel");
    ep.textContent = err.message;
    ep.classList.remove("hidden");
  } finally {
    btn.disabled = false;
  }
}

function hideAll() {
  ["error-panel", "flow-panel", "answer-panel", "quality-panel", "corrections-panel"]
    .forEach(id => document.getElementById(id).classList.add("hidden"));
}

function renderFlow(data) {
  const panel = document.getElementById("flow-panel");
  const steps = document.getElementById("flow-steps");
  if (!data.classification && !data.route_taken) return;

  panel.classList.remove("hidden");
  let html = "";

  if (data.classification) {
    const c = data.classification;
    html += `<div class="flow-step">
      <span class="flow-icon">🔍</span>
      <div>
        <div class="flow-title">Classification: <strong>${esc(c.category)}</strong></div>
        <div class="flow-detail">Confidence: ${(c.confidence * 100).toFixed(0)}% — ${esc(c.reasoning)}</div>
      </div>
    </div>`;
  }

  if (data.route_taken) {
    html += `<div class="flow-step">
      <span class="flow-icon">↳</span>
      <div>
        <div class="flow-title">Route: ${esc(data.route_taken)}</div>
      </div>
    </div>`;
  }

  steps.innerHTML = html;
}

function renderAnswer(data) {
  const panel = document.getElementById("answer-panel");
  panel.classList.remove("hidden");

  document.getElementById("answer-model").textContent = data.model;
  document.getElementById("answer-latency").textContent = `${Math.round(data.latency_ms)}ms`;
  document.getElementById("answer-route").textContent = data.retrieval_method;
  document.getElementById("answer-text").textContent = data.answer;

  const citationList = document.getElementById("citation-list");
  const citationSection = document.getElementById("citations-section");
  citationList.innerHTML = "";

  if (data.citations && data.citations.length > 0) {
    citationSection.classList.remove("hidden");
    data.citations.forEach(c => {
      const item = document.createElement("div");
      item.className = "citation-item";
      item.innerHTML = `
        <div class="citation-source">${esc(c.document)} — ${esc(c.chunk_id)}</div>
        <div class="citation-content">${esc(c.content)}</div>
        <div class="citation-score">Relevance: ${(c.score * 100).toFixed(1)}%</div>
      `;
      citationList.appendChild(item);
    });
  } else {
    citationSection.classList.add("hidden");
  }
}

function renderQuality(data) {
  if (!data.quality) return;
  const panel = document.getElementById("quality-panel");
  panel.classList.remove("hidden");

  const q = data.quality;
  const fill = document.getElementById("gauge-fill");
  const pct = Math.min(100, Math.max(0, q.score * 100));
  fill.style.width = pct + "%";
  fill.style.background = q.passed ? "var(--green)" : "var(--red)";

  document.getElementById("gauge-score").textContent = q.score.toFixed(3);
  const status = document.getElementById("gauge-status");
  status.textContent = q.passed ? "PASSED" : "BELOW THRESHOLD";
  status.style.color = q.passed ? "var(--green)" : "var(--red)";
  document.getElementById("gauge-details").textContent = q.details;
}

function renderCorrections(data) {
  if (!data.corrections || data.corrections.length === 0) return;
  const panel = document.getElementById("corrections-panel");
  const list = document.getElementById("corrections-list");
  panel.classList.remove("hidden");

  list.innerHTML = data.corrections.map(c => `
    <div class="correction-round ${c.passed ? 'passed' : 'failed'}">
      <div class="correction-header">
        <span class="correction-num">Round ${c.round}</span>
        <span class="correction-status">${c.passed ? '✓ Passed' : '✗ Below threshold'}</span>
        <span class="correction-score">${c.quality_score.toFixed(3)}</span>
      </div>
      <div class="correction-query">${esc(c.expanded_query)}</div>
      <div class="correction-results">${c.results_count} results retrieved</div>
    </div>
  `).join("");
}

function esc(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}
