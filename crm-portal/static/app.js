// Snapmint CRM Calendar - front end (vanilla JS, talks only to server.py)

const STATUS = {
  DRAFT: "Draft", QUEUED: "Queued", SUBMITTING: "Sending to vendor", PENDING: "In review at Meta",
  REJECTED: "Rejected", CATEGORY_CHANGED: "Category changed", PAUSED: "Paused", ERROR: "Error",
  WE_PUSHING: "Adding to WebEngage", WE_MANUAL: "Add in WebEngage", WE_ERROR: "WebEngage failed",
  IN_WEBENGAGE: "In WebEngage",
};
const STAGES = [
  { key: "draft", label: "Draft", states: ["DRAFT"], color: "#9ca3af", hint: "editable" },
  { key: "queued", label: "Queued", states: ["QUEUED"], color: "#2563eb", hint: "sent one by one" },
  { key: "vendor", label: "With vendor / Meta", states: ["SUBMITTING", "PENDING"], color: "#d97706", hint: "awaiting decision" },
  { key: "edit", label: "Needs edit", states: ["REJECTED", "CATEGORY_CHANGED", "PAUSED", "ERROR"], color: "#dc2626", hint: "edit & resubmit", alert: true },
  { key: "we", label: "WebEngage step", states: ["WE_PUSHING", "WE_MANUAL", "WE_ERROR"], color: "#7c3aed", hint: "add template" },
  { key: "done", label: "In WebEngage", states: ["IN_WEBENGAGE"], color: "#059669", hint: "ready for campaign" },
];
const ACTIVE = new Set(["QUEUED", "SUBMITTING", "PENDING", "WE_PUSHING"]);
const EDITABLE = new Set(["DRAFT", "REJECTED", "CATEGORY_CHANGED", "PAUSED", "ERROR"]);
const NEEDS_EDIT = new Set(["REJECTED", "CATEGORY_CHANGED", "PAUSED", "ERROR"]);
const PAGE = 50;
const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

const S = {
  cal: null, tpl: {}, settings: null, requirements: [], mode: "simulate",
  view: "calendar", f: { date: "", channel: "", q: "", exp: false, page: 0 },
  tf: { stage: "", q: "" }, drawer: null, dirty: false,
};

const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmtN = (n) => Number(n || 0).toLocaleString("en-IN");
const fmtShort = (n) => (n >= 1e7 ? (n / 1e7).toFixed(2) + " Cr" : n >= 1e5 ? (n / 1e5).toFixed(1) + " L" : fmtN(n));
const me = () => { try { return localStorage.getItem("crm_name") || ""; } catch { return ""; } };
const setMe = (v) => { try { localStorage.setItem("crm_name", v); } catch { /* private mode */ } };
const fmtTime = (iso) => { if (!iso) return ""; const d = new Date(iso); return d.toLocaleString("en-IN", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }); };

async function api(path, opts = {}) {
  const res = await fetch(path, { headers: { "Content-Type": "application/json" }, ...opts });
  let data = {};
  try { data = await res.json(); } catch { /* empty */ }
  if (!res.ok) { const e = new Error(data.error || `HTTP ${res.status}`); e.data = data; e.status = res.status; throw e; }
  return data;
}
const post = (path, body) => api(path, { method: "POST", body: JSON.stringify(body || {}) });

function toast(msg, kind = "") {
  const t = document.createElement("div");
  t.className = "toast " + kind;
  t.textContent = msg;
  $("#toasts").appendChild(t);
  setTimeout(() => t.remove(), 4200);
}

function chClass(ch) {
  const c = (ch || "").toLowerCase();
  if (c.startsWith("wa") || c.includes("whatsapp")) return "ch-wa";
  if (c.includes("push")) return "ch-push";
  if (c.includes("sms")) return "ch-sms";
  if (c.includes("rcs")) return "ch-rcs";
  if (c.includes("mail")) return "ch-email";
  return "ch-ivr";
}
const isWA = (r) => /^(wa|whatsapp)/i.test(r.channel || "");
const statusChip = (st, t) => `<span class="status st-${st}">${esc(st === "CATEGORY_CHANGED" && t ? `Approved as ${t.approved_category}` : STATUS[st] || st)}</span>`;
const dayNum = (d) => parseInt(String(d || "").split("-")[0], 10) || 0;
const timeMin = (t) => {
  const m = String(t || "").match(/(\d{1,2}):(\d{2})(?::\d{2})?\s*([AP]M)?/i);
  if (!m) return 0;
  return ((+m[1] % 12) + ((m[3] || "").toUpperCase() === "PM" ? 12 : 0)) * 60 + +m[2];
};
const shortTime = (t) => String(t || "").replace(/:00(\s*[AP]M)/i, "$1");

