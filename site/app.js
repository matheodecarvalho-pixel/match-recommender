// Match Recommender: renders output/matches_ranked.json. No build step, no libraries.

const SOURCES = ["matches_ranked.json", "../output/matches_ranked.json"];
const SIGNAL_LABELS = {
  form: "Form", stakes: "Stakes", entertainment: "Goals", rivalry: "Rivalry",
  closeness: "Closeness", records: "Records", revenge: "Revenge",
  big_match: "Big match", par: "Above / under par",
};

// ---------- My Feed: what each person cares about, kept on this device ----------

// Slider id -> label, hint. Stakes are split by the kind of race.
const SLIDERS = [
  ["big_match", "Big matches", "Heavyweight clubs"],
  ["title", "Title races", "Teams fighting for the top, and knockouts"],
  ["europe", "Fight for Europe", "European places, top 8 / top 24"],
  ["relegation", "Relegation battles", "Drama at the bottom"],
  ["entertainment", "Goals", "Teams scoring and conceding a lot"],
  ["form", "Form", "Teams on a roll"],
  ["rivalry", "Rivalries", "Derbies and European classics"],
  ["revenge", "Revenge", "Old clubs and old scores to settle"],
  ["par", "Surprises & slumps", "Teams far above or below their usual place"],
  ["closeness", "Close games", "Evenly matched teams"],
];
const LEVELS = ["Don't care", "A little", "Normal", "A lot", "Can't miss it"];  // 0, 0.5, 1, 1.5, 2
const STAKE_KIND = { stakes_title: "title", stakes_knockout: "title", stakes_europe: "europe", stakes_cutoff: "europe", stakes_relegation: "relegation" };

const PRESETS = {
  "Balanced": {},
  "Big games only": { big_match: 2, rivalry: 1.5, title: 1.5, entertainment: 0.5, form: 0.5, europe: 0.5, relegation: 0, closeness: 0.5 },
  "Goals galore": { entertainment: 2, form: 1.5, closeness: 0.5, big_match: 0.5, europe: 0.5, relegation: 0.5 },
  "Drama at the bottom": { relegation: 2, par: 2, closeness: 1.5, title: 0.5, big_match: 0.5 },
  "Title races": { title: 2, europe: 1.5, big_match: 1, closeness: 1.5, relegation: 0.5 },
};

// Six quick questions; each answer sets a few sliders (later answers win).
const QUIZ = [
  { q: "Saturday night, one match on TV. You pick…", a: [
    ["Two giants, whatever's at stake", { big_match: 2, rivalry: 1.5 }],
    ["A wild 4–3 between two mid-table sides", { entertainment: 2, closeness: 0.5 }],
    ["The bottom two fighting to stay up", { relegation: 2, closeness: 1.5 }],
    ["First v second, one point apart", { title: 2, closeness: 1.5 }],
  ] },
  { q: "Can a 0–0 be a great game?", a: [
    ["Yes, give me a tactical battle", { closeness: 2, entertainment: 0.5 }],
    ["Never. I want goals", { entertainment: 2, closeness: 0.5 }],
    ["Depends who's playing", { big_match: 1.5 }],
  ] },
  { q: "Derbies and rivalries are…", a: [
    ["The best games of the season", { rivalry: 2 }],
    ["A nice bonus", { rivalry: 1 }],
    ["Just another game", { rivalry: 0.5 }],
  ] },
  { q: "A player facing his old club, or a team that knocked yours out last year:", a: [
    ["Spicy. I'm in", { revenge: 2 }],
    ["Fun detail", { revenge: 1 }],
    ["Couldn't care less", { revenge: 0 }],
  ] },
  { q: "Spurs bottom of the table, Brighton up in 3rd…", a: [
    ["I love a giant in crisis or a surprise team", { par: 2 }],
    ["I'd rather watch teams in form", { form: 2, par: 0.5 }],
    ["Doesn't change much for me", { par: 1 }],
  ] },
  { q: "The race for European spots…", a: [
    ["Glued to it", { europe: 2 }],
    ["Only the title matters", { title: 2, europe: 0.5 }],
    ["Not my thing", { europe: 0.5, title: 1 }],
  ] },
];
const PROFILES = {  // strongest slider -> what we call you
  big_match: "The Big-Game Hunter", entertainment: "The Goal Junkie", relegation: "The Drama Seeker",
  title: "The Title Chaser", europe: "The Table Watcher", rivalry: "The Derby Devotee",
  revenge: "The Grudge Keeper", par: "The Crisis Watcher", form: "The Form Reader",
  closeness: "The Purist",
};
const FEED_KEY = "mr.feed";

// ---------- My Style: how you like football to be played ----------

