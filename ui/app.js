"use strict";
// Pokerbot practice UI. Plain JS, no build step, no external resources.

const $ = (sel) => document.querySelector(sel);
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const fmt = (n) => Number(n).toLocaleString("en-US");
const fx = (n, d = 2) => Number(n).toFixed(d);
const signed = (n, d = 2) => (n > 0 ? "+" : n < 0 ? "−" : "±") + Math.abs(n).toFixed(d);

const store = {
  get(key, fallback) { try { const v = localStorage.getItem("pokerui." + key); return v == null ? fallback : JSON.parse(v); } catch { return fallback; } },
  set(key, value) { try { localStorage.setItem("pokerui." + key, JSON.stringify(value)); } catch { /* storage unavailable */ } },
};

async function api(path, body) {
  const opts = body === undefined ? {} : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
  const res = await fetch(path, opts);
  const data = await res.json().catch(() => ({ error: `HTTP ${res.status}` }));
  if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
  return data;
}

const S = {
  bots: [],
  lineup: store.get("lineup", null),
  runs: [],          // summaries, newest first
  full: {},          // id -> full run (when finished)
  selected: null,    // run id shown in Results
  active: null,      // run id being polled
};

// ------------------------------------------------------------------ theme
const THEMES = ["system", "light", "dark"];
function applyTheme(t) {
  if (t === "system") document.documentElement.removeAttribute("data-theme");
  else document.documentElement.setAttribute("data-theme", t);
  $("#theme").textContent = "Theme: " + t;
}
let theme = store.get("theme", "system");
applyTheme(theme);
$("#theme").addEventListener("click", () => { theme = THEMES[(THEMES.indexOf(theme) + 1) % 3]; store.set("theme", theme); applyTheme(theme); });

// ------------------------------------------------------------------ tabs
function showTab(name) {
  document.querySelectorAll(".tabs button").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.tab === name)));
  document.querySelectorAll(".tab").forEach((t) => { t.hidden = t.id !== "tab-" + name; });
  store.set("tab", name);
  if (name === "compare") renderCompare();
  if (name === "replay") syncReplayRuns();
}
document.querySelectorAll(".tabs button").forEach((b) => b.addEventListener("click", () => showTab(b.dataset.tab)));

// ------------------------------------------------------------------ bots & line-up
const botExists = (p) => S.bots.some((b) => b.path === p);
const botName = (p) => p.split("/").pop();

async function loadBots() {
  const data = await api("/api/bots");
  S.bots = data.bots;
  if (!S.lineup || !S.lineup.length) S.lineup = defaultLineup();
  renderSeats(); renderBotList(); renderPresets(); renderCloneSource();
}

function defaultLineup() {
  const pick = (...names) => names.map((n) => S.bots.find((b) => b.path === n || b.name === n)?.path).filter(Boolean);
  const l = pick("starter", "sparring/check_or_fold", "sparring/min_raiser", "sparring/calling_station", "sparring/shover", "sparring/nit", "sparring/nit", "starter");
  while (l.length < 8 && S.bots.length) l.push(S.bots[l.length % S.bots.length].path);
  return l;
}

function renderSeats() {
  const ol = $("#seats");
  ol.innerHTML = "";
  S.lineup.forEach((path, i) => {
    const li = document.createElement("li");
    const options = S.bots.map((b) => `<option value="${esc(b.path)}"${b.path === path ? " selected" : ""}>${esc(b.path)}</option>`);
    if (!botExists(path)) options.unshift(`<option value="${esc(path)}" selected>missing: ${esc(path)}</option>`);
    li.innerHTML = `<span class="seat-no">#${i}</span><select aria-label="Bot for entry ${i}" class="${botExists(path) ? "" : "missing"}">${options.join("")}</select>`;
    li.querySelector("select").addEventListener("change", (e) => { S.lineup[i] = e.target.value; saveLineup(); renderSeats(); });
    ol.appendChild(li);
  });
  $("#seat-count").textContent = S.lineup.length;
  $("#seat-minus").disabled = S.lineup.length <= 2;
  $("#seat-plus").disabled = S.lineup.length >= 10;
}
function saveLineup() { store.set("lineup", S.lineup); }
$("#seat-minus").addEventListener("click", () => { if (S.lineup.length > 2) { S.lineup.pop(); saveLineup(); renderSeats(); } });
$("#seat-plus").addEventListener("click", () => { if (S.lineup.length < 10) { S.lineup.push(S.lineup[S.lineup.length - 1]); saveLineup(); renderSeats(); } });
$("#refresh-bots").addEventListener("click", async () => { await loadBots(); flash($("#refresh-bots"), "Refreshed"); });

function flash(btn, text) { const old = btn.textContent; btn.textContent = text; setTimeout(() => { btn.textContent = old; }, 900); }

