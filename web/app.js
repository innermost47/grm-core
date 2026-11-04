// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Anthony Charretier
//
// The page: the introduction, the journey through time, the constants, the elastics.

import { solveUniverse, expansion, DEFAULTS, PARAMS, UNITS } from "./universe.js";
import { Universe3D } from "./scene.js";
import { Music } from "./music.js";
import { TEXTS, RELATIONS_FR, pickLanguage, formatTime, formatTemperature, formatLength, formatLogLength } from "./i18n.js";

const PRESETS = {
  ours: { ...DEFAULTS },
  gravity: { ...DEFAULTS, G: 10 },
  alpha: { ...DEFAULTS, alpha: 1.1 },
  electron: { ...DEFAULTS, me: 2 },
  baryons: { ...DEFAULTS, ombh2: DEFAULTS.ombh2 * 2 },
  fast: { ...DEFAULTS, H0: 80 },
  crunch: { ...DEFAULTS, omch2: 5, ombh2: 2 },
  hot: { ...DEFAULTS, Tcmb: 100 },
  broken: { ...DEFAULTS, alpha: 1.8, G: 30, me: 3, mp: 0.5, H0: 40, omch2: 1.5 },
};
const LT_START = -2;                       // log10 of the first moment shown (0.01 s)
const $ = (id) => document.getElementById(id);

let lang = pickLanguage();
let T = TEXTS[lang];
let params = { ...DEFAULTS };
let state = null;                          // the solved universe
let uOf = null;                            // ln a at time t
const OURS_VALUES = solveUniverse(DEFAULTS).values;
let lt = LT_START, playing = false, stopAtToday = true, started = false, muted = false;
const music = new Music();
const view = new Universe3D($("scene"));

// ------------------------------------------------------------------ storage (only conveniences of this browser)
const store = {
  get(key, fallback) {
    try { const v = localStorage.getItem(key); return v ? JSON.parse(v) : fallback; } catch { return fallback; }
  },
  set(key, value) {
    try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* private mode: not kept */ }
  },
};
params = { ...DEFAULTS, ...store.get("grm-universe-params", {}) };

// ------------------------------------------------------------------ the network
function solve(fromSlider = false) {
  try {
    const before = state?.values;
    const s = solveUniverse(params);
    state = s;
    if (before) {
      // how far the universe moved (in dex, over a few of its nodes): the elastics shake that much
      const keys = ["t0", "tstar", "Tsun", "cair", "zrec", "l1", "Mstar", "trec"];
      const moved = keys.reduce((a, k) => a + Math.abs(Math.log10(s.values[k] / before[k])), 0);
      view.kick(Math.min(1.2, moved * 6));
    }
    if (fromSlider && started) consequences(s.values);
    uOf = expansion(s.values);
    music.setUniverse(s.values);
    $("invalid").hidden = true;
    store.set("grm-universe-params", params);
    renderElastics();
    buildChapters();
    return true;
  } catch (e) {
    $("invalid").hidden = false;
    $("invalid").textContent = `${T.invalid} ${e.message}`;
    return false;
  }
}

// The film runs on one coordinate, lt. In an open universe lt = log10 t: every decade of time gets its share.
// In a closed one, after the turnaround, lt mirrors the expansion: lt = 2 log10 t_max - log10 (time left), so the
// fall lasts on screen as long as the rise, down to the same last hundredth of a second before the Crunch.
const closed = () => "tcrunch" in state.values;
const ltTop = () => Math.log10(state.values.tmax);
const ltEnd = () => (closed() ? 2 * ltTop() - LT_START : Math.log10(state.values.tsmbh) + 2.5);
const ltToday = () => Math.log10(state.values.t0);
// the moment at lt: its time, the time left before the Crunch, falling or not, the Crunch's last flash
function moment(x) {
  const v = state.values;
  if (!closed() || x <= ltTop()) return { t: 10 ** x, left: closed() ? v.tcrunch - 10 ** x : Infinity, falling: false, final: 0 };
  const left = 10 ** (2 * ltTop() - x);
  return { t: v.tcrunch - left, left, falling: true, final: Math.min(1, Math.max(0, (x - (ltEnd() - 1.6)) / 1.6)) };
}
// where a threshold of the fall sits on the film (time left d before the Crunch)
const ltLeft = (d) => 2 * ltTop() - Math.log10(d);

