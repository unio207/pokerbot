"use strict";
// Pokerbot practice UI. Plain JS, no build step, no external resources.

const $ = (sel) => document.querySelector(sel);
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const fmt = (n) => Number(n).toLocaleString("en-US");
const fx = (n, d = 2) => Number(n).toFixed(d);
const pct = (v) => (v == null ? "–" : `${Math.round(100 * v)}%`);

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

const MIN_SEATS = 2, MAX_SEATS = 10;
const S = {
  bots: [],
  lineup: null,      // one entry per seat: a bot path, or null for an empty seat (filled seats first)
  info: null,        // bot path whose description is shown
  runs: [],          // summaries, newest first
  session: { runs: 0, tables: 0 },
  full: {},          // id -> full run (when finished)
  selected: null,    // run id shown in Results
  active: null,      // run id being polled
};
const E = { kit: null, variants: {} };
const variantTitle = (v) => (v === "kit" ? "organizers' kit" : E.variants[v] || v);

// ------------------------------------------------------------------ glossary
// Every hover explanation on the page lives here: key -> { label?, text }. `text` is a
// string, or a function of the hovered element when it quotes numbers from the page.
// Attach one with data-term="key" (see term() below); the tooltip code finds it by itself.
const shownRun = () => S.shown || {};
const seatsIn = (run) => run.results?.entries.length || run.settings?.lineup.length || 8;
const share = (v) => `${Math.round(v * 10) / 10}%`;
const VARIANT_TEXT = {
  holdem: "Standard hold'em: each bot gets 2 private cards and makes its best five-card hand from those and 5 shared cards.",
  discard_reveal: "Discard and reveal: each bot gets 3 private cards. After the first three shared cards it throws one away face down and turns one of the other two face up for all to see.",
  short_deck: "Short deck: the 2s to 5s are taken out, leaving 36 cards. A flush beats a full house, and the ace counts as a low card only in A-6-7-8-9.",
  omaha: "Omaha: each bot gets 4 private cards and must use exactly 2 of them with exactly 3 of the shared cards.",
  auction: "Auction: after the first three shared cards every bot secretly bids chips for an extra private card. The highest bidder gets it and pays the second-highest bid into the pot.",
  kit: "The variant built into the organizers' kit.",
};
const TERMS = {
  // ---- header and match settings
  mini: { label: "Mini simulator", text: "Our own quick imitation of the tournament, used when the organizers' kit is not installed. Its rules are our best guess, and its time checks are kinder than the real ones, so a bot that is just fast enough here may be too slow there." },
  kit: { label: "Organizers' kit", text: "Matches are played by the organizers' own program, so the rules are the real ones." },
  engine: { text: "Which program plays the matches. The organizers' kit has the real tournament rules. The mini simulator is our own unofficial imitation; only it offers the variants, varied rules and the built-in hand replay." },
  variant: { text: (el) => `Which version of poker is played. The real one is only announced on the day. ${VARIANT_TEXT[el.dataset.variant || $("#s-variant").value] || ""}` },
  tables: { text: () => {
    const n = Number($("#s-tables").value) || 0;
    return `How many separate games to play. One table is one whole game: it runs until one bot holds every chip or the hand cap is reached. More tables means less luck in the results${n > 0 ? `: with ${fmt(n)} tables, gaps smaller than about ${Math.max(1, Math.round(40 / Math.sqrt(n)))} points per table are just noise` : ""}.`;
  } },
  run_tables: { text: "Tables finished in this run. Each table is one whole game between all the bots in the line-up." },
  seed: { text: "A name for one particular set of shuffles. The same seed with the same settings deals the same cards and seating again, so a match can be repeated exactly. A different seed gives different deals." },
  newseed: { text: "Picks a fresh random seed each time you press Run, so every run gets new deals. Untick it to replay the same deals, for example to compare two versions of a bot fairly." },
  vary: { label: "Varied rules", text: "Each seed becomes a slightly different tournament: it picks the hand cap (150 to 300), the hands per level (15 to 25) and the starting stack (1,500 to 3,000), and every table draws its own payouts. This catches bots that assume 2,000 chips and 50/30/20 instead of reading the rules they are handed." },
  handcap: { label: "Hand cap", text: "The most hands one table may play. If several bots still have chips then, the points not yet awarded are shared between them by chip count (a formula called ICM). The official value is 250." },
  hpl: { label: "Hands per level", text: "The blinds (forced bets) go up after this many hands, so waiting gets more and more expensive. They start at 10 and 20. The official value is 20 hands." },
  payouts: { label: "Payouts", text: "Points a table awards for finishing 1st, 2nd, 3rd and so on (in the settings, type them with spaces between). Places not listed score 0. The official default is 50, 30, 20." },
  payouts_drawn: { label: "Payouts drawn per table", text: "Every table picks its own points for 1st, 2nd and 3rd place. They always add up to 100, with 40 to 60 for first. The Hand replay tab shows each table's payouts." },
  stack: { label: "Starting stack", text: "Chips each bot starts every table with. The official value is 2,000, which is 100 times the first big blind of 20." },
  // ---- line-up
  lineup: { text: "The bots that sit down at every table. Seating is reshuffled for each table, so the order here does not matter. The same bot can be added more than once." },
  seats: { text: "How many bots play at each table (2 to 10). The tournament seats 8." },
  seat_no: { label: "Entry number", text: "Added to the bot's name in the results (for example starter#0) so two copies of the same bot can be told apart. It is not a position at the table." },
  fill: { text: (el) => `Puts a randomly chosen bot from “${groupTitle(el.dataset.fill)}” in every empty seat.` },
  bot_warn: { text: "This bot fails the upload check, for example because it imports something the tournament machines do not have. Click the bot to read the problem." },
  // ---- results
  session: { text: () => `Totals since this server was started: ${fmt(S.session.runs)} finished run${S.session.runs === 1 ? "" : "s"} and ${fmt(S.session.tables)} tables played. Restarting the server sets them back to 0.` },
  entry: { text: "One seat in the line-up: the bot's folder name plus its entry number (#0, #1, …). Two copies of the same bot show up as two entries." },
  pts: { label: "Points per table", text: "The score: points earned per table, averaged over all tables of the run. The tournament ranks bots by this. The gray ± number is how uncertain it is: the true value is probably within about twice that number either way, and more tables make it smaller. Green or red means clearly better or worse than an average bot, not just luck." },
  pts_cell: { text: (el) => {
    const mean = Number(el.dataset.mean), se = Number(el.dataset.se), par = shownRun().results?.par;
    const verdict = par == null ? "" : mean - par > 2 * se ? "clearly better than an average bot" : mean - par < -2 * se ? "clearly worse than an average bot" : "not clearly different from an average bot: the gap could be luck";
    return `Scored ${fx(mean, 1)} points per table. Allowing for luck, the true value is probably between ${fx(mean - 2 * se, 1)} and ${fx(mean + 2 * se, 1)} (twice the ± number either way).${verdict ? ` Par is ${fx(par, 1)}, so this is ${verdict}.` : ""}`;
  } },
  par: { label: "Versus par", text: () => {
    const run = shownRun(), r = run.results, n = seatsIn(run);
    if (!r) return "Par is what an average bot scores: the points a table awards, split evenly between the seats.";
    const how = run.settings.engine === "kit" ? `the average of all ${n} entries` : `${fmt(Math.round(r.par * n))} points per table split between ${n} seats`;
    return `Par is what an average bot scores here: ${fx(r.par, 1)} points, which is ${how}. The tick marks par. The bar runs right in green when the bot beats par and left in red when it falls short. The thin line at the bar's end is the ± uncertainty: if it reaches back across the tick, the difference could be luck.`;
  } },
  win: { label: "Win", text: () => `Share of tables this bot finished in 1st place. With ${seatsIn(shownRun())} seats an average bot manages about ${share(100 / seatsIn(shownRun()))}.` },
  top3: { label: "Top 3", text: () => `Share of tables this bot finished 1st, 2nd or 3rd, usually the places that score points. With ${seatsIn(shownRun())} seats an average bot manages about ${share(Math.min(100, 300 / seatsIn(shownRun())))}.` },
  vpip: { label: "Plays", text: "How often this bot chooses to put chips in before the first three shared cards (forced bets do not count). Poker players call this VPIP. Around 15–30% is normal; 0% means it folds everything. Hover a number to see how often it raised." },
  vpip_cell: { text: (el) => `Before the first three shared cards, this bot chose to put chips in on ${pct(Number(el.dataset.vpip))} of the hands it was dealt (poker name: VPIP) and raised on ${pct(Number(el.dataset.pfr))} of all those hands (PFR). A raise counts in both numbers.` },
  slow: { label: "Slowest µs", text: "Nearly the slowest decision this bot made, in millionths of a second: only 1 decision in 1,000 took longer. The limit is 1,000 (one millisecond). Going over uses up a reserve of 100 milliseconds per table; once that is empty the bot loses its turn. Highlighted at 1,000 or more." },
  failed: { label: "Failed decisions", text: "Turns where the bot crashed, ran out of time, or answered with a move that is not allowed. The platform then checks if checking is free and folds otherwise. This should be 0. Click a red number for details." },
  failed_total: { text: "Failed decisions of all bots in the run added up: turns where a bot crashed, ran out of time or made a move that is not allowed. Should be 0." },
  inactive: { label: "Inactive", text: "This bot was dealt at least 50 hands and never once chose to put chips in: it only checked or folded. It probably does not support this variant, or it is broken." },
  topbot: { text: "The entry with the most points per table in that run." },
  // ---- hand replay
  notable: { text: "Lists only the hands where something big happened: cards were turned over at the end (a showdown), a bot bet all its chips (all-in), or a bot lost its last chips (a bust)." },
  rp_table: { text: "Only the first tables of a run (20 unless set otherwise) are recorded hand by hand. Each line shows who finished 1st and how many hands the table took." },
  rp_hand: { text: "Each line shows: hand number · the two blinds (forced bets) · chips won · who won them." },
  rp_payouts: { text: "Points this table awards for 1st, 2nd and 3rd place." },
  rp_places: { text: "How this table ended: the bots that finished 1st, 2nd and 3rd." },
  level: { label: "Level and blinds", text: () => {
    const h = R.hands[R.handIdx], every = S.runs.find((r) => r.id === R.run)?.settings.hands_per_level;
    return `Blinds are forced bets: before seeing their cards, two seats must put in ${fmt(h.blinds[0])} and ${fmt(h.blinds[1])}, so there is always something to win. The blinds go up${every ? ` every ${fmt(every)} hands` : " as the table goes on"}; each step is called a level.`;
  } },
  pot: { label: "Pot", text: "All the chips bet in this hand so far. Whoever wins the hand takes them." },
  board: { label: "Shared cards", text: "Face up for everyone to use: three at once (the flop), then a fourth (the turn) and a fifth (the river), with a round of betting after each." },
  seat_stack: { text: "Chips this bot has left right now, not counting what it has already bet in this hand." },
  hole: { text: "This bot's private cards. At a real table the other bots cannot see them; the replay shows everyone's." },
  discarded: { label: "Discard", text: "The private card this bot threw away (discard and reveal variant). The other bots never see it." },
  revealed: { label: "Reveal", text: "The private card this bot had to turn face up (discard and reveal variant). Every other bot can see it." },
  extra: { label: "Auction card", text: "The extra private card this bot got by winning the auction." },
  btn: { label: "Button", text: "Marks the dealer's seat, which moves on one seat every hand. The two seats after it pay the blinds, and once shared cards are out the button acts last in each betting round, which is an advantage." },
  sb: { label: "Small blind", text: "A forced bet, half the big blind, that this seat must put in before seeing its cards." },
  bb: { label: "Big blind", text: "The larger forced bet, paid by the seat after the small blind. It is the price the others must match to stay in the hand. Stack sizes are often counted in big blinds (BB)." },
  out: { label: "Out", text: "This bot lost all its chips in an earlier hand and no longer plays at this table." },
  folded: { label: "Fold", text: "Gives up this hand: the bot loses the chips it already put in and waits for the next hand." },
  allin: { label: "All-in", text: "The bot has bet every chip it has. It cannot act again in this hand, and it can win from each opponent no more than it put in itself." },
  busted: { label: "Busted", text: "Lost its last chips in this hand and is out of this table. The longer a bot lasts, the higher its finishing place." },
  won: { label: "Won", text: "Chips this bot collected from the pot in this hand." },
  bet_chip: { text: "Chips this bot has put in during the current betting round. They move into the pot when the round ends." },
  chips: { label: "Chip check", text: () => `A self-check of the replay. Chips are never created or destroyed, so all stacks, bets and the pot must always add up to the same total (${fmt(R.meta[R.handIdx].total)} on this table). If this line turns red, the simulator or the replay has a bug, not your bot.` },
  check: { label: "Check", text: "Passes the turn without betting. Only possible when nobody has bet in this round." },
  call: { label: "Call", text: "Matches the highest bet so far to stay in the hand." },
  bet: { label: "Bet", text: "Puts chips in when nobody else has bet in this round. The others must match it, raise it or fold." },
  raise: { label: "Raise", text: "Makes the bet bigger. The number is the new total everyone must match in this round, not the amount added." },
  uncalled: { label: "Uncalled bet returned", text: "Nobody matched the last part of this bet, so that part goes straight back to the bot that made it. It was never at risk." },
  leftover: { label: "Left over", text: "Chips put in by a bot that folded, beyond what any bot still in the hand had matched. No one can win them in the normal split, so they go to the best hand." },
  shows: { label: "Showdown", text: "The betting is over and more than one bot is still in, so they turn their cards over and the best five-card hand wins." },
  bid: { label: "Bid", text: "Auction variant: after the first three shared cards each bot secretly offers chips for an extra private card. All bids are made public afterwards." },
  auction: { label: "Wins the auction", text: "This bot bid the most, so it gets the extra card. It pays the second-highest bid, not its own, into the pot. If the top bids tie, each of those bots pays its own bid and gets a card." },
  // ---- poker words inside bot descriptions (see GLOSS)
  icm: { label: "ICM", text: "A formula that turns chip stacks into expected points. Its main lesson: losing chips hurts more than winning the same number helps, so close to the scoring places it pays to take fewer risks." },
  cbet: { label: "C-bet (continuation bet)", text: "Betting again after the first three shared cards because you were the one who raised before them, whether or not they helped your hand." },
  shove: { label: "Shove", text: "Betting all your chips at once (going all-in)." },
  steal: { label: "Steal", text: "Raising with a weak hand before any shared cards, hoping everyone folds so you collect the blinds." },
  preflop: { label: "Preflop", text: "The first betting round, before any shared cards are dealt." },
  headsup: { label: "Heads-up", text: "Only two players are left." },
  opens: { label: "Open", text: "Being the first to raise in a hand." },
  position: { label: "Position", text: "Where a bot sits relative to the button. Acting later is better, because you see what the others do first." },
  shortstack: { label: "Short stack", text: "Having few chips compared with the blinds (roughly 10 big blinds or fewer), which leaves little choice beyond all-in or fold." },
  pushfold: { label: "Push-or-fold", text: "A simple style for small stacks: bet everything or fold, nothing in between." },
  premium: { label: "Premium hands", text: "The very best starting hands, such as a pair of aces or kings, or ace-king." },
  maniac: { label: "Maniac", text: "A player who bets and raises wildly with almost anything." },
};
// term("vpip", "Plays") -> an element that shows TERMS.vpip on hover. TAB adds a keyboard stop.
const TAB = ` tabindex="0"`;
const term = (key, html, attrs = "") => `<span class="term" data-term="${key}"${attrs}>${html}</span>`;
// What a seat's last action (first word of its label) is explained by.
const ACT_TERM = { SB: "sb", BB: "bb", fold: "folded", check: "check", call: "call", bet: "bet", raise: "raise", discard: "discarded", reveal: "revealed", bid: "bid", won: "auction" };
// Poker words found in server-provided bot descriptions, marked up in one pass by gloss().
const GLOSS = [["icm", "ICM"], ["cbet", "c-bets?"], ["pushfold", "push-or-fold|shove/fold"], ["shortstack", "short[- ]stack(?:s|ed)?"], ["shove", "shov(?:e|es|ed|er|ing)"],
  ["steal", "steal(?:s|ing)?"], ["bb", "BB|big blinds?"], ["preflop", "pre-?flop"], ["headsup", "heads-up"], ["allin", "all[- ]in"], ["opens", "opens"],
  ["position", "position(?:al|-based)?"], ["premium", "premium hands?"], ["maniac", "maniac"]];
