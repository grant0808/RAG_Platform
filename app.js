const state = {
  view: "overview",
  route: "RAG",
  selectedNode: "router",
  pipelineName: "Knowledge assistant",
  version: 12,
  activeProvider: "openai",
  activeModel: "gpt-5.4-mini",
  providers: {
    openai: {
      name: "OpenAI",
      connected: true,
      masked: "••••••••H7K2",
      validated: "4 min ago",
      models: ["gpt-5.5", "gpt-5.4", "gpt-5.4-mini"],
    },
    anthropic: {
      name: "Anthropic",
      connected: false,
      masked: "Not connected",
      validated: "—",
      models: ["claude-opus-4-6", "claude-sonnet-4-5", "claude-haiku-4-5"],
    },
  },
  sources: {
    PDF: true,
    Notion: true,
    Web: false,
  },
  deployments: 1,
};

function connectedModels() {
  return Object.entries(state.providers)
    .filter(([, provider]) => provider.connected)
    .flatMap(([id, provider]) => provider.models.map(model => ({ id: model, provider: id, providerName: provider.name })));
}

const app = document.querySelector("#app");
const sidebar = document.querySelector("#sidebar");
const routeContent = {
  RAG: { title: "Document RAG", description: "의미 기반 검색으로 문서에서 근거를 찾고 답변을 생성합니다.", source: "142 docs", latency: "1.84s", hit: "91.2%" },
};

function pageHeading(index, title, outline, description, action = "") {
  return `<header class="page-heading">
    <div><div class="eyebrow">${index} / FOUNDRY WORKBENCH</div><h1>${title} <span class="outline">${outline}</span></h1></div>
    <div>${description ? `<p>${description}</p>` : ""}${action}</div>
  </header>`;
}

function overviewView() {
  const route = routeContent[state.route];
  return `<section class="page">
    ${pageHeading("01", "Build knowledge.", "Ship answers.", "분산된 문서를 하나의 검증 가능한 AI 파이프라인으로 연결하세요.")}
    <div class="hero-grid">
      <article class="hero-card">
        <div class="hero-top"><span class="status-pill"><i></i> PIPELINE HEALTHY</span><span class="hero-number">RUN / 24,891</span></div>
        <div class="hero-copy">
          <h2>질문에서 근거까지,<br /><em>10분 안에.</em></h2>
          <p>Knowledge assistant는 문서 검색으로 출처가 명확한 답변을 제공합니다.</p>
          <button class="button button-acid" data-go="playground">Open playground →</button>
        </div>
      </article>
      <aside class="route-card" aria-label="라우팅 방식">
        <div class="route-rail">
          <button class="route-letter active" data-route="RAG" aria-label="RAG 선택">R</button>
        </div>
        <div class="route-detail">
          <span class="route-code">ACTIVE / ${state.route}</span>
          <h3>${route.title}</h3><p>${route.description}</p>
          <dl><div><dt>Source</dt><dd>${route.source}</dd></div><div><dt>p95 latency</dt><dd>${route.latency}</dd></div><div><dt>Hit rate</dt><dd>${route.hit}</dd></div></dl>
        </div>
      </aside>
    </div>
    <div class="section-title"><h2>오늘의 운영 지표</h2><span>LAST 24 HOURS / UTC+9</span></div>
    <div class="metric-grid">
      <div class="metric"><div class="metric-label"><span>REQUESTS</span><span>↗</span></div><div class="metric-value">8,421</div><div class="metric-delta">+12.4% from yesterday</div></div>
      <div class="metric"><div class="metric-label"><span>ACCURACY</span><span>◎</span></div><div class="metric-value">88.6%</div><div class="metric-delta">Target ≥ 85%</div></div>
      <div class="metric"><div class="metric-label"><span>P95 LATENCY</span><span>◷</span></div><div class="metric-value">2.41s</div><div class="metric-delta">Within 3s target</div></div>
      <div class="metric"><div class="metric-label"><span>COST / QUERY</span><span>$</span></div><div class="metric-value">$0.021</div><div class="metric-delta">30% below target</div></div>
    </div>
    <div class="section-title"><h2>최근 파이프라인</h2><span>2 ACTIVE</span></div>
    <div class="table-card"><table class="data-table"><thead><tr><th>Pipeline</th><th>Strategy</th><th>Requests</th><th>Accuracy</th><th>Last updated</th><th>Health</th></tr></thead><tbody>
      <tr data-go="pipeline"><td><div class="pipeline-name"><span class="pipeline-icon">KA</span>Knowledge assistant</div></td><td><span class="mini-badge">RAG</span></td><td>6,824</td><td>88.6%</td><td>4 min ago</td><td><span class="health">Healthy</span></td></tr>
      <tr><td><div class="pipeline-name"><span class="pipeline-icon">CS</span>CS Copilot</div></td><td><span class="mini-badge">RAG</span></td><td>1,229</td><td>91.2%</td><td>2 hrs ago</td><td><span class="health">Healthy</span></td></tr>
    </tbody></table></div>
  </section>`;
}

