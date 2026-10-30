"use strict";

const AGES = { "24_and_younger": "Under 25", "25_to_29": "25–29", "30_to_34": "30–34",
               "35_to_44": "35–44", "45_to_54": "45–54", "55_and_older": "55+" };
const GENDERS = { "": "Anyone", female: "Women", male: "Men" };
const KIND_LABEL = { music: "Music", brand: "Brand", place: "Place", setting: "Setting",
  wardrobe: "Wardrobe", food_drink: "Food & drink", activity: "Activity",
  reference: "Reference", aesthetic: "Aesthetic" };
const VERDICT_WORD = { fits: "Fits", neutral: "Neutral", off: "Misses", unknown: "No data" };

const $ = (s, el = document) => el.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmtFit = (v) => (v === null || v === undefined ? "—" : (v > 0 ? "+" : "") + v.toFixed(2));
const fmtT = (s) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;
const verdictOf = (v) => (v === null || v === undefined ? "unknown" : v >= 0.2 ? "fits" : v <= -0.2 ? "off" : "neutral");

async function api(path, opts = {}) {
  const r = await fetch(path, opts);
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(body.error || `Request failed (${r.status})`);
  return body;
}

function show(id) {
  for (const m of ["home", "progress", "report", "tested"]) $("#" + m).classList.toggle("hidden", m !== id);
  $("#nav-upload").classList.toggle("on", id === "home");
  $("#nav-tested").classList.toggle("on", id === "tested");
  window.scrollTo(0, 0);
}

function seg(el, options, value, onPick) {
  el.innerHTML = "";
  for (const [v, label] of Object.entries(options)) {
    const b = document.createElement("button");
    b.type = "button"; b.textContent = label; b.dataset.v = v;
    b.setAttribute("aria-pressed", String(v === value));
    b.onclick = () => {
      for (const x of el.children) x.setAttribute("aria-pressed", String(x === b));
      onPick(v);
    };
    el.appendChild(b);
  }
}

/* ------------------------------------------------------------ home */

const upload = { file: null, age: "25_to_29", gender: "" };

async function home() {
  show("home");
  document.title = "Culture Check";
  const lim = await api("/api/limits").catch(() => null);
  if (lim) { $("#lim-s").textContent = lim.max_seconds; $("#lim-mb").textContent = lim.max_mb; }
  seg($("#up-age"), AGES, upload.age, (v) => (upload.age = v));
  seg($("#up-gender"), GENDERS, upload.gender, (v) => (upload.gender = v));
  const samples = await api("/api/samples").catch(() => []);
  $("#samples").innerHTML = samples.length ? samples.map((s) => `
    <a class="card sample" href="/r/${s.id}">
      <div class="thumb" style="background-image:url('/api/reports/${s.id}/frames/${s.frame}.jpg')">
        <span class="badge ${verdictOf(s.fit)}">${fmtFit(s.fit)} · ${esc(s.label)}</span>
      </div>
      <div class="body">
        <h3>${esc(s.title)}</h3>
        <div class="meta">${Math.round(s.duration)}s · ${s.shots} shots · ${s.cues} cues</div>
        <div style="font-size:14px">${esc(s.headline || "")}</div>
      </div>
    </a>`).join("") : `<p class="muted">No samples yet.</p>`;
}

function pickFile(f) {
  upload.file = f || null;
  $("#drop").classList.toggle("has", !!f);
  $("#drop-name").textContent = f ? f.name : "Drop a video here, or choose one";
  $("#drop-sub").textContent = f ? `${(f.size / 1048576).toFixed(1)} MB` : "";
  $("#go").disabled = !f;
}

function wireUpload() {
  const drop = $("#drop");
  $("#file").onchange = (e) => pickFile(e.target.files[0]);
  drop.ondragover = (e) => { e.preventDefault(); drop.classList.add("over"); };
  drop.ondragleave = () => drop.classList.remove("over");
  drop.ondrop = (e) => { e.preventDefault(); drop.classList.remove("over"); pickFile(e.dataTransfer.files[0]); };
  $("#upload").onsubmit = async (e) => {
    e.preventDefault();
    if (!upload.file) return;
    const fd = new FormData();
    fd.append("video", upload.file);
    fd.append("age", upload.age);
    fd.append("gender", upload.gender);
    fd.append("location", $("#up-loc").value.trim());
    fd.append("music", $("#up-music").value.trim());
    fd.append("cast", $("#up-cast").value.trim());
    $("#go").disabled = true; $("#go").textContent = "Uploading…"; $("#up-err").textContent = "";
    try {
      const { job } = await api("/api/analyse", { method: "POST", body: fd });
      const q = new URLSearchParams({ age: upload.age });
      if (upload.gender) q.set("gender", upload.gender);
      if ($("#up-loc").value.trim()) q.set("loc", $("#up-loc").value.trim());
      history.pushState({}, "", `/r/${job}?${q}`);
      route();
    } catch (err) {
      $("#up-err").textContent = err.message;
    } finally {
      $("#go").disabled = !upload.file; $("#go").textContent = "Check it";
    }
  };
}