// Presets mirror practice.py's gauntlet; entry #0 is "you".
function presets(you) {
  const s = (n) => "sparring/" + n;
  return {
    "Mixed field": [you, s("check_or_fold"), s("min_raiser"), s("calling_station"), s("shover"), s("nit"), s("nit"), "starter"],
    "Passive field (many broken bots)": [you, s("check_or_fold"), s("check_or_fold"), s("check_or_fold"), s("check_or_fold"), s("nit"), s("nit"), s("nit")],
    "Aggressive field": [you, s("shover"), s("shover"), s("shover"), s("min_raiser"), s("min_raiser"), "starter", "starter"],
    "Seven starters": [you, ...Array(7).fill("starter")],
    "Four of you, four starters": [you, you, you, you, "starter", "starter", "starter", "starter"],
  };
}
function renderPresets() {
  const sel = $("#preset");
  const you = S.lineup[0];
  sel.innerHTML = `<option value="">Preset line-up (#0 = ${esc(botName(you))})&hellip;</option>` +
    Object.entries(presets(you)).filter(([, l]) => l.every(botExists)).map(([name]) => `<option>${esc(name)}</option>`).join("");
}
$("#preset").addEventListener("change", (e) => {
  const l = presets(S.lineup[0])[e.target.value];
  if (l) { S.lineup = l.slice(); saveLineup(); renderSeats(); }
  e.target.value = "";
});

function ago(ts) {
  const s = Date.now() / 1000 - ts;
  if (s < 60) return "just now";
  if (s < 3600) return Math.floor(s / 60) + " min ago";
  if (s < 86400) return Math.floor(s / 3600) + " h ago";
  return new Date(ts * 1000).toLocaleDateString();
}
function renderBotList() {
  $("#bot-list").innerHTML = S.bots.map((b) => `<li>
      <span class="path" title="${esc(b.path)}/agent.py">${esc(b.path)}</span>
      <span class="when" title="agent.py last modified ${esc(new Date(b.modified * 1000).toLocaleString())}">edited ${esc(ago(b.modified))}</span>
      <button class="ghost small" type="button" data-clone="${esc(b.path)}">Clone</button>
      ${b.problems.length ? `<span class="problem">upload check: ${esc(b.problems.join("; "))}</span>` : ""}
    </li>`).join("");
  document.querySelectorAll("[data-clone]").forEach((btn) => btn.addEventListener("click", () => {
    $("#clone-source").value = btn.dataset.clone; suggestCloneName(); $("#clone-name").focus();
  }));
}

// ------------------------------------------------------------------ clone
function renderCloneSource() {
  const sel = $("#clone-source");
  const keep = sel.value;
  sel.innerHTML = S.bots.map((b) => `<option value="${esc(b.path)}">${esc(b.path)}</option>`).join("");
  if (botExists(keep)) sel.value = keep; else if (botExists("starter")) sel.value = "starter";
  if (!$("#clone-name").value) suggestCloneName();
}
function suggestCloneName() {
  const src = $("#clone-source").value;
  if (!src) return;
  const dir = src.includes("/") ? src.slice(0, src.lastIndexOf("/") + 1) : "";
  const base = botName(src).replace(/_v\d+$/, "");
  let k = 2;
  while (botExists(`${dir}${base}_v${k}`)) k++;
  $("#clone-name").value = `${base}_v${k}`;
}
$("#clone-source").addEventListener("change", suggestCloneName);
$("#clone-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const msg = $("#clone-msg");
  const name = $("#clone-name").value.trim();
  msg.hidden = false;
  if (!/^[A-Za-z0-9_-]{1,64}$/.test(name)) { msg.className = "msg err"; msg.textContent = "Use only letters, digits, underscore and hyphen."; return; }
  try {
    const res = await api("/api/clone", { source: $("#clone-source").value, name });
    await loadBots();
    msg.className = "msg ok";
    msg.innerHTML = `Created <code>${esc(res.path)}/</code>. Edit <code>${esc(res.path)}/agent.py</code> in your editor; it is now in every seat's dropdown.`;
    $("#clone-name").value = ""; suggestCloneName();
  } catch (err) { msg.className = "msg err"; msg.textContent = err.message; }
});

// ------------------------------------------------------------------ settings & run
const settingsFields = { tables: "#s-tables", seed: "#s-seed", hand_cap: "#s-handcap", hands_per_level: "#s-hpl", payouts: "#s-payouts", stack: "#s-stack" };
function readSettings() {
  const out = {};
  for (const [k, sel] of Object.entries(settingsFields)) out[k] = $(sel).value.trim();
  return out;
}
function writeSettings(s) {
  for (const [k, sel] of Object.entries(settingsFields)) if (s[k] !== undefined) $(sel).value = Array.isArray(s[k]) ? s[k].join(" ") : s[k];
}
writeSettings(store.get("settings", {}));
Object.values(settingsFields).forEach((sel) => $(sel).addEventListener("change", () => store.set("settings", readSettings())));
$("#seed-random").addEventListener("click", () => { $("#s-seed").value = Math.random().toString(16).slice(2, 10); store.set("settings", readSettings()); });

