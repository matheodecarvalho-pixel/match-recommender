// Match Recommender: renders output/matches_ranked.json. No build step, no libraries.

const SOURCES = ["matches_ranked.json", "../output/matches_ranked.json"];
const SIGNAL_LABELS = {
  form: "Form", stakes: "Stakes", entertainment: "Goals", rivalry: "Rivalry",
  closeness: "Closeness", records: "Records", revenge: "Revenge",
};
const FAV_KEY = "mr.favourites";
const COMP_KEY = "mr.competitions";

let data = null;
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
function rescore(m) {
  const fav = isFavourite(m.home) || isFavourite(m.away);
  const boost = fav ? data.favourite_boost : 0;
  const score = Math.min(100, Math.round(m.base + m.competition_bonus + boost));
  const must = score >= data.must_watch_threshold || m.tier1_rivalry;
  return { ...m, score, boost, fav, must };
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

function team(name) {
  return isFavourite(name) ? el("span", { class: "fav" }, "★ " + name) : name;
}

function breakdown(m) {
  const rows = Object.entries(m.breakdown).map(([name, b]) => {
    const max = data.weights[name];
    const pct = max ? Math.round((b.points / max) * 100) : 0;
    return el("div", { class: "row" },
      el("span", { class: "name" }, SIGNAL_LABELS[name] || name),
      el("div", { class: "track", role: "img", "aria-label": `${b.points} of ${max}` },
        el("div", { class: "fill", style: `width:${pct}%` })),
      el("span", { class: "pts" }, `${b.points}/${max}`),
      b.reason ? el("span", { class: "why" }, b.reason) : null);
  });
  const extras = [];
  if (m.competition_bonus) extras.push(`+${m.competition_bonus} ${m.competition} bonus`);
  if (m.boost) extras.push(`+${m.boost} favourite team`);
  if (m.tier1_rivalry) extras.push("Must-watch: tier-1 rivalry");
  return el("div", { class: "breakdown" }, rows,
    el("p", { class: "extras" }, `Signals ${m.base} pts`, extras.length ? " · " + extras.join(" · ") : ""));
}

function card(m) {
  const id = "b-" + m.id;
  const detail = breakdown(m);
  detail.id = id;
  detail.hidden = true;
  const button = el("button", {
    type: "button", "aria-expanded": "false", "aria-controls": id,
    onclick: () => {
      detail.hidden = !detail.hidden;
      button.setAttribute("aria-expanded", String(!detail.hidden));
    },
  },
    el("div", { class: "meta" },
      el("span", {}, timeFmt.format(new Date(m.kickoff_paris))),
      el("span", {}, m.competition),
      m.must ? el("span", { class: "badge" }, "Must-watch") : null),
    el("div", { class: "teams" }, team(m.home), " v ", team(m.away)),
    el("div", { class: "score", "aria-label": `Score ${m.score} out of 100` }, String(m.score)),
    m.story ? el("div", { class: "story" }, m.story) : null);
  return el("article", { class: "card" + (m.must ? " must" : "") }, button, detail);
}

function render() {
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
    // Must-watch first, then favourites, then score.
    const list = byDay.get(day).sort((a, b) =>
      (b.must - a.must) || (b.fav - a.fav) || (b.score - a.score) || a.kickoff_paris.localeCompare(b.kickoff_paris));
    root.append(el("section", { class: "day" }, el("h2", {}, dayLabel(day)), list.map(card)));
  }
  const n = favourites.size + data.favourites.length;
  document.getElementById("fav-count").textContent = n ? `(${n})` : "";
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
      render();
    });
    return chip;
  }));
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

fetchData().then(d => {
  data = d;
  const when = new Date(d.generated_at);
  document.getElementById("updated").textContent =
    `${d.matches.length} matches in the next ${d.window_days} days · updated ${dayFmt.format(when)}, ${timeFmt.format(when)}`;
  renderChips();
  setupFavourites();
  render();
}).catch(err => {
  document.getElementById("updated").textContent = "Couldn't load matches: " + err.message;
});
