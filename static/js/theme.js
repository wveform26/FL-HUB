import { icon } from "./icons.js";

const STORAGE_KEY = "flhub-theme";
const MEDIA = window.matchMedia("(prefers-color-scheme: light)");
const OPTIONS = [
  { value: "light", icon: "sun", label: "Светлая тема" },
  { value: "dark", icon: "moon", label: "Тёмная тема" },
  { value: "auto", icon: "monitor", label: "Как в системе" },
];

let preference = readPreference();

function readPreference() {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    return stored === "light" || stored === "dark" ? stored : "auto";
  } catch {
    return "auto";
  }
}

export function systemTheme() {
  return MEDIA.matches ? "light" : "dark";
}

export function resolvedTheme() {
  return preference === "auto" ? systemTheme() : preference;
}

export function currentPreference() {
  return preference;
}

export function applyTheme() {
  const theme = resolvedTheme();
  const root = document.documentElement;
  root.dataset.theme = theme;
  root.style.colorScheme = theme;
  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta) meta.setAttribute("content", theme === "light" ? "#f4f3f7" : "#08080c");
  syncButtons();
  document.dispatchEvent(new CustomEvent("theme:change", { detail: { theme, preference } }));
  return theme;
}

export function setTheme(value) {
  preference = value === "light" || value === "dark" ? value : "auto";
  try {
    if (preference === "auto") localStorage.removeItem(STORAGE_KEY);
    else localStorage.setItem(STORAGE_KEY, preference);
  } catch {
    /* приватный режим — просто не запоминаем */
  }
  applyTheme();
}

function syncButtons() {
  document.querySelectorAll("[data-theme-option]").forEach((button) => {
    const active = button.dataset.themeOption === preference;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-pressed", active ? "true" : "false");
  });
  const title = `Тема: ${preference === "auto" ? `системная (${systemTheme()})` : preference === "light" ? "светлая" : "тёмная"}`;
  document.querySelectorAll("[data-theme-switch]").forEach((node) => node.setAttribute("title", title));
}

/** Обновить состояние кнопок после перерисовки шапки. */
export const syncThemeButtons = syncButtons;

export function themeSwitchHtml() {
  const buttons = OPTIONS.map(
    (option) => `
      <button class="theme-option" type="button" data-theme-option="${option.value}"
              title="${option.label}" aria-label="${option.label}" aria-pressed="false">
        ${icon(option.icon)}
      </button>`
  ).join("");
  return `<div class="theme-switch" data-theme-switch role="group" aria-label="Выбор темы оформления">${buttons}</div>`;
}

export function initTheme() {
  applyTheme();
  const listen = MEDIA.addEventListener ? "addEventListener" : "addListener";
  MEDIA[listen]("change", () => {
    if (preference === "auto") applyTheme();
  });
  document.addEventListener("click", (event) => {
    const button = event.target.closest("[data-theme-option]");
    if (!button) return;
    event.preventDefault();
    setTheme(button.dataset.themeOption);
  });
}