const STYLE_INFO = {
  possession: ["🎯", "Possession & control", "Tiki-taka, patient build-up"],
  press: ["⚡", "High press & transition", "Win it high, attack fast"],
  low_block: ["🧱", "Low block & counter", "Compact, deep, strike on the break"],
  direct: ["💪", "Direct & physical", "Long balls, duels, set pieces"],
  chaos: ["🎢", "All-out attack", "Open games, risks at both ends"],
  pragmatic: ["♟️", "Pragmatic", "Adapt, control risk, manage the game"],
};
const STYLE_LEVELS = ["Avoid", "Not really", "Neutral", "Like", "Love"];  // -1 .. 1
const STYLE_POINTS = 12;   // a match with two teams you love gains up to 12 points
const CLASH_POINTS = 6;    // opposite philosophies meeting
const CLASHES = [["possession", "low_block"], ["possession", "press"], ["press", "low_block"], ["chaos", "pragmatic"]];
const STYLE_KEY = "mr.style";
const STYLE_QUIZ = [
  { q: "What pace do you enjoy?", a: [
    ["Fast and vertical, end to end", { press: 1, chaos: 1, direct: 0.5, possession: -0.5 }],
    ["Slow, patient build-up", { possession: 1, pragmatic: 0.5, chaos: -0.5 }],
    ["Depends on the game", {}],
  ] },
  { q: "Tiki-taka or counter-attacks?", a: [
    ["Tiki-taka: keep the ball, wear them down", { possession: 1, low_block: -0.5 }],
    ["Counters: sit, wait, strike", { low_block: 1, press: 0.5, possession: -0.5 }],
    ["Both have their charm", {}],
  ] },
  { q: "A team hunting the ball in the opponent's box…", a: [
    ["That's the best thing in football", { press: 1 }],
    ["Fine either way", {}],
    ["I prefer teams that pick their moment", { low_block: 0.5, pragmatic: 0.5, press: -0.5 }],
  ] },
  { q: "A 4–4 with defenders all over the place:", a: [
    ["Yes please", { chaos: 1, pragmatic: -0.5 }],
    ["I'd rather watch a tactical battle", { pragmatic: 1, chaos: -1 }],
    ["Fun once in a while", {}],
  ] },
  { q: "Long balls, duels and set pieces:", a: [
    ["Proper football. Love it", { direct: 1 }],
    ["Not really my thing", { direct: -1 }],
    ["No strong feelings", {}],
  ] },
  { q: "Possession side against a deep block, or press against build-up: a clash of styles…", a: [
    ["That's what makes a game interesting", { __clash: true }],
    ["Doesn't matter to me", { __clash: false }],
  ] },
];
const STYLE_PROFILES = {
  possession: "The Tiki-Taka Purist", press: "The Heavy-Metal Fan", low_block: "The Counter-Attack Connoisseur",
  direct: "The Old-School Romantic", chaos: "The Chaos Lover", pragmatic: "The Chess Player",
};
const ESPN = "https://site.api.espn.com/apis/site/v2/sports/soccer";
const LIVE_POLL_MS = 30000;
const STAT_ROWS = [  // ESPN boxscore label -> what we show
  ["Possession", "Possession", v => `${Math.round(parseFloat(v))}%`],
  ["SHOTS", "Shots"], ["ON GOAL", "On target"], ["Corner Kicks", "Corners"],
  ["Fouls", "Fouls"], ["Yellow Cards", "Yellow cards"], ["Red Cards", "Red cards"], ["Saves", "Saves"],
];
const TV_SOURCES = ["broadcasters.json", "../data/broadcasters.json"];
const COUNTRY_KEY = "mr.country";
const FAV_KEY = "mr.favourites";
const COMP_KEY = "mr.competitions";

let data = null;
let feed = load(FEED_KEY, { mults: {}, profile: null });  // slider multipliers, quiz profile
let myStyle = load(STYLE_KEY, { prefs: {}, clash: false, profile: null });  // style -> -1..1
const teamStyles = {};  // team -> {style, confidence}
let tv = null;        // broadcasters.json: rights per competition and country
let country = null;   // ISO code: picked by hand, else from the device time zone
let favourites = new Set(load(FAV_KEY, []));
let hidden = new Set(load(COMP_KEY, []));  // competitions switched off

function load(key, fallback) {
  try { return JSON.parse(localStorage.getItem(key)) ?? fallback; } catch { return fallback; }
}
function save(key, value) {
  try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* private mode: keep in memory */ }
}

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") node.className = v;
    else if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
    else node.setAttribute(k, v);
  }
  for (const c of children.flat()) if (c != null) node.append(c);
  return node;
}

async function fetchJson(sources) {
  for (const url of sources) {
    try {
      const r = await fetch(url, { cache: "no-cache" });
      if (r.ok) return await r.json();
    } catch { /* try the next location */ }
  }
  return null;
}

// ---------- Where to watch ----------

// The time zone never leaves the device: it is only looked up in broadcasters.json.
function deviceCountry() {
  try {
    const zone = Intl.DateTimeFormat().resolvedOptions().timeZone;
    return tv?.timezones?.[zone] || null;
  } catch { return null; }
}

function watchInfo(m) {
  if (!tv || !country) return null;
  // ESPN lists US channels per match, which beats the competition-wide table.
  if (country === "US" && m.espn?.us_tv?.length) return { channels: m.espn.us_tv, source: "ESPN", perMatch: true };
  const entry = tv.rights?.[m.competition]?.[country];
  if (!entry) return null;
  // Some channels only show the final (M6 has the Champions League final in France).
  const channels = m.stage === "FINAL" && entry.final ? [...entry.channels, ...entry.final] : entry.channels;
  return { ...entry, channels, perMatch: false };
}

function watchLine(m) {
  const w = watchInfo(m);
  return w ? el("div", { class: "watch" }, "📺 " + w.channels.join(" · ")) : null;
}

function watchDetail(m) {
  const name = tv?.countries?.[country] || country;
  const w = watchInfo(m);
  if (!country) return null;
  if (!w) return el("p", { class: "watch-detail" }, `No listing for ${m.competition} in ${name}.`);
  const src = w.source === "ESPN" ? "ESPN" : el("a", { href: w.source, target: "_blank", rel: "noopener" }, "source");
  return el("p", { class: "watch-detail" },
    `${w.perMatch ? "On" : "Usually on"} in ${name}: `, el("strong", {}, w.channels.join(", ")),
    " · ", src);
}

function setupCountry() {
  const select = document.getElementById("country");
  const auto = deviceCountry();
  country = load(COUNTRY_KEY, null) || auto;
  const names = Object.entries(tv?.countries || {}).sort((a, b) => a[1].localeCompare(b[1]));
  select.replaceChildren(
    el("option", { value: "" }, auto ? `Auto (${tv.countries[auto] || auto})` : "Pick a country"),
    ...names.map(([code, name]) => el("option", { value: code }, name)));
  select.value = load(COUNTRY_KEY, null) || "";
  select.addEventListener("change", () => {
    country = select.value || auto;
    save(COUNTRY_KEY, select.value || null);
    render();
  });
}