$("#run").addEventListener("click", async () => {
  $("#run-error").hidden = true;
  const missing = S.lineup.filter((p) => !botExists(p));
  if (missing.length) return showRunError(`Missing bot folder(s): ${missing.join(", ")}. Pick another bot or press Refresh bots.`);
  try {
    const res = await api("/api/runs", { lineup: S.lineup, ...readSettings() });
    store.set("settings", readSettings());
    S.active = res.id; S.selected = res.id;
    setRunning(true);
    await refreshHistory();
    showTab("results");
    poll();
  } catch (err) { showRunError(err.message); }
});
$("#cancel").addEventListener("click", () => { if (S.active) api(`/api/runs/${S.active}/cancel`, {}).catch(() => {}); });
function showRunError(text) { const box = $("#run-error"); box.textContent = text; box.hidden = false; }
function setRunning(on) {
  $("#run").disabled = on; $("#run").textContent = on ? "Running…" : "Run match";
  $("#cancel").hidden = !on; $("#progress").hidden = !on && !S.active;
}

async function poll() {
  if (!S.active) return;
  let run;
  try { run = await api(`/api/runs/${S.active}`); } catch (err) { showRunError(err.message); S.active = null; setRunning(false); return; }
  const total = run.settings.tables;
  $("#progress").hidden = false;
  $("#progress-fill").style.width = `${(100 * run.done) / total}%`;
  const secs = run.started ? ((run.finished || Date.now() / 1000) - run.started).toFixed(1) : "0.0";
  $("#progress-text").textContent = `${run.status === "queued" ? "queued" : `${fmt(run.done)} / ${fmt(total)} tables`} · ${secs}s`;
  if (run.status === "queued" || run.status === "running") {
    if (S.selected === run.id) renderResult(run);
    setTimeout(poll, 300);
    return;
  }
  S.active = null;
  setRunning(false);
  if (run.status === "error") showRunError(`Run #${run.id} failed:\n${run.error}`);
  S.full[run.id] = run;
  await refreshHistory();
  if (S.selected === run.id) renderResult(run);
  syncReplayRuns();
}

// ------------------------------------------------------------------ history & results
async function refreshHistory() {
  const data = await api("/api/runs");
  S.runs = data.runs;
  const tb = $("#history");
  $("#history-empty").hidden = S.runs.length > 0;
  tb.innerHTML = S.runs.map((r) => {
    const e0 = r.results?.entries?.[0];
    const failed = r.results ? r.results.entries.reduce((a, e) => a + e.failed_decisions, 0) : null;
    const lineup = r.settings.lineup.map(botName).join(", ");
    return `<tr class="clickable${r.id === S.selected ? " selected" : ""}" data-run="${r.id}">
      <td>${r.id}</td><td>${esc(new Date(r.created * 1000).toLocaleTimeString())}</td>
      <td class="lineup" title="${esc(lineup)}">${esc(lineup)}</td><td><code>${esc(r.settings.seed)}</code></td>
      <td class="num">${fmt(r.done)}${r.done !== r.settings.tables ? ` / ${fmt(r.settings.tables)}` : ""}</td>
      <td class="status-${r.status}">${r.status}</td>
      <td class="num">${e0 ? `${fx(e0.average_points)} <span class="pm">±${fx(e0.se, 1)}</span>` : ""}</td>
      <td class="num ${failed ? "fail" : "zero"}">${failed ?? ""}</td></tr>`;
  }).join("");
  tb.querySelectorAll("tr").forEach((tr) => tr.addEventListener("click", () => selectRun(Number(tr.dataset.run))));
  fillRunSelects();
}

async function selectRun(id) {
  S.selected = id;
  document.querySelectorAll("#history tr").forEach((tr) => tr.classList.toggle("selected", Number(tr.dataset.run) === id));
  const run = S.full[id] || (await api(`/api/runs/${id}`));
  if (["done", "cancelled", "error"].includes(run.status)) S.full[id] = run;
  renderResult(run);
}

function meter(mean, se, par, max) {
  const pct = (v) => Math.max(0, Math.min(100, (100 * v) / max));
  const lo = Math.min(mean, par), hi = Math.max(mean, par);
  return `<div class="meter" title="par ${fx(par, 1)}; bar = points/table; whisker = ±1 SE">
    <div class="fill ${mean >= par ? "up" : "down"}" style="left:${pct(lo)}%;width:${pct(hi) - pct(lo)}%"></div>
    <div class="err" style="left:${pct(mean - se)}%;width:${pct(mean + se) - pct(mean - se)}%"></div>
    <div class="par" style="left:${pct(par)}%"></div></div>`;
}

