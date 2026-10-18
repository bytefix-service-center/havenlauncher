const $ = (id) => document.getElementById(id);
const el = (tag, cls, text) => { const n = document.createElement(tag); if (cls) n.className = cls; if (text != null && text !== "") n.textContent = text; return n; };
const api = () => window.pywebview && window.pywebview.api;

let seen = 0, mediaVer = -1, cfg = {}, tab = "overview", lastName = "";

/* ---------- тексты ---------- */
const L10N = { Get: "Установить", Install: "Установить", Open: "Открыть", Update: "Обновить", Retry: "Повторить", Delete: "Удалить" };
const tr = (t) => L10N[t] || t || "";
const mmss = (s) => String(Math.floor(s / 60)).padStart(2, "0") + ":" + String(s % 60).padStart(2, "0");
const etaText = (s) => (s < 45 ? "меньше минуты" : "≈ " + Math.max(1, Math.round(s / 60)) + " мин");
const DAY = 864e5, HR = 36e5;
const span = (ms) => ms >= DAY ? Math.ceil(ms / DAY) + " дн." : ms >= HR ? Math.ceil(ms / HR) + " ч." : Math.max(1, Math.ceil(ms / 6e4)) + " мин.";
const dt = (ms) => new Date(ms).toLocaleString("ru-RU", { day: "numeric", month: "long", hour: "2-digit", minute: "2-digit" });
const dtShort = (ms) => new Date(ms).toLocaleString("ru-RU", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });

$("fPl").textContent = /Mac/i.test(navigator.platform) ? "macOS" : "Windows";

/* ---------- акцентный цвет из админки ---------- */
function hexHue(hex) {
  const m = /^#?([0-9a-f]{6})$/i.exec(hex || ""); if (!m) return null;
  const n = parseInt(m[1], 16), r = (n >> 16) / 255, g = ((n >> 8) & 255) / 255, b = (n & 255) / 255;
  const mx = Math.max(r, g, b), d = mx - Math.min(r, g, b); if (!d) return null;
  const h = mx === r ? ((g - b) / d) % 6 : mx === g ? (b - r) / d + 2 : (r - g) / d + 4;
  return Math.round(((h * 60) + 360) % 360);
}

/* ---------- верхняя панель при прокрутке ---------- */
$("scroll").addEventListener("scroll", () => $("bar").classList.toggle("show", $("scroll").scrollTop > 90), { passive: true });

/* ---------- вкладки ---------- */
function syncTabs() {
  const hasC = !$("tCommunity").hidden;
  if (!hasC) tab = "overview";
  [...$("tabs").children].forEach((b) => b.classList.toggle("on", b.dataset.t === tab));
  ["overview", "community"].forEach((t) => ($("p-" + t).hidden = t !== tab));
  $("tabs").hidden = !hasC;
}
$("tabs").onclick = (e) => {
  const b = e.target.closest("button"); if (!b) return;
  tab = b.dataset.t; syncTabs(); $("scroll").scrollTop = 0;
};

/* ---------- медиа: иконка и скриншоты ---------- */
async function loadMedia() {
  try {
    const m = await api().media();
    for (const id of ["iconImg", "barImg"]) { const i = $(id); i.hidden = !m.icon; if (m.icon) i.src = m.icon; }
    const strip = $("strip"); strip.innerHTML = "";
    m.shots.forEach((u) => { const i = el("img"); i.src = u; i.alt = ""; i.loading = "lazy"; strip.appendChild(i); });
    $("shotsWrap").hidden = !m.shots.length;
  } catch (e) {}
}

/* ---------- сообщество ---------- */
function paintCommunity() {
  const L = $("linksList"), F = $("faqList"); L.innerHTML = F.innerHTML = "";
  (cfg.links || []).forEach((l) => {
    const b = el("button", "link"); b.append(el("span", "lic", l.icon || "🔗"), el("span", "", l.label));
    b.onclick = () => api().open_url(l.url).catch(() => {}); L.appendChild(b);
  });
  (cfg.faq || []).forEach((f) => {
    const d = el("details", "q"); d.append(el("summary", "", f.q), el("p", "", f.a)); F.appendChild(d);
  });
  $("faqWrap").hidden = !(cfg.faq || []).length;
  $("tCommunity").hidden = !((cfg.links || []).length || (cfg.faq || []).length);
}