// decades of time per second of playback: slow where much happens
function speed(x) {
  const v = state.values, l = Math.log10;
  const near = (y, w = 0.6) => Math.abs(x - y) < w;
  if (closed() && x > ltTop() - 0.3) {
    // the fall: slow at the turnaround, at each threshold, and in the last moments
    if (x > ltEnd() - 2) return 0.3;
    if ([ltTop(), ltLeft(v.dmerge), ltLeft(v.dcook), ltLeft(v.trec), ltLeft(v.tnuc)].some((y) => near(y, 0.5))) return 0.35;
    return 1.2;
  }
  if (x > l(v.tstarsend) + 0.5) {
    // the long night: fast between its events, slow on each of them, then the dark
    if (x > l(v.tevap) - 1.2 && x < l(v.tevap) + 0.8) return 0.35;         // the stars flung away: give it time
    if ([l(v.tblack), l(v.tproton), l(v.tbh), l(v.tsmbh)].some((y) => near(y))) return 0.5;
    if (x > l(v.tsmbh) + 0.6) return 0.5;
    return 3;
  }
  if (x < l(v.tnuc) - 0.5) return 1.1;
  if (x < l(v.tnuc) + 0.5) return 0.35;
  if (x < l(v.trec) - 0.6) return 0.9;
  if (x < l(v.trec) + 0.3) return 0.28;
  if (x < l(v.tfirst) - 0.4) return 0.8;
  if (x < l(v.t0) + 0.02) return 0.22;
  if (x < l(v.tredgiant) + 0.3) return 0.25;
  return 0.9;
}

function epochAt(m, Tlight) {
  const v = state.values, t = m.t;
  if (m.falling) {
    // the highest threshold the light has passed on the way back
    if (m.final > 0.4) return "crunch";
    const passed = [["merge", v.Tmerge], ["cook", v.Tcook], ["plasmaAgain", v.Trec], ["nucleiBroken", v.Tnuc]]
      .filter(([, T]) => Tlight >= T).sort((a, b) => b[1] - a[1]);
    return passed.length ? passed[0][0] : "recollapse";
  }
  if (t < v.tnuc * 0.5) return "plasma";
  if (t < v.tnuc * 20) return "nuclei";
  if (t < v.trec * 0.9) return "sound";
  if (t < v.trec * 3) return "light";
  if (t < v.tfirst) return "dark";
  if (t < v.tfirst * 6) return "stars";
  if (t < v.tsunborn) return "galaxies";
  if (t < v.t0 * 0.995) return "sun";
  if (t < v.t0 * 1.02) return "today";
  if (t < v.tredgiant * 1.1) return "giant";
  if (t < v.tstarsend * 3) return "starsEnd";
  if (t < v.tevap * 0.1) return "blackDwarfs";
  if (t < v.tevap * 30) return "evaporate";
  if (v.tproton < v.tbh && t <= v.tproton * 0.03) return "longNight";
  if (v.tproton < v.tbh && t < v.tproton * 30) return "protons";
  if (t < v.tbh * 0.05) return "holes";
  if (t < v.tsmbh * 3) return "hawking";
  return "end";
}

// ------------------------------------------------------------------ chapters
// The film stops at the start of each epoch (unless the spectator turns the pauses off or asks "to the end"), so that
// there is time to read; each start is marked on the timeline, and a click on a mark goes there.
let chapters = [];                         // [{ lt, ep }]
let autoPause = true, nonstop = false, atChapter = false;
let pendingPause = null;                   // "chapter", "today" or "end": the card is shown once the frame is drawn
try { autoPause = localStorage.getItem("grm-universe-pauses") !== "off"; } catch { /* default: on */ }
function epochOfLt(x) {
  const m = moment(x);
  const u = m.falling ? uOf.left(m.left) : uOf(m.t);
  return epochAt(m, state.values.T0 * Math.exp(-u));
}
function buildChapters() {
  chapters = [];
  let prev = epochOfLt(LT_START);
  const end = ltEnd();
  for (let x = LT_START + 0.01; x <= end; x += 0.01) {
    const ep = epochOfLt(x);
    if (ep !== prev) {
      // the exact start, by bisection (the grid only finds the hundredth of a decade)
      let lo = x - 0.01, hi = x;
      for (let k = 0; k < 20; k++) {
        const mid = 0.5 * (lo + hi);
        if (epochOfLt(mid) === ep) hi = mid;
        else lo = mid;
      }
      chapters.push({ lt: hi, ep });
    }
    prev = ep;
  }
  renderChapters();
}
function renderChapters() {
  const box = $("chapters-marks");
  if (!box || !state) return;
  const span = ltEnd() - LT_START;
  box.innerHTML = "";
  for (const c of chapters) {
    const b = document.createElement("button");
    b.className = "mark";
    b.style.left = `${(100 * (c.lt - LT_START)) / span}%`;
    b.title = T.epochs[c.ep][0];
    b.setAttribute("aria-label", T.epochs[c.ep][0]);
    b.addEventListener("click", () => {
      lt = c.lt + 0.005;
      stopAtToday = lt < ltToday();
      message("");
      atChapter = true;
      setPlaying(false);
      pendingPause = c.ep === "today" ? "today" : "chapter";
    });
    box.appendChild(b);
  }
}