function sourcesView() {
  const connectors = [
    ["PDF", "PDF", "파일 업로드", "문서, 보고서, 매뉴얼"], ["NT", "Notion", "Workspace sync", "페이지와 데이터베이스"], ["WB", "Web", "URL crawler", "사이트와 공개 문서"],
  ];
  const count = Object.values(state.sources).filter(Boolean).length;
  return `<section class="page">
    ${pageHeading("02", "Connect every", "source.", "데이터는 원본에 가깝게 유지하고, 파이프라인에는 필요한 맥락만 전달합니다.", `<button class="button button-primary" data-connect-all>Connect sample data</button>`)}
    <div class="source-summary"><div class="summary-block"><b>${count}</b><span>Connected sources</span></div><div class="summary-block"><b>2.84 GB</b><span>Indexed knowledge</span></div><div class="summary-block"><b>4 min</b><span>Last synchronization</span></div></div>
    <div class="section-title"><h2>커넥터 카탈로그</h2><span>6 AVAILABLE / ${count} CONNECTED</span></div>
    <div class="connector-grid">
      ${connectors.map(([logo, name, kind, desc]) => { const connected = state.sources[name]; return `<article class="connector ${connected ? "connected" : ""}"><div class="connector-head"><span class="connector-logo">${logo}</span><span class="connector-status">${connected ? "● CONNECTED" : "○ AVAILABLE"}</span></div><h3>${name}</h3><p>${kind}<br />${desc}</p><button class="button ${connected ? "button-ghost" : "button-primary"}" data-source="${name}">${connected ? "Manage" : "Connect →"}</button></article>`; }).join("")}
    </div>
  </section>`;
}

function providersView() {
  const models = connectedModels();
  const providerCard = (id, mark, description) => {
    const provider = state.providers[id];
    return `<article class="provider-card ${provider.connected ? "connected" : ""}">
      <div class="provider-card-head"><div class="provider-identity"><span class="provider-mark">${mark}</span><div><h3>${provider.name}</h3><span>${description}</span></div></div><span class="connection-state ${provider.connected ? "online" : ""}">${provider.connected ? "● CONNECTED" : "○ NOT CONNECTED"}</span></div>
      <div class="provider-body">
        <div class="provider-meta"><div><span>SECRET</span><strong>${provider.masked}</strong></div><div><span>LAST VERIFIED</span><strong>${provider.validated}</strong></div></div>
        <form data-provider-form="${id}"><div class="key-label"><span>${provider.connected ? "Replace API key" : "API key"}</span><small>Write-only · never shown again</small></div><div class="key-input-row"><input type="password" name="apiKey" aria-label="${provider.name} API key" placeholder="${id === "openai" ? "sk-proj-••••••••" : "sk-ant-••••••••"}" autocomplete="new-password" required /><button class="button button-primary">${provider.connected ? "Rotate & verify" : "Connect & verify"}</button></div><p class="provider-help">목업에서는 연결만 시뮬레이션합니다. 실제 키는 서버의 Credential Vault로 직접 전송되어야 합니다.</p></form>
      </div>
    </article>`;
  };

  return `<section class="page">
    ${pageHeading("03", "Bring your own", "intelligence.", "OpenAI와 Anthropic 자격증명을 안전하게 연결하고, 실제 사용 가능한 모델을 파이프라인에 할당합니다.")}
    <div class="vault-banner"><span class="vault-symbol">⌁</span><div><strong>Provider Vault / write-only credentials</strong><small>키는 브라우저에 저장되지 않으며 등록 후 원문을 다시 표시하지 않습니다.</small></div><span>ADMIN ACCESS ONLY</span></div>
    <div class="provider-grid">${providerCard("openai", "OA", "Responses API · Models API")}${providerCard("anthropic", "AN", "Messages API · Models API")}</div>
    <section class="model-catalog"><div class="catalog-head"><h2>사용 가능한 모델</h2><span>${models.length} MODELS · SYNCED NOW</span></div>
      ${models.length ? models.map(model => `<div class="model-row"><div class="model-name"><strong>${model.id}</strong><span>Provider key permission verified</span></div><span class="model-provider">${model.providerName}</span><div class="capability-tags"><span>STREAM</span><span>TEXT</span><span>TOOLS</span></div><button class="button button-ghost ${state.activeModel === model.id ? "selected" : ""}" data-select-model="${model.id}" data-provider="${model.provider}">${state.activeModel === model.id ? "Selected" : "Use model"}</button></div>`).join("") : `<div class="empty-deploy"><h3>연결된 모델이 없습니다.</h3><p>Provider API 키를 연결하고 검증해 주세요.</p></div>`}
    </section>
  </section>`;
}