async function fetchData() {
  for (const url of SOURCES) {
    try {
      const r = await fetch(url, { cache: "no-cache" });
      if (r.ok) return await r.json();
    } catch { /* try the next location */ }
  }
  throw new Error("matches_ranked.json not found");
}

// Favourites from scoring.json plus the ones picked on this device.
function isFavourite(team) {
  return favourites.has(team) || data.favourites.includes(team);
}

// Re-score with this device's favourites: the base score and bonus come from the pipeline.
// Points from My Style: average of how much you like each team's style, plus a clash bonus.
function styleBonus(m) {
  const styles = [teamStyles[m.home]?.style, teamStyles[m.away]?.style].filter(Boolean);
  if (!styles.length) return { points: 0, text: "" };
  const avg = styles.reduce((t, st) => t + (myStyle.prefs[st] ?? 0), 0) / styles.length;
  let points = Math.round(STYLE_POINTS * avg), text = "";
  const clash = myStyle.clash && styles.length === 2 &&
    CLASHES.some(([a, b]) => (styles[0] === a && styles[1] === b) || (styles[0] === b && styles[1] === a));
  if (clash) points += CLASH_POINTS;
  if (points) text = `${points > 0 ? "+" : ""}${points} My Style` + (clash ? " (clash of styles)" : "");
  return { points, text, clash };
}

function mult(signal, b) {
  const key = signal === "stakes" ? (STAKE_KIND[b.kind] || "title") : signal;
  return feed.mults[key] ?? 1;
}

// Re-score with this device's My Feed sliders. Weights are renormalised so the scale stays
// 0-100: turning everything up doesn't inflate scores, it changes which matches rise.
function rescore(m) {
  let raw = 0, w = 0, wm = 0;
  const parts = {};
  for (const [name, b] of Object.entries(m.breakdown)) {
    const weight = data.weights[name] || 0, k = mult(name, b);
    parts[name] = k;
    raw += b.points * k; w += weight; wm += weight * k;
  }
  const base = wm > 0 ? raw * (w / wm) : 0;
  const fav = isFavourite(m.home) || isFavourite(m.away);
  const boost = fav ? data.favourite_boost : 0;
  const sb = styleBonus(m);
  const score = Math.max(0, Math.min(100, Math.round(100 * (base + m.competition_bonus + (m.stage_bonus || 0)) / data.scale_reference) + boost + sb.points));
  const must = score >= data.must_watch_threshold || (m.tier1_rivalry && (feed.mults.rivalry ?? 1) > 0);
  const rec = !must && score >= data.recommended_threshold;
  return { ...m, score, boost, fav, must, rec, parts, personalBase: Math.round(base * 10) / 10, styleBonus: sb };
}

const dayFmt = new Intl.DateTimeFormat("en-GB", { weekday: "long", day: "numeric", month: "long", timeZone: "Europe/Paris" });
const timeFmt = new Intl.DateTimeFormat("en-GB", { hour: "2-digit", minute: "2-digit", timeZone: "Europe/Paris" });

function dayLabel(iso) {
  const today = new Intl.DateTimeFormat("en-CA", { timeZone: "Europe/Paris" }).format(new Date());
  const tomorrow = new Intl.DateTimeFormat("en-CA", { timeZone: "Europe/Paris" }).format(new Date(Date.now() + 864e5));
  if (iso === today) return "Today";
  if (iso === tomorrow) return "Tomorrow";
  return dayFmt.format(new Date(iso + "T12:00:00"));
}

// ---------- Live scores (ESPN public feed, read straight from the browser) ----------

const live = new Map();      // espn id -> {state, clock, home, away, homeScore, awayScore, events}
const summaries = new Map(); // espn id -> {at, stats}

// ESPN groups games by US Eastern date.
const etDate = new Intl.DateTimeFormat("en-CA", { timeZone: "America/New_York" });
const ymd = d => etDate.format(d).replaceAll("-", "");

// Matches worth asking ESPN about now: from 10 minutes before kickoff to 3 hours after.
function liveCandidates() {
  const now = Date.now();
  return data.matches.filter(m => {
    if (!m.espn) return false;
    const k = new Date(m.kickoff_paris).getTime();
    return now >= k - 10 * 60e3 && now <= k + 3 * 3600e3;
  });
}

function readEvent(e) {
  const comp = e.competitions[0];
  const side = {};
  for (const c of comp.competitors) side[c.homeAway] = c;
  const teamSide = id => (side.home.team.id === id ? "home" : "away");
  const events = (comp.details || []).filter(d => !d.shootout && (d.scoringPlay || d.redCard)).map(d => ({
    minute: d.clock?.displayValue || "",
    side: teamSide(d.team?.id),
    kind: d.redCard ? "red" : d.ownGoal ? "own goal" : d.penaltyKick ? "pen" : "goal",
    who: (d.athletesInvolved || []).map(a => a.displayName || a.shortName).filter(Boolean).join(", "),
  }));
  return {
    state: e.status.type.state, clock: e.status.type.shortDetail,
    homeScore: side.home.score, awayScore: side.away.score,
    homeId: side.home.team.id, events,
  };
}