/* ------------------------------------------------------------ progress */

async function progress(id) {
  show("progress");
  $("#pg-err").textContent = "";
  for (;;) {
    let job;
    try { job = await api(`/api/jobs/${id}`); }
    catch (err) { $("#pg-err").textContent = err.message; return false; }
    if (job.state === "done") return true;
    if (job.state === "failed") { $("#pg-err").textContent = "Something went wrong: " + job.error; return false; }
    const steps = job.steps || {};
    const done = new Set(job.done || []);
    $("#pg-sub").textContent = job.state === "queued"
      ? `Waiting for ${job.ahead} video${job.ahead === 1 ? "" : "s"} ahead of yours…`
      : `About a minute for every minute of video (this one is ${Math.round(job.seconds)}s).`;
    $("#pg-steps").innerHTML = Object.entries(steps).map(([k, label]) => {
      const cls = k === job.step ? "now" : done.has(k) ? "done" : "";
      return `<li class="${cls}"><span class="dot"></span>${esc(label)}</li>`;
    }).join("");
    await new Promise((r) => setTimeout(r, 1200));
  }
}

/* ------------------------------------------------------------ report */

const R = { report: null, view: null, aud: null, chats: {}, cue: null };

function audFromUrl(rep) {
  const q = new URLSearchParams(location.search);
  const first = rep.first_audience || {};
  return { age: q.get("age") || first.age || "25_to_29",
           gender: q.get("gender") ?? (first.gender || ""),
           location: q.get("loc") ?? (first.location || "") };
}

function audKey(a) { return `${a.age}|${a.gender}|${a.location}`; }

async function openReport(id) {
  let rep;
  try { rep = await api(`/api/reports/${id}`); }
  catch {
    const ok = await progress(id);
    if (!ok) return;
    rep = await api(`/api/reports/${id}`);
  }
  R.report = rep;
  R.aud = audFromUrl(rep);
  show("report");
  document.title = `${rep.title} · Culture Check`;
  $("#r-title").textContent = rep.title;
  $("#r-meta").textContent = `${Math.round(rep.duration)} seconds · ${rep.shots.length} shots · ${rep.cues.length} cultural cues${rep.music ? " · soundtrack: " + rep.music : ""}${rep.talent ? " · featuring " + rep.talent : ""}`;
  const v = $("#r-video");
  v.src = `/api/reports/${id}/video`;
  v.ontimeupdate = tick;
  wireAudience();
  await loadView();
}

function wireAudience() {
  seg($("#r-age"), AGES, R.aud.age, (v) => { R.aud.age = v; loadView(); });
  seg($("#r-gender"), GENDERS, R.aud.gender, (v) => { R.aud.gender = v; loadView(); });
  $("#r-loc").value = R.aud.location;
  const apply = () => { R.aud.location = $("#r-loc").value.trim(); loadView(); };
  $("#r-apply").onclick = apply;
  $("#r-loc").onkeydown = (e) => { if (e.key === "Enter") apply(); };
}

async function loadView() {
  const id = R.report.id;
  const q = new URLSearchParams({ age: R.aud.age });
  if (R.aud.gender) q.set("gender", R.aud.gender);
  if (R.aud.location) q.set("loc", R.aud.location);
  history.replaceState({}, "", `/r/${id}?${q}`);
  if (R.view) provisional();
  $("#r-busy").classList.remove("hidden");
  try {
    const p = new URLSearchParams({ age: R.aud.age, gender: R.aud.gender, location: R.aud.location });
    R.view = await api(`/api/reports/${id}/view?${p}`);
    renderView();
  } catch (err) {
    $("#r-headline").textContent = err.message;
  } finally {
    for (const el of document.querySelectorAll(".pending")) el.classList.remove("pending", "loading-view");
    $("#r-busy").classList.add("hidden");
  }
}

