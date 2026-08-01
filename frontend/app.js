import { api, loginUrl } from "./api.js";
import { renderLineChart } from "./charts.js";

const RANGES = [
  { label: "7d", days: 7 },
  { label: "30d", days: 30 },
  { label: "90d", days: 90 },
];

const METRICS = [
  { title: "Steps", metric: "steps_total" },
  { title: "Resting heart rate", metric: "resting_heart_rate", unit: "bpm" },
  { title: "HRV (RMSSD)", metric: "hrv_rmssd_avg", unit: "ms" },
  { title: "Sleep duration", metric: "sleep_duration_minutes", unit: "min" },
  { title: "Sleep efficiency", metric: "sleep_efficiency", unit: "%" },
  { title: "SpO2", metric: "spo2_avg", unit: "%" },
  { title: "Calories", metric: "calories_total", unit: "kcal" },
  { title: "Readiness", metric: "readiness_score" },
  { title: "Active minutes", metric: "active_minutes", unit: "min" },
];

const TREND_LABEL = { increasing: "up", decreasing: "down", stable: "stable" };

let rangeDays = 30;

function setupThemeToggle() {
  const root = document.documentElement;
  const stored = localStorage.getItem("airlytics_theme");
  if (stored) root.dataset.theme = stored;

  document.getElementById("theme-toggle").addEventListener("click", () => {
    const next = root.dataset.theme === "dark" ? "light" : "dark";
    root.dataset.theme = next;
    localStorage.setItem("airlytics_theme", next);
  });
}

function isoDate(d) {
  return d.toISOString().slice(0, 10);
}

function currentRange() {
  const end = new Date();
  const start = new Date();
  start.setDate(end.getDate() - rangeDays);
  return { start: isoDate(start), end: isoDate(end) };
}

async function renderStatusPill() {
  const pill = document.getElementById("status-pill");
  const dot = pill.querySelector(".status-dot");
  const label = pill.querySelector(".status-label");
  try {
    const [auth, syncStates] = await Promise.all([api.authStatus(), api.syncStatus()]);
    if (!auth.connected) {
      dot.className = "status-dot error";
      label.textContent = "Not connected";
      return;
    }
    const dailySync = syncStates.find((s) => s.metric_type === "daily_summary");
    if (dailySync?.status === "error") {
      dot.className = "status-dot error";
      label.textContent = `Sync error: ${dailySync.last_error ?? "unknown"}`;
    } else if (dailySync?.last_synced_at) {
      dot.className = "status-dot";
      label.textContent = `Synced ${new Date(dailySync.last_synced_at).toLocaleString()}`;
    } else {
      dot.className = "status-dot";
      label.textContent = "Awaiting first sync";
    }
  } catch {
    dot.className = "status-dot error";
    label.textContent = "Status unavailable";
  }
}

function fillDateRange(points, start, end) {
  const byDate = new Map(points.map((p) => [p.date, p.value]));
  const result = [];
  const cursor = new Date(`${start}T00:00:00`);
  const endDate = new Date(`${end}T00:00:00`);
  while (cursor <= endDate) {
    const iso = cursor.toISOString().slice(0, 10);
    result.push({ date: iso, value: byDate.has(iso) ? byDate.get(iso) : null });
    cursor.setDate(cursor.getDate() + 1);
  }
  return result;
}

function trendBadgeHtml(trend) {
  if (!trend || trend.direction === "insufficient_data") return "";
  const pct = trend.percent_change;
  const pctLabel = pct !== null ? ` ${pct > 0 ? "+" : ""}${pct}%` : "";
  return `<span class="trend-badge trend-${trend.direction}">${TREND_LABEL[trend.direction]}${pctLabel}</span>`;
}

function average(values) {
  if (values.length === 0) return null;
  const sum = values.reduce((a, b) => a + b, 0);
  return Math.round((sum / values.length) * 10) / 10;
}