const GLOSS_RE = new RegExp(`\\b(?:${GLOSS.map(([, source]) => `(${source})`).join("|")})\\b`, "gi");
const gloss = (text) => esc(text).replace(GLOSS_RE, (match, ...groups) => term(GLOSS[groups.findIndex((g) => g !== undefined)][0], match));

// One tooltip element for the whole page, driven by data-term through listeners on document.
const Tip = { box: null, target: null, timer: null, keyboard: false, shownAt: 0 };
function hideTip() {
  clearTimeout(Tip.timer);
  if (!Tip.target) return;
  Tip.target.removeAttribute("aria-describedby");
  Tip.target = null;
  Tip.box.classList.remove("on");
}
function placeTip() {
  const r = Tip.target.getBoundingClientRect(), box = Tip.box, gap = 7, edge = 8;
  box.style.left = box.style.top = "0px"; // measure at full width before moving it
  const w = box.offsetWidth, h = box.offsetHeight;
  const left = Math.max(edge, Math.min(r.left + r.width / 2 - w / 2, document.documentElement.clientWidth - w - edge));
  const below = r.bottom + gap, above = r.top - gap - h;
  const top = below + h + edge <= window.innerHeight || above < edge ? below : above;
  box.style.left = `${Math.round(left)}px`;
  box.style.top = `${Math.round(top)}px`;
}
function showTip(el) {
  const entry = TERMS[el.dataset.term];
  let text = "";
  try { text = entry && (typeof entry.text === "function" ? entry.text(el) : entry.text); } catch { /* page state not ready */ }
  hideTip();
  if (!text || !el.isConnected) return;
  if (!Tip.box) {
    Tip.box = document.createElement("div");
    Tip.box.id = "tip"; Tip.box.className = "tip"; Tip.box.setAttribute("role", "tooltip");
    document.body.append(Tip.box);
  }
  Tip.box.innerHTML = `${entry.label ? `<b>${esc(entry.label)}</b>` : ""}${esc(text)}`;
  Tip.target = el; Tip.shownAt = performance.now();
  el.setAttribute("aria-describedby", "tip");
  placeTip();
  Tip.box.classList.add("on");
}
document.addEventListener("mouseover", (e) => {
  const el = e.target.closest?.("[data-term]");
  if (el === Tip.target && el) return;
  const wasOn = Boolean(Tip.target);
  hideTip();
  if (el) Tip.timer = setTimeout(() => showTip(el), wasOn ? 0 : 120); // moving from one term to the next: no wait
});
document.documentElement.addEventListener("mouseleave", hideTip);
document.addEventListener("mousedown", () => { Tip.keyboard = false; hideTip(); });
document.addEventListener("keydown", (e) => { Tip.keyboard = e.key === "Tab"; if (!Tip.keyboard) hideTip(); }, true);
document.addEventListener("focusin", (e) => { const el = e.target.closest?.("[data-term]"); if (el && Tip.keyboard) showTip(el); });
document.addEventListener("focusout", hideTip);
// Scrolling hides the tooltip, except the scroll the browser itself does to bring a tabbed-to term into view.
window.addEventListener("scroll", () => { if (Tip.target && Tip.keyboard && performance.now() - Tip.shownAt < 300) placeTip(); else hideTip(); }, true);
window.addEventListener("resize", hideTip);