function pipelineView() {
  const providerOptions = Object.entries(state.providers).filter(([, provider]) => provider.connected);
  const modelOptions = state.providers[state.activeProvider].models;
  return `<section class="page">
    ${pageHeading("04", "Shape the", "reasoning.", "각 단계의 Provider, 모델, 검색 방식, 라우팅 규칙을 조정하고 버전으로 안전하게 저장합니다.", `<button class="button button-primary" data-save>Save v${state.version + 1}</button>`)}
    <div class="studio-shell">
      <div class="canvas">
        <div class="canvas-toolbar"><div class="segmented"><button class="active">Flow</button><button>Runs</button><button>Versions</button></div><div class="canvas-actions"><button aria-label="축소">−</button><button aria-label="확대">+</button><button aria-label="화면 맞춤">⌗</button></div></div>
        <div class="pipeline-flow"><div class="flow-line"></div>
          <article class="node ${state.selectedNode === "source" ? "selected" : ""}" data-node="source"><span class="node-code">NODE / 01</span><div class="node-icon">▥</div><h3>LC Retriever</h3><p>PDF · Notion · Web<br />PGVector retriever</p></article>
          <article class="node node-router ${state.selectedNode === "router" ? "selected" : ""}" data-node="router"><span class="node-code">NODE / 02</span><div class="node-icon">R</div><h3>RAG Runnable</h3><p>Document retrieval<br />Grounded context</p></article>
          <article class="node ${state.selectedNode === "generate" ? "selected" : ""}" data-node="generate"><span class="node-code">NODE / 03</span><div class="node-icon">✣</div><h3>Generate answer</h3><p>${state.providers[state.activeProvider].name}<br />${state.activeModel}</p></article>
          <article class="node ${state.selectedNode === "output" ? "selected" : ""}" data-node="output"><span class="node-code">NODE / 04</span><div class="node-icon">↗</div><h3>Response</h3><p>Citations enabled<br />Stream output</p></article>
        </div>
      </div>
      <aside class="inspector">
        <div class="inspector-head"><span>LANGCHAIN / NODE 02</span><h2>${state.selectedNode === "router" ? "Strategy Runnable" : state.selectedNode.charAt(0).toUpperCase() + state.selectedNode.slice(1)}</h2></div>
        <div class="settings-group"><div class="settings-label"><span>Model provider</span><output>CONNECTED</output></div><select id="providerSelect">${providerOptions.map(([id, provider]) => `<option value="${id}" ${state.activeProvider === id ? "selected" : ""}>${provider.name}</option>`).join("")}</select></div>
        <div class="settings-group"><div class="settings-label"><span>Model</span></div><select id="modelSelect">${modelOptions.map(model => `<option value="${model}" ${state.activeModel === model ? "selected" : ""}>${model}</option>`).join("")}</select></div>
        <div class="settings-group"><div class="settings-label"><span>Retrieval mode</span></div><select><option>Document RAG</option></select></div>
        <div class="settings-group"><div class="settings-label"><span>Retrieval top K</span><output id="topKOutput">5</output></div><input id="topK" type="range" min="1" max="12" value="5" /></div>
        <div class="settings-group"><div class="settings-label"><span>Similarity threshold</span><output id="thresholdOutput">0.78</output></div><input id="threshold" type="range" min="50" max="95" value="78" /></div>
        <div class="settings-group"><div class="check-row"><span>Answer citations</span><label class="switch"><input type="checkbox" checked /><span></span></label></div><div class="check-row"><span>Query rewrite</span><label class="switch"><input type="checkbox" /><span></span></label></div></div>
        <div class="inspector-actions"><button class="button button-ghost" data-save>Save draft</button><button class="button button-primary" data-go="playground">Test run →</button></div>
      </aside>
    </div>
  </section>`;
}