function brief(text) {
  const t = text || "";
  const tags = [...(t.match(/^(\s*\[[^\]]*\]\s*)*/)[0].matchAll(/\[([^\]]+)\]/g))].map((m) => m[1]);
  const copy = (t.match(/Copy:\s*'(.*?)'\s*(CTA:|$)/s) || t.match(/Copy:\s*(.*?)\s*(CTA:|$)/s) || [])[1] || "";
  const cta = (t.match(/CTA:\s*(.*?)\s*(\|\s*LP:|$)/s) || [])[1] || "";
  const lp = (t.match(/LP:\s*(\S+)/) || [])[1] || "";
  return { tags, copy: copy.replace(/\\'/g, "'"), cta, lp };
}

// ---------------------------------------------------------------- data
async function loadAll() {
  const [cal, st] = await Promise.all([api("/api/calendar"), api("/api/settings")]);
  setCalendar(cal);
  setSettings(st);
  render();
}
function setCalendar(cal) {
  cal.rows.forEach((r) => { r._b = brief(r.comments); });
  cal.rows.sort((a, b) => dayNum(a.date) - dayNum(b.date) || timeMin(a.time) - timeMin(b.time));
  S.cal = cal;
  S.tpl = Object.fromEntries(cal.templates.map((t) => [t.id, t]));
}
function setSettings(st) {
  S.settings = st.settings; S.requirements = st.requirements; S.mode = st.settings.mode;
}
function setTemplates(data) {
  Object.assign(S.cal, { locked: data.locked, locked_at: data.locked_at, locked_by: data.locked_by, templates: data.templates });
  S.tpl = Object.fromEntries(data.templates.map((t) => [t.id, t]));
}
const tplList = () => (S.cal?.templates || []).slice().sort((a, b) => (a.usage.first_send ? 0 : 1) - (b.usage.first_send ? 0 : 1)
  || dayNum(a.usage.dates[0]) - dayNum(b.usage.dates[0]) || timeMin(a.usage.first_send.split(" ").slice(1).join(" ")) - timeMin(b.usage.first_send.split(" ").slice(1).join(" ")));

// ---------------------------------------------------------------- shell
function render() {
  $$(".nav-item").forEach((b) => b.classList.toggle("active", b.dataset.view === S.view));
  $$(".view").forEach((v) => (v.hidden = v.id !== "view-" + S.view));
  if (!S.cal || !S.settings) return showLoadError();
  renderShell();
  renderPipeline();
  if (S.view === "calendar") renderCalendar();
  if (S.view === "templates") renderTemplates();
  if (S.view === "activity") renderActivity();
  if (S.view === "settings") renderSettings();
}

function renderShell() {
  const c = S.cal;
  const titles = { calendar: "Campaign calendar", templates: "WhatsApp templates", activity: "Activity", settings: "Settings & integrations" };
  $("#pageTitle").textContent = titles[S.view];
  const month = c.rows[0] ? c.rows[0].date.split("-")[1] : "";
  $("#pageSub").textContent = {
    calendar: `${c.name || "No calendar imported"} · ${month} ${c.year} · ${fmtN(c.rows.length)} campaigns`,
    templates: `${c.templates.length} unique templates generated from ${fmtN(c.rows.filter(isWA).length)} WhatsApp campaign rows`,
    activity: "Every vendor call, decision and WebEngage step, newest first",
    settings: "Vendor and WebEngage credentials are stored only on this machine (crm-portal/data, never committed)",
  }[S.view];
  $$(".nav-item").forEach((b) => b.classList.toggle("active", b.dataset.view === S.view));
  $$(".view").forEach((v) => (v.hidden = v.id !== "view-" + S.view));
  const pill = $("#lockPill");
  pill.className = "lock-pill" + (c.locked ? " locked" : "");
  pill.innerHTML = c.locked ? `🔒 Locked${c.locked_by ? " by " + esc(c.locked_by) : ""} · ${esc(fmtTime(c.locked_at))}` : "✎ Editing";
  const lb = $("#lockBtn");
  lb.className = "btn " + (c.locked ? "btn-ghost" : "btn-primary");
  lb.innerHTML = c.locked ? "Unlock calendar" : `<svg viewBox="0 0 24 24"><rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/></svg> Lock & send for approval`;
  $("#addRowBtn").disabled = !!c.locked;
  const chip = $("#modeChip");
  chip.className = "mode-chip" + (S.mode === "live" ? " live" : "");
  chip.textContent = S.mode === "live" ? "Live vendor APIs" : "Simulation mode";
  const ne = c.templates.filter((t) => NEEDS_EDIT.has(t.status)).length;
  $("#navNeedsEdit").hidden = !ne;
  $("#navNeedsEdit").textContent = ne;
}

function renderPipeline() {
  const el = $("#pipeline");
  el.hidden = !(S.view === "calendar" || S.view === "templates");
  const ts = S.cal.templates;
  el.innerHTML = STAGES.map((s) => {
    const n = ts.filter((t) => s.states.includes(t.status)).length;
    return `<button class="stage ${s.alert && n ? "alert" : ""}" data-stage="${s.key}">
      <div class="label"><span class="dot" style="background:${s.color}"></span>${s.label}</div>
      <div class="count">${n}</div><div class="hint">${s.hint}</div></button>`;
  }).join("");
  $$(".stage", el).forEach((b) => (b.onclick = () => { S.tf.stage = b.dataset.stage; go("templates"); }));
}

function go(view) { S.view = view; closeDrawer(); render(); }

function showLoadError() {
  $("#pipeline").hidden = true;
  $("#pageTitle").textContent = { calendar: "Campaign calendar", templates: "WhatsApp templates", activity: "Activity", settings: "Settings & integrations" }[S.view];
  $("#pageSub").textContent = "";
  const el = $("#view-" + S.view);
  let box = $("#loadError");
  if (!box) {
    box = document.createElement("div");
    box.id = "loadError";
    box.className = "callout error";
  }
  box.innerHTML = `<b>The portal could not load its data from the server.</b> ${esc(S.loadError || "")}<br>
    Check that <code>python3 crm-portal/server.py</code> is running in a terminal, then
    <button class="btn btn-sm" id="retryLoad" style="margin-left:6px">Retry</button>`;
  el.prepend(box);
  $("#retryLoad").onclick = boot;
}

async function boot() {
  try {
    await loadAll();
    $("#loadError")?.remove();
  } catch (e) {
    S.loadError = e.message;
    render();
  }
}

// ---------------------------------------------------------------- calendar
function filteredRows() {
  const { date, channel, q, exp } = S.f;
  const qq = q.trim().toLowerCase();
  return S.cal.rows.filter((r) => (!date || r.date === date) && (!channel || r.channel === channel) && (!exp || r.exp)
    && (!qq || (r.segment + " " + r.naming + " " + r.comments + " " + (S.tpl[r.template_id]?.template_name || "")).toLowerCase().includes(qq)));
}

function renderCalendar() {
  const rows = S.cal.rows;
  const wa = rows.filter(isWA);
  const chans = {};
  rows.forEach((r) => (chans[r.channel] = (chans[r.channel] || 0) + 1));
  const aud = rows.reduce((s, r) => s + (+r.size || 0), 0);
  const waAud = wa.reduce((s, r) => s + (+r.size || 0), 0);
  const ready = S.cal.templates.filter((t) => t.status === "IN_WEBENGAGE").length;
  $("#kpis").innerHTML = [
    ["Campaigns planned", fmtN(rows.length), `${new Set(rows.map((r) => r.date)).size} send days`],
    ["Total audience", fmtShort(aud), "sum of segment sizes"],
    ["WhatsApp campaigns", fmtN(wa.length), `${fmtShort(waAud)} audience`],
    ["Unique WA templates", S.cal.templates.length, "need Meta approval"],
    ["Ready in WebEngage", `${ready}/${S.cal.templates.length}`, S.cal.locked ? "calendar locked" : "lock to start approvals"],
  ].map(([k, v, s]) => `<div class="kpi"><div class="k">${k}</div><div class="v">${v}</div><div class="s">${s}</div></div>`).join("");

  const dates = [...new Set(rows.map((r) => r.date))].sort((a, b) => dayNum(a) - dayNum(b));
  const cnt = {};
  rows.forEach((r) => (cnt[r.date] = (cnt[r.date] || 0) + 1));
  const dayOf = {};
  rows.forEach((r) => (dayOf[r.date] = r.day));
  $("#dateStrip").innerHTML = `<button class="date-chip ${!S.f.date ? "active" : ""}" data-date=""><div class="w">All</div><div class="d">${dates.length}</div><div class="n">days</div></button>`
    + dates.map((d) => {
      const w = (dayOf[d] || "").slice(0, 3);
      return `<button class="date-chip ${S.f.date === d ? "active" : ""} ${/sat|sun/i.test(w) ? "weekend" : ""}" data-date="${esc(d)}">
        <div class="w">${esc(w)}</div><div class="d">${dayNum(d)}</div><div class="n">${cnt[d]}</div></button>`;
    }).join("");
  $$("#dateStrip .date-chip").forEach((b) => (b.onclick = () => { S.f.date = b.dataset.date; S.f.page = 0; renderCalendar(); }));

  $("#channelFilter").innerHTML = [["", "All", rows.length], ...Object.entries(chans).sort((a, b) => b[1] - a[1]).map(([k, v]) => [k, k, v])]
    .map(([k, l, n]) => `<button class="${S.f.channel === k ? "active" : ""}" data-ch="${esc(k)}">${esc(l)}<span class="c">${n}</span></button>`).join("");
  $$("#channelFilter button").forEach((b) => (b.onclick = () => { S.f.channel = b.dataset.ch; S.f.page = 0; renderCalendar(); }));

  const list = filteredRows();
  const pages = Math.max(1, Math.ceil(list.length / PAGE));
  S.f.page = Math.min(S.f.page, pages - 1);
  const slice = list.slice(S.f.page * PAGE, S.f.page * PAGE + PAGE);
  $("#calTable tbody").innerHTML = slice.length ? slice.map((r) => {
    const t = S.tpl[r.template_id];
    return `<tr data-id="${r.id}">
      <td class="nowrap"><b>${dayNum(r.date)} ${esc(r.date.split("-")[1] || "")}</b><div class="muted">${esc(r.day)}</div></td>
      <td class="nowrap">${esc(shortTime(r.time))}</td>
      <td><div class="seg-name">${esc(r.naming || r.segment)}</div>${r.exclude ? `<div class="excl">excl. ${esc(r.exclude)}</div>` : ""}</td>
      <td><span class="ch ${chClass(r.channel)}">${esc(r.channel)}</span></td>
      <td class="content-cell"><div class="content-copy">${esc(r._b.copy || r.comments)}</div>
        <div class="content-meta">${r.exp ? `<span class="tag exp">EXP</span>` : ""}${r._b.cta ? `<span class="tag cta">${esc(r._b.cta)}</span>` : ""}${r._b.tags.map((x) => `<span class="tag">${esc(x)}</span>`).join("")}</div></td>
      <td class="num">${fmtN(r.size)}</td>
      <td>${t ? `${statusChip(t.status, t)}<div class="muted" style="margin-top:4px;font-family:var(--mono)">${esc(t.template_name)}</div>` : `<span class="muted">—</span>`}</td>
    </tr>`;
  }).join("") : `<tr><td colspan="7" class="empty">No campaigns match these filters.</td></tr>`;
  $$("#calTable tbody tr[data-id]").forEach((tr) => (tr.onclick = () => openRow(tr.dataset.id)));
  $("#pager").innerHTML = `<div>Showing ${list.length ? S.f.page * PAGE + 1 : 0}–${Math.min(list.length, (S.f.page + 1) * PAGE)} of ${fmtN(list.length)}</div>
    <div class="btns"><button class="btn btn-sm" ${S.f.page === 0 ? "disabled" : ""} data-p="-1">← Prev</button>
    <span style="align-self:center">Page ${S.f.page + 1} / ${pages}</span>
    <button class="btn btn-sm" ${S.f.page >= pages - 1 ? "disabled" : ""} data-p="1">Next →</button></div>`;
  $$("#pager button").forEach((b) => (b.onclick = () => { S.f.page += +b.dataset.p; renderCalendar(); }));
}

const ROW_FIELDS = [
  ["date", "Date", "1-Nov"], ["time", "Time", "11:20:00 AM"], ["product", "Product"], ["channel", "Channel", "", ["Push", "WA Utility", "WA Marketing", "SMS", "RCS", "Email", "IVR"]],
  ["segment", "Segment name"], ["naming", "Naming structure"], ["exclude", "Segments to exclude"], ["size", "Size"],
  ["start_age", "Start age"], ["end_age", "End age"], ["gender", "Gender"], ["location", "Location"],
  ["campaign_type", "Campaign type"], ["exp", "EXP", "", ["", "EXP"]], ["comms_a", "Comms A"], ["comms_b", "Comms B"],
  ["banner_url", "Banner URL (WhatsApp header image)", "https://…"],
];

function openRow(id) {
  const r = id ? S.cal.rows.find((x) => x.id === id) : { id: "", date: S.f.date || "", channel: "WA Utility", product: "MKP", comments: "", size: "" };
  const locked = S.cal.locked;
  const t = S.tpl[r.template_id];
  S.drawer = { type: "row", id: r.id };
  openDrawer({
    kicker: `<span class="ch ${chClass(r.channel)}">${esc(r.channel || "New")}</span> ${esc(r.day || "")} ${esc(r.date || "")} ${esc(shortTime(r.time))}`,
    title: r.naming || r.segment || "New campaign",
    tabs: [],
    body: `${locked ? `<div class="callout info">🔒 The calendar is locked, so campaign rows are read-only. WhatsApp copy can still be fixed on the template when it needs edits.</div>` : ""}
      <div class="section"><div class="section-title">Campaign</div>
        <div class="grid3">${ROW_FIELDS.map(([k, l, ph, opts]) => `<div class="field"><label>${l}</label>${opts
          ? `<select data-k="${k}" ${locked ? "disabled" : ""}>${[...new Set([...opts, r[k] || ""])].map((o) => `<option ${o === (r[k] || "") ? "selected" : ""}>${esc(o)}</option>`).join("")}</select>`
          : `<input data-k="${k}" value="${esc(r[k])}" placeholder="${esc(ph || "")}" ${locked ? "disabled" : ""}>`}</div>`).join("")}
          <div class="field full"><label>Comments <span class="api">[Tag] Static Visual: … Copy: '…' CTA: … | LP: …</span></label>
          <textarea data-k="comments" rows="4" ${locked ? "disabled" : ""}>${esc(r.comments)}</textarea>
          <div class="help">For WhatsApp rows the template is built from Copy, CTA and LP. Rows with identical creative share one template.</div></div>
        </div></div>
      ${t ? `<div class="section"><div class="section-title">Linked WhatsApp template</div>
        <div class="source-box" style="display:flex;justify-content:space-between;align-items:center;gap:12px">
          <div><div style="font-family:var(--mono);font-weight:600">${esc(t.template_name)}</div>
          <div class="muted" style="font-size:12px;margin-top:2px">${t.usage.rows} calendar rows · first send ${esc(t.usage.first_send)}</div></div>
          <div style="display:flex;gap:8px;align-items:center">${statusChip(t.status, t)}<button class="btn btn-sm" id="openTpl">Open template</button></div>
        </div></div>` : ""}`,
    foot: locked ? `<button class="btn" data-close>Close</button>` : `${r.id ? `<button class="btn btn-danger" id="delRow">Delete</button>` : ""}<span class="left"></span><button class="btn" data-close>Cancel</button><button class="btn btn-primary" id="saveRow">Save campaign</button>`,
  });
  $("#openTpl")?.addEventListener("click", () => openTemplate(t.id));
  $("#saveRow")?.addEventListener("click", async () => {
    const body = {};
    $$("#drawerBody [data-k]").forEach((el) => (body[el.dataset.k] = el.value));
    try {
      await post(r.id ? `/api/rows/${r.id}` : "/api/rows", body);
      toast("Campaign saved", "ok"); closeDrawer(); await reloadCalendar();
    } catch (e) { toast(e.message, "err"); }
  });
  $("#delRow")?.addEventListener("click", async () => {
    if (!confirm("Delete this campaign row?")) return;
    try { await post(`/api/rows/${r.id}/delete`); toast("Deleted"); closeDrawer(); await reloadCalendar(); } catch (e) { toast(e.message, "err"); }
  });
}

async function reloadCalendar() { setCalendar(await api("/api/calendar")); render(); }

// ---------------------------------------------------------------- templates
function renderTemplates() {
  const ts = tplList();
  const counts = Object.fromEntries(STAGES.map((s) => [s.key, ts.filter((t) => s.states.includes(t.status)).length]));
  $("#tplIntro").className = "callout " + (S.cal.locked ? "ok" : "info");
  $("#tplIntro").innerHTML = S.cal.locked
    ? `<div><b>Calendar locked.</b> Templates are sent to the vendor one at a time, earliest first send first. Approved in the <b>same category</b> → added to WebEngage. Rejected or re-categorised → <b>Needs edit</b>: open it, change the copy and click <b>Save & resubmit</b>.</div>`
    : `<div><b>How it works:</b> finish the calendar, then click <b>Lock & send for approval</b>. Each template below goes to its vendor (TrustSignal / Route Mobile / Meta) as a separate API call, in the vendor's JSON format. Only templates approved in the category you asked for are added to WebEngage.</div>`;
  $("#statusFilter").innerHTML = [["", "All", ts.length], ...STAGES.map((s) => [s.key, s.label, counts[s.key]])]
    .map(([k, l, n]) => `<button class="${S.tf.stage === k ? "active" : ""}" data-st="${k}">${l}<span class="c">${n}</span></button>`).join("");
  $$("#statusFilter button").forEach((b) => (b.onclick = () => { S.tf.stage = b.dataset.st; renderTemplates(); }));
  const stage = STAGES.find((s) => s.key === S.tf.stage);
  const q = S.tf.q.trim().toLowerCase();
  const list = ts.filter((t) => (!stage || stage.states.includes(t.status)) && (!q || (t.template_name + " " + t.body).toLowerCase().includes(q)));
  $("#tplTable tbody").innerHTML = list.length ? list.map((t) => {
    const i = ts.indexOf(t) + 1;
    const issues = t.validation.errors.length ? `<span class="tag" style="background:var(--red-soft);color:var(--red)">${t.validation.errors.length} to fix</span>`
      : t.validation.warnings.length ? `<span class="tag" style="background:var(--amber-soft);color:var(--amber)">${t.validation.warnings.length} warning</span>` : "";
    return `<tr data-id="${t.id}">
      <td class="muted">${i}</td>
      <td><div class="seg-name">${esc(t.template_name)}</div><div class="content-copy" style="color:var(--text-2);margin-top:2px">${esc(t.body)}</div>
        <div class="content-meta">${t.button_text ? `<span class="tag cta">${esc(t.button_text)}</span>` : ""}${issues}</div></td>
      <td class="nowrap">${esc(t.usage.first_send ? shortTime(t.usage.first_send) : "—")}</td>
      <td class="num">${t.usage.rows}</td>
      <td class="num">${fmtShort(t.usage.audience)}</td>
      <td class="nowrap">${esc(t.category)}${t.approved_category && t.approved_category !== t.category ? ` → <b style="color:var(--red)">${esc(t.approved_category)}</b>` : ""}</td>
      <td class="nowrap">${esc(t.vendor)}</td>
      <td>${statusChip(t.status, t)}${t.reason ? `<div class="muted" style="margin-top:4px;max-width:220px">${esc(t.reason)}</div>` : ""}</td>
      <td><button class="btn btn-sm">${NEEDS_EDIT.has(t.status) ? "Edit" : t.status === "WE_MANUAL" ? "Confirm" : "Open"}</button></td>
    </tr>`;
  }).join("") : `<tr><td colspan="9" class="empty">No templates in this stage.</td></tr>`;
  $$("#tplTable tbody tr[data-id]").forEach((tr) => (tr.onclick = () => openTemplate(tr.dataset.id)));
}

function stepsFor(t) {
  const s = t.status;
  const idx = { DRAFT: 0, QUEUED: 1, SUBMITTING: 2, PENDING: 2, REJECTED: 2, CATEGORY_CHANGED: 3, PAUSED: 2, ERROR: 2, WE_PUSHING: 4, WE_MANUAL: 4, WE_ERROR: 4, IN_WEBENGAGE: 5 }[s] ?? 0;
  const fail = NEEDS_EDIT.has(s) || s === "WE_ERROR";
  const names = ["Draft", "Locked & queued", "Vendor → Meta review", "Approved, same category", "Added to WebEngage"];
  return `<div class="steps">${names.map((n, i) => {
    const cls = i < idx ? "done" : i === idx ? (fail ? "fail" : "cur") : "";
    return `<div class="step ${idx === 5 ? "done" : cls}"><div class="b">${(idx === 5 || i < idx) ? "✓" : (i === idx && fail) ? "!" : i + 1}</div>${n}</div>`;
  }).join("")}</div>`;
}

function statusCallout(t) {
  const s = t.status;
  if (s === "DRAFT") return S.cal.locked ? "" : `<div class="callout info">Draft. It is sent to <b>${esc(t.vendor)}</b> automatically when the calendar is locked.</div>`;
  if (s === "QUEUED") return `<div class="callout info"><b>Queued.</b> The portal sends templates one by one; this one goes out shortly.</div>`;
  if (s === "SUBMITTING") return `<div class="callout warn"><b>Calling ${esc(t.vendor)}…</b></div>`;
  if (s === "PENDING") return `<div class="callout warn"><b>Submitted to ${esc(t.vendor)}</b> (vendor id <code>${esc(t.vendor_template_id)}</code>). Waiting for Meta's decision. The portal polls the vendor and also accepts webhooks.</div>`;
  if (s === "REJECTED") return `<div class="callout error"><b>Rejected by Meta.</b> ${esc(t.reason)}<br>Edit the copy below and click <b>Save & resubmit</b>. Not added to WebEngage.</div>`;
  if (s === "CATEGORY_CHANGED") return `<div class="callout error"><b>Approved as ${esc(t.approved_category)}, but you asked for ${esc(t.category)}.</b> ${esc(t.reason)}<br>So it is <b>not</b> added to WebEngage. Remove promotional wording (offers, discounts, "free", urgency) or request ${esc(t.approved_category)}, then <b>Save & resubmit</b>. A new version name is used because Meta keeps the old one.</div>`;
  if (s === "PAUSED") return `<div class="callout error"><b>Paused by Meta</b> (quality). ${esc(t.reason)}</div>`;
  if (s === "ERROR") return `<div class="callout error"><b>Vendor call failed.</b> ${esc(t.reason)}</div>`;
  if (s === "WE_PUSHING") return `<div class="callout violet"><b>Approved.</b> Adding to WebEngage…</div>`;
  if (s === "WE_MANUAL") return `<div class="callout violet"><b>Approved in ${esc(t.approved_category)} ✓ — add it in WebEngage.</b> WebEngage has no public API for templates, so: WebEngage → WhatsApp → Templates → <b>Add Template</b>, select WSP <b>${esc(S.settings.webengage.wsp_name || t.vendor)}</b>, and use the values in the <b>API payloads</b> tab. Then enter the WebEngage template name/ID below and confirm.</div>`;
  if (s === "WE_ERROR") return `<div class="callout error"><b>WebEngage call failed.</b> ${esc(t.reason)}</div>`;
  if (s === "IN_WEBENGAGE") return `<div class="callout ok"><b>In WebEngage</b> as <code>${esc(t.webengage_template_id)}</code> · approved ${esc(t.approved_category)} · ${esc(fmtTime(t.pushed_at))}. Next: campaign set-up in WebEngage.</div>`;
  return "";
}

const F = (k, label, api, inner, cls = "") => `<div class="field ${cls}"><label>${label}<span class="api">${api}</span></label>${inner}</div>`;

function templateForm(t, ro) {
  const dis = ro ? "disabled" : "";
  const inp = (k, ph = "") => `<input data-k="${k}" value="${esc(t[k])}" placeholder="${esc(ph)}" ${dis}>`;
  const sel = (k, opts) => `<select data-k="${k}" ${dis}>${opts.map((o) => { const [v, l] = Array.isArray(o) ? o : [o, o]; return `<option value="${esc(v)}" ${v === t[k] ? "selected" : ""}>${esc(l)}</option>`; }).join("")}</select>`;
  const vendors = Object.keys(S.settings.vendors);
  const vconf = S.settings.vendors[t.vendor] || {};
  return `
  <div class="section"><div class="section-title">Sender & routing</div><div class="grid2">
    ${F("vendor", "Vendor (WSP)", "→ API call target", sel("vendor", vendors))}
    ${F("waba_id", "WABA ID", vconf.type === "meta" ? "path /{waba_id}" : "waba_id", `<input value="${esc(t.waba_id || vconf.waba_id || "")}" placeholder="set in Settings" disabled>`)}
    ${F("sender_number", "Sender number (WABA number)", "phone_number", inp("sender_number", vconf.sender_number || "+91…"))}
    ${F("language", "Language", "language", sel("language", [["en", "English (en)"], ["en_US", "English US (en_US)"], ["hi", "Hindi (hi)"]]))}
    ${F("template_name", "Template name", "name", inp("template_name"), "full")}
    ${F("category", "Category to request", "category", sel("category", ["UTILITY", "MARKETING"]))}
    ${F("parameter_format", "Parameter format", "parameter_format", `<input value="POSITIONAL" disabled>`)}
  </div></div>
  <div class="section"><div class="section-title">Header</div><div class="grid2">
    ${F("header_type", "Header type", "HEADER.format", sel("header_type", [["NONE", "None"], ["IMAGE", "Image"], ["TEXT", "Text"]]))}
    ${t.header_type === "IMAGE" ? F("header_media_url", "Header image URL (banner)", "example.header_handle", inp("header_media_url", "https://…/banner.jpg"))
      : t.header_type === "TEXT" ? F("header_text", "Header text <span class='counter' data-c='header_text'></span>", "HEADER.text", inp("header_text")) : "<div></div>"}
  </div></div>
  <div class="section"><div class="section-title">Body</div><div class="grid2">
    ${F("body", "Body text <span class='counter' data-c='body'></span>", "BODY.text", `<textarea data-k="body" rows="4" ${dis}>${esc(t.body)}</textarea>`, "full")}
    ${F("body_samples", "Sample values for {{1}}, {{2}}…", "BODY.example.body_text", inp("body_samples", "Rahul | ₹1,250"))}
    ${F("footer", "Footer <span class='counter' data-c='footer'></span>", "FOOTER.text", inp("footer"))}
  </div></div>
  <div class="section"><div class="section-title">Button</div><div class="grid2">
    ${F("button_type", "Button type", "BUTTONS[0].type", sel("button_type", [["NONE", "None"], ["URL", "Visit website (URL)"], ["QUICK_REPLY", "Quick reply"]]))}
    ${t.button_type !== "NONE" ? F("button_text", "Button text <span class='counter' data-c='button_text'></span>", "BUTTONS[0].text", inp("button_text")) : "<div></div>"}
    ${t.button_type === "URL" ? F("button_url", "Button URL", "BUTTONS[0].url", inp("button_url", "https://www.snapmint.com/p/{{1}}"), "full")
      + F("button_url_sample", "Sample full URL", "BUTTONS[0].example", inp("button_url_sample")) : ""}
  </div></div>
  <div class="section"><div class="section-title">WebEngage personalisation</div><div class="grid2">
    ${F("url_variable", "Value for button {{1}}", "WebEngage expression", inp("url_variable", '{{event["custom"][…]}}'), "full")}
    ${F("body_variables", "Values for body {{1}}, {{2}}…", "pipe-separated", inp("body_variables", "{{user.first_name}}"), "full")}
  </div></div>`;
}

function previewHtml(t) {
  const hl = (s) => esc(s).replace(/\{\{(\d+)\}\}/g, '<span class="var">{{$1}}</span>');
  const hdr = t.header_type === "IMAGE"
    ? `<div class="hdr-img">${/^https:\/\//.test(t.header_media_url || "") ? `<img src="${esc(t.header_media_url)}" alt="">` : `🖼 ${esc((t.visual_brief || "Header image").slice(0, 140))}`}</div>`
    : t.header_type === "TEXT" ? `<div class="hdr-txt">${hl(t.header_text)}</div>` : "";
  return `<div class="phone"><div class="phone-top"><div class="av">S</div><div>Snapmint<div class="vf">${esc(t.sender_number || "Business account")}</div></div></div>
    <div class="bubble">${hdr}<div class="bd">${hl(t.body) || "<i style='color:#999'>Body text…</i>"}</div>${t.footer ? `<div class="ft">${esc(t.footer)}</div>` : ""}<div class="tm">11:20</div></div>
    ${t.button_type !== "NONE" && t.button_text ? `<div class="bubble-btn">${t.button_type === "URL" ? "↗ " : "↩ "}${esc(t.button_text)}</div>` : ""}</div>`;
}

function checksHtml(v) {
  const items = [...v.errors.map((m) => ["err", "!", m]), ...v.warnings.map((m) => ["warn", "!", m])];
  if (!items.length) items.push(["ok", "✓", "Passes Meta's format rules."]);
  return `<div class="checks">${items.map(([c, i, m]) => `<div class="chk ${c}"><span class="i">${i}</span><span>${esc(m)}</span></div>`).join("")}</div>`;
}

function formValues() {
  const o = {};
  $$("#drawerBody [data-k]").forEach((el) => (o[el.dataset.k] = el.value));
  return o;
}

function openTemplate(id, tab = "content") {
  const t = S.tpl[id];
  if (!t) return;
  S.drawer = { type: "tpl", id, tab, status: t.status };
  S.dirty = false;
  const ro = !EDITABLE.has(t.status) || (t.status === "DRAFT" && S.cal.locked);
  const tabs = [["content", "Template"], ["payload", "API payloads"], ["usage", `Calendar rows (${t.usage.rows})`], ["history", "History"]];
  let body = stepsFor(t) + statusCallout(t);
  if (tab === "content") {
    body += `<div class="split"><div>${templateForm(t, ro)}
      <div class="section"><div class="section-title">From the calendar</div><div class="source-box"><dl>
        <dt>Tags</dt><dd>${t.tags.map((x) => `<span class="tag">${esc(x)}</span>`).join(" ") || "—"}</dd>
        <dt>Static visual brief</dt><dd>${esc(t.visual_brief) || "—"}</dd>
        <dt>Original copy</dt><dd>${esc(t.source_copy)}</dd>
        <dt>CTA · LP</dt><dd>${esc(t.source_cta)} · <span style="font-family:var(--mono);font-size:12px">${esc(t.source_lp)}</span></dd></dl></div></div>
    </div><div><div class="side-sticky"><div class="section-title">Preview</div><div id="pv">${previewHtml(t)}</div><div id="chk">${checksHtml(t.validation)}</div></div></div></div>`;
  } else if (tab === "payload") {
    body += `<div id="payloads"><div class="empty">Loading…</div></div>`;
  } else if (tab === "usage") {
    const rows = S.cal.rows.filter((r) => r.template_id === id);
    body += `<table class="table"><thead><tr><th>Date</th><th>Time</th><th>Segment</th><th>Excludes</th><th class="num">Size</th></tr></thead><tbody>
      ${rows.map((r) => `<tr data-row="${r.id}"><td class="nowrap">${esc(r.day.slice(0, 3))} ${esc(r.date)}</td><td>${esc(shortTime(r.time))}</td><td class="seg-name">${esc(r.naming)}</td><td class="muted">${esc(r.exclude)}</td><td class="num">${fmtN(r.size)}</td></tr>`).join("")}</tbody></table>`;
  } else {
    body += `<div class="timeline" style="padding:0">${(t.history || []).slice().reverse().map((h) => `<div class="tl"><div class="when">${esc(fmtTime(h.at))}</div>
      <div class="what"><b>${esc(h.event.replace(/_/g, " "))}</b><div class="det">${esc(Object.entries(h).filter(([k]) => !["at", "event"].includes(k)).map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(", ") : v}`).join(" · "))}</div></div></div>`).join("") || `<div class="empty">No activity yet.</div>`}</div>`;
  }
  let foot = `<span class="left">Vendor: ${esc(t.vendor)}${t.attempts ? ` · ${t.attempts} attempt${t.attempts > 1 ? "s" : ""}` : ""}</span><button class="btn" data-close>Close</button>`;
  if (!ro && tab === "content") foot += `<button class="btn ${NEEDS_EDIT.has(t.status) ? "" : "btn-primary"}" id="saveTpl">Save</button>`;
  if (NEEDS_EDIT.has(t.status)) foot += `<button class="btn btn-primary" id="resubmit">Save & resubmit</button>`;
  if (t.status === "WE_MANUAL" || t.status === "WE_ERROR") {
    if (t.status === "WE_ERROR") foot += `<button class="btn" id="retryWe">Retry WebEngage</button>`;
    foot += `<input id="weRef" placeholder="Template name / ID in WebEngage" value="${esc(t.template_name)}"><button class="btn btn-success" id="confirmWe">Confirm added</button>`;
  }
  openDrawer({ kicker: `${statusChip(t.status, t)} <span>${esc(t.category)} · ${t.usage.rows} rows · first send ${esc(t.usage.first_send)}</span>`, title: t.template_name, tabs, tab, body, foot });
  $$("#drawerTabs .tab").forEach((b) => (b.onclick = () => openTemplate(id, b.dataset.tab)));
  $$("#drawerBody tr[data-row]").forEach((tr) => (tr.onclick = () => openRow(tr.dataset.row)));
  if (tab === "payload") loadPayloads(id);
  if (tab === "content") wireForm(t);
  $("#saveTpl")?.addEventListener("click", () => saveTemplate(id));
  $("#resubmit")?.addEventListener("click", async () => {
    if (tab === "content" && !(await saveTemplate(id, true))) return;
    try { await post(`/api/templates/${id}/resubmit`, { by: me() }); toast("Resubmitted — back in the queue", "ok"); await refreshTemplates(); openTemplate(id); }
    catch (e) { toast(e.data?.validation?.errors?.[0] || e.message, "err"); }
  });
  $("#retryWe")?.addEventListener("click", async () => {
    try { await post(`/api/templates/${id}/push-webengage`); toast("Added to WebEngage", "ok"); } catch (e) { toast(e.message, "err"); }
    await refreshTemplates(); openTemplate(id);
  });
  $("#confirmWe")?.addEventListener("click", async () => {
    try { await post(`/api/templates/${id}/confirm-webengage`, { reference: $("#weRef").value, by: me() }); toast("Marked as added in WebEngage", "ok"); await refreshTemplates(); openTemplate(id); }
    catch (e) { toast(e.message, "err"); }
  });
}

function wireForm(t) {
  let timer;
  const counters = { body: 1024, footer: 60, button_text: 25, header_text: 60 };
  const upd = () => {
    const v = { ...t, ...formValues() };
    $$("#drawerBody [data-c]").forEach((c) => { const k = c.dataset.c; c.textContent = `${(v[k] || "").length}/${counters[k]}`; });
    $("#pv").innerHTML = previewHtml(v);
    clearTimeout(timer);
    timer = setTimeout(async () => {
      try { const r = await post(`/api/templates/${t.id}/validate`, formValues()); $("#chk").innerHTML = checksHtml(r.validation); } catch { /* ignore */ }
    }, 250);
  };
  $$("#drawerBody [data-k]").forEach((el) => {
    el.addEventListener("input", () => { S.dirty = true; upd(); });
    if (["header_type", "button_type", "vendor"].includes(el.dataset.k)) el.addEventListener("change", async () => { await saveTemplate(t.id, true); openTemplate(t.id); });
  });
  upd();
}

async function saveTemplate(id, quiet = false) {
  try {
    const r = await post(`/api/templates/${id}`, formValues());
    S.dirty = false;
    await refreshTemplates();
    if (!quiet) { toast("Template saved", "ok"); openTemplate(id); }
    return r;
  } catch (e) { toast(e.message, "err"); return null; }
}

async function loadPayloads(id) {
  const r = await api(`/api/templates/${id}/payload`);
  const t = S.tpl[id];
  const v = S.settings.vendors[t.vendor] || {};
  const endpoint = v.type === "meta"
    ? `POST https://graph.facebook.com/${v.graph_version || "v23.0"}/${v.waba_id || "{WABA_ID}"}/message_templates`
    : `POST ${v.create_url || `{${t.vendor} template-create URL — set in Settings}`}`;
  const weUrl = S.settings.webengage.template_api_url;
  $("#payloads").innerHTML = `
    <div class="code-head"><span class="t">1 · Vendor request — ${esc(t.vendor)}</span><span class="m">${esc(endpoint)}</span></div>
    <pre class="code">${esc(JSON.stringify(t.last_request || r.vendor_payload, null, 2))}</pre>
    ${t.last_response ? `<div class="code-head"><span class="t">Vendor response</span></div><pre class="code">${esc(JSON.stringify(t.last_response, null, 2))}</pre>` : ""}
    <div class="code-head"><span class="t">2 · WebEngage template</span><span class="m">${esc(weUrl ? "POST " + weUrl : "Manual — WebEngage → WhatsApp → Templates → Add Template")}</span></div>
    <pre class="code">${esc(JSON.stringify(t.webengage_packet || r.webengage_payload, null, 2))}</pre>`;
}

// ---------------------------------------------------------------- drawer & modal
function openDrawer({ kicker, title, tabs = [], tab, body, foot }) {
  $("#drawerKicker").innerHTML = kicker;
  $("#drawerTitle").textContent = title;
  $("#drawerTabs").innerHTML = tabs.map(([k, l]) => `<button class="tab ${k === tab ? "active" : ""}" data-tab="${k}">${esc(l)}</button>`).join("");
  $("#drawerTabs").hidden = !tabs.length;
  $("#drawerBody").innerHTML = body;
  $("#drawerFoot").innerHTML = foot;
  $("#drawer").hidden = false; $("#scrim").hidden = false;
  $$("#drawerFoot [data-close]").forEach((b) => (b.onclick = closeDrawer));
}
function closeDrawer() { $("#drawer").hidden = true; $("#scrim").hidden = true; S.drawer = null; S.dirty = false; }

function modal(title, body, foot) {
  $("#modalTitle").textContent = title;
  $("#modalBody").innerHTML = body;
  $("#modalFoot").innerHTML = foot;
  $("#modal").hidden = false;
}
const closeModal = () => ($("#modal").hidden = true);

// ---------------------------------------------------------------- lock
function lockFlow() {
  if (S.cal.locked) {
    const busy = S.cal.templates.filter((t) => ["SUBMITTING", "PENDING"].includes(t.status)).length;
    modal("Unlock the calendar?", `<p>Campaign rows become editable again. Templates still <b>queued</b> go back to draft.${busy ? ` <b>${busy}</b> template(s) already with the vendor stay there.` : ""}</p>`,
      `<button class="btn" id="mCancel">Cancel</button><button class="btn btn-primary" id="mOk">Unlock</button>`);
    $("#mCancel").onclick = closeModal;
    $("#mOk").onclick = async () => {
      try { setCalendar(await post("/api/unlock", { by: me() })); closeModal(); render(); toast("Calendar unlocked"); } catch (e) { toast(e.message, "err"); }
    };
    return;
  }
  const drafts = tplList().filter((t) => t.status === "DRAFT");
  const bad = drafts.filter((t) => t.validation.errors.length);
  const warn = drafts.filter((t) => !t.validation.errors.length && t.validation.warnings.length);
  modal("Lock calendar & send for approval", `
    <p>Locking freezes the <b>${fmtN(S.cal.rows.length)}</b> campaign rows and sends <b>${drafts.length}</b> WhatsApp templates to their vendors —
    <b>one API call at a time</b>, earliest first send first. Mode: <b>${S.mode === "live" ? "Live vendor APIs" : "Simulation (no real calls)"}</b>.</p>
    ${bad.length ? `<div class="callout error"><b>${bad.length} template(s) must be fixed first:</b><div class="mini-list">${bad.map((t) => `<div class="it"><span style="font-family:var(--mono)">${esc(t.template_name)}</span><span>${esc(t.validation.errors[0])}</span></div>`).join("")}</div></div>` : ""}
    ${warn.length ? `<div class="callout warn"><b>${warn.length} UTILITY template(s) have promotional wording.</b> Meta will probably approve them as MARKETING; those won't be added to WebEngage until you edit and resubmit.</div>` : ""}
    <div class="field"><label>Locked by</label><input id="lockBy" value="${esc(me())}" placeholder="Your name"></div>`,
    `<button class="btn" id="mCancel">Cancel</button><button class="btn btn-primary" id="mOk" ${bad.length ? "disabled" : ""}>Lock & send ${drafts.length} templates</button>`);
  $("#mCancel").onclick = closeModal;
  $("#mOk").onclick = async () => {
    const by = $("#lockBy").value.trim();
    setMe(by);
    try { setCalendar(await post("/api/lock", { by })); closeModal(); S.tf.stage = ""; go("templates"); toast(`Locked — ${drafts.length} templates queued`, "ok"); }
    catch (e) { toast(e.message, "err"); }
  };
}

// ---------------------------------------------------------------- activity
async function renderActivity() {
  const items = await api("/api/audit");
  $("#activityList").innerHTML = items.length ? items.map((a) => {
    const det = Object.entries(a).filter(([k]) => !["at", "event", "template", "template_id"].includes(k)).map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(", ") : v}`).join(" · ");
    return `<div class="tl"><div class="when">${esc(fmtTime(a.at))}</div><div class="what"><b>${esc(a.event.replace(/_/g, " "))}</b>${a.template ? ` · <span style="font-family:var(--mono)">${esc(a.template)}</span>` : ""}<div class="det">${esc(det)}</div></div></div>`;
  }).join("") : `<div class="empty">Nothing yet.</div>`;
}