// ------------------------------------------------------------------ tabs
function showTab(name) {
  document.querySelectorAll(".tabs button").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.tab === name)));
  document.querySelectorAll(".tab").forEach((t) => { t.hidden = t.id !== "tab-" + name; });
  try { history.replaceState(null, "", "#" + name); } catch { /* not allowed here */ }
  if (name === "replay") syncReplayRuns();
}
document.querySelectorAll(".tabs button").forEach((b) => b.addEventListener("click", () => showTab(b.dataset.tab)));

// ------------------------------------------------------------------ line-up
const findBot = (p) => S.bots.find((b) => b.path === p);
const botName = (p) => p.split("/").pop();
const filled = () => S.lineup.filter(Boolean);
const groupTitle = (g) => g || "top level";

function normalizeLineup(saved) {
  let l = Array.isArray(saved) ? saved.filter((p) => p === null || typeof p === "string") : [];
  l = [...l.filter(Boolean), ...l.filter((p) => !p)].slice(0, MAX_SEATS);
  while (l.length < MIN_SEATS) l.push(null);
  return l;
}
function defaultLineup() {
  const want = ["starter", "sparring/check_or_fold", "sparring/min_raiser", "sparring/calling_station", "sparring/shover", "sparring/nit", "sparring/nit", "starter"];
  return normalizeLineup(want.map((p) => (findBot(p) ? p : null)).concat(Array(8).fill(null)).slice(0, 8));
}
function saveLineup() { S.lineup = normalizeLineup(S.lineup); store.set("lineup", S.lineup); renderSeats(); renderBotList(); }

async function loadBots() {
  const data = await api("/api/bots");
  S.bots = data.bots;
  if (!S.lineup) {
    const saved = store.get("lineup", null);
    S.lineup = saved ? normalizeLineup(saved) : defaultLineup();
  }
  renderSeats(); renderBotList(); renderBotInfo();
}