async function renderMetricCard(card, def, start, end, rangeLabel) {
  const [rawPoints, trend] = await Promise.all([
    api.dailyMetric(def.metric, start, end).catch(() => []),
    api.trend(def.metric, start, end).catch(() => null),
  ]);
  const points = fillDateRange(rawPoints, start, end);
  const nonNullValues = points.map((p) => p.value).filter((v) => v !== null);

  const avg = average(nonNullValues);
  const valueHtml = avg !== null ? `${avg}${def.unit ? `<span class="metric-card-unit">${def.unit}</span>` : ""}` : "—";

  const latest = [...points].reverse().find((p) => p.value !== null);
  const latestHtml = latest ? `latest ${latest.value} (${latest.date})` : "no recent data";

  card.innerHTML = `
    <div class="metric-card-header">
      <span class="metric-card-title">${def.title}</span>
      ${trendBadgeHtml(trend)}
    </div>
    <div class="metric-card-value">${valueHtml}</div>
    <div class="metric-card-sub">avg over ${rangeLabel} &middot; ${latestHtml}</div>
    <div class="metric-card-chart"></div>
  `;
  renderLineChart(card.querySelector(".metric-card-chart"), points);
}

function severityClass(zScore) {
  return Math.abs(zScore) >= 3 ? "high" : "moderate";
}

async function renderAnomalies(start, end) {
  const container = document.getElementById("anomalies-container");
  try {
    const anomalies = await api.anomalies(start, end);
    if (anomalies.length === 0) {
      container.innerHTML = '<div class="empty-state">No anomalies detected in this range.</div>';
      return;
    }
    container.innerHTML = `<div class="anomaly-list">${anomalies
      .slice()
      .reverse()
      .map(
        (a) => `
        <div class="anomaly-row">
          <span class="anomaly-icon ${severityClass(a.z_score)}"></span>
          <span class="anomaly-date">${a.date}</span>
          <span>${a.metric.replace(/_/g, " ")} was ${a.value} (baseline ${a.baseline_mean} &plusmn; ${a.baseline_stddev})</span>
        </div>`,
      )
      .join("")}</div>`;
  } catch {
    container.innerHTML = '<div class="empty-state">Could not load anomalies.</div>';
  }
}

async function renderDashboard() {
  const { start, end } = currentRange();
  const rangeLabel = RANGES.find((r) => r.days === rangeDays)?.label ?? `${rangeDays}d`;
  const grid = document.getElementById("metric-grid");
  grid.innerHTML = "";
  METRICS.forEach((def) => {
    const card = document.createElement("div");
    card.className = "metric-card";
    grid.appendChild(card);
    renderMetricCard(card, def, start, end, rangeLabel);
  });
  renderAnomalies(start, end);
}

function setupRangeTabs() {
  const container = document.getElementById("range-tabs");
  container.innerHTML = RANGES.map(
    (r) => `<button class="range-tab ${r.days === rangeDays ? "active" : ""}" data-days="${r.days}">${r.label}</button>`,
  ).join("");
  container.querySelectorAll(".range-tab").forEach((btn) => {
    btn.addEventListener("click", () => {
      rangeDays = Number(btn.dataset.days);
      container.querySelectorAll(".range-tab").forEach((b) => b.classList.toggle("active", b === btn));
      renderDashboard();
    });
  });
}

async function renderInsights() {
  const container = document.getElementById("insights-container");
  container.innerHTML = '<div class="empty-state">Loading insights…</div>';
  try {
    const insights = await api.insights(7);
    if (insights.length === 0) {
      container.innerHTML = `
        <div class="empty-state">
          No insights yet.
          <button class="btn" id="generate-insights-btn">Generate insights</button>
        </div>`;
      document.getElementById("generate-insights-btn").addEventListener("click", async (e) => {
        e.target.textContent = "Generating…";
        e.target.disabled = true;
        try {
          await api.generateInsights();
          renderInsights();
        } catch {
          container.innerHTML = '<div class="empty-state">Could not generate insights right now.</div>';
        }
      });
      return;
    }
    container.innerHTML = `<div class="insight-list">${insights
      .map(
        (i) => `
        <div class="insight-card">
          <span class="insight-card-category">${i.category}</span>
          <span class="insight-card-body">${i.body}</span>
        </div>`,
      )
      .join("")}</div>`;
  } catch {
    container.innerHTML = '<div class="empty-state">Could not load insights.</div>';
  }
}

