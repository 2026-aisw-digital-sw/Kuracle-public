const state = {
  lastRunId: "",
};

const els = {
  sessionId: document.querySelector("#sessionId"),
  userId: document.querySelector("#userId"),
  apiToken: document.querySelector("#apiToken"),
  statusList: document.querySelector("#statusList"),
  messages: document.querySelector("#messages"),
  askForm: document.querySelector("#askForm"),
  messageText: document.querySelector("#messageText"),
  asyncMode: document.querySelector("#asyncMode"),
  timeline: document.querySelector("#timeline"),
  runs: document.querySelector("#runs"),
  traceRunId: document.querySelector("#traceRunId"),
  traceOutput: document.querySelector("#traceOutput"),
};

function headers(extra = {}) {
  const token = els.apiToken.value.trim();
  return {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...extra,
  };
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: headers(options.headers || {}),
  });
  const text = await response.text();
  const data = text ? JSON.parse(text) : null;
  if (!response.ok) {
    const detail = data && data.detail ? data.detail : response.statusText;
    throw new Error(`${response.status} ${detail}`);
  }
  return data;
}

function addMessage(role, text, meta = "") {
  const item = document.createElement("article");
  item.className = `message ${role}`;
  const body = document.createElement("div");
  body.textContent = text;
  item.appendChild(body);
  if (meta) {
    const small = document.createElement("div");
    small.className = "meta";
    small.textContent = meta;
    item.appendChild(small);
  }
  els.messages.appendChild(item);
  els.messages.scrollTop = els.messages.scrollHeight;
}

function renderStatus(items) {
  els.statusList.replaceChildren();
  for (const [key, value] of Object.entries(items)) {
    const dt = document.createElement("dt");
    const dd = document.createElement("dd");
    dt.textContent = key;
    dd.textContent = String(value);
    if (String(value).toLowerCase().includes("ok")) dd.className = "status-ok";
    if (String(value).toLowerCase().includes("degraded")) dd.className = "status-warn";
    if (String(value).toLowerCase().includes("error")) dd.className = "status-error";
    els.statusList.append(dt, dd);
  }
}

async function submitQuestion(event) {
  event.preventDefault();
  const text = els.messageText.value.trim();
  if (!text) return;
  els.messageText.value = "";
  addMessage("user", text);
  try {
    if (els.asyncMode.checked) {
      const submitted = await api("/gateway/web/submit", {
        method: "POST",
        body: JSON.stringify({
          message: text,
          member_id: els.userId.value.trim() || "web-user",
          session_id: els.sessionId.value.trim() || "web-session",
          timeout_seconds: 120,
        }),
      });
      addMessage("system", `Job queued: ${submitted.job.job_id}`);
      await pollJob(submitted.job.job_id);
    } else {
      const data = await api("/gateway/web/query", {
        method: "POST",
        body: JSON.stringify({
          message: text,
          member_id: els.userId.value.trim() || "web-user",
          session_id: els.sessionId.value.trim() || "web-session",
          timeout_seconds: 120,
        }),
      });
      showResult(data.result);
    }
    await refreshSession();
  } catch (error) {
    addMessage("error", error.message);
  }
}

async function pollJob(jobId) {
  for (let attempt = 0; attempt < 90; attempt += 1) {
    const job = await api(`/jobs/${jobId}`);
    if (job.status === "COMPLETED") {
      showResult(job.result);
      return;
    }
    if (job.status === "FAILED" || job.status === "CANCELLED") {
      throw new Error(`${job.status}: ${job.error || "job did not complete"}`);
    }
    await sleep(1000);
  }
  throw new Error(`Timed out waiting for ${jobId}`);
}

function showResult(result) {
  if (!result) {
    addMessage("system", "No result payload was returned.");
    return;
  }
  const final = result.final || {};
  const response = final.response || "No answer was generated.";
  const meta = [result.run_id, result.trace_id].filter(Boolean).join(" | ");
  state.lastRunId = result.run_id || "";
  if (state.lastRunId) els.traceRunId.value = state.lastRunId;
  addMessage("assistant", response, meta);
}

async function refreshSession() {
  const sessionId = els.sessionId.value.trim() || "web-session";
  const [summary, timeline] = await Promise.all([
    api(`/sessions/${encodeURIComponent(sessionId)}/summary`),
    api(`/sessions/${encodeURIComponent(sessionId)}/timeline?limit=40`),
  ]);
  renderStatus({
    turns: summary.counts.turns,
    jobs: summary.counts.async_jobs,
    runs: summary.counts.runs,
    escalations: summary.counts.escalations,
    outbox: summary.counts.outbox,
  });
  renderTimeline(timeline);
  renderRuns(summary.recent.runs || []);
}