function renderSeats() {
  $("#seats").innerHTML = S.lineup.map((path, i) => {
    if (!path) return `<li class="empty-seat"><span class="seat-no" data-term="seat_no">${i}</span><span class="seat-bot">empty</span></li>`;
    const bot = findBot(path);
    return `<li class="${bot ? "" : "missing"}"><span class="seat-no" data-term="seat_no">${i}</span>
      <button type="button" class="seat-bot" data-info="${esc(path)}" title="${esc(path)}: show description">${esc(botName(path))}${bot ? (bot.group ? ` <small>${esc(bot.group)}</small>` : "") : " <small>folder missing</small>"}</button>
      <button type="button" class="seat-x" data-remove="${i}" aria-label="Remove ${esc(botName(path))} from seat ${i}" title="Remove">&times;</button></li>`;
  }).join("");
  $("#seat-count").textContent = S.lineup.length;
  $("#seat-minus").disabled = S.lineup.length <= MIN_SEATS;
  $("#seat-plus").disabled = S.lineup.length >= MAX_SEATS;
}
$("#seats").addEventListener("click", (e) => {
  const rm = e.target.closest("[data-remove]"), info = e.target.closest("[data-info]");
  if (rm) { S.lineup.splice(Number(rm.dataset.remove), 1); S.lineup.push(null); saveLineup(); }
  else if (info) { S.info = info.dataset.info; renderBotInfo(); }
});
$("#seat-minus").addEventListener("click", () => { if (S.lineup.length > MIN_SEATS) { S.lineup.pop(); saveLineup(); } });
$("#seat-plus").addEventListener("click", () => { if (S.lineup.length < MAX_SEATS) { S.lineup.push(null); saveLineup(); } });
$("#clear-seats").addEventListener("click", () => { S.lineup = S.lineup.map(() => null); saveLineup(); });

function addBot(path) {
  const free = S.lineup.indexOf(null);
  if (free >= 0) S.lineup[free] = path;
  else if (S.lineup.length < MAX_SEATS) S.lineup.push(path);
  else return showRunError(`All ${MAX_SEATS} seats are taken. Remove a bot first.`);
  $("#run-error").hidden = true;
  saveLineup();
}
function fillFrom(group) {
  const pool = S.bots.filter((b) => b.group === group && !b.name.startsWith("_")).map((b) => b.path); // not _template
  if (!pool.length) return;
  let bag = [];
  S.lineup = S.lineup.map((p) => {
    if (p) return p;
    if (!bag.length) bag = pool.slice().sort(() => Math.random() - 0.5);
    return bag.pop();
  });
  saveLineup();
}

// One sentence on how the bot plays: the server's summary if it sends one, else the header.
const botSummary = (b) => b.summary || b.header.profile || b.header.notes || "";
function botTitle(b) {
  const h = b.header;
  return [`${b.path}/agent.py`, h.profile && `Profile: ${h.profile}`, h.variants && `Variants: ${h.variants}`, h.notes && `Notes: ${h.notes}`,
    h.source && `Source: ${h.source}`, ...b.problems.map((p) => `Problem: ${p}`)].filter(Boolean).join("\n");
}
function renderBotList() {
  const q = $("#bot-filter").value.trim().toLowerCase();
  const counts = {};
  filled().forEach((p) => { counts[p] = (counts[p] || 0) + 1; });
  const groups = [...new Set(S.bots.map((b) => b.group))].sort();
  const html = groups.map((g) => {
    const bots = S.bots.filter((b) => b.group === g && (!q || `${b.path} ${Object.values(b.header).join(" ")}`.toLowerCase().includes(q)));
    if (!bots.length) return "";
    return `<div class="bot-group"><div class="group-head"><span>${esc(groupTitle(g))} <small>${bots.length}</small></span>
        <button type="button" class="ghost small" data-fill="${esc(g)}" data-term="fill">Fill empty seats</button></div>
      ${bots.map((b) => `<button type="button" class="bot${b.path === S.info ? " shown" : ""}" data-add="${esc(b.path)}" title="${esc(botTitle(b))}">
        <span class="bn">${esc(b.name)}</span>${b.problems.length ? `<span class="bwarn" data-term="bot_warn" title="" aria-label="has problems">&#9888;</span>` : ""}
        <span class="bs">${esc([b.header.variants && `variants: ${b.header.variants}`, botSummary(b)].filter(Boolean).join(" · "))}</span>
        ${counts[b.path] ? `<span class="cnt">&times;${counts[b.path]}</span>` : `<span class="plus">+</span>`}</button>`).join("")}</div>`;
  }).join("");
  $("#bot-list").innerHTML = html || `<p class="empty">${S.bots.length ? "No bot matches the filter." : "No bot folders found (a folder needs an agent.py)."}</p>`;
}
function renderBotInfo() {
  const box = $("#bot-info");
  const b = S.info && findBot(S.info);
  box.hidden = !b;
  if (!b) return;
  const h = b.header, text = botSummary(b);
  box.innerHTML = `<div class="bi-name">${esc(b.name)} <code>${esc(b.path)}/agent.py</code></div>
    <div class="bi-text">${text ? gloss(text) : `<span class="dim">No description. Add a <code>Profile:</code> line to the docstring at the top of its agent.py.</span>`}</div>
    ${h.variants ? `<div class="bi-more">Variants: ${esc(h.variants)}</div>` : ""}
    ${h.notes && h.notes !== text ? `<div class="bi-more">${gloss(h.notes)}</div>` : ""}
    ${b.problems.map((p) => `<div class="bi-problem">&#9888; ${esc(p)}</div>`).join("")}`;
}
$("#bot-list").addEventListener("click", (e) => {
  const add = e.target.closest("[data-add]"), fill = e.target.closest("[data-fill]");
  if (add) { S.info = add.dataset.add; addBot(add.dataset.add); renderBotInfo(); }
  else if (fill) fillFrom(fill.dataset.fill);
});
$("#bot-filter").addEventListener("input", renderBotList);
function flash(btn, text) { const old = btn.textContent; btn.textContent = text; setTimeout(() => { btn.textContent = old; }, 700); }
$("#refresh-bots").addEventListener("click", async () => { try { await loadBots(); flash($("#refresh-bots"), "✓"); } catch (err) { showRunError(err.message); } });
// New bot folders show up without a restart: re-scan whenever the window regains focus.
let lastScan = 0;
window.addEventListener("focus", () => {
  if (Date.now() - lastScan < 1500) return;
  lastScan = Date.now();
  loadBots().catch(() => {});
});

