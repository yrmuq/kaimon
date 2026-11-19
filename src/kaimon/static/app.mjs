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
};

const catalogs = { en: null, ru: null };
const state = {
  text: "",
  name: "",
  pairs: [],
  index: -1,
  lang: "en",
  theme: "system",
};

const openBtn = document.querySelector("#open");
const fileInput = document.querySelector("#file");
const nextBtn = document.querySelector("#next");
const downloadBtn = document.querySelector("#download");
const langSelect = document.querySelector("#lang");
const themeSelect = document.querySelector("#theme");
const filename = document.querySelector("#filename");
const status = document.querySelector("#status");
const error = document.querySelector("#error");
const drop = document.querySelector("#drop");
const editors = [
  document.querySelector("#left-editor"),
  document.querySelector("#right-editor"),
].map((node) => ({
  pre: node.querySelector("pre"),
  area: node.querySelector("textarea"),
}));

let request = null;
let syncing = false;

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
  if (!pair || !pairUsable(pair, state.text.length)) return null;
  return pair;
}

function alivePairs() {
  return state.pairs.filter((pair) => pairUsable(pair, state.text.length));
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

function setStatusText() {
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
  downloadBtn.disabled = !state.text;
  drop.hidden = Boolean(state.text);
}

function loadDocument(name, text, pairs) {
  state.name = name;
  state.text = text;
  state.pairs = pairs;
  state.index = pairs.findIndex((pair) => pairUsable(pair, text.length));
  filename.textContent = name;
  for (const editor of editors) {
    editor.area.disabled = false;
    editor.area.value = text;
    editor.area.scrollTop = 0;
    editor.area.scrollLeft = 0;
  }
  refresh(true);
}

function onEdit(source) {
  if (syncing || !state.name) return;
  const next = source.value;
  if (next === state.text) return;
  const change = diffChange(state.text, next);
  state.text = next;
  state.pairs = state.pairs.map((pair) => remapPair(pair, change.cut, change.endOld, change.insertLen));
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
}

function showNext() {
  for (let i = state.index + 1; i < state.pairs.length; i += 1) {
    if (pairUsable(state.pairs[i], state.text.length)) {
      state.index = i;
      refresh(true);
      return;
    }
  }
  status.textContent = currentPair() ? t("17") : t("19");
}

async function openFile(file) {
  clearError();
  if (!file) return;
  if (!file.name.toLowerCase().endsWith(".txt")) {
    setError("K008");
    return;
  }
  request?.abort();
  const current = new AbortController();
  request = current;
  status.textContent = t("14");
  nextBtn.disabled = true;
  const body = new FormData();
  body.append("file", file, file.name);
  try {
    const response = await fetch("/api/analyze", { method: "POST", body, signal: current.signal });
    const payload = await response.json().catch(() => ({}));
    if (current.signal.aborted) return;
    if (!response.ok) {
      setError(payload.error || "K005", payload.message);
      setStatusText();
      return;
    }
    loadDocument(payload.name, payload.text, payload.pairs);
  } catch (err) {
    if (err.name === "AbortError") return;
    setError("K005");
  }
}

openBtn.addEventListener("click", () => fileInput.click());
fileInput.addEventListener("change", () => {
  const file = fileInput.files?.[0];
  fileInput.value = "";
  openFile(file);
});
nextBtn.addEventListener("click", showNext);
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
  });
}
window.addEventListener("dragover", (event) => event.preventDefault());
window.addEventListener("drop", (event) => {
  event.preventDefault();
  openFile(event.dataTransfer?.files?.[0]);
});
matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
  if (state.theme === "system") applyTheme();
});

const savedLang = storageGet("kaimon-lang");
const savedTheme = storageGet("kaimon-theme");
state.lang = savedLang === "en" || savedLang === "ru" ? savedLang : systemLang();
state.theme = savedTheme === "light" || savedTheme === "dark" || savedTheme === "system" ? savedTheme : "system";
langSelect.value = state.lang;
themeSelect.value = state.theme;
applyTheme();

const [enText, ruText] = await Promise.all([
  fetch("/languages/English.ini").then((response) => response.text()),
  fetch("/languages/Russian.ini").then((response) => response.text()),
]);
catalogs.en = parseCatalog(enText);
catalogs.ru = parseCatalog(ruText);
applyLanguage();
refresh(false);