/* ---------- события ---------- */
const STAR = '<svg viewBox="0 0 24 24"><path d="M12 17.27 18.18 21l-1.64-7.03L22 9.24l-7.19-.61L12 2 9.19 8.63 2 9.24l5.46 4.73L5.82 21z"/></svg>';
function evState(x, now) {
  const { live, st, en } = x;
  const chip = live ? (en === Infinity ? "Идёт сейчас" : "До " + dtShort(en)) : "Начнётся " + dtShort(st);
  const rel = live ? (en === Infinity ? "" : "Ещё " + span(en - now)) : "Через " + span(st - now);
  return { chip, rel };
}
function openEvent(x) {
  const { e, live, st, en } = x, now = Date.now(), t = evState(x, now);
  $("sImgBox").hidden = !e.image; if (e.image) $("sImg").src = e.image;
  $("sBadge").textContent = e.badge || ""; $("sBadge").hidden = !e.badge;
  $("sTime").textContent = t.rel; $("sTime").hidden = !t.rel;
  $("sTitle").textContent = e.title;
  const w = $("sWhen"); w.innerHTML = "";
  const row = (k, v) => { const d = el("div"); d.append(k + " ", el("b", "", v)); w.appendChild(d); };
  if (live) { if (st) row("Началось:", dt(st)); row(en === Infinity ? "Окончание:" : "Закончится:", en === Infinity ? "без срока" : dt(en)); }
  else { row("Начнётся:", dt(st)); if (en !== Infinity) row("Закончится:", dt(en)); }
  $("sText").textContent = e.text || ""; $("sText").hidden = !e.text;
  const b = $("sBtn"); b.hidden = !e.url; b.textContent = e.btn || "Подробнее";
  b.onclick = () => api().open_url(e.url).catch(() => {});
  $("sheet").hidden = false; $("sheet").querySelector(".card-scroll").scrollTop = 0;
  $("sheetX").focus();
}
const closeSheet = () => ($("sheet").hidden = true);
$("sheetBg").onclick = $("sheetX").onclick = closeSheet;
addEventListener("keydown", (e) => { if (e.key === "Escape") closeSheet(); });

function paintEvents() {
  const now = Date.now(), list = [];
  (cfg.events || []).forEach((e) => {
    const st = e.start ? Date.parse(e.start) : 0, en = e.end ? Date.parse(e.end) : Infinity;
    if (now >= en) return;
    list.push({ e, live: now >= st, st, en });
  });
  list.sort((a, b) => (b.live - a.live) || (a.live ? a.en - b.en : a.st - b.st));
  const box = $("evList"); box.innerHTML = "";
  list.forEach((x) => {
    const c = el("button", "ev"), media = el("div", "ev-media");
    if (x.e.image) { const im = el("img"); im.src = x.e.image; im.alt = ""; im.loading = "lazy"; media.append(im); }
    else media.innerHTML = STAR;
    if (x.live) media.append(el("span", "ev-live", "Сейчас"));
    const sub = el("div", "ev-sub");
    if (x.e.badge) sub.append(el("span", "badge", x.e.badge));
    sub.append(el("span", "", evState(x, now).chip));
    c.append(media, el("h3", "", x.e.title), sub);
    c.onclick = () => openEvent(x); box.appendChild(c);
  });
  $("evWrap").hidden = !list.length;
}

async function loadConfig() {
  try {
    cfg = (await api().config()) || {};
    const h = hexHue(cfg.accent);
    if (h == null) document.documentElement.style.removeProperty("--h");
    else document.documentElement.style.setProperty("--h", h);
    if (cfg.tagline !== undefined) {
      const ab = $("about"), abText = cfg.tagline || "";
      if (ab.textContent !== abText) {
        ab.textContent = abText; ab.classList.add("clamp");
        $("aboutMore").hidden = abText.length < 200 && abText.split("\n").length < 4;   // короткий текст кнопки не требует
        $("aboutMore").textContent = "Показать полностью";
      }
      $("aboutWrap").hidden = !cfg.tagline;
    }
  } catch (e) {}
  paintEvents(); paintCommunity(); syncTabs();
}
setInterval(paintEvents, 6e4);
setInterval(loadConfig, 3e5);