// ------------------------------------------------------------------ settings
const FIELDS = { engine: "#s-engine", variant: "#s-variant", tables: "#s-tables", seed: "#s-seed", hand_cap: "#s-handcap", hands_per_level: "#s-hpl", payouts: "#s-payouts", stack: "#s-stack" };
const CHECKS = { newseed: "#s-newseed", vary: "#s-vary" };
function readPrefs() {
  const out = {};
  for (const [k, sel] of Object.entries(FIELDS)) out[k] = $(sel).value.trim();
  for (const [k, sel] of Object.entries(CHECKS)) out[k] = $(sel).checked;
  return out;
}
function savePrefs() { store.set("settings", readPrefs()); }
function restorePrefs() {
  const p = store.get("settings", {});
  for (const [k, sel] of Object.entries(FIELDS)) if (typeof p[k] === "string" && p[k] !== "" && k !== "engine" && k !== "variant") $(sel).value = p[k];
  for (const [k, sel] of Object.entries(CHECKS)) if (typeof p[k] === "boolean") $(sel).checked = p[k];
  return p;
}
function applySettings() {
  const kit = $("#s-engine").value === "kit";
  const vary = $("#s-vary").checked && !kit;
  $("#s-variant").disabled = kit; $("#s-variant").title = kit ? "The kit plays its own variant" : "";
  $("#s-vary").disabled = kit;
  $("#s-seed").disabled = $("#s-newseed").checked;
  $("#advanced").hidden = vary; // the seed picks these when Vary is on
  for (const id of ["#s-hpl", "#s-payouts", "#s-stack"]) { $(id).disabled = kit; $(id).title = kit ? "Set by the kit's rules" : ""; }
  const note = $("#engine-note");
  note.classList.toggle("official", kit);
  note.dataset.term = kit ? "kit" : "mini";
  note.textContent = kit ? `Organizers' kit in use: ${E.kit}` : "Mini simulator: unofficial rules, optimistic timing.";
}
async function loadEngine() {
  const info = await api("/api/engine");
  const prefs = restorePrefs();
  E.kit = info.kit;
  E.variants = Object.fromEntries((info.variants || []).map((v) => [v.name, v.title]));
  $("#s-variant").innerHTML = (info.variants || []).map((v) => `<option value="${esc(v.name)}">${esc(v.title)}</option>`).join("");
  if (E.variants[prefs.variant]) $("#s-variant").value = prefs.variant;
  $("#engine-label").hidden = !E.kit;
  $("#s-engine").value = E.kit ? (["kit", "mini"].includes(prefs.engine) ? prefs.engine : info.default) : "mini";
  applySettings();
}
[...Object.values(FIELDS), ...Object.values(CHECKS)].forEach((sel) => $(sel).addEventListener("change", () => { applySettings(); savePrefs(); }));

// ------------------------------------------------------------------ run
function runBody() {
  const p = readPrefs();
  const body = { lineup: filled(), engine: p.engine, variant: p.variant, seed: p.newseed ? "" : p.seed, vary: p.vary };
  for (const k of ["tables", "hand_cap", "hands_per_level", "stack", "payouts"]) if (p[k] !== "") body[k] = p[k];
  return body;
}
async function startRun() {
  if (S.active) return;
  $("#run-error").hidden = true;
  const lineup = filled();
  if (lineup.length < MIN_SEATS) return showRunError("Add at least 2 bots to the line-up.");
  const missing = lineup.filter((p) => !findBot(p));
  if (missing.length) return showRunError(`Missing bot folder(s): ${missing.join(", ")}. Remove them from the line-up.`);
  try {
    const res = await api("/api/runs", runBody());
    savePrefs();
    S.active = res.id; S.selected = res.id; S.seedShown = false;
    setRunning(true);
    showTab("results");
    poll();
  } catch (err) { showRunError(err.message); }
}
$("#run").addEventListener("click", startRun);
$("#cancel").addEventListener("click", () => { if (S.active) api(`/api/runs/${S.active}/cancel`, {}).catch(() => {}); });
document.addEventListener("keydown", (e) => {
  const inSettings = e.target instanceof HTMLInputElement && e.target.closest("#match-card") && e.target.type !== "checkbox";
  if (e.key === "Enter" && (e.ctrlKey || e.metaKey || inSettings)) { e.preventDefault(); e.target.blur?.(); applySettings(); startRun(); }
});
function showRunError(text) { const box = $("#run-error"); box.textContent = text; box.hidden = false; }
function setRunning(on) {
  $("#run").disabled = on; $("#run").textContent = on ? "Running…" : "Run match";
  $("#cancel").hidden = !on; $("#progress").hidden = !on;
}

async function poll() {
  if (!S.active) return;
  let run;
  try { run = await api(`/api/runs/${S.active}`); } catch (err) { showRunError(err.message); S.active = null; setRunning(false); return; }
  const total = run.settings.tables;
  if (!S.seedShown) { $("#s-seed").value = run.settings.seed; S.seedShown = true; savePrefs(); } // the seed the server used
  $("#progress-fill").style.width = `${(100 * run.done) / total}%`;
  const secs = run.started ? ((run.finished || Date.now() / 1000) - run.started).toFixed(1) : "0.0";
  $("#progress-text").textContent = `${run.status === "queued" ? "queued" : `${fmt(run.done)} / ${fmt(total)}`} · ${secs}s`;
  if (run.status === "queued" || run.status === "running") {
    if (S.selected === run.id) renderResult(run);
    setTimeout(poll, 250);
    return;
  }
  S.active = null;
  setRunning(false);
  S.full[run.id] = run;
  await refreshHistory().catch(() => {});
  if (S.selected === run.id) renderResult(run);
  if (!$("#tab-replay").hidden) syncReplayRuns();
}

// ------------------------------------------------------------------ results
async function refreshHistory() {
  const data = await api("/api/runs");
  S.runs = data.runs;
  S.session = data.session || S.session;
  $("#history-card").hidden = S.runs.length === 0;
  $("#history").innerHTML = S.runs.map((r) => {
    const entries = r.results?.entries || [];
    const top = entries.reduce((a, e) => (!a || e.average_points > a.average_points ? e : a), null);
    const failed = entries.reduce((a, e) => a + e.failed_decisions, 0);
    return `<tr class="clickable${r.id === S.selected ? " selected" : ""}" data-run="${r.id}">
      <td><b>#${r.id}</b></td><td>${esc(variantTitle(r.settings.variant))}${r.settings.vary ? ` <span class="dim term" data-term="vary">varied</span>` : ""}</td>
      <td class="num">${fmt(r.done)}${r.done !== r.settings.tables ? ` / ${fmt(r.settings.tables)}` : ""}</td>
      <td><code>${esc(r.settings.seed)}</code></td>
      <td class="topbot">${top ? esc(top.label) : `<span class="status-${esc(r.status)}">${esc(r.status)}</span>`}</td>
      <td class="num">${top ? `<b>${fx(top.average_points, 1)}</b> <span class="pm">±${fx(top.se, 1)}</span>` : ""}</td>
      <td class="num">${failed ? `<span class="failn">${fmt(failed)}</span>` : entries.length ? `<span class="dim">0</span>` : ""}</td></tr>`;
  }).join("");
}
$("#history").addEventListener("click", (e) => { const tr = e.target.closest("tr[data-run]"); if (tr) selectRun(Number(tr.dataset.run)); });

async function selectRun(id) {
  S.selected = id;
  document.querySelectorAll("#history tr").forEach((tr) => tr.classList.toggle("selected", Number(tr.dataset.run) === id));
  const run = S.full[id] || (await api(`/api/runs/${id}`));
  if (["done", "cancelled", "error"].includes(run.status)) S.full[id] = run;
  renderResult(run);
}

// Par sits in the middle; `span` is the points-per-table distance from par to either end.
function meter(mean, se, par, span) {
  const at = (v) => Math.max(0, Math.min(100, 50 + (50 * (v - par)) / span));
  const lo = Math.min(mean, par), hi = Math.max(mean, par);
  return `<div class="meter" data-term="par">
    <div class="fill ${mean >= par ? "up" : "down"}" style="left:${at(lo)}%;width:${at(hi) - at(lo)}%"></div>
    <div class="err" style="left:${at(mean - se)}%;width:${at(mean + se) - at(mean - se)}%"></div>
    <div class="par" style="left:${at(par)}%"></div></div>`;
}

