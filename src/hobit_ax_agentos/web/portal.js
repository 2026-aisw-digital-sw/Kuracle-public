const ui = {
  session: document.querySelector("#portalSession"),
  user: document.querySelector("#portalUser"),
  token: document.querySelector("#portalToken"),
  alerts: document.querySelector("#alertCards"),
  messages: document.querySelector("#portalMessages"),
  askForm: document.querySelector("#portalAskForm"),
  text: document.querySelector("#portalText"),
  asyncMode: document.querySelector("#portalAsync"),
  prepared: document.querySelector("#preparedAnswers"),
  suggestions: document.querySelector("#suggestedQuestions"),
  watchForm: document.querySelector("#watchForm"),
  watchIssue: document.querySelector("#watchIssue"),
  watchDeadline: document.querySelector("#watchDeadline"),
  watches: document.querySelector("#watchList"),
};

const REQUIRED_PROFILE_FIELDS = {
  student: [
    ["scope", "과정"],
    ["status", "재학 상태"],
    ["grade", "학년"],
    ["gpa", "GPA"],
    ["credits_earned", "취득 학점"],
    ["major", "전공"],
  ],
  staff: [
    ["department", "부서"],
    ["role", "역할"],
  ],
  faculty: [
    ["department", "학과"],
    ["rank", "직급"],
  ],
  public: [],
};

function sessionId() {
  return ui.session.value.trim() || "web-session";
}

function userId() {
  return ui.user.value.trim() || "web-user";
}

function requestHeaders() {
  const token = ui.token.value.trim();
  return {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { ...requestHeaders(), ...(options.headers || {}) },
  });
  const text = await response.text();
  const data = text ? JSON.parse(text) : null;
  if (!response.ok) {
    const detail = data && data.detail ? data.detail : response.statusText;
    throw new Error(`${response.status} ${detail}`);
  }
  return data;
}

async function optionalApi(path, options = {}) {
  try {
    return await api(path, options);
  } catch {
    return null;
  }
}

function message(role, text, meta = "") {
  const node = document.createElement("article");
  node.className = `message ${role}`;
  node.textContent = text;
  if (meta) {
    const small = document.createElement("div");
    small.className = "meta";
    small.textContent = meta;
    node.appendChild(small);
  }
  ui.messages.appendChild(node);
  ui.messages.scrollTop = ui.messages.scrollHeight;
}

function empty(target, text) {
  target.replaceChildren();
  const node = document.createElement("div");
  node.className = "empty";
  node.textContent = text;
  target.appendChild(node);
}

function card(target, title, body, meta = "", className = "") {
  const node = document.createElement("article");
  node.className = `card ${className}`.trim();
  const strong = document.createElement("strong");
  const text = document.createElement("div");
  strong.textContent = title;
  text.textContent = body;
  node.append(strong, text);
  if (meta) {
    const small = document.createElement("div");
    small.className = "meta";
    small.textContent = meta;
    node.appendChild(small);
  }
  target.appendChild(node);
  return node;
}

function isFilled(value) {
  return value !== null && value !== undefined && value !== "";
}

function missingProfileFields(profileRecord) {
  if (!profileRecord) {
    return REQUIRED_PROFILE_FIELDS.student.map(([, label]) => label);
  }
  const fields = REQUIRED_PROFILE_FIELDS[profileRecord.profile_type] || [];
  return fields
    .filter(([key]) => !isFilled((profileRecord.profile || {})[key]))
    .map(([, label]) => label);
}

function profileCompleteness(profileRecord) {
  if (!profileRecord) return 0;
  const fields = REQUIRED_PROFILE_FIELDS[profileRecord.profile_type] || [];
  if (!fields.length) return 1;
  const filled = fields.filter(([key]) => isFilled((profileRecord.profile || {})[key])).length;
  return filled / fields.length;
}

function daysLeft(deadline) {
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const date = new Date(deadline);
  const day = new Date(date.getFullYear(), date.getMonth(), date.getDate());
  return Math.ceil((day.getTime() - today.getTime()) / 86400000);
}

function formatDate(date) {
  return new Intl.DateTimeFormat("ko-KR", {
    month: "short",
    day: "numeric",
    weekday: "short",
  }).format(new Date(date));
}

function summarize(text, max = 150) {
  const compact = String(text || "").replace(/\s+/g, " ").trim();
  return compact.length > max ? `${compact.slice(0, max)}...` : compact;
}

function actionBadge(kind) {
  if (kind === "now") return "지금 처리";
  if (kind === "soon") return "곧 처리";
  if (kind === "ready") return "준비됨";
  return "확인";
}