// ---------------------------------------------------------------- settings
const FEAS = [
  ["Calendar portal, lock, one-by-one queue", "y", "Built", "Runs locally, no installs."],
  ["Submit WhatsApp template to Meta for approval", "y", "Documented API", "Meta Graph <code>POST /{WABA_ID}/message_templates</code>; status via <code>GET /{template_id}</code> + webhooks."],
  ["Submit through TrustSignal / Route Mobile", "p", "Ask vendor", "Neither publishes a WhatsApp template-create API. The adapter is ready: paste their create + status URL, key and field names."],
  ["Same-category gate (Utility stays Utility)", "y", "Built", "Meta returns the approved category; mismatches never reach WebEngage."],
  ["Edit & resubmit after rejection", "y", "Built", "Meta allows editing rejected/paused templates; a re-categorised template gets a new version name."],
  ["Add approved template to WebEngage via API", "n", "No public API", "WebEngage REST API covers users, events, transactional campaigns, journeys, surveys — not templates. Templates are added in the dashboard (Add Template). Ask your WebEngage CSM for a private endpoint; paste it below and the push becomes automatic. Until then: guided manual step + confirm."],
  ["Create WhatsApp campaign in WebEngage via API", "n", "No public API", "Same limitation; next phase would be a guided set-up sheet using the Naming Structure column."],
];