function runHead(run) {
  const s = run.settings, r = run.results, kit = s.engine === "kit";
  const rules = kit
    ? `${term("kit", "organizers' kit rules", TAB)} · ${term("handcap", "hand cap", TAB)} <b>${fmt(s.hand_cap)}</b>`
    : `${term("handcap", "hand cap", TAB)} <b>${fmt(s.hand_cap)}</b> · <b>${fmt(s.hands_per_level)}</b> ${term("hpl", "hands/level", TAB)} · ${term("stack", "stack", TAB)} <b>${fmt(s.stack)}</b> · ${term("payouts", "payouts", TAB)} <b>${s.random_payouts ? term("payouts_drawn", "drawn per table", TAB) : esc(s.payouts.join(" / "))}</b>${s.vary ? ` <span class="term dim" data-term="vary"${TAB}>(picked by the seed)</span>` : ""}`;
  return `<div class="run-head">
      <span class="run-no">Run #${run.id}</span>
      <span><b>${fmt(run.done)}</b>${run.done !== s.tables ? ` of ${fmt(s.tables)}` : ""} ${term("run_tables", "tables", TAB)}</span>
      ${r ? `<span><b>${fx(r.seconds, 1)}</b> s</span>` : ""}
      <span><b class="term" data-term="variant" data-variant="${esc(s.variant)}"${TAB}>${esc(variantTitle(s.variant))}</b></span>
      <span>${term("seed", "seed", TAB)} <code>${esc(s.seed)}</code></span>
      <span class="session">${term("session", "Session", TAB)}: <b>${fmt(S.session.runs)}</b> run${S.session.runs === 1 ? "" : "s"} · <b>${fmt(S.session.tables)}</b> tables</span>
    </div>
    <div class="rules-line">Rules: ${rules}</div>`;
}

function renderResult(run) {
  const view = $("#result-view");
  const s = run.settings, r = run.results;
  S.shown = run; // the glossary quotes this run's numbers
  if (!r) {
    const body = run.status === "error" ? `<p class="status-error">Run failed.</p><pre class="error-box">${esc(run.error || "No tables finished.")}</pre>`
      : run.status === "cancelled" ? `<p class="empty">Cancelled before any table finished.</p>`
      : `<p class="empty">Running… ${fmt(run.done)} / ${fmt(s.tables)} tables</p>`;
    view.innerHTML = `<div class="card">${runHead(run)}${body}</div>`;
    return;
  }
  const entries = r.entries.slice().sort((a, b) => b.average_points - a.average_points);
  const span = Math.max(4, ...entries.map((e) => Math.abs(e.average_points - r.par) + e.se)) * 1.05;
  const totalFailed = entries.reduce((a, e) => a + e.failed_decisions, 0);
  const notices = [
    run.status === "cancelled" ? `Cancelled: results cover the ${fmt(run.done)} finished tables.` : "",
    ...(r.warnings || []),
  ].filter(Boolean).map((w) => `<div class="notice">${esc(w)}</div>`).join("");
  const failBanner = totalFailed ? `<div class="fail-banner" role="alert">${fmt(totalFailed)} ${term("failed", `failed decision${totalFailed === 1 ? "" : "s"}`)} (each played as check/fold). Click a red count for details.</div>` : "";
  const rows = entries.map((e, i) => {
    const slow = e.latency_us ? e.latency_us["p99.9"] : null;
    const tone = e.vs_par > 2 * e.se ? "pos" : e.vs_par < -2 * e.se ? "neg" : "";
    const notes = e.failed_decisions ? `<tr class="notes-row" data-notes="${i}" hidden><td colspan="9">${e.failure_notes.length
      ? e.failure_notes.map((n) => `<p><b>${esc(e.label)}</b> · table ${esc(n.table)}, hand ${esc(n.hand)} · <b>${esc(n.reason)}</b></p><pre>${esc(n.detail)}</pre>`).join("")
      : `<p>No details were recorded for ${esc(e.label)}.</p>`}</td></tr>` : "";
    return `<tr class="${e.failed_decisions ? "has-fail" : ""}${e.inactive ? " idle" : ""}">
      <td class="rank">${i + 1}</td>
      <td class="bot"><div class="botcell"><span class="botname" title="${esc(e.bot)}">${esc(e.label)}</span>${e.inactive ? `<span class="badge-idle" data-term="inactive">INACTIVE</span>` : ""}</div></td>
      <td class="num pts ${tone}" data-term="pts_cell" data-mean="${e.average_points}" data-se="${e.se}">${fx(e.average_points, 1)}<span class="pm"> ±${fx(e.se, 1)}</span></td>
      <td class="meter-cell">${meter(e.average_points, e.se, r.par, span)}</td>
      <td class="num big">${pct(e.win_rate)}</td>
      <td class="num big">${pct(e.top3_rate)}</td>
      <td class="num big${e.inactive ? " warn" : ""}"${e.vpip == null ? "" : ` data-term="vpip_cell" data-vpip="${e.vpip}" data-pfr="${e.pfr}"`}>${pct(e.vpip)}</td>
      <td class="num big${slow != null && slow >= 1000 ? " slow" : ""}">${slow == null ? "–" : fmt(Math.round(slow))}</td>
      <td class="num big">${e.failed_decisions ? `<button type="button" class="failn" data-toggle="${i}" title="Show details">${fmt(e.failed_decisions)}</button>` : `<span class="dim">0</span>`}</td></tr>${notes}`;
  }).join("");
  view.innerHTML = `<div class="card">
      ${runHead(run)}${notices}${failBanner}
      <div class="table-wrap"><table class="results">
        <thead><tr><th></th><th class="term" data-term="entry"${TAB}>Entry</th>
          <th class="num term" data-term="pts"${TAB}>Pts / table</th>
          <th class="term" data-term="par"${TAB}>vs par ${fx(r.par, 1)}</th>
          <th class="num term" data-term="win"${TAB}>Win</th>
          <th class="num term" data-term="top3"${TAB}>Top 3</th>
          <th class="num term" data-term="vpip"${TAB}>Plays</th>
          <th class="num term" data-term="slow"${TAB}>Slowest µs</th>
          <th class="num term" data-term="failed"${TAB}>Failed</th></tr></thead>
        <tbody>${rows}</tbody></table></div>
      ${run.kit_stderr ? `<details class="failures"><summary>What the bots printed to stderr (from the kit)</summary><pre>${esc(run.kit_stderr)}</pre></details>` : ""}
    </div>`;
}
$("#result-view").addEventListener("click", (e) => {
  const btn = e.target.closest("[data-toggle]");
  if (!btn) return;
  const row = $(`#result-view tr[data-notes="${btn.dataset.toggle}"]`);
  if (row) row.hidden = !row.hidden;
});