function buildActionItems({ profile, watches, outbox, escalations }) {
  const items = [];
  const missing = missingProfileFields(profile);

  if (profileCompleteness(profile) < 1) {
    items.push({
      priority: 0,
      kind: "now",
      title: "학생 정보 보완 필요",
      body: `개인 상황을 알아야 복수전공, 휴학, 졸업 같은 행정 판단을 정확히 할 수 있습니다. 부족한 항목: ${missing.join(", ")}`,
      meta: "프로필 기반 추천",
      actionText: "프로필 정보를 알려주기",
      query: `내 행정 상담 프로필을 보완하려고 합니다. 필요한 항목은 ${missing.join(", ")}입니다. 어떤 정보를 준비하면 되는지 알려줘.`,
    });
  }

  const activeWatches = watches.filter((watch) => watch.status === "ACTIVE");
  for (const watch of activeWatches) {
    const left = daysLeft(watch.deadline);
    if (left < 0) continue;
    if (left <= watch.reminder_window_days) {
      items.push({
        priority: left <= 1 ? 0 : 1,
        kind: left <= 1 ? "now" : "soon",
        title: `${watch.issue_type} 행정 처리 확인`,
        body:
          left === 0
            ? "마감일이 오늘입니다. 제출 서류, 신청 경로, 예외 조건을 바로 확인해야 합니다."
            : `마감까지 ${left}일 남았습니다. 지금 준비해야 할 서류와 신청 절차를 확인하세요.`,
        meta: `${formatDate(watch.deadline)} 마감`,
        actionText: "처리 체크리스트 생성",
        query: `${watch.issue_type} 마감이 ${left}일 남았습니다. 지금 처리해야 할 행정 절차, 자격 요건, 제출 서류를 체크리스트로 알려줘.`,
      });
    } else if (left <= 30) {
      items.push({
        priority: 3,
        kind: "info",
        title: `${watch.issue_type} 일정 사전 점검`,
        body: `마감까지 ${left}일 남았습니다. 조건 확인과 서류 준비를 시작하기 좋습니다.`,
        meta: `${formatDate(watch.deadline)} 마감`,
        actionText: "준비 항목 확인",
        query: `${watch.issue_type} 마감이 ${left}일 남았습니다. 사전에 확인해야 할 행정 조건과 준비물을 알려줘.`,
      });
    }
  }

  for (const delivery of outbox.filter((item) => item.status === "PENDING").slice(0, 5)) {
    items.push({
      priority: 2,
      kind: "ready",
      title: "준비된 행정 안내 확인",
      body: summarize(delivery.text),
      meta: [delivery.channel, delivery.updated_at].filter(Boolean).join(" · "),
      actionText: "대화창에서 열기",
      onClick: () => message("agent", delivery.text, "prepared answer"),
    });
  }

  for (const escalation of escalations.filter((item) => item.status !== "RESOLVED").slice(0, 3)) {
    items.push({
      priority: 3,
      kind: "info",
      title: "담당자 확인 진행 중",
      body: escalation.reason || "규정 해석 또는 사용자 상황 확인이 필요해 담당자 검토로 전환되었습니다.",
      meta: escalation.status,
    });
  }

  if (!activeWatches.length) {
    items.push({
      priority: 4,
      kind: "info",
      title: "관심 행정 일정 등록",
      body: "복수전공, 휴학, 수강신청, 졸업, 장학금처럼 놓치면 손해가 큰 행정 업무를 등록하면 마감 전에 먼저 알려드립니다.",
      meta: "오른쪽 등록 영역 사용",
    });
  }

  return items.sort((a, b) => a.priority - b.priority);
}

async function loadPortal() {
  await Promise.all([
    loadActionInbox(),
    loadPreparedAnswers(),
    loadSuggestions(),
    loadWatches(),
  ]);
}

async function loadActionInbox() {
  ui.alerts.replaceChildren();
  empty(ui.alerts, "행정 처리 항목을 확인하는 중입니다.");
  const [profile, watches, outbox, escalations] = await Promise.all([
    optionalApi(`/profiles/${encodeURIComponent(userId())}`),
    optionalApi(`/sessions/${encodeURIComponent(sessionId())}/deadline-watches`),
    optionalApi(`/sessions/${encodeURIComponent(sessionId())}/outbox?limit=20`),
    optionalApi("/escalations"),
  ]);

  const session = sessionId();
  const user = userId();
  const items = buildActionItems({
    profile,
    watches: Array.isArray(watches) ? watches : [],
    outbox: Array.isArray(outbox) ? outbox : [],
    escalations: Array.isArray(escalations)
      ? escalations.filter((item) => item.session_id === session || item.user_id === user)
      : [],
  });

  ui.alerts.replaceChildren();
  if (!items.length) {
    empty(ui.alerts, "지금 당장 처리해야 할 행정 업무가 없습니다.");
    return;
  }

  for (const item of items) {
    const node = card(ui.alerts, item.title, item.body, item.meta, `alert action-${item.kind}`);
    const badge = document.createElement("span");
    badge.className = `badge ${item.kind}`;
    badge.textContent = actionBadge(item.kind);
    node.prepend(badge);

    if (item.query || item.onClick) {
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = item.actionText || "확인";
      button.addEventListener("click", () => {
        if (item.onClick) {
          item.onClick();
        } else {
          ask(item.query);
        }
      });
      node.appendChild(button);
    }
  }
}