/* ---------- состояние установки ---------- */
function render(s) {
  if (!s) return;
  const running = s.phase === "running", checking = s.phase === "checking";
  const name = s.appName || "";
  if (name !== lastName) {
    lastName = name;
    $("tname").textContent = $("barTitle").textContent = name;
    const ch = (name.trim()[0] || "").toUpperCase();
    $("letter").textContent = $("barLetter").textContent = ch;
  }
  $("dev").textContent = s.version ? "Версия " + s.version : "";
  $("fVer").textContent = s.version || "—";
  const soon = !!s.comingSoon;
  const rd = soon && s.releaseDate && /^\d{4}-\d{2}-\d{2}/.test(s.releaseDate) ? new Date(s.releaseDate.slice(0, 10) + "T00:00:00") : null;
  const rdText = rd && !isNaN(rd) ? rd.toLocaleDateString("ru-RU", { day: "numeric", month: "long", year: "numeric" }) : "";
  if (soon) $("dev").textContent = rdText ? "Выйдет " + rdText : "Скоро";
  $("fSt").textContent = soon ? (rdText ? "Выйдет " + rdText : "Скоро") : running ? "Установка…" : checking ? "Проверка…" : s.action === "update" ? "Обновление" : s.action === "launch" ? "Установлено" : s.action === "install" ? "Не установлено" : "—";

  /* сообщение / ошибка */
  const note = $("msg");
  note.textContent = running ? "" : soon ? "Игра ещё не вышла. " + (rdText ? "Дата выхода: " + rdText + "." : "Скоро.") : (s.error || !s.online) ? (s.message || "") : "";
  note.className = "note" + (s.error ? " err" : "");

  /* кнопки */
  const b1 = $("btn"), b2 = $("btn2");
  const idle = !running && !checking;
  b1.hidden = !idle || !s.button; b1.textContent = tr(s.button);
  b2.hidden = !idle || !s.button2;
  if (!b2.dataset.sure) b2.textContent = tr(s.button2);
  $("btnrow").hidden = b1.hidden && b2.hidden;

  /* прогресс (и проверка обновлений — бесконечная полоса) */
  const prog = $("progress"), track = prog.querySelector(".track");
  prog.hidden = idle;
  track.classList.toggle("ind", checking);
  if (checking) {
    $("fill").style.width = "";
    $("stage").textContent = "Проверяем обновления"; $("pct").textContent = "";
    $("step").textContent = ""; $("time").textContent = "";
  } else if (running) {
    const n = (s.stages || []).length || 1;
    const total = Math.min(1, ((s.stageIdx || 0) + (s.stageFrac || 0)) / n);
    $("fill").style.width = Math.round(total * 100) + "%";
    $("stage").textContent = s.stageName || "";
    $("pct").textContent = Math.round(total * 100) + "%";
    $("step").textContent = "Шаг " + ((s.stageIdx || 0) + 1) + " из " + n;
    $("time").textContent = mmss(s.elapsed || 0) + (s.eta != null ? " · осталось " + etaText(s.eta) : "");
  }

  /* что нового */
  const hasNotes = !!s.notes && !running;
  $("wn").hidden = !hasNotes;
  if (hasNotes) {
    const n = $("notes");
    if (n.textContent !== s.notes) {
      n.textContent = s.notes; n.classList.add("clamp");
      requestAnimationFrame(() => { $("more").hidden = n.scrollHeight <= n.clientHeight + 2; $("more").textContent = "Показать полностью"; });
    }
    $("wnVer").textContent = s.version ? "Версия " + s.version : "";
  }

  /* журнал */
  if (s.log && s.log.length) {
    const pre = $("log");
    const stick = pre.scrollTop + pre.clientHeight >= pre.scrollHeight - 30;
    pre.textContent += (pre.textContent ? "\n" : "") + s.log.join("\n");
    if (stick) pre.scrollTop = pre.scrollHeight;
  }
  seen = s.logTotal || 0;
  $("logWrap").hidden = !(seen > 0 || s.error);

  if (s.mediaVer !== mediaVer) { mediaVer = s.mediaVer; loadMedia(); }
}

/* ---------- действия ---------- */
async function press(which, btn) {
  if (which === "second" && !btn.dataset.sure) {
    btn.dataset.sure = "1"; btn.textContent = "Точно удалить?"; btn.classList.add("sure");
    setTimeout(() => { delete btn.dataset.sure; btn.classList.remove("sure"); btn.textContent = "Удалить"; }, 3000);
    return;
  }
  delete btn.dataset.sure; btn.classList.remove("sure");
  btn.disabled = true;
  try { await api().act(which); } catch (e) {}
  setTimeout(() => (btn.disabled = false), 500);
}
$("btn").onclick = () => press("main", $("btn"));
$("btn2").onclick = () => press("second", $("btn2"));

$("more").onclick = () => {
  const n = $("notes"), collapsed = n.classList.toggle("clamp");
  $("more").textContent = collapsed ? "Показать полностью" : "Свернуть";
};
$("aboutMore").onclick = () => {
  const a = $("about"), collapsed = a.classList.toggle("clamp");
  $("aboutMore").textContent = collapsed ? "Показать полностью" : "Свернуть";
};
$("lt").onclick = () => {
  const pre = $("log"); pre.hidden = !pre.hidden;
  $("lt").classList.toggle("open", !pre.hidden);
  if (!pre.hidden) pre.scrollTop = pre.scrollHeight;
};

/* ---------- опрос движка ---------- */
async function tick() {
  try {
    const s = await api().state(seen);
    if (s.logTotal < seen) { $("log").textContent = ""; seen = 0; }
    render(s);
  } catch (e) {}
  setTimeout(tick, 250);
}
window.addEventListener("pywebviewready", () => { tick(); loadConfig(); });