const MODEL_LABELS = { ridge: "Ridge", elastic_net: "Elastic Net", gradient_boosting: "Gradient Boosting" };

function modelLabel(name) {
  return MODEL_LABELS[name] ?? name;
}

function featureLabel(featureColumn) {
  const metricKey = featureColumn.replace(/_lag1$/, "");
  return METRICS.find((m) => m.metric === metricKey)?.title ?? metricKey.replace(/_/g, " ");
}

async function renderForecast() {
  const container = document.getElementById("forecast-container");
  container.innerHTML = '<div class="empty-state">Loading forecast…</div>';
  try {
    const status = await api.forecastStatus();
    if (status === null) {
      container.innerHTML = `
        <div class="empty-state">
          No forecast model trained yet.
          <button class="btn" id="train-forecast-btn">Train model</button>
        </div>`;
      document.getElementById("train-forecast-btn").addEventListener("click", async (e) => {
        e.target.textContent = "Training…";
        e.target.disabled = true;
        try {
          await api.trainForecast();
          renderForecast();
        } catch {
          container.innerHTML = '<div class="empty-state">Could not train the model right now.</div>';
        }
      });
      return;
    }

    const prediction = await api.forecastPrediction().catch(() => null);
    const drivers = await api.forecastFeatureImportance().catch(() => null);

    const candidateRows = Object.entries(status.candidate_results ?? {})
      .filter(([name]) => name !== status.winning_model)
      .map(
        ([name, r]) =>
          `<div class="forecast-validation-row forecast-validation-row-muted"><span>${modelLabel(name)} MAE</span><span>${
            r.model_mae ?? "—"
          }</span></div>`,
      )
      .join("");

    const driverRows = drivers
      ? drivers.importances
          .map(
            (d) =>
              `<div class="forecast-validation-row"><span>${featureLabel(d.feature)}</span><span>${d.importance_pct}%</span></div>`,
          )
          .join("")
      : '<div class="empty-state">No driver breakdown available.</div>';

    container.innerHTML = `
      <div class="forecast-grid">
        <div class="metric-card">
          <div class="metric-card-header">
            <span class="metric-card-title">Predicted readiness</span>
          </div>
          <div class="metric-card-value">${prediction ? prediction.predicted_readiness : "—"}</div>
          <div class="metric-card-sub">${
            prediction
              ? `for ${prediction.predicted_date} &middot; last actual ${prediction.last_actual_readiness} (${prediction.last_actual_date})`
              : "no current prediction available"
          }</div>
        </div>
        <div class="forecast-validation-card">
          <div class="metric-card-title">Model validation (walk-forward)</div>
          <div class="forecast-validation-row"><span>Best model</span><span>${modelLabel(status.winning_model)}</span></div>
          <div class="forecast-validation-row"><span>Model MAE</span><span>${status.model_mae ?? "—"}</span></div>
          <div class="forecast-validation-row"><span>Naive baseline MAE</span><span>${status.baseline_mae ?? "—"}</span></div>
          <div class="forecast-validation-row"><span>Improvement vs baseline</span><span>${
            status.improvement_pct !== null ? `${status.improvement_pct}%` : "—"
          }</span></div>
          <div class="forecast-validation-row"><span>Samples / test folds</span><span>${status.n_samples} / ${status.n_test_folds}</span></div>
          ${candidateRows}
          <button class="btn" id="retrain-forecast-btn">Retrain</button>
        </div>
        <div class="forecast-validation-card">
          <div class="metric-card-title">Top drivers</div>
          ${driverRows}
        </div>
      </div>`;

    document.getElementById("retrain-forecast-btn").addEventListener("click", async (e) => {
      e.target.textContent = "Training…";
      e.target.disabled = true;
      try {
        await api.trainForecast();
        renderForecast();
      } catch {
        container.innerHTML = '<div class="empty-state">Could not retrain the model right now.</div>';
      }
    });
  } catch {
    container.innerHTML = '<div class="empty-state">Could not load forecast.</div>';
  }
}

let conversationId = localStorage.getItem("airlytics_conversation_id") ?? null;

function renderMarkdown(content) {
  return DOMPurify.sanitize(marked.parse(content));
}

