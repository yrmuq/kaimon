import { diffChange, mapPoint, pairUsable, remapPair } from "./pairs.mjs";

const ERROR_IDS = {
  K001: "100",
  K002: "101",
  K003: "102",
  K004: "103",
  K005: "104",
  K006: "105",
  K007: "106",
  K008: "107",
  K009: "108",
  K010: "109",
  K011: "110",
  K012: "111",
  K013: "112",
  K014: "113",
  K015: "114",
};

const catalogs = { en: null, ru: null };
const state = {
  text: "",
  name: "",
  pairs: [],
  index: -1,
  saved: null,
  semantic: 72,
  lexical: 76,
  lang: "en",
  theme: "system",
  phase: "idle",
  pendingName: "",
};

const openBtn = document.querySelector("#open");
const fileInput = document.querySelector("#file");
const nextBtn = document.querySelector("#next");
const backBtn = document.querySelector("#back");
const saveBtn = document.querySelector("#save");
const downloadBtn = document.querySelector("#download");
const semanticInput = document.querySelector("#semantic");
const lexicalInput = document.querySelector("#lexical");
const semanticValue = document.querySelector("#semantic-value");
const lexicalValue = document.querySelector("#lexical-value");
const langSelect = document.querySelector("#lang");
const themeSelect = document.querySelector("#theme");
const filename = document.querySelector("#filename");
const status = document.querySelector("#status");
const progress = document.querySelector("#progress");
const progressBar = progress.querySelector("span");
const error = document.querySelector("#error");
const drop = document.querySelector("#drop");
const fileList = document.querySelector("#file-list");
const filesEmpty = document.querySelector("#files-empty");
const resume = document.querySelector("#resume");
const resumeYes = document.querySelector("#resume-yes");
const resumeNo = document.querySelector("#resume-no");
const editors = [
  document.querySelector("#left-editor"),
  document.querySelector("#right-editor"),
].map((node) => ({
  pre: node.querySelector("pre"),
  area: node.querySelector("textarea"),
}));

let request = null;
let syncing = false;
let draftTimer = null;
let draftGen = 0;
let openToken = 0;
let resumeWait = null;
let sessionTimer = null;