/* A cue's fit for an audience, from its Qloo profile: culturecheck/fit.py's
   `score`, so a new audience shows its numbers before the server answers. */
const GENDER_SHARE = 0.35;
function score(profile, aud) {
  if (!profile) return null;
  let f = profile.age[aud.age] ?? 0;
  if (aud.gender) f = (1 - GENDER_SHARE) * f + GENDER_SHARE * ((profile.gender || {})[aud.gender] ?? 0);
  return Math.round(f * 1000) / 1000;
}

function label(aud) {
  const age = AGES[aud.age].replace("Under 25", "under 25");
  const who = aud.gender ? `${aud.gender === "female" ? "women" : "men"} ${age}` : age;
  return aud.location ? `${who} in ${aud.location}` : who;
}

function provisional() {
  const cues = R.view.cues.map((c) => {
    const fit = score(c.profile, R.aud);
    return { ...c, fit, verdict: verdictOf(fit), local: null };
  });
  let total = 0, weights = 0;
  const counts = { fits: 0, neutral: 0, off: 0, unknown: 0 };
  for (const c of cues) {
    counts[c.verdict]++;
    if (c.fit !== null) { total += c.fit * (c.weight || 1); weights += c.weight || 1; }
  }
  const overall = weights ? Math.round(1000 * total / weights) / 1000 : null;
  const judged = R.report.appeal?.by_age?.[R.aud.age];
  R.view = { ...R.view, cues, label: label(R.aud), audience: { ...R.aud },
    appeal: judged ? { ...judged, verdict: verdictOf(judged.appeal) } : null,
    overall: { fit: overall, verdict: verdictOf(overall), counts }, swaps: {}, qloo_calls: 0,
    brief: { headline: `Re-scored for ${label(R.aud)} from Qloo's audience profiles.`,
             summary: "Replacements and the brief for this audience are on their way.",
             findings: [], changes: [], keep: [] } };
  renderView();
  for (const id of ["#r-brief", "#r-headline", "#r-summary"]) $(id).classList.add("pending", "loading-view");
}

function gauge(fit, caption) {
  const v = fit ?? 0, ang = Math.PI * (1 - (v + 1) / 2);
  const cx = 110, cy = 112, r = 90;
  const pt = (a, rr = r) => [cx + rr * Math.cos(a), cy - rr * Math.sin(a)];
  const arc = (a0, a1, cls) => {
    const [x0, y0] = pt(a0), [x1, y1] = pt(a1);
    return `<path d="M${x0} ${y0} A${r} ${r} 0 0 1 ${x1} ${y1}" stroke="var(--${cls})" stroke-width="14" fill="none" opacity=".9"/>`;
  };
  const a = (x) => Math.PI * (1 - (x + 1) / 2);
  const [nx, ny] = pt(ang, r - 22);
  const word = VERDICT_WORD[verdictOf(fit)];
  return `<svg viewBox="0 0 220 128" aria-hidden="true">
      ${arc(a(-1), a(-0.2), "off")}${arc(a(-0.2) - 0.02, a(0.2), "neutral")}${arc(a(0.2) - 0.02, a(1), "fits")}
      <line x1="${cx}" y1="${cy}" x2="${nx}" y2="${ny}" stroke="var(--ink)" stroke-width="3" stroke-linecap="round"/>
      <circle cx="${cx}" cy="${cy}" r="6" fill="var(--ink)"/>
    </svg>
    <div class="num">${fmtFit(fit)}</div>
    <div class="word" style="color:var(--${verdictOf(fit)})">${word} · ${esc(caption)}</div>`;
}

const cueById = (id) => R.view.cues.find((c) => c.id === id);