async function pollLive() {
  const wanted = liveCandidates();
  const boards = new Set(wanted.map(m => `${m.espn.league}|${ymd(new Date(m.kickoff_paris))}`));
  await Promise.all([...boards].map(async key => {
    const [league, date] = key.split("|");
    try {
      const r = await fetch(`${ESPN}/${league}/scoreboard?dates=${date}`);
      if (!r.ok) return;
      for (const e of (await r.json()).events || []) live.set(e.id, readEvent(e));
    } catch { /* offline or feed down: keep the last known state */ }
  }));
  document.querySelectorAll("[data-espn]").forEach(paintLive);
  const active = wanted.some(m => (live.get(m.espn.id)?.state ?? "pre") !== "post");
  if (active) setTimeout(pollLive, LIVE_POLL_MS);
}

function paintLive(node) {
  const info = live.get(node.dataset.espn);
  const strip = node.querySelector(".live");
  if (!info || info.state === "pre") { strip.hidden = true; return; }
  strip.hidden = false;
  strip.classList.toggle("on", info.state === "in");
  strip.replaceChildren(
    el("span", { class: "live-tag" }, info.state === "in" ? `LIVE ${info.clock}` : info.clock),
    el("span", { class: "live-score" }, `${info.homeScore} – ${info.awayScore}`));
  const centre = node.querySelector(".centre");
  if (centre && !centre.hidden) paintCentre(node);
}

async function loadStats(m) {
  const cached = summaries.get(m.espn.id);
  const state = live.get(m.espn.id)?.state;
  if (cached && (state === "post" || Date.now() - cached.at < 60e3)) return cached.stats;
  try {
    const r = await fetch(`${ESPN}/${m.espn.league}/summary?event=${m.espn.id}`);
    if (!r.ok) return cached?.stats;
    const teams = (await r.json()).boxscore?.teams || [];
    const homeId = live.get(m.espn.id)?.homeId;
    const pick = isHome => teams.find(t => (t.team.id === homeId) === isHome);
    const values = t => Object.fromEntries((t?.statistics || []).map(s => [s.label || s.name, s.displayValue]));
    const stats = { home: values(pick(true)), away: values(pick(false)) };
    summaries.set(m.espn.id, { at: Date.now(), stats });
    return stats;
  } catch { return cached?.stats; }
}

async function paintCentre(node) {
  const m = data.matches.find(x => x.espn && x.espn.id === node.dataset.espn)
    || results?.matches.find(x => x.espn && x.espn.id === node.dataset.espn);
  const info = live.get(node.dataset.espn);
  const centre = node.querySelector(".centre");
  if (!m || !info || info.state === "pre") { centre.hidden = true; return; }
  centre.hidden = false;
  const line = ev => el("li", { class: ev.side },
    el("span", { class: "min" }, ev.minute),
    el("span", {}, (ev.kind === "red" ? "🟥 " : "⚽ ") + ev.who + (["own goal", "pen"].includes(ev.kind) ? ` (${ev.kind})` : "")));
  const stats = await loadStats(m);
  const rows = stats ? STAT_ROWS.filter(([k]) => stats.home[k] != null || stats.away[k] != null).map(([k, label, fmt]) => {
    const f = fmt || (v => v ?? "–");
    return el("tr", {}, el("td", {}, f(stats.home[k])), el("th", { scope: "row" }, label), el("td", {}, f(stats.away[k])));
  }) : [];
  centre.replaceChildren(
    info.events.length ? el("ul", { class: "events" }, info.events.map(line)) : el("p", { class: "quiet" }, "No goals yet."),
    rows.length ? el("table", { class: "stats" },
      el("thead", {}, el("tr", {}, el("th", {}, m.home), el("th", {}), el("th", {}, m.away))),
      el("tbody", {}, rows)) : null,
    el("p", { class: "quiet" }, "Data: ESPN"));
}

const crests = {};  // team -> badge URL, from matches_ranked.json and results.json

function crest(name) {
  const url = crests[name];
  if (!url) return null;
  const img = el("img", { class: "crest", src: url, alt: "", width: "28", height: "28", loading: "lazy", decoding: "async" });
  img.addEventListener("error", () => img.remove());  // a missing badge just disappears
  return img;
}

// A team name with its badge; `after` puts the badge on the right (away side of a result).
function team(name, after = false) {
  const label = isFavourite(name) ? el("span", { class: "fav" }, "★ " + name) : el("span", {}, name);
  return el("span", { class: "team" }, after ? [label, crest(name)] : [crest(name), label]);
}

function breakdown(m) {
  const rows = Object.entries(m.breakdown).map(([name, b]) => {
    const max = data.weights[name];
    const pct = max ? Math.round((b.points / max) * 100) : 0;
    const k = m.parts?.[name] ?? 1;
    return el("div", { class: "row" },
      el("span", { class: "name" }, SIGNAL_LABELS[name] || name),
      el("div", { class: "track", role: "img", "aria-label": `${b.points} of ${max}` },
        el("div", { class: "fill", style: `width:${pct}%` })),
      el("span", { class: "pts" }, `${b.points}/${max}`, k !== 1 ? el("small", { class: "mult" }, ` ×${k}`) : null),
      b.reason ? el("span", { class: "why" }, b.reason) : null);
  });
  const extras = [];
  if (m.competition_bonus) extras.push(`+${m.competition_bonus} ${m.competition} bonus`);
  if (m.stage_bonus) extras.push(`+${m.stage_bonus} knockout round`);
  if (m.tier1_rivalry) extras.push("Must-watch: tier-1 rivalry");
  if (m.styleBonus?.text) extras.push(m.styleBonus.text);
  if (Object.keys(feed.mults).length) extras.push("Weighted by My Feed");
  const styleLine = [m.home, m.away].filter(t => teamStyles[t]).map(t => {
    const [icon, label] = STYLE_INFO[teamStyles[t].style];
    return `${t}: ${icon} ${label}`;
  });
  return el("div", { class: "breakdown" },
    styleLine.length ? el("p", { class: "styles-line" }, styleLine.join(" · ")) : null,
    rows,
    extras.length ? el("p", { class: "extras" }, extras.join(" · ")) : null);
}