function playgroundView() {
  return `<section class="page">
    ${pageHeading("05", "Test with", "evidence.", "실제 질문을 실행하고 어떤 Provider 모델과 근거가 답변에 사용됐는지 추적합니다.")}
    <div class="playground-layout">
      <div class="chat-panel"><div class="chat-head"><strong>${state.pipelineName}</strong><span class="model-pill">${state.providers[state.activeProvider].name} · ${state.activeModel} / v${state.version}</span></div>
        <div class="messages" id="messages"><div class="message"><div class="message-meta"><span>FOUNDRY</span><span>09:41</span></div><div class="message-body">연결된 문서에 대해 질문해 주세요. 답변과 함께 사용된 출처를 표시합니다.</div></div></div>
        <form class="composer" id="chatForm"><div class="composer-box"><textarea id="chatInput" aria-label="질문 입력" placeholder="예: 고객 데이터 보안 정책은 어떻게 되나요?" required></textarea><button aria-label="질문 전송">↑</button></div><p class="composer-hint">ENTER TO SEND · SHIFT+ENTER FOR NEW LINE</p></form>
      </div>
      <aside class="trace-panel"><div class="trace-head"><span>LIVE / LANGCHAIN TRACE</span><h2>Runnable execution</h2></div><div class="trace-route"><div class="trace-rail"><div class="trace-step active" data-trace="RAG">R</div></div><div class="trace-details"><div class="trace-row"><strong>Retriever Runnable</strong><span>Selected · 142 docs</span></div><div class="trace-row"><strong>Chat Model</strong><span>Streaming answer</span></div></div></div><div class="trace-metrics"><div><span>PROVIDER</span><b>${state.providers[state.activeProvider].name}</b></div><div><span>MODEL</span><b>${state.activeModel}</b></div><div><span>CONFIDENCE</span><b id="traceConfidence">91.8%</b></div><div><span>LATENCY</span><b id="traceLatency">1.84s</b></div><div><span>COST</span><b id="traceCost">$0.024</b></div><div><span>TOKENS</span><b>1,284</b></div></div></aside>
    </div>
  </section>`;
}

function deploymentsView() {
  return `<section class="page">
    ${pageHeading("06", "Deploy once.", "Observe always.", "웹과 API로 배포하고 Provider·모델별 요청량, 비용, 지연시간을 한 화면에서 추적합니다.", `<button class="button button-primary" data-deploy>+ Create deployment</button>`)}
    <div class="section-title"><h2>활성 배포</h2><span>${state.deployments} PRODUCTION</span></div>
    <article class="deployment-card"><div class="deployment-main"><div class="deployment-title"><div><h3>Knowledge assistant / Production</h3><p>VERSION ${state.version} · DEPLOYED 2 DAYS AGO</p></div><span class="live-badge">● LIVE</span></div><div class="endpoint"><span>POST</span><code>https://api.foundry.dev/v1/chat/knw_82af</code><button data-copy="https://api.foundry.dev/v1/chat/knw_82af">Copy</button></div></div><div class="deployment-stats"><div><span>24H REQUESTS</span><strong>8,421</strong></div><div><span>ERROR RATE</span><strong>0.12%</strong></div></div></article>
    <article class="deployment-card"><div class="deployment-main"><div class="deployment-title"><div><h3>Knowledge assistant / Preview</h3><p>VERSION ${state.version + 1} · DRAFT</p></div><span class="mini-badge">PREVIEW</span></div><div class="endpoint"><span>WEB</span><code>https://chat.foundry.dev/preview/knw_82af</code><button data-copy="https://chat.foundry.dev/preview/knw_82af">Copy</button></div></div><div class="deployment-stats"><div><span>TEST RUNS</span><strong>248</strong></div><div><span>ACCURACY</span><strong>89.1%</strong></div></div></article>
    <div class="empty-deploy"><div class="pipeline-icon" style="margin:auto">+</div><h3>새로운 환경이 필요하신가요?</h3><p>동일한 파이프라인을 별도 엔드포인트로 안전하게 배포할 수 있습니다.</p></div>
  </section>`;
}

