"use strict";

const $ = (s) => document.querySelector(s);
// 静的スナップショット版（cli.py snapshot で生成）では取り込み・収集・複数ランク選択を無効にする
const SNAPSHOT = !!window.SVWB_SNAPSHOT;
const state = { format: "rotation", days: 14, ranks: new Set(), meta: null, sort: { key: "share", dir: -1 }, decks: [] };
let shareChart = null;

// ---------- utils ----------
const pct = (v, d = 1) => (v == null ? "—" : (v * 100).toFixed(d) + "%");
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
function qs(extra = {}) {
  const p = new URLSearchParams({ format: state.format, days: state.days, ...extra });
  if (state.ranks.size && !("noRanks" in extra)) p.set("ranks", [...state.ranks].join(","));
  p.delete("noRanks");
  return p.toString();
}
async function api(path, opts) {
  const r = await fetch(path, opts);
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
  return r.json();
}
function fmtTime(iso) {
  if (!iso) return "—";
  const d = new Date(iso.replace(" ", "T") + (iso.endsWith("Z") ? "" : "Z"));
  return d.toLocaleString("ja-JP", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

// 色はクラスに固定（デッキの順位では変えない）
function classColor(cls) {
  const i = state.meta ? state.meta.classes.indexOf(cls) : -1;
  return i >= 0 ? css(`--c${i + 1}`) : css("--text-muted");
}
function classOf(deck) {
  const a = state.meta?.archetypes.find((x) => x.name === deck);
  if (a) return a.class;
  return deck.startsWith("その他") ? deck.slice(3) : null;
}

// ---------- tooltip ----------
const tip = $("#tip");
function showTip(html, ev) {
  tip.innerHTML = html;
  tip.hidden = false;
  const pad = 14, w = tip.offsetWidth, h = tip.offsetHeight;
  let x = ev.clientX + pad, y = ev.clientY + pad;
  if (x + w > innerWidth - 8) x = ev.clientX - w - pad;
  if (y + h > innerHeight - 8) y = ev.clientY - h - pad;
  tip.style.left = x + "px";
  tip.style.top = y + "px";
}
const hideTip = () => (tip.hidden = true);
document.addEventListener("scroll", hideTip, true);

// ---------- filters ----------
function buildFilters() {
  const box = $("#fRanks");
  box.innerHTML = "";
  const all = document.createElement("button");
  all.textContent = "全ランク";
  all.setAttribute("aria-pressed", state.ranks.size === 0);
  all.onclick = () => { state.ranks.clear(); buildFilters(); refresh(); };
  box.append(all);
  for (const r of [...state.meta.ranks].reverse()) {
    const b = document.createElement("button");
    b.textContent = r;
    b.setAttribute("aria-pressed", state.ranks.has(r));
    b.onclick = () => {
      if (SNAPSHOT) { const on = state.ranks.has(r); state.ranks.clear(); if (!on) state.ranks.add(r); }
      else state.ranks.has(r) ? state.ranks.delete(r) : state.ranks.add(r);
      buildFilters(); refresh();
    };
    box.append(b);
  }
}
$("#fFormat").onchange = (e) => { state.format = e.target.value; refresh(); };
$("#fDays").onchange = (e) => { state.days = +e.target.value; refresh(); };
$("#themeBtn").onclick = () => {
  const cur = document.documentElement.dataset.theme || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
  document.documentElement.dataset.theme = cur === "dark" ? "light" : "dark";
  try { localStorage.setItem("theme", document.documentElement.dataset.theme); } catch {}
  refresh();
};
try { const t = localStorage.getItem("theme"); if (t) document.documentElement.dataset.theme = t; } catch {}

// ---------- KPIs ----------
function renderKpis(s, meta) {
  const src = Object.entries(s.by_source).map(([k, v]) => `${k} ${v.toLocaleString()}`).join(" / ") || "なし";
  const live = [meta.sources.x ? "X" : null, meta.sources.rss ? `RSS×${meta.sources.rss}` : null].filter(Boolean).join("・") || "手動のみ";
  const items = [
    ["収集した投稿", s.posts.toLocaleString(), src],
    ["対戦記録", s.matches.toLocaleString(), `使用報告 ${s.reports.toLocaleString()}`],
    ["最新の投稿", fmtTime(s.last_post), `未処理 ${s.pending}`],
    ["自動収集", live, meta.sources.llm ? "抽出: Claude" : "抽出: ルール"],
  ];
  $("#kpis").innerHTML = items.map(([k, v, sub]) => `<div class="kpi"><div class="k">${k}</div><div class="v">${esc(v)}</div><div class="note">${esc(sub)}</div></div>`).join("");
  $("#updated").textContent = "最終取得 " + fmtTime(s.last_fetch);
  $("#demoBanner").hidden = !(s.by_source.demo && Object.keys(s.by_source).length === 1);
  $("#srcStatus").textContent = `X API: ${meta.sources.x ? "有効" : "未設定"} ／ RSS: ${meta.sources.rss} 件 ／ Claude 抽出: ${meta.sources.llm ? "有効" : "未設定（ルールで抽出）"} ／ 収集間隔 ${meta.poll_minutes} 分`;
}

// ---------- tier table ----------
const COLS = [
  ["deck", "デッキ"], ["class", "クラス"], ["share", "使用率"], ["trend", "直近3日の変化"],
  ["winrate", "推定勝率"], ["ci", "95% 信頼区間"], ["games", "試合数"],
];
function renderTier(rows) {
  state.decks = rows;
  const { key, dir } = state.sort;
  const sorted = [...rows].sort((a, b) => {
    const va = key === "ci" ? a.ci_low : a[key], vb = key === "ci" ? b.ci_low : b[key];
    return (typeof va === "string" ? va.localeCompare(vb, "ja") : (va ?? -1) - (vb ?? -1)) * dir;
  });
  const maxShare = Math.max(0.0001, ...rows.map((r) => r.share));
  const head = "<thead><tr>" + COLS.map(([k, l]) => `<th data-k="${k}" aria-sort="${key === k ? (dir > 0 ? "ascending" : "descending") : "none"}">${l}${key === k ? (dir > 0 ? " ▲" : " ▼") : ""}</th>`).join("") + "</tr></thead>";
  const lo = 0.3, hi = 0.7, pos = (v) => ((Math.min(hi, Math.max(lo, v)) - lo) / (hi - lo)) * 100;
  const body = sorted.map((r) => {
    const t = r.trend, cls = t > 0.01 ? "up" : t < -0.01 ? "down" : "flat";
    const arrow = t > 0.01 ? "▲" : t < -0.01 ? "▼" : "―";
    const thin = r.games < 30;
    return `<tr data-deck="${esc(r.deck)}">
      <td><span class="deckcell"><i class="dot" style="background:${classColor(r.class)}"></i>${esc(r.deck)}</span></td>
      <td class="cls">${esc(r.class ?? "")}</td>
      <td>${pct(r.share)} <span class="bar"><i style="width:${(r.share / maxShare) * 100}%"></i></span></td>
      <td class="${cls}">${arrow} ${(Math.abs(t) * 100).toFixed(1)}pt</td>
      <td>${thin ? '<span class="cls">(少)</span> ' : ""}${pct(r.winrate)}</td>
      <td><span class="ci"><i style="left:${pos(r.ci_low)}%;width:${pos(r.ci_high) - pos(r.ci_low)}%"></i><b style="left:${pos(r.winrate)}%"></b></span></td>
      <td>${Math.round(r.games).toLocaleString()}</td></tr>`;
  }).join("");
  const t = $("#tierTable");
  t.innerHTML = head + "<tbody>" + (body || `<tr><td colspan="7" class="cls">データがありません</td></tr>`) + "</tbody>";
  t.querySelectorAll("th").forEach((th) => (th.onclick = () => {
    const k = th.dataset.k;
    state.sort = { key: k, dir: state.sort.key === k ? -state.sort.dir : (k === "deck" || k === "class" ? 1 : -1) };
    renderTier(state.decks);
  }));
  t.querySelectorAll("tbody tr[data-deck]").forEach((tr) => {
    const r = rows.find((x) => x.deck === tr.dataset.deck);
    tr.onmousemove = (ev) => showTip(`<b>${esc(r.deck)}</b><br>使用率 ${pct(r.share)}（前 ${pct(r.share_prior)} → 直近 ${pct(r.share_recent)}）<br>推定勝率 ${pct(r.winrate)}（生 ${pct(r.winrate_raw)}）<br>95%CI ${pct(r.ci_low)}〜${pct(r.ci_high)}<br>試合数 ${Math.round(r.games)}`, ev);
    tr.onmouseleave = hideTip;
  });
}

// ---------- share chart ----------
function renderShares(data) {
  const top = Object.keys(data.series).slice(0, 7);
  const seenClass = {};
  const datasets = top.map((deck) => {
    const cls = classOf(deck);
    const dup = (seenClass[cls] = (seenClass[cls] || 0) + 1) > 1;
    const color = classColor(cls);
    return {
      label: deck, data: data.series[deck].map((v) => v * 100),
      borderColor: color, backgroundColor: color, borderWidth: 2, borderDash: dup ? [6, 4] : [],
      pointRadius: 0, pointHoverRadius: 5, pointHoverBorderWidth: 2, pointHoverBorderColor: css("--surface-1"), tension: 0.25,
    };
  });
  const others = data.days.map((_, i) => 100 - top.reduce((s, d) => s + data.series[d][i] * 100, 0));
  datasets.push({ label: "その他", data: others, borderColor: css("--text-muted"), backgroundColor: css("--text-muted"), borderWidth: 1.5, borderDash: [2, 3], pointRadius: 0, tension: 0.25 });
  const grid = css("--grid"), ink = css("--text-secondary");
  const cfg = {
    type: "line",
    data: { labels: data.days.map((d) => d.slice(5).replace("-", "/")), datasets },
    options: {
      responsive: true, maintainAspectRatio: false, animation: false,
      interaction: { mode: "index", intersect: false },
      scales: {
        y: { beginAtZero: true, ticks: { color: ink, callback: (v) => v + "%" }, grid: { color: grid }, border: { display: false } },
        x: { ticks: { color: ink, maxRotation: 0, autoSkipPadding: 12 }, grid: { display: false } },
      },
      plugins: {
        legend: { position: "bottom", labels: { color: css("--text-primary"), boxWidth: 14, boxHeight: 2, useBorderRadius: true, borderRadius: 1 } },
        tooltip: {
          backgroundColor: css("--surface-1"), titleColor: css("--text-primary"), bodyColor: css("--text-primary"),
          borderColor: css("--border"), borderWidth: 1, itemSort: (a, b) => b.parsed.y - a.parsed.y,
          callbacks: {
            label: (c) => ` ${c.dataset.label}  ${c.parsed.y.toFixed(1)}%`,
            footer: (items) => `サンプル ${Math.round(data.samples[items[0].dataIndex])}`,
          },
        },
      },
    },
  };
  if (shareChart) shareChart.destroy();
  shareChart = new Chart($("#shareChart"), cfg);
}

// ---------- matchup heatmap ----------
function divColor(v) {
  const d = Math.max(-1, Math.min(1, (v - 0.5) / 0.2)); // ±20pt で飽和
  const amt = Math.round(Math.abs(d) * 75);
  return `color-mix(in oklab, ${d >= 0 ? "var(--div-pos)" : "var(--div-neg)"} ${amt}%, var(--div-mid))`;
}
function renderMatchups(m) {
  const t = $("#muTable");
  if (!m.decks.length) { t.innerHTML = '<tr><td class="cls">データがありません</td></tr>'; return; }
  const head = "<thead><tr><th></th>" + m.decks.map((d) => `<th scope="col">${esc(d)}</th>`).join("") + "</tr></thead>";
  const body = m.decks.map((a, i) => "<tr><th scope=\"row\">" + esc(a) + "</th>" + m.grid[i].map((c, j) => {
    if (!c) return `<td><div class="na">${i === j ? "ミラー" : "—"}</div></td>`;
    return `<td><div class="${c.games < 30 ? "thin" : ""}" style="background:${divColor(c.winrate)}" data-i="${i}" data-j="${j}">${(c.winrate * 100).toFixed(0)}</div></td>`;
  }).join("") + "</tr>").join("");
  t.innerHTML = head + "<tbody>" + body + "</tbody>";
  t.querySelectorAll("td div[data-i]").forEach((el) => {
    const i = +el.dataset.i, j = +el.dataset.j, c = m.grid[i][j];
    el.onmousemove = (ev) => showTip(`<b>${esc(m.decks[i])}</b> vs <b>${esc(m.decks[j])}</b><br>推定勝率 ${pct(c.winrate)}（生 ${pct(c.raw)}）<br>95%CI ${pct(c.ci_low)}〜${pct(c.ci_high)}<br>試合数 ${Math.round(c.games)}${c.games < 30 ? "<br><i>サンプル不足</i>" : ""}`, ev);
    el.onmouseleave = hideTip;
  });
}

// ---------- rank table ----------
function renderRanks(r, deckOrder) {
  const t = $("#rankTable");
  const ranks = Object.keys(r);
  if (!ranks.length) { t.innerHTML = '<tr><td class="cls">データがありません</td></tr>'; return; }
  const decks = deckOrder.slice(0, 12);
  const max = Math.max(0.0001, ...ranks.flatMap((k) => decks.map((d) => r[k].share[d] || 0)));
  const head = "<thead><tr><th></th>" + decks.map((d) => `<th scope="col">${esc(d)}</th>`).join("") + '<th scope="col">サンプル</th></tr></thead>';
  const body = ranks.map((k) => `<tr><th scope="row">${esc(k)}</th>` + decks.map((d) => {
    const v = r[k].share[d] || 0;
    return `<td><div style="background:color-mix(in oklab, var(--accent) ${Math.round((v / max) * 70)}%, var(--surface-1))" data-tip="${esc(k)} 帯の ${esc(d)}: ${pct(v)}">${(v * 100).toFixed(1)}</div></td>`;
  }).join("") + `<td class="cls">${Math.round(r[k].samples)}</td></tr>`).join("");
  t.innerHTML = head + "<tbody>" + body + "</tbody>";
  t.querySelectorAll("[data-tip]").forEach((el) => { el.onmousemove = (ev) => showTip(el.dataset.tip, ev); el.onmouseleave = hideTip; });
}

// ---------- posts ----------
async function renderPosts() {
  const deck = $("#postDeck").value;
  const rows = await api("/api/posts?limit=60" + (deck ? "&deck=" + encodeURIComponent(deck) : ""));
  $("#posts").innerHTML = rows.map((p) => {
    const tags = [
      ...p.matches.map((m) => `<span class="tag ${m.result === "win" ? "w" : "l"}">${esc(m.deck)} vs ${esc(m.opponent ?? "?")} ${m.result === "win" ? "勝" : "負"}${m.rank ? " · " + esc(m.rank) : ""}</span>`),
      ...p.reports.map((r) => `<span class="tag">${esc(r.deck)}${r.wins != null ? ` ${r.wins}勝${r.losses}敗` : " 使用"}${r.rank ? " · " + esc(r.rank) : ""}</span>`),
    ].join("") || '<span class="tag">対戦情報なし</span>';
    const who = p.url ? `<a href="${esc(p.url)}" target="_blank" rel="noopener">${esc(p.author ?? "")}</a>` : esc(p.author ?? "");
    return `<li><div class="meta">${fmtTime(p.posted_at)} · ${esc(p.source)} · ${who} · ${esc(p.extractor ?? "未処理")}</div><div class="text">${esc(p.text)}</div>${tags}</li>`;
  }).join("") || '<li class="cls">投稿がありません</li>';
}
$("#postDeck").onchange = renderPosts;

// ---------- import ----------
$("#impBtn").onclick = async () => {
  const out = $("#impResult");
  out.textContent = "取り込み中…";
  try {
    const r = await api("/api/import", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ kind: $("#impKind").value, content: $("#impText").value }) });
    out.textContent = `${r.received} 件読み込み、新規 ${r.added} 件。抽出: ${JSON.stringify(r.extract)}`;
    refresh();
  } catch (e) { out.textContent = "エラー: " + e.message; }
};
$("#collectBtn").onclick = async () => {
  const out = $("#impResult");
  out.textContent = "収集中…";
  try { out.textContent = "収集結果: " + JSON.stringify(await api("/api/collect", { method: "POST" })); refresh(); }
  catch (e) { out.textContent = "エラー: " + e.message; }
};