function card(m) {
  const id = "b-" + m.id;
  const centre = el("div", { class: "centre" });
  centre.hidden = true;
  const detail = el("div", { id }, centre, watchDetail(m), breakdown(m));
  detail.hidden = true;
  let node;
  const button = el("button", {
    type: "button", "aria-expanded": "false", "aria-controls": id,
    onclick: () => {
      detail.hidden = !detail.hidden;
      button.setAttribute("aria-expanded", String(!detail.hidden));
      if (!detail.hidden && m.espn) { centre.hidden = false; paintCentre(node); }
    },
  },
    el("div", { class: "meta" },
      el("span", {}, timeFmt.format(new Date(m.kickoff_paris))),
      el("span", {}, m.competition),
      m.must ? el("span", { class: "badge" }, "Must-watch") : null,
      m.rec ? el("span", { class: "badge rec" }, "Recommended") : null),
    el("div", { class: "teams" }, team(m.home), " v ", team(m.away)),
    el("div", { class: "live", hidden: "" }),
    el("div", { class: "score", "aria-label": `Score ${m.score} out of 100` }, String(m.score)),
    m.story ? el("div", { class: "story" }, m.story) : null,
    watchLine(m));
  node = el("article", { class: "card" + (m.must ? " must" : m.rec ? " rec" : "") + (m.fav ? " fav" : "") }, button, detail);
  if (m.espn) {
    node.dataset.espn = m.espn.id;
    paintLive(node);
  }
  return node;
}

function render() {
  document.getElementById("days").hidden = view !== "week";
  document.getElementById("results").hidden = view !== "results";
  document.querySelectorAll(".tabs button").forEach(b => b.setAttribute("aria-selected", String(b.dataset.view === view)));
  if (view === "results") return renderResults();
  const matches = data.matches.map(rescore).filter(m => !hidden.has(m.competition));
  const byDay = new Map();
  for (const m of matches) {
    if (!byDay.has(m.day)) byDay.set(m.day, []);
    byDay.get(m.day).push(m);
  }
  const root = document.getElementById("days");
  root.replaceChildren();
  if (!matches.length) {
    root.append(el("p", { class: "empty" }, "No matches for these filters this week."));
    return;
  }
  for (const day of [...byDay.keys()].sort()) {
    // Best first: must-watch, then favourites, then score. By kickoff: the day in time order.
    const list = byDay.get(day).sort(sortBy === "time"
      ? (a, b) => a.kickoff_paris.localeCompare(b.kickoff_paris) || (b.score - a.score)
      : (a, b) => (b.must - a.must) || (b.fav - a.fav) || (b.score - a.score) || a.kickoff_paris.localeCompare(b.kickoff_paris));
    root.append(el("section", { class: "day" }, el("h2", {}, dayLabel(day)), list.map(card)));
  }
  const n = favourites.size + data.favourites.length;
  document.getElementById("fav-count").textContent = n ? `(${n})` : "";
}

// ---------- Results: past matches, with search ----------

const RESULTS_SOURCES = ["results.json", "../output/results.json"];
const VIEW_KEY = "mr.view";
const SPOILER_KEY = "mr.hideScores";
const PAGE = 60;
let view = load(VIEW_KEY, "week");
const SORT_KEY = "mr.sort";
let sortBy = load(SORT_KEY, "score");  // "score" (best first) or "time" (kickoff order)
let results = null;
let shown = PAGE;
let hideScores = load(SPOILER_KEY, false);

// "Barça", "barca", "BARCELONA" all match; aliases come from teams.csv.
const fold = t => t.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();

function matchesQuery(m, q) {
  if (!q) return true;
  const hay = [m.home, m.away, results.aliases[m.home] || "", results.aliases[m.away] || "", m.competition].map(fold).join(" ");
  return q.split(" ").every(word => hay.includes(word));
}

async function ensureEvent(m) {
  // A past game's goals and cards come from that day's ESPN scoreboard.
  if (!m.espn || live.has(m.espn.id)) return;
  try {
    const r = await fetch(`${ESPN}/${m.espn.league}/scoreboard?dates=${ymd(new Date(m.kickoff_paris))}`);
    if (r.ok) for (const e of (await r.json()).events || []) live.set(e.id, readEvent(e));
  } catch { /* offline: the panel says so */ }
}

function resultRow(m) {
  const homeWon = m.home_goals > m.away_goals, awayWon = m.away_goals > m.home_goals;
  const score = el("span", { class: "result-score" + (hideScores ? " veiled" : "") },
    hideScores ? "? – ?" : `${m.home_goals} – ${m.away_goals}`);
  const centre = el("div", { class: "centre" });
  centre.hidden = true;
  let node;
  const button = el("button", { type: "button", "aria-expanded": "false",
    onclick: async () => {
      const open = centre.hidden;
      centre.hidden = !open;
      button.setAttribute("aria-expanded", String(open));
      if (open) {
        score.textContent = `${m.home_goals} – ${m.away_goals}`;  // opening a game reveals its score
        score.classList.remove("veiled");
        const before = pastScore(m);
        const note = before
          ? el("p", { class: "before" }, el("strong", {}, `Before kickoff: ${before.score}/100`), before.must ? " · Must-watch" : before.rec ? " · Recommended" : "",
              before.story ? el("span", { class: "quiet block" }, before.story) : null,
              m.interest.reconstructed ? el("span", { class: "quiet block" }, "Rebuilt afterwards from the form, tables and results as they stood before kickoff.") : null)
          : el("p", { class: "quiet" }, "No pre-match score: played before the site started rating matches.");
        if (m.espn) { centre.replaceChildren(el("p", { class: "quiet" }, "Loading…")); await ensureEvent(m); await paintCentre(node); centre.prepend(note); }
        else centre.replaceChildren(note, el("p", { class: "quiet" }, "No match details for this game."));
      }
    } },
    el("div", { class: "meta" }, el("span", {}, timeFmt.format(new Date(m.kickoff_paris))), el("span", {}, m.competition),
      interestPill(m)),
    el("div", { class: "result-line" },
      el("span", { class: "side" + (homeWon && !hideScores ? " won" : "") }, team(m.home)),
      score,
      el("span", { class: "side away" + (awayWon && !hideScores ? " won" : "") }, team(m.away, true))));
  node = el("article", { class: "card result" }, button, centre);
  if (m.espn) node.dataset.espn = m.espn.id;
  return node;
}