function storageGet(key) {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function storageSet(key, value) {
  try {
    localStorage.setItem(key, value);
  } catch {
    /* private mode can reject storage; the choice still applies for this visit */
  }
}

function saveSession() {
  clearTimeout(sessionTimer);
  if (state.phase === "analyzing") {
    const name = state.pendingName || state.name;
    if (name) storageSet("kaimon-session", JSON.stringify({ phase: "analyzing", name }));
    return;
  }
  if (!state.name) {
    storageSet("kaimon-session", JSON.stringify({ phase: "idle" }));
    return;
  }
  storageSet("kaimon-session", JSON.stringify({
    phase: "ready",
    name: state.name,
    text: state.text,
    pairs: state.pairs,
    index: state.index,
    saved: state.saved,
    scrolls: editors.map((editor) => editor.area.scrollTop),
    selections: editors.map((editor) => [editor.area.selectionStart, editor.area.selectionEnd]),
  }));
}

function scheduleSession() {
  clearTimeout(sessionTimer);
  sessionTimer = setTimeout(saveSession, 200);
}

function markAnalyzing(name) {
  state.phase = "analyzing";
  state.pendingName = name;
  saveSession();
}

function finishOpenAttempt() {
  state.phase = "ready";
  state.pendingName = "";
  saveSession();
}

function systemLang() {
  const list = navigator.languages?.length ? navigator.languages : [navigator.language || "en"];
  return list.some((tag) => String(tag).toLowerCase().startsWith("ru")) ? "ru" : "en";
}

function parseCatalog(text) {
  const map = new Map();
  for (const line of text.split(/\r?\n/)) {
    if (!line.trim() || line.startsWith(";")) continue;
    const parts = line.split(" = ");
    if (parts.length < 3) continue;
    map.set(parts[0].trim(), parts.slice(2).join(" = "));
  }
  return map;
}

function t(id, vars) {
  const map = catalogs[state.lang] || catalogs.en;
  let value = map?.get(String(id)) || catalogs.en?.get(String(id)) || "";
  if (vars) {
    for (const [key, item] of Object.entries(vars)) {
      value = value.replaceAll(`{${key}}`, String(item));
    }
  }
  return value;
}

function applyTheme() {
  const dark = state.theme === "dark" || (state.theme === "system" && matchMedia("(prefers-color-scheme: dark)").matches);
  document.documentElement.dataset.theme = dark ? "dark" : "light";
}

function applyLanguage() {
  document.documentElement.lang = state.lang;
  document.title = t("1");
  for (const node of document.querySelectorAll("[data-i18n]")) {
    node.textContent = t(node.getAttribute("data-i18n"));
  }
  langSelect.options[0].textContent = t("10");
  langSelect.options[1].textContent = t("11");
  themeSelect.options[0].textContent = t("7");
  themeSelect.options[1].textContent = t("8");
  themeSelect.options[2].textContent = t("9");
  refresh(false);
}

function setError(code, fallback) {
  const id = ERROR_IDS[code];
  error.hidden = false;
  error.textContent = id ? `${code}: ${t(id)}` : `${code}: ${fallback || ""}`;
}

function clearError() {
  error.hidden = true;
  error.textContent = "";
}

function escapeHtml(value) {
  return value.replace(/&/g, "&").replace(/</g, "<").replace(/>/g, ">");
}

function highlighted(text, span) {
  if (!span || span[0] < 0 || span[1] > text.length || span[0] >= span[1]) return escapeHtml(text);
  return `${escapeHtml(text.slice(0, span[0]))}<mark>${escapeHtml(text.slice(span[0], span[1]))}</mark>${escapeHtml(text.slice(span[1]))}`;
}

function currentPair() {
  if (state.index < 0) return null;
  const pair = state.pairs[state.index];
  return shown(pair) ? pair : null;
}

function alivePairs() {
  return state.pairs.filter((pair) => shown(pair));
}

function shown(pair) {
  if (!pair || !pairUsable(pair, state.text.length)) return false;
  return pair.semantic * 100 >= state.semantic || pair.lexical * 100 >= state.lexical;
}

function readThreshold(raw, fallback) {
  const value = Number(raw);
  if (!Number.isInteger(value) || value < 50 || value > 95) return fallback;
  return value;
}

function showThresholds() {
  semanticInput.value = String(state.semantic);
  lexicalInput.value = String(state.lexical);
  semanticValue.textContent = `${state.semantic}%`;
  lexicalValue.textContent = `${state.lexical}%`;
}

function onThreshold() {
  state.semantic = readThreshold(semanticInput.value, 72);
  state.lexical = readThreshold(lexicalInput.value, 76);
  storageSet("kaimon-semantic", String(state.semantic));
  storageSet("kaimon-lexical", String(state.lexical));
  showThresholds();
  if (!shown(state.pairs[state.index])) {
    state.index = state.pairs.findIndex((pair) => shown(pair));
  }
  refresh(true);
  scheduleSession();
}

function renderBackdrops() {
  const pair = currentPair();
  editors[0].pre.innerHTML = highlighted(state.text, pair?.left || null);
  editors[1].pre.innerHTML = highlighted(state.text, pair?.right || null);
  for (const editor of editors) {
    editor.pre.scrollTop = editor.area.scrollTop;
    editor.pre.scrollLeft = editor.area.scrollLeft;
  }
}

function scrollToOffset(area, offset) {
  const line = state.text.slice(0, offset).split("\n").length - 1;
  area.scrollTop = Math.max(0, line * 24 - area.clientHeight * 0.2);
  area.dispatchEvent(new Event("scroll"));
}

function hideProgress() {
  progress.hidden = true;
  progressBar.style.width = "0";
}

function showProgress(event) {
  const percent = Math.max(0, Math.min(100, Number(event.percent) || 0));
  let detail = t("21");
  if (event.step === "model") detail = t("22");
  else if (event.step === "split") detail = t("23", { count: event.count ?? 0 });
  else if (event.step === "embed") detail = t("24", { done: event.done ?? 0, total: event.total ?? 0 });
  else if (event.step === "select") detail = t("25");
  progress.hidden = false;
  progressBar.style.width = `${percent}%`;
  status.textContent = t("26", { percent, step: detail });
}

function setStatusText() {
  hideProgress();
  if (!state.text) {
    status.textContent = t("18");
    return;
  }
  const pair = currentPair();
  if (!state.pairs.length) {
    status.textContent = t("15");
    return;
  }
  if (!pair) {
    status.textContent = t("20");
    return;
  }
  const alive = alivePairs();
  status.textContent = t("16", {
    current: alive.indexOf(pair) + 1,
    total: alive.length,
    score: Math.round(pair.score * 100),
  });
}

function refresh(jump) {
  renderBackdrops();
  const pair = currentPair();
  if (pair && jump) {
    scrollToOffset(editors[0].area, pair.left[0]);
    scrollToOffset(editors[1].area, pair.right[0]);
  }
  setStatusText();
  nextBtn.disabled = !state.text || alivePairs().length === 0;
  backBtn.disabled = !state.text || alivePairs().length === 0;
  downloadBtn.disabled = !state.text;
  saveBtn.disabled = !state.name;
  drop.hidden = Boolean(state.text);
}

function loadDocument(name, text, pairs, clean, view) {
  state.phase = "ready";
  state.pendingName = "";
  state.name = name;
  state.text = text;
  state.saved = clean ? text : null;
  state.pairs = pairs;
  state.index = pairs.findIndex((pair) => shown(pair));
  if (view && Number.isInteger(view.index)) state.index = view.index;
  filename.textContent = name;
  for (const button of fileList.querySelectorAll("button")) {
    if (button.textContent === name) button.setAttribute("aria-current", "true");
    else button.removeAttribute("aria-current");
  }
  for (const editor of editors) {
    editor.area.disabled = false;
    editor.area.value = text;
    editor.area.scrollTop = 0;
    editor.area.scrollLeft = 0;
  }
  refresh(!view);
  if (view) {
    const len = text.length;
    editors.forEach((editor, i) => {
      editor.area.scrollTop = Number(view.scrolls?.[i]) || 0;
      const sel = view.selections?.[i];
      if (Array.isArray(sel)) {
        editor.area.selectionStart = Math.min(Math.max(Number(sel[0]) || 0, 0), len);
        editor.area.selectionEnd = Math.min(Math.max(Number(sel[1]) || 0, 0), len);
      }
    });
    renderBackdrops();
  }
  saveSession();
}

function onEdit(source) {
  if (syncing || !state.name) return;
  const next = source.value;
  if (next === state.text) return;
  const change = diffChange(state.text, next);
  state.text = next;
  state.pairs = state.pairs.map((pair) => remapPair(pair, change.cut, change.endOld, change.insertLen));
  if (!shown(state.pairs[state.index])) {
    state.index = state.pairs.findIndex((pair) => shown(pair));
  }
  const other = editors.find((editor) => editor.area !== source);
  const top = other.area.scrollTop;
  const left = other.area.scrollLeft;
  const selStart = mapPoint(other.area.selectionStart, change.cut, change.endOld, change.insertLen);
  const selEnd = mapPoint(other.area.selectionEnd, change.cut, change.endOld, change.insertLen);
  syncing = true;
  other.area.value = next;
  syncing = false;
  other.area.scrollTop = top;
  other.area.scrollLeft = left;
  const len = next.length;
  other.area.selectionStart = Math.min(Math.max(selStart, 0), len);
  other.area.selectionEnd = Math.min(Math.max(selEnd, 0), len);
  refresh(false);
  scheduleDraft();
  scheduleSession();
}

function showPrev() {
  for (let i = state.index - 1; i >= 0; i -= 1) {
    if (shown(state.pairs[i])) {
      state.index = i;
      refresh(true);
      saveSession();
      return;
    }
  }
  status.textContent = t("37");
}

function showNext() {
  for (let i = state.index + 1; i < state.pairs.length; i += 1) {
    if (pairUsable(state.pairs[i], state.text.length) && shown(state.pairs[i])) {
      state.index = i;
      refresh(true);
      saveSession();
      return;
    }
  }
  status.textContent = currentPair() ? t("17") : t("19");
}

async function readAnalysis(response) {
  const type = response.headers.get("content-type") || "";
  if (!response.ok || !type.includes("ndjson")) {
    const payload = await response.json().catch(() => ({}));
    setError(payload.error || "K005", payload.message);
    finishOpenAttempt();
    setStatusText();
    return;
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const chunk = await reader.read();
    if (chunk.done) break;
    buffer += decoder.decode(chunk.value, { stream: true });
    let nl = buffer.indexOf("\n");
    while (nl >= 0) {
      const line = buffer.slice(0, nl).trim();
      buffer = buffer.slice(nl + 1);
      nl = buffer.indexOf("\n");
      if (!line) continue;
      const event = JSON.parse(line);
      if (event.event === "progress") showProgress(event);
      else if (event.event === "error") {
        setError(event.error || "K005", event.message);
        finishOpenAttempt();
        setStatusText();
      } else if (event.event === "result") {
        loadDocument(event.name, event.text, event.pairs, true);
      }
    }
  }
}

function stopResume(choice) {
  resume.hidden = true;
  const wait = resumeWait;
  resumeWait = null;
  if (wait) wait(choice);
}

function askResume() {
  resume.hidden = false;
  applyLanguage();
  return new Promise((resolve) => {
    resumeWait = resolve;
  });
}

async function fetchDraft(name) {
  const response = await fetch(`/api/draft?name=${encodeURIComponent(name)}`);
  if (response.status === 404) return null;
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    setError(payload.error || "K012", payload.message);
    return null;
  }
  return payload;
}