async function loadPreparedAnswers() {
  try {
    const deliveries = await api(`/sessions/${encodeURIComponent(sessionId())}/outbox?limit=20`);
    ui.prepared.replaceChildren();
    if (!deliveries.length) {
      empty(ui.prepared, "아직 준비된 답변이 없습니다.");
      return;
    }
    for (const delivery of deliveries.slice().reverse()) {
      const item = document.createElement("article");
      item.className = "item";
      const title = document.createElement("strong");
      const body = document.createElement("div");
      const meta = document.createElement("div");
      title.textContent = delivery.status;
      body.textContent = delivery.text;
      meta.className = "meta";
      meta.textContent = [delivery.channel, delivery.run_id, delivery.updated_at]
        .filter(Boolean)
        .join(" · ");
      item.append(title, body, meta);
      item.addEventListener("click", () => message("agent", delivery.text, "prepared answer"));
      ui.prepared.appendChild(item);
    }
  } catch (error) {
    empty(ui.prepared, error.message);
  }
}

async function loadSuggestions() {
  try {
    const persona = await api(`/sessions/${encodeURIComponent(sessionId())}/persona`);
    ui.suggestions.replaceChildren();
    const questions = persona && persona.predicted_questions ? persona.predicted_questions : [];
    if (!questions.length) {
      empty(ui.suggestions, "질문을 한 번 보내면 예상 질문을 만들어둡니다.");
      return;
    }
    for (const question of questions) {
      const chip = document.createElement("button");
      chip.type = "button";
      chip.className = "chip";
      chip.textContent = question;
      chip.addEventListener("click", () => {
        ui.text.value = question;
        ui.text.focus();
      });
      ui.suggestions.appendChild(chip);
    }
  } catch (error) {
    empty(ui.suggestions, error.message);
  }
}

async function loadWatches() {
  try {
    const watches = await api(`/sessions/${encodeURIComponent(sessionId())}/deadline-watches`);
    ui.watches.replaceChildren();
    if (!watches.length) {
      empty(ui.watches, "등록된 관심 일정이 없습니다.");
      return;
    }
    for (const watch of watches.slice().reverse()) {
      const item = document.createElement("article");
      item.className = "item";
      const title = document.createElement("strong");
      const meta = document.createElement("div");
      title.textContent = watch.issue_type;
      meta.className = "meta";
      meta.textContent = `${watch.deadline} · ${watch.status}`;
      item.append(title, meta);
      ui.watches.appendChild(item);
    }
  } catch (error) {
    empty(ui.watches, error.message);
  }
}

async function ask(text) {
  const query = (text || ui.text.value).trim();
  if (!query) return;
  ui.text.value = "";
  message("user", query);
  try {
    if (ui.asyncMode.checked) {
      const submitted = await api("/gateway/web/submit", {
        method: "POST",
        body: JSON.stringify({
          message: query,
          member_id: userId(),
          session_id: sessionId(),
          timeout_seconds: 120,
        }),
      });
      message("agent", "답변을 준비하고 있습니다.", submitted.job.job_id);
      const job = await pollJob(submitted.job.job_id);
      showResult(job.result);
    } else {
      const data = await api("/gateway/web/query", {
        method: "POST",
        body: JSON.stringify({
          message: query,
          member_id: userId(),
          session_id: sessionId(),
          timeout_seconds: 120,
        }),
      });
      showResult(data.result);
    }
    await loadPortal();
  } catch (error) {
    message("error", error.message);
  }
}

async function pollJob(jobId) {
  for (let i = 0; i < 100; i += 1) {
    const job = await api(`/jobs/${jobId}`);
    if (job.status === "COMPLETED") return job;
    if (job.status === "FAILED" || job.status === "CANCELLED") {
      throw new Error(`${job.status}: ${job.error || "job stopped"}`);
    }
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
  throw new Error(`Timed out waiting for ${jobId}`);
}

function showResult(result) {
  const final = result && result.final ? result.final : {};
  message("agent", final.response || "답변을 만들지 못했습니다.", result ? result.run_id : "");
}

async function registerWatch(event) {
  event.preventDefault();
  const issue = ui.watchIssue.value.trim();
  const deadline = ui.watchDeadline.value;
  if (!issue || !deadline) {
    message("error", "관심 일정 등록에는 업무명과 마감일이 필요합니다.");
    return;
  }
  try {
    await api("/triggers/deadline-watches", {
      method: "POST",
      body: JSON.stringify({
        user_id: userId(),
        session_id: sessionId(),
        issue_type: issue,
        deadline,
        reminder_window_days: 7,
        source: "portal",
      }),
    });
    ui.watchDeadline.value = "";
    await loadPortal();
  } catch (error) {
    message("error", error.message);
  }
}

document.querySelector("#identityForm").addEventListener("submit", (event) => {
  event.preventDefault();
  loadPortal();
});
document.querySelector("#refreshAlerts").addEventListener("click", loadActionInbox);
document.querySelector("#refreshPrepared").addEventListener("click", loadPreparedAnswers);
ui.askForm.addEventListener("submit", (event) => {
  event.preventDefault();
  ask();
});
ui.watchForm.addEventListener("submit", registerWatch);

message("agent", "안녕하세요. 학사 규정 질문과 선제적 행정 처리 알림을 도와드릴게요.");
loadPortal();