function renderView() {
  const { view } = R, rep = R.report, b = view.brief;
  const judged = view.appeal && view.appeal.appeal !== null && view.appeal.appeal !== undefined;
  $("#r-gauge").innerHTML = judged
    ? gauge(view.appeal.appeal, `appeal to ${AGES[R.aud.age].toLowerCase()}`)
    : gauge(view.overall.fit, `cue average · ${view.label}`);
  $("#r-headline").textContent = b.headline;
  $("#r-summary").textContent = b.summary;
  const c = view.overall.counts;
  $("#r-counts").innerHTML = ["fits", "neutral", "off", "unknown"].filter((k) => c[k])
    .map((k) => `<span class="badge ${k}">${c[k]} ${VERDICT_WORD[k].toLowerCase()}</span>`).join("")
    + (judged ? `<span class="badge unknown">cue average ${fmtFit(view.overall.fit)} · ${esc(view.label)}</span>` : "")
    + `<span class="badge unknown">${view.qloo_calls ?? 0} new Qloo calls</span>`;
  renderAppeal();
  renderAgeMap();
  renderTimeline();
  renderBrief();
  renderCues();
  renderChat();
}

/* The video's judged appeal to every age group (the same for every audience). */
function renderAppeal() {
  const ap = R.report.appeal, el = $("#r-appeal");
  if (!ap) {
    el.innerHTML = `<h2>Who it appeals to</h2><p class="muted">Not judged for this video yet.</p>`;
    return;
  }
  const me = ap.by_age[R.aud.age] || {};
  const chip = (id) => { const c = cueById(id); return c ? `<button class="ref" data-cue="${id}">${esc(c.label)}</button>` : ""; };
  el.innerHTML = `<h2>Who it appeals to</h2>
    <div class="muted" style="font-size:13px">The whole video, by age: judged from Qloo's evidence for every cue, plus what cues can't carry.</div>
    <div class="abars">${Object.entries(AGES).map(([k, lbl]) => {
      const v = ap.by_age[k]?.appeal, h = Math.min(50, Math.abs(v ?? 0) * 50);
      const style = (v ?? 0) >= 0 ? `bottom:50%;height:${h}%` : `top:50%;height:${h}%`;
      return `<div class="col ${k === R.aud.age ? "me" : ""}" data-age="${k}" title="${esc(ap.by_age[k]?.reason || "")}">
        <b style="color:var(--${verdictOf(v)})">${fmtFit(v)}</b>
        <div class="bar"><i class="fill-${verdictOf(v)}" style="${style}"></i></div><span>${lbl}</span></div>`;
    }).join("")}</div>
    <p style="margin:10px 0 4px"><b>${esc(AGES[R.aud.age])}:</b> ${esc(me.reason || "")}</p>
    ${me.toward?.length ? `<div class="kind" style="margin-top:8px">Pulls them in</div><div class="refs">${me.toward.map(chip).join("")}</div>` : ""}
    ${me.away?.length ? `<div class="kind" style="margin-top:8px">Pushes them away</div><div class="refs">${me.away.map(chip).join("")}</div>` : ""}
    ${ap.factors?.length ? `<div class="kind" style="margin-top:10px">Beyond the cues</div><div class="factors">${ap.factors.map((f) =>
      `<span class="factor" title="${esc(f.note)}">${esc(f.factor)} <em>→ ${f.toward === "none" ? "everyone" : esc(AGES[f.toward])}</em></span>`).join("")}</div>` : ""}
    <p class="muted" style="font-size:13px;margin-top:12px">${esc(ap.summary || "")}</p>`;
  wireRefs(el);
  for (const col of el.querySelectorAll(".abars .col")) col.onclick = () => {
    R.aud.age = col.dataset.age;
    for (const b of $("#r-age").children) b.setAttribute("aria-pressed", String(b.dataset.v === R.aud.age));
    loadView();
  };
}

/* Which cues reach which age group: Qloo's profiles alone. */
function renderAgeMap() {
  const map = R.report.age_map || {};
  const el = $("#r-agemap");
  el.innerHTML = `<h2>Which cues reach which age group</h2>
    <div class="muted" style="font-size:13px">Each cue under the age groups Qloo says over-index on it (affinity ≥ 0.2), strongest first.</div>
    <div class="agemap">${Object.entries(AGES).map(([k, lbl]) => `
      <div class="colm ${k === R.aud.age ? "me" : ""}"><h4>${lbl}</h4>
        ${(map[k] || []).length ? map[k].map((c) => `<button class="chip" data-cue="${c.id}"><b>${fmtFit(c.value)}</b>${esc(c.label)}</button>`).join("")
          : `<span class="none">nothing in this video</span>`}
      </div>`).join("")}</div>`;
  for (const b of el.querySelectorAll(".chip")) b.onclick = () => focusCue(b.dataset.cue);
}