const views = { overview: overviewView, sources: sourcesView, providers: providersView, pipeline: pipelineView, playground: playgroundView, deployments: deploymentsView };

function render(view = state.view) {
  state.view = view;
  app.innerHTML = views[view]();
  document.querySelectorAll(".nav-item").forEach(button => button.classList.toggle("active", button.dataset.view === view));
  document.querySelector("#currentContext").textContent = view === "overview" ? state.pipelineName : buttonLabel(view);
  window.history.replaceState(null, "", `#${view}`);
  sidebar.classList.remove("open");
  document.querySelector("#menuButton").setAttribute("aria-expanded", "false");
  bindViewEvents();
  app.focus({ preventScroll: true });
}

function buttonLabel(view) {
  return ({ sources: "Data sources", providers: "Model providers", pipeline: state.pipelineName, playground: "Playground", deployments: "Deployments" })[view] || state.pipelineName;
}

function showToast(message) {
  const region = document.querySelector("#toastRegion");
  const toast = document.createElement("div");
  toast.className = "toast";
  toast.textContent = message;
  region.appendChild(toast);
  setTimeout(() => toast.remove(), 2800);
}

function bindViewEvents() {
  document.querySelectorAll("[data-go]").forEach(el => el.addEventListener("click", () => render(el.dataset.go)));
  document.querySelectorAll("[data-route]").forEach(el => el.addEventListener("click", () => { state.route = el.dataset.route; render("overview"); }));
  document.querySelectorAll("[data-node]").forEach(el => el.addEventListener("click", () => { state.selectedNode = el.dataset.node; render("pipeline"); }));
  document.querySelectorAll("[data-save]").forEach(el => el.addEventListener("click", () => { state.version += 1; showToast(`파이프라인 v${state.version}이 저장되었습니다.`); render("pipeline"); }));
  document.querySelectorAll("[data-source]").forEach(el => el.addEventListener("click", () => { const source = el.dataset.source; if (state.sources[source]) { showToast(`${source} 연결 설정을 열었습니다.`); } else { state.sources[source] = true; showToast(`${source} 샘플 소스가 연결되었습니다.`); render("sources"); } }));
  document.querySelector("[data-connect-all]")?.addEventListener("click", () => { Object.keys(state.sources).forEach(k => state.sources[k] = true); showToast("모든 샘플 데이터가 연결되었습니다."); render("sources"); });
  document.querySelector("#topK")?.addEventListener("input", e => document.querySelector("#topKOutput").textContent = e.target.value);
  document.querySelector("#threshold")?.addEventListener("input", e => document.querySelector("#thresholdOutput").textContent = (e.target.value / 100).toFixed(2));
  document.querySelectorAll("[data-provider-form]").forEach(form => form.addEventListener("submit", handleProviderConnection));
  document.querySelectorAll("[data-select-model]").forEach(button => button.addEventListener("click", () => {
    state.activeProvider = button.dataset.provider;
    state.activeModel = button.dataset.selectModel;
    showToast(`${state.providers[state.activeProvider].name} · ${state.activeModel}을 기본 모델로 선택했습니다.`);
    render("providers");
  }));
  document.querySelector("#providerSelect")?.addEventListener("change", event => {
    state.activeProvider = event.target.value;
    state.activeModel = state.providers[state.activeProvider].models[0];
    showToast(`${state.providers[state.activeProvider].name} Provider로 변경했습니다.`);
    render("pipeline");
  });
  document.querySelector("#modelSelect")?.addEventListener("change", event => {
    state.activeModel = event.target.value;
    showToast(`${state.activeModel} 모델을 선택했습니다.`);
    render("pipeline");
  });
  document.querySelector("#chatForm")?.addEventListener("submit", handleChat);
  document.querySelector("#chatInput")?.addEventListener("keydown", e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); e.currentTarget.form.requestSubmit(); } });
  document.querySelectorAll("[data-copy]").forEach(el => el.addEventListener("click", async () => { try { await navigator.clipboard.writeText(el.dataset.copy); showToast("엔드포인트를 복사했습니다."); } catch { showToast("복사할 주소: " + el.dataset.copy); } }));
  document.querySelector("[data-deploy]")?.addEventListener("click", () => { state.deployments += 1; showToast("새 Preview 환경을 생성했습니다."); });
}

