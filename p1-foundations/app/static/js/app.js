document.addEventListener("DOMContentLoaded", () => {
  loadStats();
  loadHealth();
  setupP5Link();

  const form = document.getElementById("ask-form");
  form.addEventListener("submit", handleAsk);
});

function setupP5Link() {
  // Resolve P5 URL relative to current host
  const host = window.location.hostname;
  const protocol = window.location.protocol;
  const p5Host = host.replace(/^ragdocs\./, "rag-graph.");
  const p5Link = document.getElementById("p5-link");
  if (p5Link) {
    p5Link.href = protocol + "//" + p5Host;
  }
}

async function loadStats() {
  try {
    const res = await fetch("/api/documents/stats");
    if (!res.ok) return;
    const data = await res.json();

    document.getElementById("stat-docs").textContent = data.total_documents;
    document.getElementById("stat-chunks").textContent = data.total_chunks;
    document.getElementById("stat-embed").textContent = shortModel(data.embedding_model);
    document.getElementById("stat-reranker").textContent = shortModel(data.reranker_model);
    document.getElementById("stat-llm").textContent = data.llm_model;
  } catch {
    /* stats will show dashes */
  }
}

async function loadHealth() {
  const el = document.getElementById("stat-health");
  const dot = document.getElementById("status-dot");
  const label = document.getElementById("status-label");
  try {
    const res = await fetch("/health");
    if (!res.ok) throw new Error();
    const data = await res.json();
    const healthy = data.status === "healthy";
    const ollamaUp = data.ollama_connected;

    el.textContent = healthy ? "Healthy" : "Degraded";
    el.style.color = ollamaUp ? "var(--green)" : "var(--yellow)";

    if (dot) dot.className = "status-dot " + (ollamaUp ? "online" : "degraded");
    if (label) {
      label.textContent = ollamaUp ? "Online" : "Degraded";
      label.style.color = ollamaUp ? "var(--green)" : "var(--yellow)";
    }
  } catch {
    el.textContent = "Offline";
    el.style.color = "var(--red)";
    if (dot) dot.className = "status-dot offline";
    if (label) {
      label.textContent = "Offline";
      label.style.color = "var(--red)";
    }
  }
}

async function handleAsk(e) {
  e.preventDefault();

  const question = document.getElementById("question").value.trim();
  if (!question) return;

  const topK = parseInt(document.getElementById("top-k").value) || 5;
  const btn = document.getElementById("ask-btn");
  const loading = document.getElementById("loading");
  const answerPanel = document.getElementById("answer-panel");
  const errorPanel = document.getElementById("error-panel");

  btn.disabled = true;
  loading.classList.remove("hidden");
  answerPanel.classList.add("hidden");
  errorPanel.classList.add("hidden");

  try {
    const res = await fetch("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, top_k: topK }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => null);
      throw new Error(err?.detail?.message || `Request failed (${res.status})`);
    }

    const data = await res.json();
    renderAnswer(data);
  } catch (err) {
    errorPanel.textContent = err.message;
    errorPanel.classList.remove("hidden");
  } finally {
    btn.disabled = false;
    loading.classList.add("hidden");
  }
}

function renderAnswer(data) {
  const panel = document.getElementById("answer-panel");
  panel.classList.remove("hidden");

  document.getElementById("answer-model").textContent = data.model;
  document.getElementById("answer-method").textContent = data.retrieval_method;
  document.getElementById("answer-latency").textContent = `${Math.round(data.latency_ms)}ms`;
  document.getElementById("answer-text").textContent = data.answer;

  const citationList = document.getElementById("citation-list");
  citationList.innerHTML = "";

  if (data.citations && data.citations.length > 0) {
    data.citations.forEach((c) => {
      const item = document.createElement("div");
      item.className = "citation-item";
      item.innerHTML = `
        <div class="citation-source">${escapeHtml(c.document)} — ${escapeHtml(c.chunk_id)}</div>
        <div class="citation-content">${escapeHtml(c.content)}</div>
        <div class="citation-score">Relevance: ${(c.score * 100).toFixed(1)}%</div>
      `;
      citationList.appendChild(item);
    });
  }
}

function shortModel(name) {
  if (!name) return "—";
  const parts = name.split("/");
  return parts[parts.length - 1];
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}