function renderResult(run) {
  const view = $("#result-view");
  const s = run.settings;
  const meta = `<div class="result-meta"><span>Run <b>#${run.id}</b></span><span>seed <b>${esc(s.seed)}</b></span>
    <span><b>${fmt(run.done)}</b>${run.done !== s.tables ? ` of ${fmt(s.tables)}` : ""} tables</span><span>hand cap <b>${s.hand_cap}</b></span>
    <span><b>${s.hands_per_level}</b> hands/level</span><span>payouts <b>${s.payouts.join("/")}</b></span><span>stack <b>${fmt(s.stack)}</b></span>
    ${run.results ? `<span><b>${run.results.seconds}</b> s</span>` : ""}</div>`;
  if (!run.results) {
    view.innerHTML = `<div class="card">${meta}<p class="empty">${run.status === "error" ? `<span class="status-error">Run failed.</span><pre class="error-box">${esc(run.error)}</pre>` : run.status === "cancelled" ? "Cancelled before any table finished." : "Running… results appear when the run finishes."}</p></div>`;
    return;
  }
  const r = run.results;
  const maxPts = Math.max(...s.payouts, ...r.entries.map((e) => e.average_points + e.se));
  const failed = r.entries.filter((e) => e.failed_decisions > 0);
  const totalFailed = failed.reduce((a, e) => a + e.failed_decisions, 0);
  const banner = totalFailed
    ? `<div class="fail-banner" role="alert">${fmt(totalFailed)} FAILED DECISION${totalFailed === 1 ? "" : "S"} — ${failed.map((e) => `${esc(e.label)}: ${e.failed_decisions}`).join(", ")}
        <small>Each one was played as check/fold. Fix before uploading. Details below the table.</small></div>`
    : `<div class="ok-banner">No failed decisions.</div>`;
  const rows = r.entries.map((e, i) => {
    const p = e.latency_us;
    return `<tr class="${e.failed_decisions ? "has-fail" : ""}">
      <td>#${i}</td><td><span class="botname" title="${esc(e.bot)}">${esc(botName(e.bot))}</span> <span class="botpath">${esc(e.bot)}</span></td>
      <td class="num"><b>${fx(e.average_points)}</b></td><td class="num pm">±${fx(e.se)}</td>
      <td class="num ${e.vs_par > 2 * e.se ? "pos" : e.vs_par < -2 * e.se ? "neg" : ""}">${signed(e.vs_par)}</td>
      <td>${meter(e.average_points, e.se, r.par, maxPts)}</td>
      <td class="num">${fx(100 * e.finish_rates["1"], 1)}%</td><td class="num">${fx(100 * e.finish_rates["2"], 1)}%</td><td class="num">${fx(100 * e.finish_rates["3"], 1)}%</td>
      <td class="num ${e.failed_decisions ? "fail" : "zero"}">${fmt(e.failed_decisions)}</td>
      <td class="num">${fx(p.p50, 0)}</td><td class="num ${p["p99.9"] > 1000 ? "slow" : ""}">${fx(p["p99.9"], 0)}</td><td class="num ${p.max > 1000 ? "slow" : ""}">${fmt(Math.round(p.max))}</td></tr>`;
  }).join("");
  const multi = r.by_bot.length < r.entries.length;
  const byBot = `<div class="card by-bot"><h2>By bot${multi ? "" : " (one seat each)"}</h2><div class="table-wrap"><table>
      <thead><tr><th>Bot</th><th class="num">Seats</th><th class="num">Points / table (avg of its seats)</th><th class="num">± SE</th><th class="num">vs par</th><th class="num">Failed</th></tr></thead>
      <tbody>${r.by_bot.map((b) => `<tr><td><span class="botname">${esc(botName(b.bot))}</span> <span class="botpath">${esc(b.bot)}</span></td><td class="num">${b.seats}</td>
      <td class="num"><b>${fx(b.average_points)}</b></td><td class="num pm">±${fx(b.se)}</td><td class="num ${b.vs_par > 2 * b.se ? "pos" : b.vs_par < -2 * b.se ? "neg" : ""}">${signed(b.vs_par)}</td>
      <td class="num ${b.failed_decisions ? "fail" : "zero"}">${fmt(b.failed_decisions)}</td></tr>`).join("")}</tbody></table></div></div>`;
  const notes = failed.length ? `<details class="failures" open><summary>Failure details (first ${5} per entry)</summary>${failed.map((e) =>
      e.failure_notes.map((n) => `<p><b>${esc(e.label)}</b> · table ${n.table}, hand ${n.hand} · <b>${esc(n.reason)}</b></p><pre>${esc(n.detail)}</pre>`).join("")).join("")}</details>` : "";
  view.innerHTML = `<div class="card">
      <div class="card-head"><h2>Results</h2><button id="use-lineup" class="ghost small" type="button">Load this line-up &amp; settings</button></div>
      ${meta}${run.status === "cancelled" ? `<p class="warnline">Cancelled: results cover the ${run.done} finished tables.</p>` : ""}${banner}
      <div class="table-wrap"><table>
        <thead><tr><th>Entry</th><th>Bot</th><th class="num">Pts / table</th><th class="num">± SE</th><th class="num">vs par ${fx(r.par, 1)}</th><th></th>
          <th class="num">1st</th><th class="num">2nd</th><th class="num">3rd</th><th class="num">Failed</th>
          <th class="num" title="decision time, microseconds">p50 µs</th><th class="num">p99.9 µs</th><th class="num">max µs</th></tr></thead>
        <tbody>${rows}</tbody></table></div>
      ${notes}
      <p class="note">± is one standard error of the mean. Green/red vs par means more than 2 SE from par. The decision limit is 1,000 µs (100 ms time bank per table); in-process timing here is optimistic.</p>
    </div>${byBot}`;
  $("#use-lineup").addEventListener("click", () => {
    S.lineup = s.lineup.slice(); saveLineup(); renderSeats(); renderPresets();
    writeSettings({ ...s, payouts: s.payouts }); store.set("settings", readSettings());
    flash($("#use-lineup"), "Loaded");
  });
}