// The score a match had before kickoff (frozen in score_archive.json), re-scored with My Feed.
function pastScore(m) {
  if (!m.interest) return null;
  return rescore({ ...m, ...m.interest, breakdown: m.interest.breakdown });
}

function interestPill(m) {
  const p = pastScore(m);
  if (!p) return null;
  const cls = p.must ? "interest must" : p.rec ? "interest rec" : "interest";
  return el("span", { class: cls, title: m.interest.reconstructed ? "Worth-watching score before kickoff (rebuilt from pre-match data)" : "Worth-watching score before kickoff" }, `${p.score}`);
}

async function renderResults() {
  const list = document.getElementById("results-list");
  if (!results) {
    list.replaceChildren(el("p", { class: "empty" }, "Loading results…"));
    results = await fetchJson(RESULTS_SOURCES);
    if (!results) { list.replaceChildren(el("p", { class: "empty" }, "Couldn't load results.")); return; }
    for (const [k, v] of Object.entries(results.crests || {})) crests[k] ??= v;
    for (const [k, v] of Object.entries(results.styles || {})) teamStyles[k] ??= v;
  }
  const q = fold(document.getElementById("search").value || "");
  const found = results.matches.filter(m => !hidden.has(m.competition) && matchesQuery(m, q));
  const byDay = new Map();
  for (const m of found.slice(0, shown)) {
    if (!byDay.has(m.day)) byDay.set(m.day, []);
    byDay.get(m.day).push(m);
  }
  list.replaceChildren(
    found.length ? el("p", { class: "quiet" }, `${found.length} match${found.length === 1 ? "" : "es"}${q ? ` for “${document.getElementById("search").value.trim()}”` : " this season"}`)
      : el("p", { class: "empty" }, "No results for this search."),
    ...[...byDay.entries()].map(([day, ms]) => el("section", { class: "day" }, el("h2", {}, dayLabel(day)),
      (sortBy === "time" ? ms : [...ms].sort((a, b) => (pastScore(b)?.score ?? -1) - (pastScore(a)?.score ?? -1))).map(resultRow))),
    found.length > shown ? el("button", { type: "button", class: "more", onclick: () => { shown += PAGE; renderResults(); } }, `Show more (${found.length - shown} left)`) : null);
}

function setupTabs() {
  document.querySelectorAll(".tabs button").forEach(b => b.addEventListener("click", () => {
    view = b.dataset.view;
    save(VIEW_KEY, view);
    render();
  }));
  const sorts = document.querySelectorAll(".sort button");
  const paintSort = () => sorts.forEach(b => b.setAttribute("aria-pressed", String(b.dataset.sort === sortBy)));
  paintSort();
  sorts.forEach(b => b.addEventListener("click", () => { sortBy = b.dataset.sort; save(SORT_KEY, sortBy); paintSort(); render(); }));
  const search = document.getElementById("search");
  search.addEventListener("input", () => { shown = PAGE; renderResults(); });
  const spoiler = document.getElementById("hide-scores");
  spoiler.checked = hideScores;
  spoiler.addEventListener("change", () => { hideScores = spoiler.checked; save(SPOILER_KEY, hideScores); renderResults(); });
}

// ---------- Landing page and competitions panel ----------

const LANDING_KEY = "mr.seenLanding";

function showLanding(show) {
  document.getElementById("landing").hidden = !show;
  document.getElementById("app").hidden = show;
  window.scrollTo(0, 0);
}

function setupShell() {
  const enter = () => { save(LANDING_KEY, true); showLanding(false); };
  document.getElementById("enter").addEventListener("click", enter);
  document.getElementById("enter-quiz").addEventListener("click", () => {
    enter();
    endQuiz();
    document.getElementById("feed").showModal();
    startQuiz();
  });
  document.getElementById("home").addEventListener("click", () => showLanding(true));
  const comps = document.getElementById("comps");
  document.getElementById("open-comps").addEventListener("click", () => comps.showModal());
  const setAll = hide => {
    hidden = new Set(hide ? [...new Set(data.matches.map(m => m.competition))] : []);
    save(COMP_KEY, [...hidden]);
    renderChips();
    render();
  };
  document.getElementById("comps-all").addEventListener("click", () => setAll(false));
  document.getElementById("comps-none").addEventListener("click", () => setAll(true));
}

function compsLabel() {
  const all = [...new Set(data.matches.map(m => m.competition))];
  const shown = all.filter(c => !hidden.has(c));
  document.getElementById("comps-label").textContent =
    shown.length === all.length ? "All competitions" : shown.length === 1 ? shown[0] : `${shown.length} of ${all.length} competitions`;
}

function renderChips() {
  const comps = [...new Set(data.matches.map(m => m.competition))].sort();
  const box = document.getElementById("competitions");
  box.replaceChildren(...comps.map(c => {
    const chip = el("button", { type: "button", class: "chip", "aria-pressed": String(!hidden.has(c)) }, c);
    chip.addEventListener("click", () => {
      hidden.has(c) ? hidden.delete(c) : hidden.add(c);
      chip.setAttribute("aria-pressed", String(!hidden.has(c)));
      save(COMP_KEY, [...hidden]);
      compsLabel();
      render();
    });
    return chip;
  }));
  compsLabel();
}