/* Which moments reach which age group: a row per age, a cell per shot. */
function renderShotAges() {
  const rep = R.report, rows = rep.shot_ages || [];
  if (!rows.length) { $("#r-shotages").innerHTML = ""; return; }
  const colour = (v) => {
    if (v === null || v === undefined) return "var(--soft)";
    const a = Math.min(1, Math.abs(v) / 0.6);
    return `color-mix(in srgb, var(--${v >= 0 ? "fits" : "off"}) ${Math.round(15 + 85 * a)}%, var(--soft))`;
  };
  $("#r-shotages").innerHTML = Object.entries(AGES).map(([k, lbl]) => `
    <div class="row ${k === R.aud.age ? "me" : ""}"><span>${lbl}</span><div class="cells">${rows.map((r) => {
      const s = rep.shots.find((x) => x.shot === r.shot);
      return `<i style="flex:${(s.end - s.start).toFixed(2)};background:${colour(r.ages[k])}" title="Shot ${r.shot} · ${lbl}: ${fmtFit(r.ages[k])} (${r.cues} cues)"></i>`;
    }).join("")}</div></div>`).join("");
}

function renderTimeline() {
  renderShotAges();
  const rep = R.report, dur = rep.duration || 1;
  $("#r-shots").innerHTML = rep.shots.map((s) => {
    const f = s.frames[Math.floor(s.frames.length / 2)];
    return `<div class="shot" data-shot="${s.shot}" title="Shot ${s.shot} · ${fmtT(s.start)}–${fmtT(s.end)}"
      style="flex:${(s.end - s.start).toFixed(2)};${f !== undefined ? `background-image:url('/api/reports/${rep.id}/frames/${f}.jpg')` : ""}"><span>${s.shot}</span></div>`;
  }).join("");
  for (const el of $("#r-shots").children) el.onclick = () => seekShot(+el.dataset.shot);
  const cues = [...R.view.cues].sort((a, b) => (b.weight - a.weight) || ((a.fit ?? 9) - (b.fit ?? 9)));
  const shotOf = Object.fromEntries(rep.shots.map((s) => [s.shot, s]));
  $("#r-tracks").innerHTML = cues.map((cue) => `
    <div class="track" data-cue="${cue.id}" title="${esc(cue.label)} · fit ${fmtFit(cue.fit)}">
      <div class="name">${esc(cue.label)}</div>
      <div class="lane">${cue.shots.map((sid) => {
        const s = shotOf[sid]; if (!s) return "";
        return `<span class="seg-bar fill-${cue.verdict}" style="left:${(100 * s.start / dur).toFixed(2)}%;width:${(100 * (s.end - s.start) / dur).toFixed(2)}%"></span>`;
      }).join("")}<span class="playhead"></span></div>
    </div>`).join("");
  for (const el of $("#r-tracks").children) el.onclick = () => focusCue(el.dataset.cue);
  tick();
}

function tick() {
  const v = $("#r-video"), dur = R.report?.duration || 1;
  const t = v.currentTime || 0;
  for (const p of document.querySelectorAll(".playhead")) p.style.left = `${Math.min(100, 100 * t / dur)}%`;
  const cur = R.report?.shots.find((s) => t >= s.start && t < s.end);
  for (const el of $("#r-shots").children) el.classList.toggle("on", cur && +el.dataset.shot === cur.shot);
}

function seekShot(id) {
  const s = R.report.shots.find((x) => x.shot === id);
  if (!s) return;
  const v = $("#r-video");
  v.currentTime = s.start + 0.05;
  v.scrollIntoView({ behavior: "smooth", block: "center" });
}

function focusCue(id) {
  R.cue = id;
  for (const el of document.querySelectorAll(".track")) el.classList.toggle("on", el.dataset.cue === id);
  for (const el of document.querySelectorAll(".cue")) el.classList.toggle("on", el.dataset.cue === id);
  const card = document.querySelector(`.cue[data-cue="${id}"]`);
  if (card) card.scrollIntoView({ behavior: "smooth", block: "center" });
  const cue = cueById(id);
  if (cue && cue.shots.length) {
    const s = R.report.shots.find((x) => x.shot === cue.shots[0]);
    if (s) $("#r-video").currentTime = s.start + 0.05;
  }
}

function refs(cues, shots) {
  return `<div class="refs">${(cues || []).map((id) => {
    const c = cueById(id); return c ? `<button class="ref" data-cue="${id}">${esc(c.label)}</button>` : "";
  }).join("")}${(shots || []).map((s) => `<button class="ref" data-shot="${s}">shot ${s}</button>`).join("")}</div>`;
}