function handleProviderConnection(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const input = form.elements.apiKey;
  const providerId = form.dataset.providerForm;
  if (input.value.trim().length < 8) {
    showToast("유효한 형식의 API 키를 입력해 주세요.");
    return;
  }

  input.value = "";
  const submit = form.querySelector("button");
  submit.disabled = true;
  submit.textContent = "Verifying…";
  showToast(`${state.providers[providerId].name} 연결을 검증하고 있습니다.`);

  setTimeout(() => {
    state.providers[providerId].connected = true;
    state.providers[providerId].masked = "••••••••NEW1";
    state.providers[providerId].validated = "Just now";
    showToast(`${state.providers[providerId].name} 연결과 모델 동기화가 완료되었습니다.`);
    render("providers");
  }, 700);
}

function handleChat(event) {
  event.preventDefault();
  const input = document.querySelector("#chatInput");
  const text = input.value.trim();
  if (!text) return;
  const messages = document.querySelector("#messages");
  messages.insertAdjacentHTML("beforeend", `<div class="message user"><div class="message-meta"><span>YOU</span><span>NOW</span></div><div class="message-body"></div></div>`);
  messages.lastElementChild.querySelector(".message-body").textContent = text;
  messages.insertAdjacentHTML("beforeend", `<div class="message thinking-message"><div class="message-meta"><span>FOUNDRY</span><span>ROUTING</span></div><div class="message-body"><span class="thinking"><i></i><i></i><i></i></span></div></div>`);
  input.value = "";
  messages.scrollTop = messages.scrollHeight;

  const route = "RAG";
  document.querySelectorAll("[data-trace]").forEach(el => el.classList.toggle("active", el.dataset.trace === route));
  document.querySelector("#traceConfidence").textContent = "91.8%";
  document.querySelector("#traceLatency").textContent = "1.84s";
  document.querySelector("#traceCost").textContent = "$0.024";

  setTimeout(() => {
    document.querySelector(".thinking-message")?.remove();
    const answer = "연결된 운영 가이드에 따르면, 고객 데이터는 테넌트별 인덱스로 격리되고 모든 외부 통신에는 TLS가 적용됩니다. 원본 문서와 임베딩 역시 조직별로 분리됩니다.";
    const sources = ["security-policy.pdf · p.12", "architecture.md · §4"];
    messages.insertAdjacentHTML("beforeend", `<div class="message"><div class="message-meta"><span>FOUNDRY · ${route}</span><span>NOW</span></div><div class="message-body">${answer}<div class="message-sources">${sources.map(s => `<span class="source-chip">${s}</span>`).join("")}</div></div></div>`);
    messages.scrollTop = messages.scrollHeight;
  }, 850);
}

document.querySelectorAll(".nav-item").forEach(button => button.addEventListener("click", () => render(button.dataset.view)));
document.querySelectorAll("[data-action='new-pipeline']").forEach(button => button.addEventListener("click", () => document.querySelector("#pipelineDialog").showModal()));
document.querySelector("#pipelineForm").addEventListener("submit", event => {
  if (event.submitter?.value === "cancel") return;
  const form = new FormData(event.currentTarget);
  state.pipelineName = form.get("name") || "Untitled pipeline";
  showToast(`${state.pipelineName} 파이프라인을 생성했습니다.`);
  setTimeout(() => render("pipeline"), 0);
});
document.querySelector("#menuButton").addEventListener("click", event => { const open = sidebar.classList.toggle("open"); event.currentTarget.setAttribute("aria-expanded", String(open)); });

const commandMenu = document.querySelector("#commandMenu");
function toggleCommand(open) { commandMenu.hidden = !open; if (open) setTimeout(() => document.querySelector("#commandInput").focus(), 0); }
document.querySelector("#commandButton").addEventListener("click", () => toggleCommand(true));
document.querySelectorAll("[data-command]").forEach(button => button.addEventListener("click", () => { toggleCommand(false); if (button.dataset.command === "new") document.querySelector("#pipelineDialog").showModal(); else render(button.dataset.command); }));
commandMenu.addEventListener("click", event => { if (event.target === commandMenu) toggleCommand(false); });
document.addEventListener("keydown", event => {
  if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") { event.preventDefault(); toggleCommand(commandMenu.hidden); }
  if (event.key === "Escape" && !commandMenu.hidden) toggleCommand(false);
});

const initialView = location.hash.slice(1);
render(views[initialView] ? initialView : "overview");