// ------------------------------------------------------------------ texts
// a button: a Font Awesome icon and its words (on a phone the HUD shows the icons only; the words stay as a title)
function label(id, icon, text, small = "") {
  const el = $(id);
  const cls = icon.includes("fa-regular") ? icon : `fa-solid ${icon}`;
  el.innerHTML = `<i class="${cls}" aria-hidden="true"></i><span class="words">${text}</span>${small ? `<small>${small}</small>` : ""}`;
  el.title = text;
  el.setAttribute("aria-label", text);
}
const playIcon = () => (playing ? "fa-pause" : lt >= ltEndSafe() ? "fa-rotate-right" : "fa-play");
const ltEndSafe = () => (state ? ltEnd() : Infinity);
function labelPlay() { label("play", playIcon(), playing ? T.pause : atChapter ? T.resume : T.play); }
function labelChapters() { label("chapters", autoPause ? "fa-bookmark" : "fa-regular fa-bookmark", autoPause ? T.pausesOn : T.pausesOff); }
function labelMute() { label("mute", muted ? "fa-volume-xmark" : "fa-volume-high", muted ? T.muteOff : T.muteOn); }

function applyTexts() {
  document.documentElement.lang = lang;
  document.title = T.pageTitle;
  $("title").textContent = T.title;
  $("lead").textContent = T.lead;
  $("intro-text").innerHTML = T.intro.map((p) => `<p>${p}</p>`).join("");
  label("launch", "fa-rocket", T.launch, T.launchWith);
  label("open-settings", "fa-sliders", T.settings);
  $("sound-hint").textContent = T.sound;
  $("by").textContent = T.by;
  $("source").textContent = T.source;
  $("license").textContent = T.license;
  label("lang", "fa-language", lang === "fr" ? "English" : "Français");
  labelPlay();
  label("today", "fa-earth-europe", T.toToday);
  label("toend", "fa-forward-fast", T.toEnd);
  label("newbang", "fa-burst", T.newBang);
  label("btn-settings", "fa-sliders", T.settings);
  label("message-settings", "fa-sliders", T.settings);
  label("btn-elastics", "fa-diagram-project", T.elastics);
  labelMute();
  labelChapters();
  renderChapters();
  $("k-time").textContent = T.time;
  $("k-left").textContent = T.left;
  $("k-temp").textContent = T.temperature;
  $("k-size").textContent = T.size;
  label("settings-launch", "fa-burst", T.launchThis);
  document.querySelectorAll("[data-close]").forEach((b) => {
    b.innerHTML = `<i class="fa-solid fa-xmark" aria-hidden="true"></i>`;
    b.title = T.close;
    b.setAttribute("aria-label", T.close);
  });
  $("settings-title").textContent = T.settings;
  $("reset-hint").textContent = T.resetHint;
  $("elastics-title").textContent = T.elastics;
  $("presets-label").textContent = T.presets;
  label("save", "fa-floppy-disk", T.save);
  $("save-name").placeholder = T.saveName;
  label("reset", "fa-rotate-left", T.reset);
  buildSettings();
  if (state) renderElastics();
}