function setupFavourites() {
  const dialog = document.getElementById("favs");
  const list = document.getElementById("fav-list");
  const search = document.getElementById("fav-search");
  document.getElementById("boost").textContent = data.favourite_boost;
  const teams = [...new Set(data.matches.flatMap(m => [m.home, m.away]))].sort((a, b) => a.localeCompare(b));

  function draw() {
    const q = search.value.trim().toLowerCase();
    list.replaceChildren(...teams.filter(t => t.toLowerCase().includes(q)).map(t => {
      const fixed = data.favourites.includes(t);
      const box = el("input", { type: "checkbox" });
      box.checked = fixed || favourites.has(t);
      box.disabled = fixed;
      box.addEventListener("change", () => {
        box.checked ? favourites.add(t) : favourites.delete(t);
        save(FAV_KEY, [...favourites]);
        render();
      });
      return el("label", {}, box, t + (fixed ? " (from scoring.json)" : ""));
    }));
  }
  search.addEventListener("input", draw);
  document.getElementById("open-favs").addEventListener("click", () => { draw(); dialog.showModal(); });
}

// ---------- My Feed panel ----------

function saveFeed() {
  save(FEED_KEY, feed);
  document.getElementById("open-feed").classList.toggle("on", Object.keys(feed.mults).length > 0);
  document.getElementById("feed-name").textContent = feed.profile || (Object.keys(feed.mults).length ? "Custom" : "");
  render();
}

function applyMults(mults, profile) {
  feed = { mults: Object.fromEntries(Object.entries(mults).filter(([, v]) => v !== 1)), profile };
  saveFeed();
}

function drawSliders() {
  const box = document.getElementById("feed-sliders");
  box.replaceChildren(...SLIDERS.map(([id, label, hint]) => {
    const value = feed.mults[id] ?? 1;
    const out = el("output", {}, LEVELS[value * 2]);
    const input = el("input", { type: "range", min: "0", max: "2", step: "0.5", "aria-label": label });
    input.value = String(value);
    input.addEventListener("input", () => {
      const v = Number(input.value);
      out.textContent = LEVELS[v * 2];
      const mults = { ...feed.mults, [id]: v };
      applyMults(mults, null);
      markPreset();
    });
    return el("div", { class: "slider" },
      el("div", { class: "slider-head" }, el("strong", {}, label), out),
      input, el("span", { class: "hint" }, hint));
  }));
}

function markPreset() {
  const current = JSON.stringify(feed.mults);
  document.querySelectorAll("#feed-presets .chip").forEach(chip => {
    const p = Object.fromEntries(Object.entries(PRESETS[chip.textContent]).filter(([, v]) => v !== 1));
    chip.setAttribute("aria-pressed", String(JSON.stringify(p) === current && !feed.profile));
  });
}

function startQuiz() {
  const view = document.getElementById("quiz");
  const answers = {};
  document.getElementById("feed-main").hidden = true;
  view.hidden = false;
  const step = i => {
    if (i === QUIZ.length) return finish();
    const { q, a } = QUIZ[i];
    view.replaceChildren(
      el("p", { class: "quiz-step" }, `Question ${i + 1} of ${QUIZ.length}`),
      el("div", { class: "quiz-bar" }, el("div", { style: `width:${(i / QUIZ.length) * 100}%` })),
      el("h3", {}, q),
      ...a.map(([label, set]) => el("button", { type: "button", class: "answer", onclick: () => { Object.assign(answers, set); step(i + 1); } }, label)),
      el("button", { type: "button", class: "link", onclick: endQuiz }, "Cancel"));
  };
  const finish = () => {
    const top = Object.entries(answers).sort((x, y) => y[1] - x[1])[0];
    const profile = top && top[1] > 1 ? PROFILES[top[0]] : "The All-Rounder";
    applyMults(answers, profile);
    const picks = data.matches.map(rescore).sort((x, y) => y.score - x.score).slice(0, 3);
    view.replaceChildren(
      el("p", { class: "quiz-step" }, "Your football profile"),
      el("h3", { class: "profile" }, profile),
      el("p", {}, "Your top picks this week:"),
      el("ol", { class: "picks" }, picks.map(m => el("li", {}, `${m.home} v ${m.away} `, el("span", { class: "quiet" }, `(${m.score})`)))),
      el("button", { type: "button", class: "primary", onclick: () => { endQuiz(); document.getElementById("feed").close(); } }, "See my feed"),
      el("button", { type: "button", class: "link", onclick: endQuiz }, "Fine-tune the sliders"));
  };
  step(0);
}

function endQuiz() {
  document.getElementById("quiz").hidden = true;
  document.getElementById("feed-main").hidden = false;
  drawSliders();
  markPreset();
}

function setupFeed() {
  const dialog = document.getElementById("feed");
  document.getElementById("feed-presets").replaceChildren(...Object.keys(PRESETS).map(name =>
    el("button", { type: "button", class: "chip", "aria-pressed": "false",
      onclick: () => { applyMults({ ...PRESETS[name] }, name === "Balanced" ? null : name); drawSliders(); markPreset(); } }, name)));
  document.getElementById("start-quiz").addEventListener("click", startQuiz);
  document.getElementById("open-feed").addEventListener("click", () => { endQuiz(); dialog.showModal(); });
  document.getElementById("open-feed").classList.toggle("on", Object.keys(feed.mults).length > 0);
  document.getElementById("feed-name").textContent = feed.profile || (Object.keys(feed.mults).length ? "Custom" : "");
}