// ------------------------------------------------------------------ replay
const R = { run: null, tables: [], table: null, hands: [], handIdx: 0, list: [], steps: [], step: 0, timer: null };
const RANKS = { T: "10" };
const SUITS = { s: ["♠", false], h: ["♥", true], d: ["♦", true], c: ["♣", false] };
function card(c, cls = "", key = "") {
  if (!c) return `<span class="pc slot ${cls}"></span>`;
  const [sym, red] = SUITS[c[1]] || ["?", false];
  const rank = RANKS[c[0]] || c[0];
  return `<span class="pc ${red ? "red" : ""} ${cls}"${key ? ` data-term="${key}"` : ""} aria-label="${rank} of ${{ s: "spades", h: "hearts", d: "diamonds", c: "clubs" }[c[1]]}"><span>${rank}</span><span class="s">${sym}</span></span>`;
}

function runLabel(r) { return `#${r.id} · ${variantTitle(r.settings.variant)} · seed ${r.settings.seed} · ${fmt(r.done)} tables`; }
function syncReplayRuns() {
  const sel = $("#rp-run");
  const runs = S.runs.filter((r) => r.results && (r.replay_tables > 0 || r.history_file));
  const keep = sel.value;
  sel.innerHTML = runs.map((r) => `<option value="${r.id}">${esc(runLabel(r))}</option>`).join("");
  $("#replay-empty").hidden = runs.length > 0;
  if (!runs.length) { $("#replay-body").hidden = true; $("#replay-kit").hidden = true; return; }
  const want = runs.some((r) => String(r.id) === keep) && sel.dataset.touched ? keep
    : runs.some((r) => r.id === S.selected) ? String(S.selected) : String(runs[0].id);
  sel.value = want;
  if (String(R.run) !== want) loadReplayRun(Number(want));
}
$("#rp-run").addEventListener("change", (e) => { e.target.dataset.touched = "1"; loadReplayRun(Number(e.target.value)); });

async function loadReplayRun(id) {
  stopPlay();
  R.run = id;
  const run = S.runs.find((r) => r.id === id);
  const kit = Boolean(run && run.history_file);
  $("#replay-kit").hidden = !kit;
  for (const sel of ["#rp-table", "#rp-hand", "#rp-notable"]) $(sel).closest("label").hidden = kit;
  if (kit) {
    $("#replay-body").hidden = true;
    $("#replay-kit").innerHTML = `<p>Kit runs open in the kit's own viewer (it shows the cards of the bot in seat 0).</p>
      <p><button id="kit-viewer" class="primary" type="button">Open in the kit's viewer</button> <span id="kit-viewer-msg" class="hint"></span></p>
      <p class="hint">File: <code>${esc(run.history_file)}</code></p>`;
    $("#kit-viewer").addEventListener("click", async () => {
      const msg = $("#kit-viewer-msg");
      msg.textContent = "Starting the viewer…";
      try {
        const res = await api(`/api/runs/${id}/viewer`, {});
        msg.innerHTML = `Viewer running at <a href="${esc(res.url)}" target="_blank" rel="noopener">${esc(res.url)}</a>`;
        window.open(res.url, "_blank", "noopener");
      } catch (err) { msg.textContent = err.message; }
    });
    return;
  }
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
  const order = t.places.map((place, seat) => [place, seat]).sort((x, y) => x[0] - y[0]).slice(0, 3);
  const variant = t.hands[0]?.variant || t.settings?.variant;
  $("#rp-head").innerHTML = `<span>Table <b>${esc(t.table)}</b></span>${variant ? `<span><b class="term" data-term="variant" data-variant="${esc(variant)}"${TAB}>${esc(variantTitle(variant))}</b></span>` : ""}
    <span>${term("rp_payouts", "payouts", TAB)} <b>${Array.isArray(t.payouts) ? esc(t.payouts.join(" / ")) : "–"}</b></span>
    <span data-term="rp_places">${order.map(([place, seat]) => `${place}. <b>${esc(t.seats[seat].label)}</b>`).join(" &nbsp; ")}</span>`;
  $("#replay-body").hidden = false;
  buildHandList();
  selectHand(0);
}

function seatName(seat) { return R.table.seats[seat].label; }