async function discardDraft(name) {
  await fetch(`/api/draft?name=${encodeURIComponent(name)}`, { method: "DELETE" });
}

function scheduleDraft() {
  clearTimeout(draftTimer);
  const gen = ++draftGen;
  draftTimer = setTimeout(() => sendDraft(gen), 700);
}

async function sendDraft(gen) {
  if (!state.name || gen !== draftGen) return;
  if (state.saved !== null && state.text === state.saved) {
    await discardDraft(state.name);
    return;
  }
  const response = await fetch("/api/draft", {
    method: "PUT",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ name: state.name, text: state.text, pairs: state.pairs }),
  });
  if (gen !== draftGen) {
    if (state.saved !== null && state.text === state.saved) await discardDraft(state.name);
    return;
  }
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    setError(payload.error || "K012", payload.message);
  }
}

async function chooseDraft(name) {
  const draft = await fetchDraft(name);
  if (!draft) return "missing";
  const choice = await askResume();
  if (choice !== "continue") return choice;
  loadDocument(draft.name, draft.text, draft.pairs, false);
  return "continue";
}

async function openSaved(name) {
  const token = ++openToken;
  clearError();
  stopResume("abort");
  request?.abort();
  const choice = await chooseDraft(name);
  if (token !== openToken || choice === "abort") return;
  if (choice === "continue") return;
  if (choice === "saved") await discardDraft(name);
  markAnalyzing(name);
  const current = new AbortController();
  request = current;
  showProgress({ step: "read", percent: 2 });
  nextBtn.disabled = true;
  try {
    const response = await fetch("/api/open", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ name }),
      signal: current.signal,
    });
    if (current.signal.aborted || token !== openToken) return;
    await readAnalysis(response);
  } catch (err) {
    if (err.name === "AbortError") return;
    finishOpenAttempt();
    setError("K005");
    setStatusText();
  }
}

