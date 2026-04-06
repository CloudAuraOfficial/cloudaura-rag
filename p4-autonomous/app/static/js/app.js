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
    renderGrades(data);
    renderAnswer(data);
    renderCritique(data);
    renderSteps(data);
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
  ["error-panel", "grades-panel", "answer-panel", "critique-panel", "steps-panel"]
    .forEach(id => document.getElementById(id).classList.add("hidden"));
}

function renderGrades(data) {
  if (!data.relevance_grades || data.relevance_grades.length === 0) return;
  const panel = document.getElementById("grades-panel");
  panel.classList.remove("hidden");

  const relevant = data.relevance_grades.filter(g => g.relevant).length;
  const filtered = data.filtered_count || 0;
  const total = data.relevance_grades.length;

  document.getElementById("grades-summary").innerHTML = `
    <div class="grade-stat relevant">
      <span class="count">${relevant}</span>
      <span>relevant of ${total}</span>
    </div>
    <div class="grade-stat filtered">
      <span class="count">${filtered}</span>
      <span>filtered out</span>
    </div>
  `;

  const list = document.getElementById("grades-list");
  list.innerHTML = data.relevance_grades.map(g => `
    <div class="grade-item ${g.relevant ? 'relevant' : 'irrelevant'}">
      <span class="grade-badge">${g.relevant ? 'RELEVANT' : 'FILTERED'}</span>
      <div class="grade-info">
        <div class="grade-chunk">${esc(g.chunk_id)}</div>
        <div class="grade-reasoning">${esc(g.reasoning)}</div>
      </div>
      <span class="grade-confidence">${(g.confidence * 100).toFixed(0)}%</span>
    </div>
  `).join("");
}

function renderAnswer(data) {
  const panel = document.getElementById("answer-panel");
  panel.classList.remove("hidden");

  document.getElementById("answer-model").textContent = data.model;
  document.getElementById("answer-latency").textContent = `${Math.round(data.latency_ms)}ms`;
  document.getElementById("answer-method").textContent = data.retrieval_method;
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

function renderCritique(data) {
  if (!data.critique) return;
  const panel = document.getElementById("critique-panel");
  panel.classList.remove("hidden");

  const c = data.critique;
  const scoreColor = c.overall_score >= 0.7 ? "var(--green)" : c.overall_score >= 0.4 ? "var(--yellow)" : "var(--red)";

  document.getElementById("critique-card").innerHTML = `
    <div class="critique-checks">
      <span class="critique-check ${c.faithful ? 'pass' : 'fail'}">
        <span class="check-icon">${c.faithful ? '&#10003;' : '&#10007;'}</span> Faithful
      </span>
      <span class="critique-check ${c.complete ? 'pass' : 'fail'}">
        <span class="check-icon">${c.complete ? '&#10003;' : '&#10007;'}</span> Complete
      </span>
      <span class="critique-check ${c.hallucination_free ? 'pass' : 'fail'}">
        <span class="check-icon">${c.hallucination_free ? '&#10003;' : '&#10007;'}</span> Hallucination-Free
      </span>
    </div>
    <div class="critique-score-bar">
      <span class="critique-score-label">Overall</span>
      <div class="critique-bar">
        <div class="critique-bar-fill" style="width:${c.overall_score * 100}%;background:${scoreColor}"></div>
      </div>
      <span class="critique-score-value">${c.overall_score.toFixed(2)}</span>
    </div>
    <p class="critique-reasoning">${esc(c.reasoning)}</p>
  `;
}

function renderSteps(data) {
  if (!data.agent_steps || data.agent_steps.length === 0) return;
  const panel = document.getElementById("steps-panel");
  panel.classList.remove("hidden");

  const list = document.getElementById("steps-list");
  list.innerHTML = data.agent_steps.map(s => `
    <div class="agent-step">
      <div class="step-header">
        <span class="step-num">Step ${s.step}</span>
        <span class="step-thought">${esc(s.thought)}</span>
        ${s.tool_call ? `<span class="step-tool-badge">${esc(s.tool_call.tool)}</span>` : ''}
      </div>
      <div class="step-body">
        ${s.tool_call ? `<div class="step-args">${esc(JSON.stringify(s.tool_call.args))}</div>` : ''}
        ${s.observation ? `<div class="step-observation">${esc(s.observation)}</div>` : ''}
      </div>
    </div>
  `).join("");
}

function esc(text) {
  if (!text) return "";
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}