function wireRefs(root) {
  for (const b of root.querySelectorAll(".ref")) {
    b.onclick = () => (b.dataset.cue ? focusCue(b.dataset.cue) : seekShot(+b.dataset.shot));
  }
}

function renderBrief() {
  const b = R.view.brief;
  const el = $("#r-brief");
  el.innerHTML = `<h2>The brief</h2>
    <h3>What we found</h3>
    ${b.findings.map((f) => `<div class="finding"><b>${esc(f.title)}</b><span class="muted">${esc(f.detail)}</span>${refs(f.cues, f.shots)}</div>`).join("")}
    ${b.changes.length ? `<h3>What to change</h3>${b.changes.map((ch) => {
      const c = cueById(ch.cue);
      return `<div class="change"><span class="arrow">${esc(c ? c.label : ch.cue)} → ${esc(ch.to)}</span><span></span><span class="muted" style="grid-column:1/-1">${esc(ch.why)}</span></div>`;
    }).join("")}` : ""}
    ${b.keep.length ? `<h3>What's working</h3>${refs(b.keep, [])}` : ""}`;
  wireRefs(el);
}

function ageBars(cue) {
  if (!cue.profile) return "";
  return `<div class="ages">${Object.entries(AGES).map(([k, lbl]) => {
    const v = cue.profile.age[k] ?? 0, h = Math.min(50, Math.abs(v) * 50);
    const style = v >= 0 ? `bottom:50%;height:${h}%` : `top:50%;height:${h}%`;
    return `<div class="col ${k === R.aud.age ? "me" : ""}"><div class="bar"><i class="fill-${verdictOf(v)}" style="${style}"></i></div><span>${lbl}</span></div>`;
  }).join("")}</div>`;
}

function fitBar(fit) {
  const pos = (x) => 50 + 50 * Math.max(-1, Math.min(1, x));
  const val = fit === null || fit === undefined ? "" :
    `<span class="val fill-${verdictOf(fit)}" style="left:${Math.min(50, pos(fit))}%;width:${Math.abs(pos(fit) - 50)}%"></span>`;
  return `<div class="fitbar"><span class="zero"></span>${val}</div>`;
}

function renderCues() {
  const view = R.view;
  const order = { off: 0, neutral: 1, fits: 2, unknown: 3 };
  const cues = [...view.cues].sort((a, b) => (order[a.verdict] - order[b.verdict]) || (b.weight - a.weight) || ((a.fit ?? 0) - (b.fit ?? 0)));
  $("#r-cues").innerHTML = cues.map((c) => {
    const img = c.info?.image;
    const swaps = view.swaps[c.id] || [];
    const gender = c.profile?.gender;
    const lean = gender && Math.abs((gender.female ?? 0)) >= 0.1
      ? `leans ${gender.female > 0 ? "female" : "male"} (${Math.abs(gender.female).toFixed(2)})` : gender ? "no gender lean" : "";
    const peak = c.profile ? Object.entries(c.profile.age).sort((a, b) => b[1] - a[1])[0][0] : null;
    return `<article class="card cue" data-cue="${c.id}">
      <div class="top">
        <div class="img" style="${img ? `background-image:url('${esc(img)}')` : ""}">${img ? "" : esc((KIND_LABEL[c.kind] || c.kind).slice(0, 3))}</div>
        <div style="flex:1;min-width:0">
          <div class="kind">${esc(KIND_LABEL[c.kind] || c.kind)} · ${c.source} · shots ${c.shots.join(", ")}</div>
          <div class="label">${esc(c.label)}</div>
          <div class="sub">${c.qloo ? `Qloo: ${esc(c.qloo.name)}${c.qloo.kind === "tag" ? " (tag)" : ""}` : "Not in Qloo with audience data"}</div>
        </div>
        <span class="badge ${c.verdict}">${VERDICT_WORD[c.verdict]}</span>
      </div>
      <div class="fitrow">${fitBar(c.fit)}<span class="n">${fmtFit(c.fit)}</span></div>
      ${ageBars(c)}
      ${c.profile ? `<div class="lean">Peaks with ${esc(AGES[peak])}${lean ? " · " + lean : ""}${c.local !== null && c.local !== undefined ? ` · ${c.local > 0 ? `local following ${c.local.toFixed(2)}` : "no following"} in ${esc(R.aud.location)}` : ""}</div>` : ""}
      <div class="why">${esc(c.why)}</div>
      ${swaps.length ? `<div class="kind">Swap for</div><div class="swaps">${swaps.map((s) => `
        <div class="swap"><b>${esc(s.name)}</b><span class="n">${fmtFit(s.fit)}</span><span class="how">${esc(s.how || "")}</span></div>`).join("")}</div>` : ""}
    </article>`;
  }).join("");
  for (const el of document.querySelectorAll(".cue")) el.onclick = () => {
    R.cue = el.dataset.cue;
    for (const t of document.querySelectorAll(".track")) t.classList.toggle("on", t.dataset.cue === R.cue);
  };
}