// ------------------------------------------------------------------ compare
function runLabel(r) { return `#${r.id} · ${r.settings.lineup.map(botName).slice(0, 3).join(", ")}${r.settings.lineup.length > 3 ? "…" : ""} · seed ${r.settings.seed} · ${r.done} t`; }
function fillRunSelects() {
  const done = S.runs.filter((r) => r.results);
  for (const [sel, idx] of [["#cmp-a", 1], ["#cmp-b", 0]]) {
    const el = $(sel), keep = el.value;
    el.innerHTML = done.map((r) => `<option value="${r.id}">${esc(runLabel(r))}</option>`).join("");
    if (done.some((r) => String(r.id) === keep) && el.dataset.touched) el.value = keep;
    else if (done[idx]) el.value = done[idx].id;
  }
  if (!$("#tab-compare").hidden) renderCompare();
}
["#cmp-a", "#cmp-b"].forEach((sel) => $(sel).addEventListener("change", (e) => { e.target.dataset.touched = "1"; renderCompare(); }));

async function renderCompare() {
  const view = $("#compare-view");
  const a = $("#cmp-a").value, b = $("#cmp-b").value;
  if (!a || !b || a === b) { view.innerHTML = `<p class="empty">${S.runs.filter((r) => r.results).length < 2 ? "Run at least two matches to compare them." : "Pick two different runs."}</p>`; return; }
  let c;
  try { c = await api(`/api/compare?a=${a}&b=${b}`); } catch (err) { view.innerHTML = `<p class="error-box">${esc(err.message)}</p>`; return; }
  const diffSettings = Object.entries(c.same_settings).filter(([, same]) => !same).map(([k]) => k);
  const rows = c.rows.map((row) => {
    const A = row.a, B = row.b;
    let verdict = "";
    if (row.diff !== undefined) {
      const z = row.se > 0 ? row.diff / row.se : 0;
      verdict = Math.abs(z) >= 2 ? `<span class="verdict ${z > 0 ? "better" : "worse"}">B ${z > 0 ? "better" : "worse"} (${fx(Math.abs(z), 1)} SE)</span>` : `<span class="verdict">within noise</span>`;
    }
    const changed = A && B && A.bot !== B.bot;
    return `<tr><td>#${row.seat}</td>
      <td>${A ? `${esc(botName(A.bot))}` : "—"}</td><td class="num">${A ? fx(A.average_points) : ""}</td>
      <td>${B ? `${changed ? "<b>" : ""}${esc(botName(B.bot))}${changed ? "</b>" : ""}` : "—"}</td><td class="num">${B ? fx(B.average_points) : ""}</td>
      <td class="num ${row.diff > 0 ? "pos" : row.diff < 0 ? "neg" : ""}">${row.diff !== undefined ? signed(row.diff) : ""}</td>
      <td class="num pm">${row.se !== undefined ? "±" + fx(row.se) : ""}</td><td>${verdict}</td>
      <td class="num ${(A?.failed_decisions || 0) + (B?.failed_decisions || 0) ? "fail" : "zero"}">${A ? A.failed_decisions : "-"} / ${B ? B.failed_decisions : "-"}</td></tr>`;
  }).join("");
  view.innerHTML = `
    ${c.paired ? `<p class="note">Same seed and table count: differences are <b>paired by table</b> (same deals and seat draws), so the error bars are much tighter than comparing averages.</p>`
      : `<p class="warnline">Different seed or table count: comparison is unpaired and much noisier. Re-run with the same seed for a fair A/B.</p>`}
    ${diffSettings.length ? `<p class="warnline">Settings differ: ${esc(diffSettings.join(", "))}.</p>` : ""}
    <div class="table-wrap"><table>
      <thead><tr><th>Entry</th><th>A bot</th><th class="num">A pts</th><th>B bot</th><th class="num">B pts</th><th class="num">B − A</th><th class="num">± SE</th><th>Verdict</th><th class="num">Failed A / B</th></tr></thead>
      <tbody>${rows}</tbody></table></div>
    <p class="note">Bold B bot = the seat was swapped between runs. "Better/worse" needs at least 2 standard errors; anything less is noise, so add tables.</p>`;
}

// ------------------------------------------------------------------ replay
const R = { run: null, tables: [], table: null, hands: [], handIdx: 0, list: [], steps: [], step: 0, timer: null };
const RANKS = { T: "10" };
const SUITS = { s: ["♠", false], h: ["♥", true], d: ["♦", true], c: ["♣", false] };
function card(c, cls = "") {
  if (!c) return `<span class="pc slot ${cls}"></span>`;
  const [sym, red] = SUITS[c[1]] || ["?", false];
  const rank = RANKS[c[0]] || c[0];
  return `<span class="pc ${red ? "red" : ""} ${cls}" aria-label="${rank} of ${{ s: "spades", h: "hearts", d: "diamonds", c: "clubs" }[c[1]]}"><span>${rank}</span><span class="s">${sym}</span></span>`;
}

