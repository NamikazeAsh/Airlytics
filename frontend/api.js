async function getJson(path) {
  const response = await fetch(path);
  if (!response.ok) {
    throw new Error(`${path} failed with ${response.status}`);
  }
  return response.json();
}

async function postJson(path, body) {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const detail = await response.json().catch(() => ({}));
    throw new Error(detail.detail ?? `${path} failed with ${response.status}`);
  }
  return response.json();
}

export const api = {
  authStatus: () => getJson("/api/auth/status"),
  syncStatus: () => getJson("/api/sync/status"),
  dailyMetric: (metric, start, end) => getJson(`/api/metrics/daily?metric=${metric}&start=${start}&end=${end}`),
  readiness: (start, end) => getJson(`/api/metrics/readiness?start=${start}&end=${end}`),
  trend: (metric, start, end) => getJson(`/api/analytics/trend?metric=${metric}&start=${start}&end=${end}`),
  anomalies: (start, end) => getJson(`/api/analytics/anomalies?start=${start}&end=${end}`),
  insights: (days = 7) => getJson(`/api/coach/insights?days=${days}`),
  generateInsights: () => postJson("/api/coach/insights/generate", {}),
  chat: (conversationId, message) => postJson("/api/coach/chat", { conversation_id: conversationId, message }),
};

export const loginUrl = "/api/auth/google/login";