function renderSettings() {
  const s = S.settings;
  const vcard = (name, c) => {
    const req = S.requirements.find((r) => r.system === name);
    const fld = (k, l, ph = "", type = "text") => `<div class="field"><label>${l}</label><input data-v="${esc(name)}" data-f="${k}" type="${type}" value="${esc(c[k] ?? "")}" placeholder="${esc(ph)}"></div>`;
    const fields = c.type === "meta"
      ? fld("waba_id", "WABA ID", "1234567890") + fld("sender_number", "Sender number", "+91…") + fld("api_key", "System user access token", "EAAG…", "password")
        + fld("app_id", "App ID") + fld("graph_version", "Graph API version", "v23.0") + fld("webhook_secret", "App secret (webhook)", "", "password") + fld("verify_token", "Webhook verify token", "", "password")
      : fld("create_url", "Template create URL", "https://…/templates") + fld("status_url", "Template status URL", "https://…/templates/{id}")
        + fld("api_key", "API key", "", "password") + `<div class="field"><label>Auth style</label><select data-v="${esc(name)}" data-f="auth_style">${["bearer", "x-api-key", "apikey", "query"].map((o) => `<option ${o === c.auth_style ? "selected" : ""}>${o}</option>`).join("")}</select></div>`
        + fld("waba_id", "WABA ID / account ID") + fld("sender_number", "Sender number (WABA number)", "+91…")
        + fld("id_path", "Response: id field", "id") + fld("status_path", "Response: status field", "status")
        + fld("category_path", "Response: category field", "category") + fld("reason_path", "Response: reason field", "rejected_reason")
        + fld("webhook_secret", "Webhook signing secret", "", "password");
    return `<div class="card"><h3>${esc(name)} <span class="pill ${req.items.every((i) => i.ok) ? "y" : "p"}">${req.items.filter((i) => i.ok).length}/${req.items.length} ready</span></h3>
      <div class="desc">${c.type === "meta" ? "Direct Meta Cloud API (no WSP in between)." : "WSP adapter — sends Meta-format JSON plus waba_id and phone_number."} Webhook: <code>/webhooks/${name.toLowerCase().replace(/\s+/g, "")}</code></div>
      <div class="grid2">${fields}</div>
      <div style="margin-top:12px">${req.items.map((i) => `<div class="req ${i.ok ? "ok" : "no"}"><span class="i">${i.ok ? "✓" : ""}</span>${esc(i.label)}</div>`).join("")}</div></div>`;
  };
  const w = s.webengage;
  const wreq = S.requirements.find((r) => r.system === "WebEngage");
  $("#settingsBody").innerHTML = `
    <div class="card wide"><h3>Feasibility</h3><div class="desc">What can be automated end to end, based on the vendors' public documentation.</div>
      <table class="feas"><thead><tr><th>Step</th><th>Status</th><th>Notes</th></tr></thead><tbody>
      ${FEAS.map(([a, k, l, n]) => `<tr><td><b>${a}</b></td><td><span class="pill ${k}">${l}</span></td><td>${n}</td></tr>`).join("")}</tbody></table></div>
    <div class="card"><h3>Workflow</h3><div class="desc">Simulation runs the whole flow without calling anyone. Promotional UTILITY copy comes back as MARKETING, like Meta does.</div>
      <div class="grid2">
        <div class="field"><label>Mode</label><select data-g="mode"><option value="simulate" ${s.mode === "simulate" ? "selected" : ""}>Simulation</option><option value="live" ${s.mode === "live" ? "selected" : ""}>Live vendor APIs</option></select></div>
        <div class="field"><label>Default vendor for new templates</label><select data-g="default_vendor">${Object.keys(s.vendors).map((v) => `<option ${v === s.default_vendor ? "selected" : ""}>${esc(v)}</option>`).join("")}</select></div>
        <div class="field"><label>Gap between vendor calls (s)</label><input data-g="submit_gap_seconds" type="number" min="0.5" step="0.5" value="${esc(s.submit_gap_seconds)}"></div>
        <div class="field"><label>Status poll interval, live (s)</label><input data-g="poll_seconds" type="number" min="10" value="${esc(s.poll_seconds)}"></div>
      </div></div>
    <div class="card"><h3>WebEngage <span class="pill ${w.template_api_url ? "y" : "p"}">${w.template_api_url ? "API push" : "Guided manual add"}</span></h3>
      <div class="desc">India data centre: <code>https://api.in.webengage.com/v1/accounts/{license_code}/…</code>. There is no public template endpoint — leave it empty to use the guided manual step.</div>
      <div class="grid2">
        <div class="field"><label>License code</label><input data-w="license_code" value="${esc(w.license_code)}"></div>
        <div class="field"><label>REST API key</label><input data-w="api_key" type="password" value="${esc(w.api_key)}"></div>
        <div class="field full"><label>Template endpoint (from WebEngage CSM)</label><input data-w="template_api_url" value="${esc(w.template_api_url)}" placeholder="https://api.in.webengage.com/v1/accounts/{license_code}/…"></div>
        <div class="field"><label>WSP name in WebEngage</label><input data-w="wsp_name" value="${esc(w.wsp_name)}"></div>
      </div>
      <div style="margin-top:12px">${wreq.items.map((i) => `<div class="req ${i.ok ? "ok" : "no"}"><span class="i">${i.ok ? "✓" : ""}</span>${esc(i.label)}</div>`).join("")}</div></div>
    ${Object.entries(s.vendors).map(([n, c]) => vcard(n, c)).join("")}
    <div class="card wide" style="display:flex;justify-content:flex-end;gap:8px"><button class="btn btn-primary" id="saveSettings">Save settings</button></div>`;
  $("#saveSettings").onclick = async () => {
    const up = { vendors: {}, webengage: {} };
    $$("[data-g]").forEach((el) => (up[el.dataset.g] = el.type === "number" ? +el.value : el.value));
    $$("[data-w]").forEach((el) => (up.webengage[el.dataset.w] = el.value));
    $$("[data-v]").forEach((el) => ((up.vendors[el.dataset.v] ||= {})[el.dataset.f] = el.value));
    try { setSettings(await post("/api/settings", up)); toast("Settings saved", "ok"); render(); } catch (e) { toast(e.message, "err"); }
  };
}