function syncReplayRuns() {
  const sel = $("#rp-run");
  const runs = S.runs.filter((r) => r.results && r.replay_tables > 0);
  const keep = sel.value;
  sel.innerHTML = runs.map((r) => `<option value="${r.id}">${esc(runLabel(r))}</option>`).join("");
  $("#replay-empty").hidden = runs.length > 0;
  if (!runs.length) { $("#replay-body").hidden = true; return; }
  const want = runs.some((r) => String(r.id) === keep) && sel.dataset.touched ? keep
    : runs.some((r) => r.id === S.selected) ? String(S.selected) : String(runs[0].id);
  sel.value = want;
  if (String(R.run) !== want) loadReplayRun(Number(want));
}
$("#rp-run").addEventListener("change", (e) => { e.target.dataset.touched = "1"; loadReplayRun(Number(e.target.value)); });

async function loadReplayRun(id) {
  stopPlay();
  R.run = id;
  const data = await api(`/api/runs/${id}/replays`);
  R.tables = data.tables;
  $("#rp-table").innerHTML = R.tables.map((t) => {
    const first = t.places.indexOf(1);
    return `<option value="${t.table}">Table ${t.table} · 1st ${esc(t.seats[first].label)} · ${t.hand_count} hands${t.failures.some((f) => f) ? " · FAILED DECISIONS" : ""}</option>`;
  }).join("");
  if (R.tables.length) await loadReplayTable(R.tables[0].table);
}
$("#rp-table").addEventListener("change", (e) => loadReplayTable(Number(e.target.value)));
$("#rp-notable").addEventListener("change", () => { const cur = R.hands[R.handIdx]?.hand; buildHandList(); selectHand(Math.max(0, R.list.indexOf(R.hands.findIndex((h) => h.hand === cur)))); });

async function loadReplayTable(tableNo) {
  stopPlay();
  const t = await api(`/api/runs/${R.run}/replays/${tableNo}`);
  R.table = t;
  R.hands = t.hands;
  R.meta = R.hands.map((h) => buildSteps(h, t));
  R.tableChipsOk = R.meta.every((m) => m.ok);
  $("#rp-table").value = String(tableNo);
  $("#replay-body").hidden = false;
  buildHandList();
  selectHand(0);
}

function seatName(seat) { return R.table.seats[seat].label; }

// Rebuild every intermediate state of a hand from its start stacks and events.
function buildSteps(h, t) {
  const n = h.start.length;
  const total = h.start.reduce((a, b) => a + b, 0);
  const st = { stack: h.start.slice(), bet: Array(n).fill(0), pot: 0, board: [], folded: Array(n).fill(false), shown: Array(n).fill(false), act: Array(n).fill(""), won: Array(n).fill(0), acting: null, newCards: 0 };
  const snap = (text, kind) => ({ ...st, stack: st.stack.slice(), bet: st.bet.slice(), board: st.board.slice(), folded: st.folded.slice(), shown: st.shown.slice(), act: st.act.slice(), won: st.won.slice(), text, kind, chips: st.stack.reduce((a, b) => a + b, 0) + st.bet.reduce((a, b) => a + b, 0) + st.pot });
  const steps = [snap(`Hand ${h.hand} dealt · button ${esc(seatName(h.button))}`, "hand")];
  let blinds = 0, allin = false, showdown = false, ok = true;
  const collect = () => { st.pot += st.bet.reduce((a, b) => a + b, 0); st.bet.fill(0); };
  const names = ["Flop", "Turn", "River"];
  for (const [kind, seat, amount, cards] of h.events) {
    st.acting = seat; st.newCards = 0;
    let text = null;
    const nm = seat == null ? "" : esc(seatName(seat));
    if (kind === "hand" || kind === "stack") {
      if (kind === "stack" && st.stack[seat] !== amount) ok = false;
      continue;
    } else if (kind === "blind") {
      st.stack[seat] -= amount; st.bet[seat] += amount;
      const which = blinds++ === 0 ? "small blind" : "big blind";
      st.act[seat] = `${which === "small blind" ? "SB" : "BB"} ${fmt(amount)}`;
      text = `${nm} posts ${which} ${fmt(amount)}${st.stack[seat] === 0 ? " (all-in)" : ""}`;
    } else if (kind === "fold") {
      st.folded[seat] = true; st.act[seat] = "fold"; text = `${nm} folds`;
    } else if (kind === "check") {
      st.act[seat] = "check"; text = `${nm} checks`;
    } else if (kind === "call") {
      st.stack[seat] -= amount; st.bet[seat] += amount;
      st.act[seat] = `call ${fmt(amount)}`; text = `${nm} calls ${fmt(amount)}${st.stack[seat] === 0 ? " (all-in)" : ""}`;
    } else if (kind === "raise") {
      const high = Math.max(...st.bet);
      st.stack[seat] -= amount - st.bet[seat]; st.bet[seat] = amount;
      const verb = high === 0 ? "bets" : "raises to";
      st.act[seat] = `${verb === "bets" ? "bet" : "raise to"} ${fmt(amount)}`;
      text = `${nm} ${verb} ${fmt(amount)}${st.stack[seat] === 0 ? " (all-in)" : ""}`;
    } else if (kind === "return") {
      st.stack[seat] += amount; st.bet[seat] -= amount; text = `Uncalled ${fmt(amount)} returned to ${nm}`;
    } else if (kind === "board") {
      collect(); st.board.push(...cards); st.newCards = cards.length; st.act.fill(""); st.acting = null;
      text = `${names[Math.min(2, st.board.length - 3)]}: ${cards.map((c) => card(c)).join(" ")}`;
    } else if (kind === "show") {
      st.shown[seat] = true; showdown = true; text = `${nm} shows ${cards.map((c) => card(c)).join(" ")}`;
    } else if (kind === "win" || kind === "leftover") {
      collect(); st.pot -= amount; st.stack[seat] += amount; st.won[seat] += amount;
      text = kind === "win" ? `${nm} wins ${fmt(amount)}` : `${nm} gets ${fmt(amount)} left over`;
    } else {
      text = `${kind} ${nm} ${amount}`;
    }
    if (st.stack.some((v, i) => v === 0 && h.start[i] > 0)) allin = true;
    if (Math.min(...st.stack) < 0) ok = false;
    const sp = snap(text, kind);
    if (sp.chips !== total) ok = false;
    steps.push(sp);
  }
  const last = steps[steps.length - 1];
  if (last.stack.some((v, i) => v !== h.end[i]) || last.pot !== 0) ok = false;
  const busts = h.start.map((v, i) => (v > 0 && h.end[i] === 0 ? i : -1)).filter((i) => i >= 0);
  last.busts = busts;
  const winners = last.won.map((v, i) => [i, v]).filter(([, v]) => v > 0);
  const pot = winners.reduce((a, [, v]) => a + v, 0);
  return { steps, ok, total, allin, showdown, busts, winners, pot };
}