// ------------------------------------------------------------------ the constants
function sliderValue(p, x) {               // slider 0..1000 -> value
  const f = x / 1000;
  return p.log ? p.min * (p.max / p.min) ** f : p.min + f * (p.max - p.min);
}
function sliderPosition(p, v) {
  return Math.round(1000 * (p.log ? Math.log(v / p.min) / Math.log(p.max / p.min) : (v - p.min) / (p.max - p.min)));
}
const show = (p, v) => (p.kind === "times" ? `× ${v.toFixed(v < 1 ? 3 : 2)}` : v.toPrecision(p.id === "ombh2" ? 3 : 4));

let solveTimer = null;
function buildSettings() {
  const box = $("sliders");
  box.innerHTML = "";
  for (const p of PARAMS) {
    const [name, hint] = T.params[p.id];
    const row = document.createElement("label");
    row.className = "slider";
    row.innerHTML = `<span class="name">${name}</span><span class="value" id="v-${p.id}"></span>
      <input type="range" min="0" max="1000" step="1" id="s-${p.id}"><span class="hint">${hint}</span>`;
    box.appendChild(row);
    const input = row.querySelector("input");
    input.value = sliderPosition(p, params[p.id]);
    row.querySelector(".value").textContent = show(p, params[p.id]);
    const apply = () => {
      row.querySelector(".value").textContent = show(p, params[p.id]);
      clearTimeout(solveTimer);
      solveTimer = setTimeout(() => solve(true), 60);
    };
    input.addEventListener("input", () => {
      params[p.id] = sliderValue(p, +input.value);
      apply();
    });
    // double click (or double tap) on a slider: back to our universe's value, for this constant only
    input.title = T.resetHint;
    const reset = (e) => {
      e.preventDefault();
      params[p.id] = DEFAULTS[p.id];
      input.value = sliderPosition(p, params[p.id]);
      apply();
    };
    input.addEventListener("dblclick", reset);
    let lastTap = 0;
    input.addEventListener("pointerup", (e) => {
      if (e.pointerType !== "touch") return;
      const now = performance.now();
      if (now - lastTap < 320) reset(e);
      lastTap = now;
    });
  }
  const sel = $("presets");
  sel.innerHTML = "";
  const group = (label, entries) => {
    const g = document.createElement("optgroup");
    g.label = label;
    for (const [key, name] of entries) {
      const o = document.createElement("option");
      o.value = key;
      o.textContent = name;
      g.appendChild(o);
    }
    sel.appendChild(g);
  };
  const none = document.createElement("option");
  none.value = "";
  none.textContent = "…";
  sel.appendChild(none);
  group(T.presets, Object.keys(PRESETS).map((k) => [k, T.presetNames[k]]));
  const mine = store.get("grm-universe-mine", {});
  if (Object.keys(mine).length) group(T.yours, Object.keys(mine).map((k) => [`mine:${k}`, k]));
  sel.value = "";
}

function choosePreset(key) {
  const mine = store.get("grm-universe-mine", {});
  const p = key.startsWith("mine:") ? mine[key.slice(5)] : PRESETS[key];
  if (!p) return;
  params = { ...DEFAULTS, ...p };
  buildSettings();
  solve(true);
}

// what this universe changes, compared with ours (said in the message box for a few seconds)
let consequenceTimer = null;
function consequences(v) {
  const o = OURS_VALUES, C = T.consequences;
  const ratio = (a, b) => (a / b >= 1 ? `× ${(a / b).toPrecision(3)}` : `÷ ${(b / a).toPrecision(3)}`);
  const lines = [];
  lines.push(`${C.starLife} ${formatTime(v.tstar, lang)} (${ratio(v.tstar, o.tstar)})`);
  lines.push(`${C.starColour} ${v.Tsun.toFixed(0)} K (${ratio(v.Tsun, o.Tsun)})`);
  const cents = 1200 * Math.log2(v.flute0 / o.flute0);
  lines.push(`${C.flute} ${cents >= 0 ? "+" : ""}${cents.toFixed(0)} cents`);
  lines.push(`${C.light} z = ${v.zrec.toFixed(0)} (${C.ours} ${o.zrec.toFixed(0)})`);
  if (v.tcrunch) lines.push(`${C.crunch} ${formatTime(v.tcrunch, lang)}`);
  if (v.zrec < 200) lines.push(C.opaque);
  if (v.tredgiant < v.t0) lines.push(C.sunDead);
  else if (v.tstar < 4.5e9 * UNITS.YEAR) lines.push(C.noTime);
  message(lines.join("\n"));
  clearTimeout(consequenceTimer);
  consequenceTimer = setTimeout(() => message(""), 9000);
}

