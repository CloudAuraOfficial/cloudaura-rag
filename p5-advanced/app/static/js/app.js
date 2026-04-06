document.addEventListener("DOMContentLoaded", () => {
  loadHealth();
  loadGraph();
  loadExamples();
  document.getElementById("ask-form").addEventListener("submit", handleAsk);
  document.querySelectorAll('input[name="mode"]').forEach(r => r.addEventListener("change", updateModeDesc));
});

const MODE_DESCRIPTIONS = {
  naive: "Simple vector similarity search — finds chunks closest to your query embedding.",
  local: "Entity-focused retrieval — traverses the knowledge graph around specific entities mentioned in the query.",
  global: "Relationship-focused retrieval — explores broad patterns and connections across the entire knowledge graph.",
  hybrid: "Combines local entity-focused and global relationship-focused retrieval for comprehensive answers.",
  mix: "Combines knowledge graph traversal with vector similarity search for complex multi-faceted questions.",
};

function updateModeDesc() {
  const mode = document.querySelector('input[name="mode"]:checked').value;
  document.getElementById("mode-desc").textContent = MODE_DESCRIPTIONS[mode] || "";
}

async function loadHealth() {
  const dot = document.getElementById("status-dot");
  const label = document.getElementById("status-label");
  try {
    const res = await fetch("/health");
    if (!res.ok) throw new Error();
    const data = await res.json();
    const ok = data.status === "healthy";
    dot.className = "status-dot " + (ok ? "online" : "degraded");
    label.textContent = ok ? (data.demo_mode ? "Demo Mode" : "Online") : "Degraded";
    label.style.color = ok ? "var(--green)" : "var(--yellow)";
  } catch {
    dot.className = "status-dot offline";
    label.textContent = "Offline";
    label.style.color = "var(--red)";
  }
}

// ── Knowledge Graph Visualization ────────────────
async function loadGraph() {
  try {
    const res = await fetch("/api/graph");
    if (!res.ok) return;
    const data = await res.json();
    renderGraph(data);

    const meta = document.getElementById("graph-meta");
    meta.innerHTML = `
      <span>${data.node_count} nodes</span>
      <span>${data.edge_count} edges</span>
      <span>Source: ${data.source}</span>
    `;
  } catch (err) {
    console.error("Graph load failed:", err);
  }
}

function renderGraph(data) {
  const container = document.getElementById("graph-container");
  const svg = d3.select("#graph-svg");
  svg.selectAll("*").remove();

  const width = container.clientWidth;
  const height = container.clientHeight;

  svg.attr("viewBox", [0, 0, width, height]);

  const typeColors = {
    technology: "#d4a245",
    concept: "#5cb87a",
    component: "#6b9fd4",
    resource: "#cf6565",
    infrastructure: "#a09a90",
    pattern: "#b57edc",
  };

  const g = svg.append("g");

  // Zoom behavior
  const zoom = d3.zoom()
    .scaleExtent([0.3, 4])
    .on("zoom", (event) => g.attr("transform", event.transform));
  svg.call(zoom);

  const simulation = d3.forceSimulation(data.nodes)
    .force("link", d3.forceLink(data.links).id(d => d.id).distance(80))
    .force("charge", d3.forceManyBody().strength(-200))
    .force("center", d3.forceCenter(width / 2, height / 2))
    .force("collision", d3.forceCollide().radius(d => (d.size || 1) * 8 + 5));

  // Links
  const link = g.append("g")
    .selectAll("line")
    .data(data.links)
    .join("line")
    .attr("class", "link-line")
    .attr("stroke-width", d => Math.max(1, d.weight * 0.8));

  // Link labels
  const linkLabel = g.append("g")
    .selectAll("text")
    .data(data.links)
    .join("text")
    .attr("class", "link-label")
    .attr("text-anchor", "middle")
    .text(d => d.label);

  // Nodes
  const node = g.append("g")
    .selectAll("g")
    .data(data.nodes)
    .join("g")
    .call(d3.drag()
      .on("start", dragstarted)
      .on("drag", dragged)
      .on("end", dragended));

  node.append("circle")
    .attr("class", "node-circle")
    .attr("r", d => (d.size || 1) * 6)
    .attr("fill", d => typeColors[d.type] || "#a09a90")
    .attr("stroke", "rgba(255,255,255,0.1)")
    .attr("stroke-width", 1);

  node.append("text")
    .attr("class", "node-label")
    .attr("dy", d => (d.size || 1) * 6 + 12)
    .attr("text-anchor", "middle")
    .text(d => d.label);

  // Tooltip on hover
  node.append("title").text(d => `${d.label} (${d.type})`);

  simulation.on("tick", () => {
    link
      .attr("x1", d => d.source.x)
      .attr("y1", d => d.source.y)
      .attr("x2", d => d.target.x)
      .attr("y2", d => d.target.y);

    linkLabel
      .attr("x", d => (d.source.x + d.target.x) / 2)
      .attr("y", d => (d.source.y + d.target.y) / 2);

    node.attr("transform", d => `translate(${d.x},${d.y})`);
  });

  function dragstarted(event) {
    if (!event.active) simulation.alphaTarget(0.3).restart();
    event.subject.fx = event.subject.x;
    event.subject.fy = event.subject.y;
  }

  function dragged(event) {
    event.subject.fx = event.x;
    event.subject.fy = event.y;
  }

  function dragended(event) {
    if (!event.active) simulation.alphaTarget(0);
    event.subject.fx = null;
    event.subject.fy = null;
  }
}

// ── Query Interface ──────────────────────────────
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
      body: JSON.stringify({ question, mode, top_k: 60 }),
    });

    loading.classList.add("hidden");

    if (!res.ok) {
      const err = await res.json().catch(() => null);
      throw new Error(err?.detail?.message || `Request failed (${res.status})`);
    }

    const data = await res.json();
    renderAnswer(data);
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
  ["error-panel", "answer-panel"].forEach(id =>
    document.getElementById(id).classList.add("hidden")
  );
}

function renderAnswer(data) {
  const panel = document.getElementById("answer-panel");
  panel.classList.remove("hidden");
  document.getElementById("answer-model").textContent = data.model;
  document.getElementById("answer-latency").textContent = `${Math.round(data.latency_ms)}ms`;
  document.getElementById("answer-mode").textContent = data.mode;
  document.getElementById("answer-text").textContent = data.answer;
}

// ── Example Queries ──────────────────────────────
async function loadExamples() {
  const list = document.getElementById("examples-list");
  const examples = [
    { question: "What is the relationship between Kubernetes and Docker?", mode: "hybrid" },
    { question: "How does the Kubernetes control plane work?", mode: "local" },
    { question: "What are the three pillars of observability?", mode: "global" },
    { question: "How are microservices deployed on Kubernetes?", mode: "mix" },
    { question: "What is a Kubernetes pod?", mode: "naive" },
  ];

  list.innerHTML = examples.map(ex => `
    <div class="example-item" data-question="${esc(ex.question)}" data-mode="${ex.mode}">
      <span class="example-mode">${ex.mode}</span>
      <span class="example-question">${esc(ex.question)}</span>
    </div>
  `).join("");

  list.querySelectorAll(".example-item").forEach(item => {
    item.addEventListener("click", () => {
      document.getElementById("question").value = item.dataset.question;
      const radio = document.querySelector(`input[name="mode"][value="${item.dataset.mode}"]`);
      if (radio) { radio.checked = true; updateModeDesc(); }
      document.getElementById("ask-form").dispatchEvent(new Event("submit"));
    });
  });
}

function esc(text) {
  if (!text) return "";
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}
