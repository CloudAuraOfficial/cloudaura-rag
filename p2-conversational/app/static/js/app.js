let currentSessionId = null;

document.addEventListener("DOMContentLoaded", () => {
  loadHealth();
  document.getElementById("ask-form").addEventListener("submit", handleAsk);
  document.getElementById("new-session-btn").addEventListener("click", newSession);
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

function newSession() {
  currentSessionId = null;
  document.getElementById("session-id").textContent = "—";
  document.getElementById("chat-container").innerHTML =
    '<div class="chat-empty" id="chat-empty"><p>Start a conversation. Ask a question about the corpus documents.</p></div>';
  document.getElementById("sub-questions-panel").classList.add("hidden");
}

async function handleAsk(e) {
  e.preventDefault();
  const question = document.getElementById("question").value.trim();
  if (!question) return;

  const mode = document.querySelector('input[name="mode"]:checked').value;
  const btn = document.getElementById("ask-btn");
  const container = document.getElementById("chat-container");

  // Remove empty state
  const empty = document.getElementById("chat-empty");
  if (empty) empty.remove();

  // Add user message
  appendMessage("user", question);
  document.getElementById("question").value = "";
  btn.disabled = true;

  // Add loading indicator
  const loadingEl = document.createElement("div");
  loadingEl.className = "chat-message assistant loading";
  loadingEl.innerHTML = '<div class="loading-bar"></div><span class="loading-text">Retrieving…</span>';
  container.appendChild(loadingEl);
  container.scrollTop = container.scrollHeight;

  try {
    const res = await fetch("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question,
        session_id: currentSessionId,
        mode,
        top_k: 5,
      }),
    });

    loadingEl.remove();

    if (!res.ok) {
      const err = await res.json().catch(() => null);
      throw new Error(err?.detail?.message || `Request failed (${res.status})`);
    }

    const data = await res.json();
    currentSessionId = data.session_id;
    document.getElementById("session-id").textContent = data.session_id;

    appendMessage("assistant", data.answer, data);

    // Show sub-questions if branched
    if (data.sub_questions && data.sub_questions.length > 0) {
      renderSubQuestions(data.sub_questions);
    } else {
      document.getElementById("sub-questions-panel").classList.add("hidden");
    }
  } catch (err) {
    loadingEl.remove();
    appendMessage("error", err.message);
  } finally {
    btn.disabled = false;
  }
}

function appendMessage(role, content, data) {
  const container = document.getElementById("chat-container");
  const msg = document.createElement("div");
  msg.className = `chat-message ${role}`;

  if (role === "user") {
    msg.innerHTML = `<div class="msg-role">You</div><div class="msg-text">${escapeHtml(content)}</div>`;
  } else if (role === "assistant") {
    let meta = "";
    if (data) {
      meta = `<div class="msg-meta">
        <span class="meta-chip">${data.model}</span>
        <span class="meta-chip">${Math.round(data.latency_ms)}ms</span>
        <span class="meta-chip accent">${data.retrieval_method}</span>
        <span class="meta-chip">Context: ${data.conversation_context} turns</span>
      </div>`;
    }
    let citations = "";
    if (data && data.citations && data.citations.length > 0) {
      citations = `<div class="msg-citations">${data.citations.map(c =>
        `<div class="citation-chip" title="${escapeHtml(c.content)}">${escapeHtml(c.document)} · ${(c.score * 100).toFixed(0)}%</div>`
      ).join("")}</div>`;
    }
    msg.innerHTML = `<div class="msg-role">Assistant</div><div class="msg-text">${escapeHtml(content)}</div>${meta}${citations}`;
  } else {
    msg.innerHTML = `<div class="msg-error">${escapeHtml(content)}</div>`;
  }

  container.appendChild(msg);
  container.scrollTop = container.scrollHeight;
}

function renderSubQuestions(sqs) {
  const panel = document.getElementById("sub-questions-panel");
  const tree = document.getElementById("sq-tree");
  panel.classList.remove("hidden");
  tree.innerHTML = sqs.map((sq, i) =>
    `<div class="sq-branch">
      <span class="sq-index">${i + 1}</span>
      <span class="sq-text">${escapeHtml(sq.question)}</span>
      <span class="sq-count">${sq.results_count} results</span>
    </div>`
  ).join("");
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}