/* ------------------------------------------------------------ chat */

function md(text) {
  const lines = esc(text).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").split(/\n/);
  let out = "", list = false;
  for (const l of lines) {
    const m = l.match(/^\s*[-*•]\s+(.*)/);
    if (m) { if (!list) { out += "<ul>"; list = true; } out += `<li>${m[1]}</li>`; continue; }
    if (list) { out += "</ul>"; list = false; }
    if (l.trim()) out += `<p>${l}</p>`;
  }
  return out + (list ? "</ul>" : "");
}

function chatLog() {
  const k = R.report.id + "|" + audKey(R.aud);
  return (R.chats[k] ||= []);
}

function renderChat() {
  const log = chatLog();
  $("#c-log").innerHTML = log.length ? log.map((m) => m.role === "user"
    ? `<div class="msg user">${esc(m.content)}</div>`
    : `<div>${(m.steps || []).map((s) => `<div class="tool">${esc(s.summary)}</div>`).join("")}<div class="msg assistant">${md(m.content)}</div></div>`).join("")
    : `<div class="muted" style="font-size:14px">Ask about any cue, a different song or brand, another audience, or where something happens in the video.</div>`;
  $("#c-log").scrollTop = 1e6;
  const worst = R.view.cues.filter((c) => c.fit !== null).sort((a, b) => a.fit - b.fit)[0];
  const music = R.view.cues.find((c) => c.kind === "music");
  const other = R.aud.age === "55_and_older" ? "24_and_younger" : "55_and_older";
  const ideas = [
    worst && `Why does "${worst.label}" miss, and what should replace it?`,
    music ? `What music would this audience rather hear than ${music.qloo?.name || music.label}?` : "What music would this audience want over this video?",
    `What if it were for ${AGES[other].toLowerCase()} instead?`,
    "Which brands does this audience love that would suit this video?",
  ].filter(Boolean);
  $("#c-suggest").innerHTML = log.length ? "" : ideas.map((q) => `<button type="button">${esc(q)}</button>`).join("");
  for (const b of $("#c-suggest").children) b.onclick = () => ask(b.textContent);
}

async function ask(text) {
  text = text.trim();
  if (!text) return;
  const log = chatLog();
  log.push({ role: "user", content: text });
  renderChat();
  $("#c-log").insertAdjacentHTML("beforeend", `<div class="typing" id="c-typing">Thinking, and asking Qloo…</div>`);
  $("#c-log").scrollTop = 1e6;
  try {
    const res = await api(`/api/reports/${R.report.id}/chat`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ age: R.aud.age, gender: R.aud.gender, location: R.aud.location,
                             messages: log.map(({ role, content }) => ({ role, content })) }),
    });
    log.push({ role: "assistant", content: res.text, steps: res.steps });
  } catch (err) {
    log.push({ role: "assistant", content: "Sorry: " + err.message, steps: [] });
  }
  renderChat();
}

$("#c-form").onsubmit = (e) => { e.preventDefault(); const t = $("#c-in").value; $("#c-in").value = ""; ask(t); };

/* ------------------------------------------------------------ real-world results */

const REACH_AGES = ["18-24", "25-34", "35-44", "45-54", "55-64", "65+"];
const YOUNG = "24_and_younger", OLD = "55_and_older";
const millions = (n) => n >= 1e6 ? `${(n / 1e6).toFixed(1)}M` : `${Math.round(n / 1e3)}K`;
const youngLean = (ad) => (ad.appeal[YOUNG]?.appeal ?? 0) - (ad.appeal[OLD]?.appeal ?? 0);

