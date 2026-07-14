// Sprylar Manager — webbversion.
// Ingen egen server: data/store.enc.json committas av en GitHub Action
// (se .github/workflows/sync.yml + scripts/sync_gmail.py), och den här
// filen hämtar/dekrypterar/ritar upp den helt i webbläsaren.

const DATA_URL = "data/store.json";
const POLL_MS = 60000; // kolla efter ny (redan synkad) data en gång i minuten

const L = { paid: "Betalt", sold: "Sålt / väntar", receipt: "Inlämningskvitto", message: "Meddelande", shipping: "Frakthandling", invoice: "Faktura", other: "Övrigt" };
const I = { paid: "✓", sold: "◷", receipt: "▣", message: "✉", shipping: "↗", invoice: "kr", other: "•" };
const MONTHS = ["januari", "februari", "mars", "april", "maj", "juni", "juli", "augusti", "september", "oktober", "november", "december"];

let state = {
  emails: [],
  listings: [],
  itemImages: {},
  lastSync: 0,
  filter: "all",
  view: "orders",
  pollHandle: null,
};

// ---------- helpers ----------
function dec(s) { const t = document.createElement("textarea"); t.innerHTML = s || ""; return t.value; }
function norm(x) {
  return {
    ...x,
    subject: dec(x.subject), snippet: dec(x.snippet), body: dec(x.body),
    order: x.order || "", buyer: x.buyer || "", object_id: x.object_id || "",
    sale_amount: Number(x.sale_amount) || 0, shipping_cost: Number(x.shipping_cost) || 0,
    total_amount: Number(x.total_amount) || 0,
    unread: Boolean(x.unread), latest_message_is_mine: Boolean(x.latest_message_is_mine),
  };
}
function cat(e) {
  const s = (e.subject + " " + (e.from || "") + " " + (e.snippet || "")).toLowerCase();
  if (s.includes("betalt objekt") || s.includes("betalningsbekräftelse")) return "paid";
  if (s.includes("sålt objekt") || s.includes("påmint köparen") || s.includes("samfraktspris")) return "sold";
  if (s.includes("inlämningskvitto") || s.includes("paket inlämnat")) return "receipt";
  if (s.includes("via tradera") || s.startsWith("ang:") || s.includes("nytt meddelande")) return "message";
  if (s.includes("frakthandlingar") || s.includes("fraktsedel")) return "shipping";
  if (s.includes("faktura")) return "invoice";
  return "other";
}
function unanswered(e) { return cat(e) === "message" && !e.latest_message_is_mine; }
function money(n) { return new Intl.NumberFormat("sv-SE", { style: "currency", currency: "SEK", maximumFractionDigits: 0 }).format(n || 0); }
function title(it) {
  const e = it.find(x => cat(x) === "sold") || it.find(x => cat(x) === "paid") || it[0];
  return e.subject
    .replace(/^Sålt objekt\s*-\s*/i, "")
    .replace(/^Betalt objekt\s*-\s*/i, "")
    .replace(/\s*\(\d{8,10}\)\.?\s*Köpare:.*$/i, "")
    .replace(/\s*\(\d{8,10}\)\s*$/i, "")
    .trim();
}
function groups() {
  const g = {}, map = {};
  state.emails.forEach(e => { if (e.order) { (g[e.order] ??= []).push(e); if (e.object_id) map[e.object_id] = e.order; } });
  state.emails.forEach(e => { if (!e.order && e.object_id && map[e.object_id] && !g[map[e.object_id]].some(x => x.id === e.id)) g[map[e.object_id]].push(e); });
  return g;
}
function mergedShipping(it) {
  const c = it.filter(e => cat(e) === "shipping" || cat(e) === "receipt" || /frakthandlingar och kvitto/i.test(e.subject || ""));
  const pick = f => c.map(e => e[f]).find(Boolean) || "";
  return { carrier: pick("shipping_carrier"), service: pick("shipping_service"), weight: pick("shipping_weight"), pickup: pick("shipping_pickup"), tracking: pick("tracking_number"), shipment: pick("shipment_number") || pick("tracking_number"), size: pick("package_size"), dimensions: pick("package_dimensions"), qr: pick("qr_code_data_url") };
}
function counts() {
  const c = { all: state.emails.length, paid: 0, sold: 0, receipt: 0, message: 0, shipping: 0, unread: 0, unanswered: 0 };
  state.emails.forEach(e => { const k = cat(e); if (c[k] != null) c[k]++; if (e.unread) c.unread++; if (unanswered(e)) c.unanswered++; });
  return c;
}
function amounts(it) {
  const sale = Math.max(0, ...it.map(e => e.sale_amount || 0));
  const shipping = Math.max(0, ...it.map(e => e.shipping_cost || 0));
  const total = Math.max(0, ...it.map(e => e.total_amount || 0)) || (sale + shipping);
  return { sale, shipping, total };
}
function paidDate(it) {
  const e = it.find(x => cat(x) === "paid") || it.find(x => cat(x) === "sold") || it[0];
  return new Date(Number(e.internal_date) || e.date);
}
function monthly() {
  const out = {};
  Object.values(groups()).forEach(it => {
    if (!it.some(e => cat(e) === "paid")) return;
    const d = paidDate(it); if (isNaN(d)) return;
    const k = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`, a = amounts(it);
    out[k] ??= { sale: 0, shipping: 0, total: 0, count: 0 };
    out[k].sale += a.sale; out[k].shipping += a.shipping; out[k].total += a.total; out[k].count++;
  });
  return Object.entries(out).sort((a, b) => b[0].localeCompare(a[0]));
}
function annual(year) {
  const r = { sale: 0, shipping: 0, total: 0, count: 0 };
  Object.values(groups()).forEach(it => {
    if (!it.some(e => cat(e) === "paid")) return;
    const d = paidDate(it); if (isNaN(d) || d.getFullYear() !== year) return;
    const a = amounts(it);
    r.sale += a.sale; r.shipping += a.shipping; r.total += a.total; r.count++;
  });
  return r;
}
function years() {
  const set = new Set();
  Object.values(groups()).forEach(it => {
    if (!it.some(e => cat(e) === "paid")) return;
    const d = paidDate(it);
    if (!isNaN(d)) set.add(d.getFullYear());
  });
  return [...set].sort((a, b) => b - a);
}
function amtRows(a) {
  return `<div class="amt-row"><span>Varor</span><strong>${money(a.sale)}</strong></div><div class="amt-row"><span>Frakt</span><strong>−${money(a.shipping)}</strong></div><div class="amt-row total"><span>Totalt</span><strong>${money(a.total)}</strong></div>`;
}
const STAGES = [
  ["unsold", "Ej sålda"],
  ["sold", "Sålda"],
  ["paid", "Betalda"],
  ["shipping", "Frakthandling"],
  ["receipt", "Inlämnade"],
];
function stage(it) {
  if (it.some(e => cat(e) === "receipt")) return "receipt";
  if (it.some(e => cat(e) === "shipping")) return "shipping";
  if (it.some(e => cat(e) === "paid")) return "paid";
  if (it.some(e => cat(e) === "sold")) return "sold";
  return "unsold";
}
function fmtEnd(iso) {
  const d = new Date(iso);
  if (isNaN(d)) return "";
  const hh = String(d.getHours()).padStart(2, "0");
  const mm = String(d.getMinutes()).padStart(2, "0");
  return `${d.getDate()} ${MONTHS[d.getMonth()].slice(0, 3)} ${hh}:${mm}`;
}
function timeAgo(ts) {
  if (!ts) return "—";
  const diffMin = Math.round((Date.now() - ts * 1000) / 60000);
  if (diffMin < 1) return "just nu";
  if (diffMin < 60) return `${diffMin} min sedan`;
  const h = Math.round(diffMin / 60);
  return `${h} tim sedan`;
}

// ---------- synk-indikator (topplinje) ----------
function showSyncBar() { document.querySelector("#sync-bar")?.classList.add("active"); }
function hideSyncBar() { document.querySelector("#sync-bar")?.classList.remove("active"); }

// ---------- laddning ----------
async function loadData() {
  showSyncBar();
  try {
    const res = await fetch(`${DATA_URL}?t=${Date.now()}`, { cache: "no-store" });
    if (!res.ok) {
      document.querySelector("#app").innerHTML = `<div style="padding:30px">Hittar ingen data ännu — har GitHub Action-synken kört minst en gång?</div>`;
      return;
    }
    const payload = await res.json();
    state.emails = (payload.emails || []).map(norm);
    state.listings = payload.listings || [];
    state.itemImages = payload.item_images || {};
    state.lastSync = payload.last_sync || 0;
    renderApp();
    startPolling();
  } catch (e) {
    document.querySelector("#app").innerHTML = `<div style="padding:30px">Kunde inte läsa data/store.json.</div>`;
  } finally {
    hideSyncBar();
  }
}

// ---------- polling (upptäck ny data som Action:en committat) ----------
function startPolling() {
  stopPolling();
  state.pollHandle = setInterval(checkForUpdate, POLL_MS);
}
function stopPolling() {
  if (state.pollHandle) clearInterval(state.pollHandle);
  state.pollHandle = null;
}
async function checkForUpdate() {
  showSyncBar();
  try {
    const res = await fetch(`${DATA_URL}?t=${Date.now()}`, { cache: "no-store" });
    if (!res.ok) return;
    const payload = await res.json();
    if ((payload.last_sync || 0) !== state.lastSync) {
      state.emails = (payload.emails || []).map(norm);
      state.listings = payload.listings || [];
      state.itemImages = payload.item_images || {};
      state.lastSync = payload.last_sync || 0;
      renderApp();
      toast("Ny data synkad från Gmail");
    } else {
      updateSyncLine();
    }
  } catch { /* tillfälligt nätverksfel, försök igen nästa gång */ } finally {
    hideSyncBar();
  }
}

// ---------- app shell ----------
function renderApp() {
  const c = counts(), m = monthly(), y2 = years();
  document.querySelector("#app").innerHTML = `
  <div class="layout">
    <aside>
      <div class="brand"><div class="logo">S</div><div><strong>Sprylar Manager</strong><small>webb</small></div></div>
      <div class="nav">
        <a href="https://mail.google.com/mail/u/0/#inbox" target="_blank">Totalt antal mejl <b>${c.all}</b></a>
        <a href="https://mail.google.com/mail/u/0/#search/is%3Aunread+in%3Ainbox" target="_blank">Olästa <b>${c.unread}</b></a>
        ${[["unanswered", "Obesvarade", c.unanswered], ["shipping", "Frakthandlingar", c.shipping], ["paid", "Betalt", c.paid], ["sold", "Sålt / väntar", c.sold], ["receipt", "Inlämningskvitton", c.receipt], ["message", "Meddelanden", c.message]]
          .map(x => `<button data-f="${x[0]}" class="${state.filter === x[0] ? "active" : ""}">${x[1]} <b>${x[2]}</b></button>`).join("")}
      </div>
      <div class="side-stats">
        <div class="side-stat"><span>Aktiva annonser</span><strong>${state.listings.length}</strong></div>
        <div class="side-stat"><span>Totalt antal mejl</span><strong>${c.all}</strong></div>
        <div class="side-stat alert"><span>Olästa</span><strong>${c.unread}</strong></div>
        <div class="side-stat alert"><span>Obesvarade</span><strong>${c.unanswered}</strong></div>
        <div class="side-stat"><span>Order</span><strong>${Object.keys(groups()).length}</strong></div>
        <div class="side-stat"><span>Frakthandlingar</span><strong>${c.shipping}</strong></div>
        <div class="side-stat"><span>Inlämnade</span><strong>${c.receipt}</strong></div>
      </div>
      <div class="versionbox"><strong>Sprylar Manager</strong><br>Statisk webbversion<br>Synkas via GitHub Actions</div>
    </aside>
    <aside class="finance-side">
      <h2>Försäljning</h2>
      ${y2.length ? y2.map(yr => { const a = annual(yr); return `<div class="fs-card"><h3>${yr}</h3><div class="fs-big">${money(a.sale - a.shipping)}</div>${amtRows(a)}<div class="fs-count">${a.count} betalda order</div></div>`; }).join("") : '<div class="fs-empty">Ingen försäljning ännu.</div>'}
      <h2>Månadsvis</h2>
      ${m.length ? m.map(([k, v]) => { const [yr, mo] = k.split("-"); return `<div class="fs-card"><h3>${MONTHS[Number(mo) - 1]} ${yr}</h3><div class="fs-big">${money(v.sale - v.shipping)}</div>${amtRows(v)}<div class="fs-count">${v.count} betalda order</div></div>`; }).join("") : '<div class="fs-empty">Inga belopp identifierade.</div>'}
    </aside>
    <main>
      <div class="top">
        <div><h1>Försäljningscentral</h1><p>Order, meddelanden, frakt och bokföringsunderlag.</p></div>
        <div class="sync-actions">
          <div class="sync" id="sync-line"></div>
          <button id="refresh-btn">Kontrollera nu</button>
        </div>
      </div>

      <div class="tabs">
        <button data-v="mail" class="${state.view === "mail" ? "active" : ""}">Mejl</button>
        <button data-v="orders" class="${state.view === "orders" ? "active" : ""}">Ordertidslinjer</button>
      </div>
      <div class="toolbar">
        <input id="q" placeholder="Sök vara, köpare, spårningsnummer eller ombud…">
        <select id="sort"><option value="new">Nyast först</option><option value="old">Äldst först</option></select>
      </div>
      <section id="content"></section>
    </main>
  </div>`;
  bind();
  draw();
  updateSyncLine();
}

function updateSyncLine() {
  const el = document.querySelector("#sync-line");
  if (el) el.innerHTML = `<strong><span class="dot"></span>Senast kontrollerad: ${new Date().toLocaleTimeString("sv-SE")}</strong>Data synkad: ${timeAgo(state.lastSync)}`;
}

function draw() {
  const q = (document.querySelector("#q")?.value || "").toLowerCase();
  const el = document.querySelector("#content");
  const sort = document.querySelector("#sort")?.value || "new";

  if (state.view === "mail") {
    let a = state.emails.filter(e =>
      (state.filter === "all" || cat(e) === state.filter || (state.filter === "unanswered" && unanswered(e))) &&
      (!q || (e.subject + " " + e.snippet + " " + e.order + " " + e.buyer + " " + e.object_id + " " + (e.tracking_number || "")).toLowerCase().includes(q))
    );
    a.sort((a, b) => sort === "old" ? new Date(a.date) - new Date(b.date) : new Date(b.date) - new Date(a.date));
    el.className = "list";
    el.innerHTML = a.map(e => {
      const k = cat(e);
      return `<article class="card"><div class="icon">${I[k]}</div><div><h3>${e.subject}</h3><div class="meta">${e.from || ""}${e.order ? ` · Order ${e.order}` : ""}${e.buyer ? ` · Köpare ${e.buyer}` : ""}</div><div class="snippet">${e.snippet || ""}</div></div><div class="right"><span class="badge">${L[k]}</span>${e.unread ? '<span class="badge red">Oläst</span>' : ""}${unanswered(e) ? '<span class="badge red">Obesvarat</span>' : ""}<a class="open" href="${e.url}" target="_blank">Gmail →</a></div></article>`;
    }).join("") || '<div class="empty">Inga mejl matchar.</div>';
    return;
  }

  let arr = Object.entries(groups()).filter(([o, it]) => {
    if (state.filter === "shipping" && !it.some(e => cat(e) === "shipping")) return false;
    if (state.filter === "paid" && !it.some(e => cat(e) === "paid")) return false;
    if (state.filter === "sold" && !it.some(e => cat(e) === "sold")) return false;
    if (state.filter === "receipt" && !it.some(e => cat(e) === "receipt")) return false;
    if (state.filter === "message" && !it.some(e => cat(e) === "message")) return false;
    if (state.filter === "unanswered" && !it.some(e => unanswered(e))) return false;
    const hay = it.map(e => [e.subject, e.buyer, e.tracking_number, e.shipping_pickup, e.shipping_carrier, e.shipping_weight, e.object_id].join(" ")).join(" ").toLowerCase();
    return !q || hay.includes(q);
  });
  arr.sort((a, b) => {
    const da = Math.max(...a[1].map(x => +new Date(x.date) || 0));
    const db = Math.max(...b[1].map(x => +new Date(x.date) || 0));
    return sort === "old" ? da - db : db - da;
  });

  const card = ([o, it]) => {
    const sold = it.find(x => cat(x) === "sold");
    const b = (sold && sold.buyer) || it.find(x => x.buyer)?.buyer || "Ej identifierad";
    const latest = [...it].sort((a, b) => new Date(b.date) - new Date(a.date))[0];
    const a = amounts(it);
    const unread = it.some(e => e.unread);
    const unans = it.some(e => unanswered(e));
    const objId = it.find(x => x.object_id)?.object_id;
    const thumb = objId && state.itemImages[objId];
    return `<article class="order" data-order="${o}"><div class="ohead">${thumb ? `<img class="thumb" src="${thumb}">` : '<div class="thumb placeholder"></div>'}<div class="otitle"><h3>${title(it)}</h3><div class="meta">${b}${objId ? ` · Obj ${objId}` : ""}</div></div></div><div class="omoney"><span>Varan ${a.sale ? money(a.sale) : "–"}</span><span>Frakt ${a.shipping ? money(a.shipping) : "–"}</span><strong>${a.total ? money(a.total) : "–"}</strong></div>${unread || unans ? `<div class="oflags">${unread ? '<span class="badge red">Oläst</span>' : ""}${unans ? '<span class="badge red">Obesvarat</span>' : ""}</div>` : ""}<a class="open" onclick="event.stopPropagation()" href="${latest.url}" target="_blank">Gmail →</a></article>`;
  };

  const listingCard = (it) => `<article class="order listing" data-listing="${it.id}"><div class="ohead">${it.image ? `<img class="thumb" src="${it.image}">` : '<div class="thumb placeholder"></div>'}<div class="otitle"><h3>${it.title}</h3><div class="meta">Sluttid ${fmtEnd(it.end_date)}</div></div></div><div class="omoney"><span>${it.bids ? `${it.bids} bud` : "Inga bud"}</span><strong>${money(it.price)}</strong></div><a class="open" onclick="event.stopPropagation()" href="${it.url}" target="_blank">Tradera →</a></article>`;
  const listings = (state.listings || []).filter(it => !q || it.title.toLowerCase().includes(q));

  el.className = "kanban";
  el.innerHTML = STAGES.map(([key, label]) => {
    if (key === "unsold") {
      return `<div class="kcol"><div class="kcol-head">${label}<b>${listings.length}</b></div>${listings.length ? listings.map(listingCard).join("") : '<div class="empty">Inga aktiva annonser</div>'}</div>`;
    }
    const items = arr.filter(([o, it]) => stage(it) === key);
    return `<div class="kcol"><div class="kcol-head">${label}<b>${items.length}</b></div>${items.length ? items.map(card).join("") : '<div class="empty">Inga order här</div>'}</div>`;
  }).join("");
}

// ---------- detaljmodal ----------
function ensureModal() {
  if (document.querySelector("#modal-backdrop")) return;
  const d = document.createElement("div");
  d.id = "modal-backdrop";
  d.className = "modal-backdrop hidden";
  d.innerHTML = `<div class="modal"><button id="modal-close" aria-label="Stäng">×</button><div id="modal-body"></div></div>`;
  document.body.appendChild(d);
  d.addEventListener("click", e => { if (e.target === d) closeModal(); });
  document.querySelector("#modal-close").onclick = closeModal;
  document.addEventListener("keydown", e => { if (e.key === "Escape") closeModal(); });
}
function openModal(html) {
  ensureModal();
  document.querySelector("#modal-body").innerHTML = html;
  document.querySelector("#modal-backdrop").classList.remove("hidden");
}
function closeModal() {
  document.querySelector("#modal-backdrop")?.classList.add("hidden");
}
function orderDetailHtml(o) {
  const it = groups()[o];
  if (!it || !it.length) return "<p>Order hittades inte.</p>";
  const sold = it.find(x => cat(x) === "sold");
  const ship = mergedShipping(it);
  const b = (sold && sold.buyer) || it.find(x => x.buyer)?.buyer || "Ej identifierad";
  const latest = [...it].sort((a, b) => new Date(b.date) - new Date(a.date))[0];
  const a = amounts(it);
  const s = ship || {};
  const objId = it.find(x => x.object_id)?.object_id;
  const thumb = objId && state.itemImages[objId];
  return `<div class="modal-head">${thumb ? `<img class="modal-thumb" src="${thumb}">` : ""}<div><h2>${title(it)}</h2><div class="meta">Köpare <strong>${b}</strong> · Order ${o}${objId ? ` · Objekt ${objId}` : ""}</div></div></div>
    <div class="modal-money"><div><span>Varan</span><strong>${a.sale ? money(a.sale) : "–"}</strong></div><div><span>Frakt</span><strong>${a.shipping ? money(a.shipping) : "–"}</strong></div><div><span>Totalt</span><strong>${a.total ? money(a.total) : "–"}</strong></div></div>
    ${ship ? `<div class="shipping-grid full"><div class="field"><span>Transportbolag</span><strong>${s.carrier || "Ej identifierat"}</strong></div><div class="field"><span>Närmaste ombud</span><strong>${s.pickup || "Ej identifierat"}</strong></div><div class="field"><span>Spårningsnr.</span><strong>${s.tracking || "Ej identifierat"}</strong></div><div class="field"><span>Sändningsnr.</span><strong>${s.shipment || "Ej identifierat"}</strong></div><div class="field"><span>Tjänst och vikt</span><strong>${[s.service, s.weight].filter(Boolean).join(" · ") || "Ej identifierat"}</strong></div><div class="field"><span>Paketstorlek och mått</span><strong>${[s.size, s.dimensions].filter(Boolean).join(" · ") || "Ej identifierat"}</strong></div></div>${s.qr ? `<img class="qr-full" src="${s.qr}" alt="QR-kod">` : ""}` : `<p class="meta">Ingen frakthandling identifierad ännu.</p>`}
    <a class="open" href="${latest.url}" target="_blank">Öppna i Gmail →</a>`;
}
function listingDetailHtml(id) {
  const it = (state.listings || []).find(x => String(x.id) === String(id));
  if (!it) return "<p>Annons hittades inte.</p>";
  return `<div class="modal-head">${it.image ? `<img class="modal-thumb" src="${it.image}">` : ""}<div><h2>${it.title}</h2><div class="meta">Sluttid ${fmtEnd(it.end_date)}</div></div></div>
    <div class="modal-money"><div><span>${it.bids ? `${it.bids} bud` : "Inga bud"}</span><strong>${money(it.price)}</strong></div></div>
    <a class="open" href="${it.url}" target="_blank">Öppna på Tradera →</a>`;
}

function toast(t) {
  const x = document.createElement("div");
  x.className = "toast"; x.textContent = t;
  document.body.appendChild(x);
  setTimeout(() => x.remove(), 3500);
}

function bind() {
  document.querySelectorAll("[data-f]").forEach(b => b.onclick = () => { state.filter = b.dataset.f; renderApp(); });
  document.querySelectorAll("[data-v]").forEach(b => b.onclick = () => { state.view = b.dataset.v; renderApp(); });
  document.querySelector("#q").oninput = draw;
  document.querySelector("#sort").onchange = draw;
  document.querySelector("#refresh-btn").onclick = () => checkForUpdate();
  document.querySelector("#content").onclick = e => {
    const oEl = e.target.closest("[data-order]");
    if (oEl) { openModal(orderDetailHtml(oEl.dataset.order)); return; }
    const lEl = e.target.closest("[data-listing]");
    if (lEl) { openModal(listingDetailHtml(lEl.dataset.listing)); return; }
  };
}

// ---------- boot ----------
loadData();
