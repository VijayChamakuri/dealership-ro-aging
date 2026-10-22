"use strict";

const BUCKETS = ["0-7", "8-15", "16-30", "31-60", "61-90", "90+"];
const DEFAULT_AS_OF = "2026-10-21";
const PAGE_SIZE = 20;
const KEY_STORAGE = "ro-aging-api-key";
const EXPORT_COLUMNS = [
  "ro_number", "branch", "open_date", "age_days", "age_bucket", "status",
  "payer_type", "unit", "complaint", "technician", "open_dollars",
];

const ICON_FLAG = '<svg class="flag" viewBox="0 0 16 16" aria-hidden="true"><path d="M8 1.8 15 14H1z" fill="currentColor"/><path d="M8 6v3.6M8 11.4v.1" stroke="#000" stroke-opacity=".7" stroke-width="1.6" stroke-linecap="round"/></svg>';
const ICON_CHECK = '<svg viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="8" r="7" fill="currentColor"/><path d="m4.8 8.2 2.2 2.2 4.2-4.6" fill="none" stroke="#fff" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>';
const ICON_ALERT = '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M8 1.8 15 14H1z" fill="currentColor"/><path d="M8 6v3.6M8 11.4v.1" stroke="#000" stroke-opacity=".7" stroke-width="1.6" stroke-linecap="round"/></svg>';