// ---------------------------------------------------------------- polling
async function refreshTemplates() {
  setTemplates(await api("/api/templates"));
}
async function tick() {
  if (!S.cal || document.hidden) return;
  const active = S.cal.templates.some((t) => ACTIVE.has(t.status));
  if (!active && !tick.force) return;
  tick.force = false;
  try {
    await refreshTemplates();
    renderShell(); renderPipeline();
    if (S.view === "templates") renderTemplates();
    if (S.view === "calendar") renderCalendar();
    const d = S.drawer;
    if (d?.type === "tpl" && !S.dirty && S.tpl[d.id] && S.tpl[d.id].status !== d.status) openTemplate(d.id, d.tab);
  } catch { /* server restarting */ }
}

// ---------------------------------------------------------------- boot
document.addEventListener("DOMContentLoaded", async () => {
  $$(".nav-item").forEach((b) => (b.onclick = () => go(b.dataset.view)));
  $("#lockBtn").onclick = lockFlow;
  $("#drawerClose").onclick = closeDrawer;
  $("#scrim").onclick = closeDrawer;
  $("#modalClose").onclick = closeModal;
  $("#exportBtn").onclick = (e) => { e.stopPropagation(); $("#exportMenu").hidden = !$("#exportMenu").hidden; };
  document.addEventListener("click", () => ($("#exportMenu").hidden = true));
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") { closeModal(); closeDrawer(); } });
  let st;
  $("#search").oninput = (e) => { clearTimeout(st); st = setTimeout(() => { S.f.q = e.target.value; S.f.page = 0; renderCalendar(); }, 150); };
  $("#tplSearch").oninput = (e) => { S.tf.q = e.target.value; renderTemplates(); };
  $("#expOnly").onchange = (e) => { S.f.exp = e.target.checked; S.f.page = 0; renderCalendar(); };
  $("#addRowBtn").onclick = () => openRow(null);
  $("#fileInput").onchange = async (e) => {
    const f = e.target.files[0];
    if (!f) return;
    try {
      const cal = await api("/api/import", { method: "POST", body: await f.text(), headers: { "X-File-Name": encodeURIComponent(f.name), "Content-Type": "text/csv" } });
      setCalendar(cal); render(); toast(`Imported ${fmtN(cal.rows.length)} campaigns · ${cal.templates.length} WhatsApp templates`, "ok");
    } catch (err) { toast(err.message, "err"); }
    e.target.value = "";
  };
  await boot();
  setInterval(tick, 3000);
  setInterval(() => { tick.force = true; }, 20000);
});