// ------------------------------------------------------------------ the elastics
function renderElastics() {
  const v = state.values;
  const rows = [
    ["t0", formatTime(v.t0, lang)], ["Rhor", formatLength(v.Rhor, lang)], ["tnuc", formatTime(v.tnuc, lang)], ["trec", formatTime(v.trec, lang)],
    ["zrec", v.zrec.toFixed(1)], ["l1", v.l1.toFixed(1)], ["tstar", formatTime(v.tstar, lang)],
    ["Tsun", `${v.Tsun.toFixed(0)} K`], ["cair", `${v.cair.toFixed(1)} m/s`], ["flute0", `${v.flute0.toFixed(2)} Hz`],
    ["pad1", `${v.pad1.toFixed(2)} Hz`], ["tblack", formatTime(v.tblack, lang)], ["tevap", formatTime(v.tevap, lang)],
    ["tproton", formatTime(v.tproton, lang)], ["tbh", formatTime(v.tbh, lang)], ["tsmbh", formatTime(v.tsmbh, lang)],
  ];
  if (v.tcrunch) rows.push(["tmax", formatTime(v.tmax, lang)], ["dmerge", formatTime(v.dmerge, lang)],
    ["dcook", formatTime(v.dcook, lang)], ["tcrunch", formatTime(v.tcrunch, lang)]);
  $("key-values").innerHTML = `<h3>${T.keyValues}</h3><dl>${rows.map(([k, s]) => `<dt>${T.values[k]}</dt><dd>${s}</dd>`).join("")}</dl>`;
  const kinds = ["law", "hypothesis", "music"];
  $("relations").innerHTML = `<p class="lead">${T.elasticsLead}</p>` + kinds.map((kind) =>
    `<h3 class="kind-${kind}">${T.kinds[kind]}</h3><ul>${state.relations.filter((r) => r.kind === kind)
      .map((r) => `<li class="kind-${kind}">${lang === "fr" ? (RELATIONS_FR[r.name] ?? r.about) : r.about}</li>`).join("")}</ul>`).join("");
}

// ------------------------------------------------------------------ the journey
function launch(fromStart = true) {
  if (!solve()) return;
  $("intro").hidden = true;
  $("hud").hidden = false;
  closePanels();
  if (!muted) music.start();
  started = true;
  if (fromStart) {
    lt = LT_START;
    view.reset();
    stopAtToday = true;
  }
  setPlaying(true);
}

function setPlaying(on) {
  playing = on;
  if (on) {
    atChapter = false;
    hidePause();
  }
  labelPlay();
}

// the message under the caption; withSettings: a button that opens the constants (for those who do not know where)
// at the end of the film, the same button starts another Big Bang
let messageAction = "settings";
function message(text, withSettings = false, action = "settings") {
  messageAction = action;
  $("message-text").textContent = text;
  if (action === "bang") label("message-settings", "fa-burst", T.newBang);
  else label("message-settings", "fa-sliders", T.settings);
  $("message-settings").hidden = !withSettings;
  $("message").hidden = !text;
}