function appendChatMessage(role, content) {
  const messages = document.getElementById("chat-messages");
  const bubble = document.createElement("div");
  bubble.className = `chat-bubble chat-bubble-${role}`;
  if (role === "assistant") {
    bubble.innerHTML = renderMarkdown(content);
  } else {
    bubble.textContent = content;
  }
  messages.appendChild(bubble);
  messages.scrollTop = messages.scrollHeight;
  return bubble;
}

function appendTypingIndicator() {
  const messages = document.getElementById("chat-messages");
  const bubble = document.createElement("div");
  bubble.className = "chat-bubble chat-bubble-assistant chat-typing";
  bubble.innerHTML =
    '<span class="typing-dot"></span><span class="typing-dot"></span><span class="typing-dot"></span>';
  messages.appendChild(bubble);
  messages.scrollTop = messages.scrollHeight;
  return bubble;
}

async function loadConversation() {
  if (!conversationId) return;
  try {
    const messages = await getConversationMessages(conversationId);
    messages.forEach((m) => appendChatMessage(m.role, m.content));
  } catch {
    conversationId = null;
    localStorage.removeItem("airlytics_conversation_id");
  }
}

async function getConversationMessages(id) {
  const response = await fetch(`/api/coach/conversations/${id}`);
  if (!response.ok) throw new Error("failed to load conversation");
  return response.json();
}

function setupChatToggle() {
  const fab = document.getElementById("chat-fab");
  const panel = document.getElementById("chat-panel");
  const closeBtn = document.getElementById("chat-close");

  fab.addEventListener("click", () => {
    panel.classList.toggle("hidden");
    if (!panel.classList.contains("hidden")) document.getElementById("chat-input").focus();
  });
  closeBtn.addEventListener("click", () => panel.classList.add("hidden"));
}

function setupChatResize() {
  const panel = document.getElementById("chat-panel");
  const handle = document.getElementById("chat-resize-handle");

  handle.addEventListener("pointerdown", (e) => {
    e.preventDefault();
    const startX = e.clientX;
    const startY = e.clientY;
    const startRect = panel.getBoundingClientRect();
    handle.setPointerCapture(e.pointerId);

    function onMove(moveEvent) {
      const deltaX = moveEvent.clientX - startX;
      const deltaY = moveEvent.clientY - startY;
      panel.style.width = `${startRect.width - deltaX}px`;
      panel.style.height = `${startRect.height - deltaY}px`;
    }

    function onUp() {
      handle.removeEventListener("pointermove", onMove);
      handle.removeEventListener("pointerup", onUp);
    }

    handle.addEventListener("pointermove", onMove);
    handle.addEventListener("pointerup", onUp);
  });
}

function setupChat() {
  setupChatToggle();
  setupChatResize();

  const form = document.getElementById("chat-form");
  const input = document.getElementById("chat-input");

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const message = input.value.trim();
    if (!message) return;
    input.value = "";
    appendChatMessage("user", message);
    const pending = appendTypingIndicator();

    try {
      const result = await api.chat(conversationId, message);
      conversationId = result.conversation_id;
      localStorage.setItem("airlytics_conversation_id", conversationId);
      pending.classList.remove("chat-typing");
      pending.innerHTML = renderMarkdown(result.reply);
    } catch (err) {
      pending.classList.remove("chat-typing");
      pending.textContent = err.message.includes("GROQ_API_KEY")
        ? "The AI coach isn't configured yet (missing Groq API key)."
        : "Something went wrong reaching the coach.";
    }
  });

  loadConversation();
}

async function init() {
  setupThemeToggle();

  const auth = await api.authStatus().catch(() => ({ connected: false }));

  if (!auth.connected) {
    document.getElementById("connect-view").classList.remove("hidden");
    document.getElementById("dashboard-view").classList.add("hidden");
    document.getElementById("login-link").href = loginUrl;
    return;
  }

  document.getElementById("connect-view").classList.add("hidden");
  document.getElementById("dashboard-view").classList.remove("hidden");

  renderStatusPill();
  setInterval(renderStatusPill, 60_000);
  setupRangeTabs();
  renderDashboard();
  renderInsights();
  renderForecast();
  setupChat();
}

init();