// ---------- main ----------
async function refresh() {
  try {
    const [s, decks, shares, mu, ranks] = await Promise.all([
      api("/api/summary?" + qs()), api("/api/decks?" + qs()), api("/api/shares?" + qs()),
      api("/api/matchups?" + qs({ top: 10 })), api("/api/ranks?" + qs({ noRanks: 1 })),
    ]);
    renderKpis(s, state.meta);
    renderTier(decks);
    renderShares(shares);
    renderMatchups(mu);
    renderRanks(ranks, decks.map((d) => d.deck));
    const sel = $("#postDeck"), cur = sel.value;
    sel.innerHTML = '<option value="">すべてのデッキ</option>' + decks.map((d) => `<option ${d.deck === cur ? "selected" : ""}>${esc(d.deck)}</option>`).join("");
    renderPosts();
  } catch (e) {
    console.error(e);
  }
}

(async function init() {
  if (SNAPSHOT) {
    $("#importCard").hidden = true;
    $("#demoHint").hidden = true;
    $("#fAuto").parentElement.hidden = true;
    $("#snapNote").hidden = false;
    $("#snapNote").textContent = `静的スナップショット（${window.SVWB_SNAPSHOT.generated} 生成）。ランク帯は1つずつ選べます。`;
  }
  state.meta = await api("/api/meta");
  buildFilters();
  await refresh();
  if (!SNAPSHOT) setInterval(() => { if ($("#fAuto").checked && !document.hidden) refresh(); }, 60_000);
})();