let last = performance.now();
function frame(now) {
  const dt = Math.min(0.1, (now - last) / 1000);
  last = now;
  if (state && started) {
    if (playing) {
      const before = lt;
      lt += speed(lt) * dt;
      if (closed() && before < ltTop() && lt >= ltTop()) music.turn();
      // a new epoch: pause there (today has its own pause and message)
      const next = chapters.find((c) => before < c.lt && lt >= c.lt && c.ep !== "today");
      if (next && autoPause && !nonstop && !(stopAtToday && next.lt > ltToday())) {
        lt = next.lt + 0.005;
        atChapter = true;
        setPlaying(false);
        pendingPause = "chapter";
      }
      if (stopAtToday && before < ltToday() && lt >= ltToday()) {
        lt = ltToday();
        stopAtToday = false;
        setPlaying(false);
        pendingPause = "today";
      }
      if (lt >= ltEnd()) {
        lt = ltEnd();
        setPlaying(false);
        pendingPause = "end";
      }
    }
    const m = moment(lt);
    const t = m.t;
    const u = m.falling ? uOf.left(m.left) : uOf(t);
    const { logT, plasma, flashes } = view.update(m, state.values, u);
    for (const big of flashes) music.flash(big);
    const ep = epochAt(m, 10 ** logT);
    const [name, text] = T.epochs[ep];
    $("epoch").textContent = name;
    // the texts quote the network: {age}, {tevap}... are its values
    $("epoch-text").textContent = text.replace("{age}", formatTime(state.values.t0, lang))
      .replace(/\{(\w+)\}/g, (_, k) => formatTime(state.values[k], lang));
    $("clock").textContent = formatTime(t, lang);
    $("k-left").hidden = $("left").hidden = !closed();
    if (closed()) $("left").textContent = formatTime(m.left, lang);
    $("temp").textContent = formatTemperature(logT, lang);
    $("size").textContent = formatLogLength(m.falling ? uOf.logSizeLeft(m.left) : uOf.logSize(t), lang);
    if (pendingPause) {
      showPause(pendingPause, ep);
      pendingPause = null;
    }
    const span = ltEnd() - LT_START;
    if (!scrubbing) $("timeline").value = Math.round((1000 * (lt - LT_START)) / span);
    $("today-mark").style.left = `${(100 * (ltToday() - LT_START)) / span}%`;
    const v = state.values;
    // the fall: the chord is heard blueshifted, like the light (1/a, a quarter of it in octaves, at most 3)
    const rise = m.falling ? Math.min(3, Math.max(0, 0.25 * Math.log2(10 ** logT / (v.T0 / v.amax)))) : 0;
    music.setEra({ plasma, rise, final: m.final, memory: t < v.tstarsend ? 1 : Math.max(0, 1 - (lt - Math.log10(v.tstarsend)) / 60),
      // the flute is us: it plays while the Earth exists, if the Sun lives long enough for life (4.5 Gyr: our case)
      earth: v.tstar > 4.5e9 * UNITS.YEAR && t > v.tsunborn + 0.6e9 * UNITS.YEAR && t < v.tredgiant && !(m.falling && 10 ** logT > v.Tcook * 0.2),
      end: lt > ltEnd() - (closed() ? 0.02 : 1.2) });
    const sun = view.sunOnScreen();
    const label = $("sun-label");
    label.hidden = !(sun && ep !== "plasma" && t > v.tsunborn && t < v.tredgiant * 1.3);
    if (sun) label.style.transform = `translate(${sun.x + 10}px, ${sun.y - 10}px)`;
  }
  view.render();
  requestAnimationFrame(frame);
}

let scrubbing = false;
function closePanels() {
  $("settings").hidden = true;
  $("elastics").hidden = true;
}

// ------------------------------------------------------------------ the pause card
let pauseKind = null;
function showPause(kind, ep) {
  pauseKind = kind;
  const index = chapters.findIndex((c) => c.ep === ep && Math.abs(c.lt - lt) < 0.05);
  $("pause-kicker").textContent = kind === "end" ? T.theEnd
    : `${T.chapter} ${index >= 0 ? index + 2 : ""}${index >= 0 ? ` / ${chapters.length + 1}` : ""}`;
  $("pause-title").textContent = $("epoch").textContent;
  $("pause-text").textContent = $("epoch-text").textContent;
  const extra = kind === "today" ? T.today : kind === "end" ? (closed() ? T.endCrunch : T.end) : "";
  $("pause-extra").textContent = extra;
  $("pause-extra").hidden = !extra;
  // the same quantities as the caption, frozen at this moment
  const rows = [...document.querySelectorAll("#caption .readout dt")].filter((d) => !d.hidden)
    .map((d) => `<dt>${d.textContent}</dt><dd>${d.nextElementSibling.textContent}</dd>`);
  $("pause-values").innerHTML = rows.join("");
  if (kind === "end") {
    label("pause-main", "fa-burst", T.newBang);
    label("pause-second", "fa-rotate-right", T.again);
  } else {
    label("pause-main", "fa-play", T.resume);
    label("pause-second", "fa-sliders", T.settings);
  }
  $("pause-toggle").hidden = kind === "end";
  label("pause-toggle", autoPause ? "fa-bookmark" : "fa-regular fa-bookmark", autoPause ? T.pausesOn : T.pausesOff);
  $("pause").hidden = false;
  document.body.classList.add("paused");
  $("pause-main").focus({ preventScroll: true });
}
function hidePause() {
  $("pause").hidden = true;
  document.body.classList.remove("paused");
  pauseKind = null;
}
function resume() {
  nonstop = false;
  message("");
  setPlaying(true);
  if (!muted) music.start();
}
$("pause-main").addEventListener("click", () => (pauseKind === "end" ? offerNewBang() : resume()));
$("pause-second").addEventListener("click", () => {
  if (pauseKind === "end") { hidePause(); launch(true); return; }
  hidePause();
  $("elastics").hidden = true;
  $("settings").hidden = false;
});
$("pause-toggle").addEventListener("click", () => {
  $("chapters").click();
  label("pause-toggle", autoPause ? "fa-bookmark" : "fa-regular fa-bookmark", autoPause ? T.pausesOn : T.pausesOff);
});
document.addEventListener("keydown", (e) => {
  if ($("pause").hidden || e.target.tagName === "INPUT" || e.target.tagName === "SELECT") return;
  if (e.key === "Enter" || e.key === " ") {
    e.preventDefault();
    $("pause-main").click();
  }
});