// Rebuild every intermediate state of a hand from its start stacks and events.
function buildSteps(h, t) {
  const n = h.start.length;
  const total = h.start.reduce((a, b) => a + b, 0);
  const st = { stack: h.start.slice(), bet: Array(n).fill(0), pot: 0, board: [], folded: Array(n).fill(false), shown: Array(n).fill(false), act: Array(n).fill(""), won: Array(n).fill(0), acting: null, newCards: 0, discarded: Array(n).fill(null), revealed: Array(n).fill(null), extra: Array(n).fill(null) };
  const snap = (text, kind) => ({ ...st, stack: st.stack.slice(), bet: st.bet.slice(), board: st.board.slice(), folded: st.folded.slice(), shown: st.shown.slice(), act: st.act.slice(), won: st.won.slice(), discarded: st.discarded.slice(), revealed: st.revealed.slice(), extra: st.extra.slice(), text, kind, chips: st.stack.reduce((a, b) => a + b, 0) + st.bet.reduce((a, b) => a + b, 0) + st.pot });
  const steps = [snap(`Hand ${h.hand} dealt · ${term("btn", "button")} ${esc(seatName(h.button))}`, "hand")];
  let blinds = 0, allin = false, showdown = false, ok = true;
  const collect = () => { st.pot += st.bet.reduce((a, b) => a + b, 0); st.bet.fill(0); };
  const names = ["Flop", "Turn", "River"];
  for (const [kind, seat, amount, cards] of h.events) {
    st.acting = seat; st.newCards = 0;
    let text = null;
    const nm = seat == null ? "" : esc(seatName(seat));
    const allIn = () => (st.stack[seat] === 0 ? ` (${term("allin", "all-in")})` : "");
    if (kind === "hand" || kind === "stack") {
      if (kind === "stack" && st.stack[seat] !== amount) ok = false;
      continue;
    } else if (kind === "blind") {
      st.stack[seat] -= amount; st.bet[seat] += amount;
      const which = blinds++ === 0 ? "small blind" : "big blind";
      st.act[seat] = `${which === "small blind" ? "SB" : "BB"} ${fmt(amount)}`;
      text = `${nm} posts ${term(which === "small blind" ? "sb" : "bb", which)} ${fmt(amount)}${allIn()}`;
    } else if (kind === "fold") {
      st.folded[seat] = true; st.act[seat] = "fold"; text = `${nm} ${term("folded", "folds")}`;
    } else if (kind === "check") {
      st.act[seat] = "check"; text = `${nm} ${term("check", "checks")}`;
    } else if (kind === "call") {
      st.stack[seat] -= amount; st.bet[seat] += amount;
      st.act[seat] = `call ${fmt(amount)}`; text = `${nm} ${term("call", "calls")} ${fmt(amount)}${allIn()}`;
    } else if (kind === "raise") {
      const high = Math.max(...st.bet);
      st.stack[seat] -= amount - st.bet[seat]; st.bet[seat] = amount;
      const verb = high === 0 ? "bets" : "raises to";
      st.act[seat] = `${verb === "bets" ? "bet" : "raise to"} ${fmt(amount)}`;
      text = `${nm} ${term(verb === "bets" ? "bet" : "raise", verb)} ${fmt(amount)}${allIn()}`;
    } else if (kind === "return") {
      st.stack[seat] += amount; st.bet[seat] -= amount; text = `${term("uncalled", "Uncalled")} ${fmt(amount)} returned to ${nm}`;
    } else if (kind === "board") {
      collect(); st.board.push(...cards); st.newCards = cards.length; st.act.fill(""); st.acting = null;
      text = `${term("board", names[Math.min(2, st.board.length - 3)])}: ${cards.map((c) => card(c)).join(" ")}`;
    } else if (kind === "discard") {
      st.discarded[seat] = cards[0]; st.act[seat] = "discard"; text = `${nm} ${term("discarded", "discards")} ${card(cards[0])} face down`;
    } else if (kind === "reveal") {
      st.revealed[seat] = cards[0]; st.act[seat] = "reveal"; text = `${nm} ${term("revealed", "turns")} ${card(cards[0])} ${term("revealed", "face up")}`;
    } else if (kind === "bid") {
      st.act[seat] = `bid ${fmt(amount)}`; text = `${nm} ${term("bid", "bid")} ${fmt(amount)}`;
    } else if (kind === "auction") {
      st.stack[seat] -= amount; st.pot += amount; st.act[seat] = `won auction`;
      text = `${nm} ${term("auction", "wins the auction")} and pays ${fmt(amount)} into the pot${allIn()}`;
    } else if (kind === "extra") {
      st.extra[seat] = cards[0]; text = `${nm} ${term("extra", "receives")} ${card(cards[0])}`;
    } else if (kind === "show") {
      st.shown[seat] = true; showdown = true; text = `${nm} ${term("shows", "shows")} ${cards.map((c) => card(c)).join(" ")}`;
    } else if (kind === "win" || kind === "leftover") {
      collect(); st.pot -= amount; st.stack[seat] += amount; st.won[seat] += amount;
      text = kind === "win" ? `${nm} ${term("won", "wins")} ${fmt(amount)}` : `${nm} gets ${fmt(amount)} ${term("leftover", "left over")}`;
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

// Seats sit on a rectangle around the felt: a bottom row, a top row and at most one seat on
// each side, so that no seat box covers another with 2 to 10 seats. Positions are % of the
// felt area; (x, y) is the middle of the seat box and (bx, by) of its bet chip.
const SEAT_ROWS = { 2: [1, 1, 0], 3: [1, 2, 0], 4: [1, 1, 1], 5: [1, 2, 1], 6: [2, 2, 1], 7: [2, 3, 1], 8: [3, 3, 1], 9: [3, 4, 1], 10: [4, 4, 1] }; // [bottom, top, each side]
const ROW_X = { 1: [50], 2: [30, 70], 3: [22, 50, 78], 4: [11.5, 37.2, 62.8, 88.5] };
function seatSlots(n) {
  const [bottom, top, side] = SEAT_ROWS[Math.max(2, Math.min(10, n))];
  const inward = (x) => 50 + (x - 50) * 0.8;
  const ring = [ // clockwise as drawn, starting at the bottom right
    ...ROW_X[bottom].slice().reverse().map((x) => ({ x, y: 92, bx: inward(x), by: 71 })),
    ...(side ? [{ x: 11.5, y: 50, bx: 27, by: 61 }] : []),
    ...ROW_X[top].map((x) => ({ x, y: 8, bx: inward(x), by: 29 })),
    ...(side ? [{ x: 88.5, y: 50, bx: 73, by: 61 }] : []),
  ];
  const first = Math.floor(bottom / 2); // seat 0 goes in the middle of the bottom row
  return ring.map((_, i) => ring[(i + first) % ring.length]);
}

function renderStep() {
  const h = R.hands[R.handIdx], m = R.meta[R.handIdx], sp = R.steps[R.step], t = R.table;
  const n = h.start.length;
  const final = R.step === R.steps.length - 1;
  const sbSeat = h.events.find((e) => e[0] === "blind")?.[1];
  const bbSeat = h.events.filter((e) => e[0] === "blind")[1]?.[1];
  const slots = seatSlots(n);
  let html = "";
  for (let i = 0; i < n; i++) {
    const { x, y, bx, by } = slots[i];
    const out = h.start[i] === 0;
    const cards = h.hole[String(i)] || [];
    const tags = [];
    if (i === h.button) tags.push(`<span class="tag btn" data-term="btn">BTN</span>`);
    if (i === sbSeat) tags.push(`<span class="tag" data-term="sb">SB</span>`);
    if (i === bbSeat) tags.push(`<span class="tag" data-term="bb">BB</span>`);
    if (out) tags.push(`<span class="tag" data-term="out">OUT</span>`);
    else if (sp.folded[i]) tags.push(`<span class="tag fold" data-term="folded">FOLDED</span>`);
    else if (sp.stack[i] === 0 && !(final && sp.won[i] === 0 && m.busts.includes(i))) tags.push(`<span class="tag allin" data-term="allin">ALL-IN</span>`);
    if (final && m.busts.includes(i)) tags.push(`<span class="tag bust" data-term="busted">BUSTED</span>`);
    if (sp.won[i]) tags.push(`<span class="tag won" data-term="won">WON ${fmt(sp.won[i])}</span>`);
    const cls = ["seat", out ? "out" : "", sp.folded[i] ? "folded" : "", sp.acting === i && !final ? "acting" : "", sp.won[i] ? "winner" : ""].join(" ");
    html += `<div class="${cls}" style="left:${x}%;top:${y}%" data-seat="${i}">
      <div class="nm" title="${esc(t.seats[i].label)} (${esc(t.seats[i].bot)})">${esc(t.seats[i].label)}</div>
      <div class="stk"${out ? "" : ` data-term="seat_stack"`}>${out ? "—" : fmt(sp.stack[i])}</div>
      <div class="hole">${out ? "" : cards.map((c) => (c === sp.discarded[i] ? card(c, "discarded", "discarded") : c === sp.revealed[i] ? card(c, "revealed", "revealed") : card(c, "", "hole"))).join("")}${!out && sp.extra[i] ? card(sp.extra[i], "extra", "extra") : ""}</div>
      <div class="tags">${tags.join("")}</div>
      <div class="act"${ACT_TERM[sp.act[i].split(" ")[0]] ? ` data-term="${ACT_TERM[sp.act[i].split(" ")[0]]}"` : ""}>${esc(sp.act[i])}</div></div>`;
    if (sp.bet[i]) html += `<div class="bet" data-term="bet_chip" style="left:${bx}%;top:${by}%">${fmt(sp.bet[i])}</div>`;
  }
  $("#rp-seats").innerHTML = html;
  const board = [0, 1, 2, 3, 4].map((k) => card(sp.board[k], `big${k >= sp.board.length - sp.newCards && k < sp.board.length ? " new" : ""}`)).join("");
  $("#rp-board").innerHTML = board;
  $("#rp-pot").textContent = `Pot ${fmt(sp.pot + sp.bet.reduce((a, b) => a + b, 0))}`;
  $("#rp-level").innerHTML = `Hand ${h.hand} · ${term("level", `Level ${h.level + 1} · Blinds ${fmt(h.blinds[0])}/${fmt(h.blinds[1])}`, TAB)}`;
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
    await loadEngine();
    await loadBots();
    await refreshHistory();
    const running = S.runs.find((r) => r.status === "running" || r.status === "queued");
    if (running) { S.active = running.id; S.selected = running.id; S.seedShown = true; setRunning(true); poll(); }
    else if (S.runs.length) await selectRun(S.runs[0].id);
    showTab(location.hash === "#replay" ? "replay" : "results");
  } catch (err) {
    showRunError("Cannot reach the server: " + err.message);
  }
})();