async function loadFiles() {
  const response = await fetch("/api/files");
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    setError(payload.error || "K010", payload.message);
    return;
  }
  fileList.replaceChildren();
  const names = payload.files || [];
  for (const name of names) {
    const item = document.createElement("li");
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = name;
    button.title = name;
    if (name === state.name) button.setAttribute("aria-current", "true");
    button.addEventListener("click", () => openSaved(name));
    item.append(button);
    fileList.append(item);
  }
  filesEmpty.hidden = names.length > 0;
}

async function openFile(file) {
  clearError();
  if (!file) return;
  if (!file.name.toLowerCase().endsWith(".txt")) {
    setError("K008");
    return;
  }
  const token = ++openToken;
  stopResume("abort");
  request?.abort();
  const choice = await chooseDraft(file.name);
  if (token !== openToken || choice === "abort") return;
  if (choice === "continue") return;
  if (choice === "saved") await discardDraft(file.name);
  markAnalyzing(file.name);
  const current = new AbortController();
  request = current;
  showProgress({ step: "read", percent: 2 });
  nextBtn.disabled = true;
  const body = new FormData();
  body.append("file", file, file.name);
  try {
    const response = await fetch("/api/analyze", { method: "POST", body, signal: current.signal });
    if (current.signal.aborted || token !== openToken) return;
    await readAnalysis(response);
  } catch (err) {
    if (err.name === "AbortError") return;
    finishOpenAttempt();
    setError("K005");
    setStatusText();
  }
}