function renderTimeline(timeline) {
  renderEvents(
    els.timeline,
    timeline.events || [],
    (event) => event.event_type,
    (event) => event.occurred_at,
  );
}

function renderRuns(runs) {
  renderEvents(
    els.runs,
    runs,
    (run) => `${run.run_id} · ${run.state}`,
    (run) => run.updated_at,
    (run) => {
      const events = run.run_summary && run.run_summary.lifecycle_events;
      return events ? `${events.length} lifecycle events` : "No lifecycle events";
    },
  );
}

function renderEvents(target, items, titleFn, timeFn, detailFn = null) {
  target.replaceChildren();
  if (!items.length) {
    const empty = document.createElement("div");
    empty.className = "empty";
    empty.textContent = "No records.";
    target.appendChild(empty);
    return;
  }
  for (const item of items.slice().reverse()) {
    const row = document.createElement("div");
    row.className = "event";
    const strong = document.createElement("strong");
    const meta = document.createElement("div");
    strong.textContent = titleFn(item);
    meta.className = "meta";
    meta.textContent = detailFn ? `${timeFn(item)} · ${detailFn(item)}` : timeFn(item);
    row.append(strong, meta);
    target.appendChild(row);
  }
}

async function loadTrace() {
  const runId = els.traceRunId.value.trim() || state.lastRunId;
  if (!runId) {
    els.traceOutput.textContent = "";
    addMessage("system", "No run_id selected.");
    return;
  }
  try {
    const trace = await api(`/runs/${encodeURIComponent(runId)}/trace`);
    els.traceOutput.replaceChildren(renderTrace(trace));
  } catch (error) {
    els.traceOutput.replaceChildren(errorBlock(error.message));
  }
}

function renderTrace(trace) {
  const wrap = document.createElement("div");
  const events = document.createElement("section");
  events.className = "panel";
  const head = document.createElement("div");
  head.className = "panel-head";
  const title = document.createElement("h2");
  title.textContent = "Lifecycle";
  head.appendChild(title);
  const list = document.createElement("div");
  list.className = "event-list";
  renderEvents(
    list,
    trace.lifecycle_events || [],
    (event) => event.event,
    (event) => event.at || "",
    (event) => [event.node_id, event.agent_id, event.state].filter(Boolean).join(" · "),
  );
  events.append(head, list);
  const pre = document.createElement("pre");
  pre.textContent = JSON.stringify(trace, null, 2);
  wrap.append(events, pre);
  return wrap;
}

function errorBlock(message) {
  const item = document.createElement("article");
  item.className = "message error";
  item.textContent = message;
  return item;
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

document.querySelectorAll("[data-view]").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll("[data-view]").forEach((item) => item.classList.remove("active"));
    document.querySelectorAll(".view").forEach((item) => item.classList.remove("active"));
    button.classList.add("active");
    document.querySelector(`#${button.dataset.view}View`).classList.add("active");
  });
});

els.askForm.addEventListener("submit", submitQuestion);
document.querySelector("#refreshSession").addEventListener("click", () => {
  refreshSession().catch((error) => addMessage("error", error.message));
});
document.querySelector("#runDoctor").addEventListener("click", async () => {
  try {
    const doctor = await api("/doctor");
    const checks = Object.fromEntries(
      (doctor.checks || []).map((check) => [
        check.name,
        check.ok ? "ok" : check.message || "error",
      ]),
    );
    renderStatus({
      status: doctor.status || "unknown",
      kernel: checks.kernel_health || "unknown",
      storage: checks.data_dir_writable || "unknown",
      imports: checks["regulation_rag.workers.supervisor"] || "unknown",
    });
  } catch (error) {
    renderStatus({ status: error.message });
  }
});
document.querySelector("#loadTimeline").addEventListener("click", () => {
  refreshSession().catch((error) => addMessage("error", error.message));
});
document.querySelector("#loadRuns").addEventListener("click", () => {
  refreshSession().catch((error) => addMessage("error", error.message));
});
document.querySelector("#loadTrace").addEventListener("click", loadTrace);

addMessage("system", "AgentOS UI ready. Send a regulation question to start.");
refreshSession().catch(() => renderStatus({ status: "ready" }));