function buildHandList() {
  const notable = $("#rp-notable").checked;
  R.list = R.hands.map((_, i) => i).filter((i) => !notable || R.meta[i].showdown || R.meta[i].allin || R.meta[i].busts.length);
  if (!R.list.length) R.list = R.hands.map((_, i) => i);
  $("#rp-hand").innerHTML = R.list.map((i, k) => {
    const h = R.hands[i], m = R.meta[i];
    const w = m.winners.map(([s]) => seatName(s)).join(" & ");
    const flags = [m.showdown ? "showdown" : "", m.busts.length ? "bust: " + m.busts.map(seatName).join(", ") : ""].filter(Boolean).join(" · ");
    return `<option value="${k}">Hand ${h.hand} · ${h.blinds[0]}/${h.blinds[1]} · pot ${fmt(m.pot)} · ${esc(w)}${flags ? " · " + esc(flags) : ""}</option>`;
  }).join("");
}
$("#rp-hand").addEventListener("change", (e) => { stopPlay(); selectHand(Number(e.target.value)); });

function selectHand(k, atEnd = false) {
  R.pos = Math.max(0, Math.min(R.list.length - 1, k));
  R.handIdx = R.list[R.pos];
  R.steps = R.meta[R.handIdx].steps;
  R.step = atEnd ? R.steps.length - 1 : 0;
  $("#rp-hand").value = String(R.pos);
  renderLog();
  renderStep();
}

function seatPos(i, n, rx, ry) {
  const a = Math.PI / 2 + (2 * Math.PI * i) / n;
  return [50 + rx * Math.cos(a), 50 + ry * Math.sin(a)];
}