openBtn.addEventListener("click", () => fileInput.click());
fileInput.addEventListener("change", () => {
  const file = fileInput.files?.[0];
  fileInput.value = "";
  openFile(file);
});
nextBtn.addEventListener("click", showNext);
backBtn.addEventListener("click", showPrev);
saveBtn.addEventListener("click", async () => {
  if (!state.name) return;
  clearTimeout(draftTimer);
  draftGen += 1;
  const response = await fetch("/api/save", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ name: state.name, text: state.text, pairs: state.pairs }),
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    setError(payload.error || "K011", payload.message);
    return;
  }
  clearError();
  state.saved = state.text;
  state.name = payload.name || state.name;
  filename.textContent = state.name;
  status.textContent = t("30");
  saveSession();
  loadFiles();
});
resumeYes.addEventListener("click", () => stopResume("continue"));
resumeNo.addEventListener("click", () => stopResume("saved"));
semanticInput.addEventListener("input", onThreshold);
lexicalInput.addEventListener("input", onThreshold);
downloadBtn.addEventListener("click", () => {
  const blob = new Blob([state.text], { type: "text/plain;charset=utf-8" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = state.name || "notes.txt";
  link.click();
  URL.revokeObjectURL(link.href);
});
langSelect.addEventListener("change", () => {
  state.lang = langSelect.value;
  storageSet("kaimon-lang", state.lang);
  applyLanguage();
});
themeSelect.addEventListener("change", () => {
  state.theme = themeSelect.value;
  storageSet("kaimon-theme", state.theme);
  applyTheme();
});
for (const editor of editors) {
  editor.area.addEventListener("input", () => onEdit(editor.area));
  editor.area.addEventListener("scroll", () => {
    editor.pre.scrollTop = editor.area.scrollTop;
    editor.pre.scrollLeft = editor.area.scrollLeft;
    if (!syncing) scheduleSession();
  });
  editor.area.addEventListener("keyup", () => scheduleSession());
  editor.area.addEventListener("mouseup", () => scheduleSession());
}
window.addEventListener("dragover", (event) => event.preventDefault());
window.addEventListener("drop", (event) => {
  event.preventDefault();
  openFile(event.dataTransfer?.files?.[0]);
});
window.addEventListener("pagehide", () => {
  saveSession();
  if (!state.name || (state.saved !== null && state.text === state.saved)) return;
  fetch("/api/draft", {
    method: "PUT",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ name: state.name, text: state.text, pairs: state.pairs }),
    keepalive: true,
  });
});
matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
  if (state.theme === "system") applyTheme();
});

async function reconnect(name) {
  clearError();
  state.phase = "analyzing";
  state.pendingName = name;
  showProgress({ step: "read", percent: 2 });
  try {
    let response = await fetch(`/api/job?name=${encodeURIComponent(name)}`);
    if (response.status === 404) {
      response = await fetch("/api/open", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ name }),
      });
    }
    if (response.status === 404) {
      finishOpenAttempt();
      return;
    }
    await readAnalysis(response);
  } catch {
    finishOpenAttempt();
    setError("K005");
    setStatusText();
  }
}

function restoreSession() {
  let session = null;
  try {
    session = JSON.parse(storageGet("kaimon-session") || "");
  } catch {
    return;
  }
  if (!session || typeof session.name !== "string") return;
  if (session.phase === "analyzing") {
    reconnect(session.name);
    return;
  }
  if (session.phase !== "ready" || typeof session.text !== "string" || !Array.isArray(session.pairs)) return;
  const clean = session.saved !== null && session.saved === session.text;
  loadDocument(session.name, session.text, session.pairs, clean, session);
}

const savedLang = storageGet("kaimon-lang");
const savedTheme = storageGet("kaimon-theme");
state.lang = savedLang === "en" || savedLang === "ru" ? savedLang : systemLang();
state.theme = savedTheme === "light" || savedTheme === "dark" || savedTheme === "system" ? savedTheme : "system";
state.semantic = readThreshold(storageGet("kaimon-semantic"), 72);
state.lexical = readThreshold(storageGet("kaimon-lexical"), 76);
langSelect.value = state.lang;
themeSelect.value = state.theme;
showThresholds();
applyTheme();

const [enText, ruText] = await Promise.all([
  fetch("/languages/English.ini").then((response) => response.text()),
  fetch("/languages/Russian.ini").then((response) => response.text()),
]);
catalogs.en = parseCatalog(enText);
catalogs.ru = parseCatalog(ruText);
applyLanguage();
refresh(false);
restoreSession();
loadFiles();