function appealChart(ad) {
  return `<div class="abars mini">${Object.entries(AGES).map(([k, lbl]) => {
    const v = ad.appeal[k]?.appeal, h = Math.min(50, Math.abs(v ?? 0) * 50);
    const style = (v ?? 0) >= 0 ? `bottom:50%;height:${h}%` : `top:50%;height:${h}%`;
    return `<div class="col"><b style="color:var(--${verdictOf(v)})">${fmtFit(v)}</b>
      <div class="bar"><i class="fill-${verdictOf(v)}" style="${style}"></i></div><span>${lbl}</span></div>`;
  }).join("")}</div>`;
}

function reachChart(ad) {
  const top = Math.max(...Object.values(ad.ages));
  return `<div class="abars mini reach">${REACH_AGES.map((a) => {
    const v = ad.ages[a];
    if (v === undefined) return `<div class="col off"><b>–</b><div class="bar"></div><span>${a}</span></div>`;
    return `<div class="col"><b>${v.toFixed(0)}%</b><div class="bar"><i style="bottom:0;height:${(100 * v / top).toFixed(0)}%"></i></div><span>${a}</span></div>`;
  }).join("")}</div>`;
}

function pairLine(ads) {
  if (ads.length !== 2) return "";
  const [a, b] = [...ads].sort((x, y) => x.mean_age - y.mean_age);
  const gap = b.mean_age - a.mean_age;
  if (gap < 0.5) return `<p class="pair">These two reached almost the same ages (${a.mean_age.toFixed(1)} and ${b.mean_age.toFixed(1)} on average), so this pair can't show whether the app ranked them correctly.</p>`;
  const right = youngLean(a) > youngLean(b);
  return `<p class="pair"><span class="badge ${right ? "fits" : "off"}">${right ? "App picked the younger-reaching ad" : "App picked the wrong ad"}</span>
    Same targeting, and <b>${esc(a.title)}</b> reached a younger audience: ${a.mean_age.toFixed(1)} against ${b.mean_age.toFixed(1)} on average.</p>`;
}

function testedAd(ad) {
  return `<article class="card tested-ad">
    <div class="thumbs">
      <video controls preload="none" playsinline src="/api/reports/${ad.report}/video"
        ${ad.frame !== null ? `poster="/api/reports/${ad.report}/frames/${ad.frame}.jpg"` : ""}></video>
      <div>
        <h3>${esc(ad.title)}</h3>
        <div class="meta">${millions(ad.reach)} reached · ${esc(ad.ran)} · ${esc(ad.where)}<br>
          Targeted ${esc(ad.target)}, ${esc(ad.gender)} · ${Math.round(ad.seconds || 0)}s${ad.versions ? " · several versions" : ""}</div>
        <div class="links"><a href="/r/${ad.report}">Full report</a><a href="https://www.facebook.com/ads/library/?id=${ad.library_id}" target="_blank" rel="noopener">Meta Ad Library</a></div>
      </div>
    </div>
    <div class="charts">
      <div><div class="kind">What the app judged</div>${appealChart(ad)}</div>
      <div><div class="kind">Who Meta reports it reached · average age ${ad.mean_age.toFixed(1)}</div>${reachChart(ad)}</div>
    </div>
    <p class="muted summary-line">${esc(ad.summary)}</p>
  </article>`;
}

async function tested() {
  show("tested");
  document.title = "Real-world results · Culture Check";
  const groups = await api("/api/tested").catch(() => []);
  $("#t-caveat").textContent = groups.length ? "A handful of ads shows the method, not its accuracy. Judged appeal and share of reach are different scales: compare the shapes. Meta's reach also depends on the advertiser's targeting, its delivery system and who uses Meta, and these ads reach a similar age mix when targeting is the same. Reach is Meta's own estimate." : "";
  $("#t-body").innerHTML = groups.length ? groups.map((g) => `
    <section class="tested-group">
      <h2>${esc(g.brand)}</h2>
      ${pairLine(g.ads)}
      <div class="tested-ads">${g.ads.map(testedAd).join("")}</div>
    </section>`).join("") : `<p class="muted">No results yet.</p>`;
}

/* ------------------------------------------------------------ routing */

function route() {
  const m = location.pathname.match(/^\/r\/([a-z0-9_-]+)/);
  if (m) openReport(m[1]);
  else if (location.pathname === "/tested") tested();
  else home();
}

window.onpopstate = route;
wireUpload();
route();