// ------------------------------------------------------------------ wiring
$("launch").addEventListener("click", () => launch(true));
$("open-settings").addEventListener("click", () => { $("settings").hidden = false; });
$("btn-settings").addEventListener("click", () => { $("elastics").hidden = true; $("settings").hidden = !$("settings").hidden; });
$("message-settings").addEventListener("click", () => {
  if (messageAction === "bang") { offerNewBang(); return; }
  $("elastics").hidden = true;
  $("settings").hidden = false;
});
$("btn-elastics").addEventListener("click", () => { $("settings").hidden = true; $("elastics").hidden = !$("elastics").hidden; });
document.querySelectorAll("[data-close]").forEach((b) => b.addEventListener("click", closePanels));
$("play").addEventListener("click", () => {
  if (lt >= ltEnd()) { lt = LT_START; view.reset(); }
  nonstop = false;
  message("");
  setPlaying(!playing);
  if (!muted) music.start();
});
$("today").addEventListener("click", () => { lt = ltToday(); stopAtToday = false; setPlaying(false); message(""); pendingPause = "today"; });
$("toend").addEventListener("click", () => { stopAtToday = false; nonstop = true; message(""); setPlaying(true); if (!muted) music.start(); });
// a new Big Bang: the constants first (the panel's button launches it)
function offerNewBang() {
  message("");
  hidePause();
  setPlaying(false);
  $("elastics").hidden = true;
  $("settings").hidden = false;
}
$("newbang").addEventListener("click", offerNewBang);
$("settings-launch").addEventListener("click", () => { message(""); launch(true); });
$("chapters").addEventListener("click", () => {
  autoPause = !autoPause;
  try { localStorage.setItem("grm-universe-pauses", autoPause ? "on" : "off"); } catch { /* not kept */ }
  labelChapters();
});
$("timeline").addEventListener("input", (e) => {
  scrubbing = true;
  hidePause();
  lt = LT_START + ((ltEnd() - LT_START) * e.target.value) / 1000;
  stopAtToday = lt < ltToday();
  message("");
});
$("timeline").addEventListener("change", () => { scrubbing = false; });
$("presets").addEventListener("change", (e) => choosePreset(e.target.value));
$("reset").addEventListener("click", () => choosePreset("ours"));
$("save").addEventListener("click", () => {
  const name = $("save-name").value.trim();
  if (!name) return;
  const mine = store.get("grm-universe-mine", {});
  mine[name] = { ...params };
  store.set("grm-universe-mine", mine);
  $("save-name").value = "";
  buildSettings();
});
$("mute").addEventListener("click", () => {
  muted = !muted;
  if (!muted) music.start();
  music.mute(muted);
  labelMute();
});
$("lang").addEventListener("click", () => {
  lang = lang === "fr" ? "en" : "fr";
  T = TEXTS[lang];
  try { localStorage.setItem("grm-universe-lang", lang); } catch { /* not kept */ }
  applyTexts();
});

applyTexts();
solve();
if (state) view.update(moment(LT_START), state.values, uOf(10 ** LT_START));
requestAnimationFrame(frame);