const $ = (id) => document.getElementById(id);
const esc = (value) => String(value ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
const money = (value) => "$" + Math.round(value).toLocaleString("en-US");
const number = (value) => value.toLocaleString("en-US");
const plural = (n, word) => `${number(n)} ${word}${n === 1 ? "" : "s"}`;
const titleCase = (value) => String(value ?? "").toLowerCase().replace(/^\w/, (c) => c.toUpperCase());
const bucketIndex = (bucket) => BUCKETS.indexOf(bucket) + 1;
const formatDate = (iso) => {
  if (!iso) return "";
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
};

const snapshot = (() => {
  try {
    const text = $("snapshot").textContent.trim();
    return text ? JSON.parse(text) : null;
  } catch {
    return null;
  }
})();

const state = {
  view: "overview",
  measure: "count",
  layout: "chart",
  branch: "",
  asOf: DEFAULT_AS_OF,
  summary: [],
  detail: [],
  breakdown: null,
  orders: { search: "", bucket: "", status: "", payer: "", sort: "age_days", dir: "desc", page: 1 },
};

/* ------------------------------------------------------------------ data */

class AuthError extends Error {}

function storedKey() {
  try { return sessionStorage.getItem(KEY_STORAGE) || ""; } catch { return ""; }
}

function storeKey(key) {
  try { sessionStorage.setItem(KEY_STORAGE, key); } catch { /* storage unavailable */ }
}

async function request(path, params = {}) {
  const query = new URLSearchParams(Object.entries(params).filter(([, v]) => v));
  const response = await fetch(`/api/v1${path}?${query}`, { headers: { "X-API-Key": storedKey() } });
  if (response.status === 401) throw new AuthError("API key required");
  if (!response.ok) throw new Error(`The server returned ${response.status} for ${path}.`);
  return response;
}

async function api(path, params = {}) {
  if (snapshot) return fromSnapshot(path, params);
  return (await request(path, params)).json();
}

function fromSnapshot(path, params) {
  const inBranch = (row) => !params.branch || row.branch === params.branch;
  switch (path) {
    case "/branches": return snapshot.branches;
    case "/data-exceptions": return snapshot.exceptions;
    case "/reconciliation": return snapshot.reconciliation;
    case "/ro-aging": return { rows: snapshot.summary.filter(inBranch) };
    case "/ro-aging/detail": return snapshot.detail.filter(inBranch);
    case "/ro-aging/breakdown": return breakdownFrom(snapshot.detail.filter(inBranch));
    default: throw new Error(`Unknown path ${path}`);
  }
}

function breakdownFrom(rows) {
  const group = (key, fallback) => {
    const map = new Map();
    for (const r of rows) {
      const name = r[key] || fallback;
      const g = map.get(name) || { name, ro_count: 0, open_dollars: 0, oldest_days: 0 };
      g.ro_count += 1;
      g.open_dollars += r.open_dollars;
      g.oldest_days = Math.max(g.oldest_days, r.age_days);
      map.set(name, g);
    }
    return [...map.values()].sort((a, b) => b.ro_count - a.ro_count || a.name.localeCompare(b.name));
  };
  return { status: group("status", "UNKNOWN"), payer_type: group("payer_type", "Unknown"), technician: group("technician", "Unassigned") };
}

/* ----------------------------------------------------------------- setup */

function init() {
  $("as-of").value = snapshot ? snapshot.as_of : DEFAULT_AS_OF;
  if (snapshot) {
    $("as-of").disabled = true;
    $("docs-link").classList.add("hidden");
    $("page-foot").textContent = `Static snapshot generated from synthetic sample data as of ${formatDate(snapshot.as_of)}.`;
  }

  document.querySelectorAll(".tabs [role=tab]").forEach((tab) => tab.addEventListener("click", () => showView(tab.id.replace("tab-", ""))));
  document.querySelectorAll("[data-measure]").forEach((b) => b.addEventListener("click", () => { state.measure = b.dataset.measure; renderOverview(); }));
  document.querySelectorAll("[data-view]").forEach((b) => b.addEventListener("click", () => { state.layout = b.dataset.view; renderOverview(); }));

  $("branch").addEventListener("change", () => { state.branch = $("branch").value; refresh(); });
  $("as-of").addEventListener("change", () => { state.asOf = $("as-of").value; refresh(); });
  $("export").addEventListener("click", exportCsv);

  const orders = state.orders;
  $("search").addEventListener("input", (e) => { orders.search = e.target.value; orders.page = 1; renderOrders(); });
  $("filter-bucket").addEventListener("change", (e) => { orders.bucket = e.target.value; orders.page = 1; renderOrders(); });
  $("filter-status").addEventListener("change", (e) => { orders.status = e.target.value; orders.page = 1; renderOrders(); });
  $("filter-payer").addEventListener("change", (e) => { orders.payer = e.target.value; orders.page = 1; renderOrders(); });
  $("reset-filters").addEventListener("click", resetOrderFilters);
  $("prev-page").addEventListener("click", () => { orders.page -= 1; renderOrders(); });
  $("next-page").addEventListener("click", () => { orders.page += 1; renderOrders(); });

  $("filter-bucket").insertAdjacentHTML("beforeend", BUCKETS.map((b) => `<option value="${b}">${b} days</option>`).join(""));
  $("legend").innerHTML = BUCKETS.map((b, i) => `<span><i class="a${i + 1}"></i>${b} days</span>`).join("");

  $("auth-form").addEventListener("submit", (event) => {
    event.preventDefault();
    storeKey($("api-key").value.trim());
    $("auth-error").classList.add("hidden");
    loadAll();
  });

  loadAll();
}

function showView(view) {
  state.view = view;
  document.querySelectorAll(".tabs [role=tab]").forEach((tab) => tab.setAttribute("aria-selected", String(tab.id === `tab-${view}`)));
  document.querySelectorAll(".view").forEach((panel) => panel.classList.toggle("hidden", panel.id !== `view-${view}`));
  $("export").classList.toggle("hidden", view === "quality");
}

async function loadAll() {
  try {
    const branches = await api("/branches");
    $("auth").classList.add("hidden");
    $("branch").innerHTML = '<option value="">All branches</option>' + branches.map((b) => `<option>${esc(b)}</option>`).join("");
    $("branch").value = state.branch;
    const [exceptions, recon] = await Promise.all([api("/data-exceptions"), api("/reconciliation", { as_of: state.asOf })]);
    renderQuality(exceptions, recon);
    await refresh();
  } catch (error) {
    handleError(error);
  }
}

async function refresh() {
  try {
    const params = { branch: state.branch, as_of: state.asOf };
    const [summary, detail, breakdown] = await Promise.all([
      api("/ro-aging", params), api("/ro-aging/detail", params), api("/ro-aging/breakdown", params),
    ]);
    state.summary = summary.rows;
    state.detail = detail;
    state.breakdown = breakdown;
    $("page-sub").textContent = `${state.branch || "All branches"}, as of ${formatDate(state.asOf)}`;
    populateOrderFilters();
    renderOverview();
    renderOrders();
  } catch (error) {
    handleError(error);
  }
}

function handleError(error) {
  if (error instanceof AuthError) {
    const hadKey = Boolean(storedKey());
    $("auth").classList.remove("hidden");
    $("auth-error").classList.toggle("hidden", !hadKey);
    $("api-key").focus();
    return;
  }
  $("page-sub").textContent = error.message;
}

/* -------------------------------------------------------------- overview */

function renderOverview() {
  document.querySelectorAll("[data-measure]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.measure === state.measure)));
  document.querySelectorAll("[data-view]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.view === state.layout)));
  $("aging-chart").classList.toggle("hidden", state.layout !== "chart");
  $("legend").classList.toggle("hidden", state.layout !== "chart");
  $("aging-table").classList.toggle("hidden", state.layout !== "table");

  renderMetrics();
  renderAgingChart();
  renderAgingTable();
  renderBarList("by-status", state.breakdown.status, (name) => titleCase(name));
  renderBarList("by-payer", state.breakdown.payer_type, (name) => esc(name));
  renderBarList("by-technician", state.breakdown.technician, (name) =>
    name === "Unassigned" ? `${ICON_FLAG}<span>Unassigned</span>` : esc(name));
}

function renderMetrics() {
  const rows = state.detail;
  const total = rows.reduce((s, r) => s + r.open_dollars, 0);
  const over30 = rows.filter((r) => r.age_days > 30).length;
  const unassigned = rows.filter((r) => !r.technician).length;
  const oldest = rows[0];
  const share = (n) => (rows.length ? Math.round((n / rows.length) * 100) : 0);
  const metrics = [
    ["Open repair orders", number(rows.length), `${state.summary.length ? new Set(state.summary.map((r) => r.branch)).size : 0} branches`],
    ["Not yet invoiced", money(total), "Labor and parts"],
    ["Open over 30 days", number(over30), `${share(over30)}% of open orders`],
    ["Oldest open order", oldest ? `${oldest.age_days} days` : "None", oldest ? `${oldest.ro_number}, ${oldest.branch}` : ""],
    ["No technician assigned", number(unassigned), `${share(unassigned)}% of open orders`],
  ];
  $("metrics").innerHTML = metrics.map(([label, value, note]) =>
    `<div class="metric"><div class="metric-label">${label}</div><div class="metric-value">${value}</div><div class="metric-note">${esc(note)}</div></div>`).join("");
}

function measureOf(row) {
  return state.measure === "count" ? row.ro_count : row.open_dollars;
}

function formatMeasure(value) {
  return state.measure === "count" ? number(value) : money(value);
}

function niceScale(value) {
  // Round the axis up to a clean step so ticks read 0, 5, 10, 15 rather than 6.25.
  if (value <= 0) return { max: 1, step: 1 };
  const rough = value / 5;
  const magnitude = 10 ** Math.floor(Math.log10(rough));
  const step = [1, 2, 5, 10].map((m) => m * magnitude).find((s) => s >= rough);
  return { max: Math.ceil(value / step) * step, step };
}

function renderAgingChart() {
  const branches = [...new Set(state.summary.map((r) => r.branch))];
  const byKey = new Map(state.summary.map((r) => [`${r.branch}|${r.age_bucket}`, r]));
  const totals = branches.map((b) => state.summary.filter((r) => r.branch === b).reduce((s, r) => s + measureOf(r), 0));
  const { max, step } = niceScale(Math.max(0, ...totals));

  const rows = branches.map((branch, i) => {
    const segments = BUCKETS.map((bucket, j) => {
      const r = byKey.get(`${branch}|${bucket}`);
      if (!r) return "";
      const width = (measureOf(r) / max) * 100;
      const label = state.measure === "count" && width > 3.2 ? r.ro_count : "";
      return `<button type="button" class="aging-seg a${j + 1}" style="flex: 0 0 ${width}%"
        data-branch="${esc(branch)}" data-bucket="${bucket}"
        aria-label="${esc(branch)}, ${bucket} days: ${plural(r.ro_count, "order")}, ${money(r.open_dollars)}">${label}</button>`;
    }).join("");
    const branchRows = state.summary.filter((r) => r.branch === branch);
    const count = branchRows.reduce((s, r) => s + r.ro_count, 0);
    const dollars = branchRows.reduce((s, r) => s + r.open_dollars, 0);
    const primary = state.measure === "count" ? number(count) : money(dollars);
    const secondary = state.measure === "count" ? money(dollars) : plural(count, "order");
    return `<div class="aging-row"><div class="aging-label" title="${esc(branch)}">${esc(branch)}</div>
      <div class="aging-track">${segments}</div>
      <div class="aging-total">${primary}<small>${secondary}</small></div></div>`;
  }).join("");

  const ticks = Array.from({ length: Math.round(max / step) + 1 }, (_, i) => `<span>${formatMeasure(i * step)}</span>`).join("");
  $("aging-chart").innerHTML = branches.length
    ? rows + `<div class="aging-axis"><span></span><div>${ticks}</div><span></span></div>`
    : '<p class="empty">No open repair orders for this selection.</p>';

  $("aging-chart").querySelectorAll(".aging-seg").forEach((seg) => {
    const r = byKey.get(`${seg.dataset.branch}|${seg.dataset.bucket}`);
    const tip = `<b>${esc(r.branch)}</b><br>Open ${r.age_bucket} days<br>${plural(r.ro_count, "order")}, ${money(r.open_dollars)}`;
    seg.addEventListener("pointermove", (e) => showTooltip(tip, e.clientX, e.clientY));
    seg.addEventListener("pointerleave", hideTooltip);
    seg.addEventListener("focus", () => { const b = seg.getBoundingClientRect(); showTooltip(tip, b.left + b.width / 2, b.top); });
    seg.addEventListener("blur", hideTooltip);
    seg.addEventListener("click", () => { hideTooltip(); drillDown(seg.dataset.branch, seg.dataset.bucket); });
  });
}

function renderAgingTable() {
  const branches = [...new Set(state.summary.map((r) => r.branch))];
  const byKey = new Map(state.summary.map((r) => [`${r.branch}|${r.age_bucket}`, r]));
  const cell = (rows) => {
    const count = rows.reduce((s, r) => s + r.ro_count, 0);
    const dollars = rows.reduce((s, r) => s + r.open_dollars, 0);
    if (!count) return '<td class="num muted">0</td>';
    return `<td class="num">${state.measure === "count" ? number(count) : money(dollars)}</td>`;
  };
  const head = `<thead><tr><th>Branch</th>${BUCKETS.map((b) => `<th class="num">${b} days</th>`).join("")}<th class="num">Total</th></tr></thead>`;
  const body = branches.map((branch) => `<tr><td class="nowrap">${esc(branch)}</td>` +
    BUCKETS.map((b) => cell([byKey.get(`${branch}|${b}`)].filter(Boolean))).join("") +
    cell(state.summary.filter((r) => r.branch === branch)) + "</tr>").join("");
  const foot = `<tfoot><tr><td>All branches</td>${BUCKETS.map((b) => cell(state.summary.filter((r) => r.age_bucket === b))).join("")}${cell(state.summary)}</tr></tfoot>`;
  $("aging-table").innerHTML = `<table class="data">${head}<tbody>${body}</tbody>${foot}</table>`;
}

function renderBarList(id, items, formatName) {
  const max = Math.max(1, ...items.map((i) => i.ro_count));
  $(id).innerHTML = items.length ? items.map((item) => `
    <div class="bar-item">
      <span class="bar-name">${formatName(item.name)}</span>
      <span class="bar-figure">${number(item.ro_count)}<small>${money(item.open_dollars)}</small></span>
      <div class="bar-track" aria-hidden="true"><div class="bar-fill" style="width:${(item.ro_count / max) * 100}%"></div></div>
    </div>`).join("") : '<p class="empty">No open repair orders.</p>';
}

async function drillDown(branch, bucket) {
  if (state.branch !== branch) {
    state.branch = branch;
    $("branch").value = branch;
    await refresh();
  }
  resetOrderFilters(false);
  state.orders.bucket = bucket;
  $("filter-bucket").value = bucket;
  renderOrders();
  showView("orders");
}

/* ---------------------------------------------------------- repair orders */

function populateOrderFilters() {
  const fill = (id, values, format) => {
    const select = $(id);
    const current = select.value;
    select.innerHTML = '<option value="">Any</option>' + values.map((v) => `<option value="${esc(v)}">${esc(format(v))}</option>`).join("");
    select.value = values.includes(current) ? current : "";
  };
  fill("filter-status", [...new Set(state.detail.map((r) => r.status))].sort(), titleCase);
  fill("filter-payer", [...new Set(state.detail.map((r) => r.payer_type))].sort(), (v) => v);
  state.orders.status = $("filter-status").value;
  state.orders.payer = $("filter-payer").value;
}

function resetOrderFilters(render = true) {
  Object.assign(state.orders, { search: "", bucket: "", status: "", payer: "", page: 1 });
  $("search").value = "";
  $("filter-bucket").value = "";
  $("filter-status").value = "";
  $("filter-payer").value = "";
  if (render) renderOrders();
}

function filteredOrders() {
  const o = state.orders;
  const term = o.search.trim().toLowerCase();
  const rows = state.detail.filter((r) =>
    (!o.bucket || r.age_bucket === o.bucket) &&
    (!o.status || r.status === o.status) &&
    (!o.payer || r.payer_type === o.payer) &&
    (!term || [r.ro_number, r.branch, r.unit, r.complaint, r.technician].some((v) => String(v ?? "").toLowerCase().includes(term))));
  const dir = o.dir === "asc" ? 1 : -1;
  return rows.sort((a, b) => {
    const x = a[o.sort] ?? "";
    const y = b[o.sort] ?? "";
    const cmp = typeof x === "number" && typeof y === "number" ? x - y : String(x).localeCompare(String(y));
    return cmp * dir || a.ro_number.localeCompare(b.ro_number);
  });
}

const ORDER_COLUMNS = [
  { key: "ro_number", label: "Repair order" },
  { key: "branch", label: "Branch" },
  { key: "open_date", label: "Opened" },
  { key: "age_days", label: "Days open", num: true },
  { key: "status", label: "Status" },
  { key: "payer_type", label: "Payer" },
  { key: "unit", label: "Unit" },
  { key: "complaint", label: "Complaint" },
  { key: "technician", label: "Technician" },
  { key: "open_dollars", label: "Open value", num: true },
];

function renderOrders() {
  const o = state.orders;
  const rows = filteredOrders();
  const pages = Math.max(1, Math.ceil(rows.length / PAGE_SIZE));
  o.page = Math.min(Math.max(1, o.page), pages);
  const pageRows = rows.slice((o.page - 1) * PAGE_SIZE, o.page * PAGE_SIZE);

  const head = ORDER_COLUMNS.map((c) => {
    const active = o.sort === c.key;
    const aria = active ? (o.dir === "asc" ? "ascending" : "descending") : "none";
    const arrow = active ? (o.dir === "asc" ? "&#9650;" : "&#9660;") : "";
    return `<th class="sortable${c.num ? " num" : ""}" aria-sort="${aria}"><button type="button" data-sort="${c.key}">${c.label}<span class="arrow">${arrow}</span></button></th>`;
  }).join("");

  const body = pageRows.map((r) => `<tr>
    <td class="ro nowrap">${esc(r.ro_number)}</td>
    <td class="nowrap">${esc(r.branch)}</td>
    <td class="nowrap">${formatDate(r.open_date)}</td>
    <td class="num"><span class="age-cell">${r.age_days}<i class="a${bucketIndex(r.age_bucket)}" title="${r.age_bucket} days"></i></span></td>
    <td class="status-text">${titleCase(r.status)}</td>
    <td>${esc(r.payer_type)}</td>
    <td class="nowrap">${esc(r.unit)}</td>
    <td>${esc(r.complaint)}</td>
    <td class="nowrap">${r.technician ? esc(r.technician) : '<span class="unassigned">Unassigned</span>'}</td>
    <td class="num">${money(r.open_dollars)}</td>
  </tr>`).join("");

  $("orders-table").innerHTML = `<thead><tr>${head}</tr></thead><tbody>${body ||
    `<tr><td colspan="${ORDER_COLUMNS.length}" class="empty">No repair orders match these filters. <button type="button" class="btn btn-quiet" id="empty-reset">Reset filters</button></td></tr>`}</tbody>`;

  $("orders-table").querySelectorAll("[data-sort]").forEach((b) => b.addEventListener("click", () => {
    const key = b.dataset.sort;
    if (o.sort === key) o.dir = o.dir === "asc" ? "desc" : "asc";
    else { o.sort = key; o.dir = ORDER_COLUMNS.find((c) => c.key === key).num ? "desc" : "asc"; }
    renderOrders();
  }));
  $("empty-reset")?.addEventListener("click", () => resetOrderFilters());

  const value = rows.reduce((s, r) => s + r.open_dollars, 0);
  $("orders-count").textContent = `${plural(rows.length, "repair order")}, ${money(value)} open`;
  $("page-label").textContent = `Page ${o.page} of ${pages}`;
  $("prev-page").disabled = o.page <= 1;
  $("next-page").disabled = o.page >= pages;
}

/* ----------------------------------------------------------- data quality */

function renderQuality(exceptions, recon) {
  $("quality-count").textContent = exceptions.length || "";

  const block = (label, data, note) => `<div><div class="metric-label">${label}</div>
    <div class="metric-value">${number(data.ro_count)} <span class="muted">orders</span></div>
    <div class="metric-note">${money(data.open_dollars)} ${note}</div></div>`;
  $("recon-totals").innerHTML =
    block("Legacy Excel report", recon.legacy, "reported open") +
    block("This service", recon.service, "reported open") +
    block("Difference", recon.difference, "overstated by the legacy report");

  const rows = recon.findings.map((f) => `<tr>
    <td class="nowrap"><b>${esc(f.finding)}</b></td>
    <td>${esc(f.description)}</td>
    <td class="num">${number(f.ro_count)}</td>
    <td class="num">${money(f.dollars)}</td>
    <td>${f.ro_numbers.map(esc).join(", ")}</td></tr>`).join("");
  const totalCount = recon.findings.reduce((s, f) => s + f.ro_count, 0);
  const totalDollars = recon.findings.reduce((s, f) => s + f.dollars, 0);
  $("recon-findings").innerHTML = `<thead><tr><th>Finding</th><th>What happened</th><th class="num">Orders</th><th class="num">Value</th><th>Repair orders</th></tr></thead>
    <tbody>${rows}</tbody><tfoot><tr><td colspan="2">Total explained</td><td class="num">${number(totalCount)}</td><td class="num">${money(totalDollars)}</td><td></td></tr></tfoot>`;

  const status = $("recon-status");
  if (recon.unexplained.length) {
    status.className = "note bad";
    status.innerHTML = `${ICON_ALERT}<span>${plural(recon.unexplained.length, "difference")} not explained by a finding: ${recon.unexplained.map(esc).join(", ")}.</span>`;
  } else {
    status.className = "note good";
    status.innerHTML = `${ICON_CHECK}<span>Every difference is explained by a documented finding.</span>`;
  }

  $("exceptions-table").innerHTML = exceptions.length
    ? `<thead><tr><th>Repair order</th><th>Branch</th><th>Status</th><th>Issue</th></tr></thead><tbody>` +
      exceptions.map((e) => `<tr><td class="ro">${esc(e.ro_number)}</td><td>${esc(e.branch)}</td><td>${titleCase(e.status)}</td><td>${esc(e.issue)}</td></tr>`).join("") +
      "</tbody>"
    : '<tbody><tr><td class="empty">No records need correction.</td></tr></tbody>';
}

/* ---------------------------------------------------------------- export */

async function exportCsv() {
  const filename = `open-repair-orders-${state.asOf}.csv`;
  try {
    // The orders tab exports exactly what is on screen, including search and filters.
    if (state.view === "orders" || snapshot) {
      const rows = state.view === "orders" ? filteredOrders() : state.detail;
      return download(toCsv(rows), filename);
    }
    const response = await request("/ro-aging/export.csv", { branch: state.branch, as_of: state.asOf });
    download(await response.text(), filename);
  } catch (error) {
    handleError(error);
  }
}

function toCsv(rows) {
  const quote = (v) => {
    const s = String(v ?? "");
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  return [EXPORT_COLUMNS.join(","), ...rows.map((r) => EXPORT_COLUMNS.map((c) => quote(r[c])).join(","))].join("\n") + "\n";
}

function download(text, filename) {
  const url = URL.createObjectURL(new Blob([text], { type: "text/csv" }));
  const link = Object.assign(document.createElement("a"), { href: url, download: filename });
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

/* --------------------------------------------------------------- tooltip */

function showTooltip(html, x, y) {
  const tip = $("tooltip");
  tip.innerHTML = html;
  tip.classList.remove("hidden");
  const { width, height } = tip.getBoundingClientRect();
  const left = Math.min(window.innerWidth - width - 8, Math.max(8, x - width / 2));
  const top = y - height - 12 < 8 ? y + 16 : y - height - 12;
  tip.style.left = `${left}px`;
  tip.style.top = `${top}px`;
}

function hideTooltip() {
  $("tooltip").classList.add("hidden");
}

init();