function renderStep() {
  const h = R.hands[R.handIdx], m = R.meta[R.handIdx], sp = R.steps[R.step], t = R.table;
  const n = h.start.length;
  const final = R.step === R.steps.length - 1;
  const sbSeat = h.events.find((e) => e[0] === "blind")?.[1];
  const bbSeat = h.events.filter((e) => e[0] === "blind")[1]?.[1];
  let html = "";
  for (let i = 0; i < n; i++) {
    const [x, y] = seatPos(i, n, 41, 38);
    const out = h.start[i] === 0;
    const cards = h.hole[String(i)] || [];
    const tags = [];
    if (i === h.button) tags.push(`<span class="tag btn">BTN</span>`);
    if (i === sbSeat) tags.push(`<span class="tag">SB</span>`);
    if (i === bbSeat) tags.push(`<span class="tag">BB</span>`);
    if (out) tags.push(`<span class="tag">OUT</span>`);
    else if (sp.folded[i]) tags.push(`<span class="tag fold">FOLDED</span>`);
    else if (sp.stack[i] === 0 && !(final && sp.won[i] === 0 && m.busts.includes(i))) tags.push(`<span class="tag allin">ALL-IN</span>`);
    if (final && m.busts.includes(i)) tags.push(`<span class="tag bust">BUSTED</span>`);
    if (sp.won[i]) tags.push(`<span class="tag won">WON ${fmt(sp.won[i])}</span>`);
    const cls = ["seat", out ? "out" : "", sp.folded[i] ? "folded" : "", sp.acting === i && !final ? "acting" : "", sp.won[i] ? "winner" : ""].join(" ");
    html += `<div class="${cls}" style="left:${x}%;top:${y}%" data-seat="${i}">
      <div class="nm" title="${esc(t.seats[i].bot)}">${esc(t.seats[i].label)}</div>
      <div class="stk">${out ? "—" : fmt(sp.stack[i])}</div>
      <div class="hole">${out ? "" : cards.map((c) => card(c)).join("")}</div>
      <div class="tags">${tags.join("")}</div>
      <div class="act">${esc(sp.act[i])}</div></div>`;
    if (sp.bet[i]) {
      const [bx, by] = seatPos(i, n, 25, 20);
      html += `<div class="bet" style="left:${bx}%;top:${by}%">${fmt(sp.bet[i])}</div>`;
    }
  }
  $("#rp-seats").innerHTML = html;
  const board = [0, 1, 2, 3, 4].map((k) => card(sp.board[k], `big${k >= sp.board.length - sp.newCards && k < sp.board.length ? " new" : ""}`)).join("");
  $("#rp-board").innerHTML = board;
  $("#rp-pot").textContent = `Pot ${fmt(sp.pot + sp.bet.reduce((a, b) => a + b, 0))}`;
  $("#rp-level").textContent = `Table ${t.table} · Hand ${h.hand} · Level ${h.level + 1} · Blinds ${fmt(h.blinds[0])}/${fmt(h.blinds[1])}`;
  $("#rp-step").textContent = `step ${R.step} / ${R.steps.length - 1} · hand ${R.pos + 1} of ${R.list.length}`;
  const chip = $("#rp-chips");
  chip.dataset.ok = String(R.tableChipsOk);
  chip.className = "hint chips-check" + (sp.chips === m.total && R.tableChipsOk ? "" : " bad");
  chip.textContent = sp.chips === m.total
    ? `Chips in play: ${fmt(sp.chips)} (constant). ${R.tableChipsOk ? `All ${R.hands.length} hands on this table conserve chips.` : "WARNING: some hand on this table does not conserve chips."}`
    : `CHIP MISMATCH: ${fmt(sp.chips)} in play, expected ${fmt(m.total)}`;
  document.querySelectorAll("#rp-log li").forEach((li, k) => {
    li.classList.toggle("current", k === R.step);
    li.classList.toggle("future", k > R.step);
  });
  document.querySelector("#rp-log li.current")?.scrollIntoView({ block: "nearest" });
  $("#rp-prev").disabled = R.step === 0 && R.pos === 0;
  $("#rp-next").disabled = final && R.pos === R.list.length - 1;
}

function renderLog() {
  $("#rp-log").innerHTML = R.steps.map((s, k) => `<li data-step="${k}"><span class="k">${k}</span><span>${s.text}</span></li>`).join("");
  document.querySelectorAll("#rp-log li").forEach((li) => li.addEventListener("click", () => { stopPlay(); R.step = Number(li.dataset.step); renderStep(); }));
}

function stepBy(d) {
  const next = R.step + d;
  if (next < 0) { if (R.pos > 0) selectHand(R.pos - 1, true); return false; }
  if (next >= R.steps.length) { if (R.pos < R.list.length - 1) { selectHand(R.pos + 1); return true; } return false; }
  R.step = next; renderStep(); return true;
}
function stopPlay() { clearTimeout(R.timer); R.timer = null; $("#rp-play").innerHTML = "▶ Play"; }
function tick() {
  const atEnd = R.step === R.steps.length - 1;
  if (!stepBy(1)) { stopPlay(); return; }
  const delay = Number($("#rp-speed").value);
  R.timer = setTimeout(tick, atEnd ? delay * 0.5 : R.step === R.steps.length - 1 ? delay * 2.5 : delay);
}
$("#rp-play").addEventListener("click", () => {
  if (R.timer) { stopPlay(); return; }
  $("#rp-play").innerHTML = "⏸ Pause";
  R.timer = setTimeout(tick, 150);
});
$("#rp-prev").addEventListener("click", () => { stopPlay(); stepBy(-1); });
$("#rp-next").addEventListener("click", () => { stopPlay(); stepBy(1); });
$("#rp-prev-hand").addEventListener("click", () => { stopPlay(); selectHand(R.pos - 1); });
$("#rp-next-hand").addEventListener("click", () => { stopPlay(); selectHand(R.pos + 1); });
document.addEventListener("keydown", (e) => {
  if ($("#tab-replay").hidden || $("#replay-body").hidden) return;
  if (["INPUT", "SELECT", "TEXTAREA"].includes(document.activeElement?.tagName)) return;
  if (e.key === "ArrowRight") { stopPlay(); stepBy(1); }
  else if (e.key === "ArrowLeft") { stopPlay(); stepBy(-1); }
  else if (e.key === " ") { e.preventDefault(); $("#rp-play").click(); }
  else if (e.key === "PageDown") { e.preventDefault(); stopPlay(); selectHand(R.pos + 1); }
  else if (e.key === "PageUp") { e.preventDefault(); stopPlay(); selectHand(R.pos - 1); }
  else return;
});

// ------------------------------------------------------------------ start
(async function init() {
  try {
    await loadBots();
    await refreshHistory();
    const running = S.runs.find((r) => r.status === "running" || r.status === "queued");
    if (running) { S.active = running.id; S.selected = running.id; setRunning(true); poll(); }
    else if (S.runs.length) await selectRun(S.runs[0].id);
    showTab(store.get("tab", "results"));
  } catch (err) {
    showRunError("Cannot reach the server: " + err.message);
  }
})();