// ---------- My Style panel ----------

function saveStyle() {
  save(STYLE_KEY, myStyle);
  const on = Object.values(myStyle.prefs).some(v => v) || myStyle.clash;
  document.getElementById("open-style").classList.toggle("on", on);
  document.getElementById("style-name").textContent = myStyle.profile || (on ? "Custom" : "");
  render();
}

function drawStyleSliders() {
  const box = document.getElementById("style-sliders");
  box.replaceChildren(...Object.entries(STYLE_INFO).map(([id, [icon, label, hint]]) => {
    const value = myStyle.prefs[id] ?? 0;
    const out = el("output", {}, STYLE_LEVELS[(value + 1) * 2]);
    const input = el("input", { type: "range", min: "-1", max: "1", step: "0.5", "aria-label": label });
    input.value = String(value);
    input.addEventListener("input", () => {
      const v = Number(input.value);
      out.textContent = STYLE_LEVELS[(v + 1) * 2];
      myStyle = { ...myStyle, prefs: { ...myStyle.prefs, [id]: v }, profile: null };
      saveStyle();
    });
    return el("div", { class: "slider" },
      el("div", { class: "slider-head" }, el("strong", {}, `${icon} ${label}`), out),
      input, el("span", { class: "hint" }, hint));
  }));
  const clash = document.getElementById("style-clash");
  clash.checked = !!myStyle.clash;
}

function startStyleQuiz() {
  const view = document.getElementById("style-quiz");
  const prefs = {};
  let clash = false;
  document.getElementById("style-main").hidden = true;
  view.hidden = false;
  const step = i => {
    if (i === STYLE_QUIZ.length) return finish();
    const { q, a } = STYLE_QUIZ[i];
    view.replaceChildren(
      el("p", { class: "quiz-step" }, `Question ${i + 1} of ${STYLE_QUIZ.length}`),
      el("div", { class: "quiz-bar" }, el("div", { style: `width:${(i / STYLE_QUIZ.length) * 100}%` })),
      el("h3", {}, q),
      ...a.map(([label, delta]) => el("button", { type: "button", class: "answer", onclick: () => {
        for (const [k, v] of Object.entries(delta)) {
          if (k === "__clash") clash = v;
          else prefs[k] = Math.max(-1, Math.min(1, (prefs[k] ?? 0) + v));
        }
        step(i + 1);
      } }, label)),
      el("button", { type: "button", class: "link", onclick: endStyleQuiz }, "Cancel"));
  };
  const finish = () => {
    const top = Object.entries(prefs).sort((x, y) => y[1] - x[1])[0];
    const profile = top && top[1] > 0 ? STYLE_PROFILES[top[0]] : "The Open Mind";
    myStyle = { prefs, clash, profile };
    saveStyle();
    const loved = Object.entries(prefs).filter(([, v]) => v > 0).sort((x, y) => y[1] - x[1]).map(([k]) => STYLE_INFO[k][0] + " " + STYLE_INFO[k][1]);
    const picks = data.matches.map(rescore).filter(m => m.styleBonus.points > 0).sort((x, y) => y.score - x.score).slice(0, 3);
    view.replaceChildren(
      el("p", { class: "quiz-step" }, "Your football style"),
      el("h3", { class: "profile" }, profile),
      loved.length ? el("p", {}, "You enjoy: " + loved.join(", ")) : null,
      picks.length ? el("p", {}, "Matches in your style this week:") : null,
      picks.length ? el("ol", { class: "picks" }, picks.map(m => el("li", {}, `${m.home} v ${m.away} `, el("span", { class: "quiet" }, `(${m.score})`)))) : null,
      el("button", { type: "button", class: "primary", onclick: () => { endStyleQuiz(); document.getElementById("mystyle").close(); } }, "See my matches"),
      el("button", { type: "button", class: "link", onclick: endStyleQuiz }, "Fine-tune my style"));
  };
  step(0);
}

function endStyleQuiz() {
  document.getElementById("style-quiz").hidden = true;
  document.getElementById("style-main").hidden = false;
  drawStyleSliders();
}

function setupStyle() {
  const dialog = document.getElementById("mystyle");
  document.getElementById("start-style-quiz").addEventListener("click", startStyleQuiz);
  document.getElementById("open-style").addEventListener("click", () => { endStyleQuiz(); dialog.showModal(); });
  document.getElementById("style-clash").addEventListener("change", e => { myStyle = { ...myStyle, clash: e.target.checked }; saveStyle(); });
  document.getElementById("style-reset").addEventListener("click", () => { myStyle = { prefs: {}, clash: false, profile: null }; saveStyle(); drawStyleSliders(); });
  const on = Object.values(myStyle.prefs).some(v => v) || myStyle.clash;
  document.getElementById("open-style").classList.toggle("on", on);
  document.getElementById("style-name").textContent = myStyle.profile || (on ? "Custom" : "");
}

showLanding(!load(LANDING_KEY, false));  // before the data arrives, so nothing flashes

Promise.all([fetchData(), fetchJson(TV_SOURCES)]).then(([d, t]) => {
  data = d;
  tv = t;
  Object.assign(crests, d.crests || {});
  Object.assign(teamStyles, d.styles || {});
  setupCountry();
  const when = new Date(d.generated_at);
  document.getElementById("updated").textContent =
    `${d.matches.length} matches in the next ${d.window_days} days · updated ${dayFmt.format(when)}, ${timeFmt.format(when)}`;
  renderChips();
  setupFavourites();
  setupFeed();
  setupStyle();
  setupTabs();
  setupShell();
  render();
  pollLive();
}).catch(err => {
  document.getElementById("updated").textContent = "Couldn't load matches: " + err.message;
});
