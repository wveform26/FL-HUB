import { icon } from "./icons.js";
import { escapeHtml } from "./utils.js";

const TOAST_ICONS = { info: "sparkles", success: "check", error: "alert" };

export function toast(message, type = "info", timeout = 4200) {
  const root = document.getElementById("toast-root");
  if (!root) return;
  const element = document.createElement("div");
  element.className = `toast toast-${type}`;
  element.innerHTML = `
    <span class="toast-icon">${icon(TOAST_ICONS[type] || "sparkles")}</span>
    <span>${escapeHtml(message)}</span>
  `;
  root.appendChild(element);
  const remove = () => {
    element.classList.add("is-leaving");
    window.setTimeout(() => element.remove(), 260);
  };
  const timer = window.setTimeout(remove, timeout);
  element.addEventListener("click", () => {
    window.clearTimeout(timer);
    remove();
  });
}

export function openModal(innerHtml) {
  const root = document.getElementById("modal-root");
  if (!root) return;
  root.innerHTML = `
    <div class="modal-overlay" data-modal-overlay>
      <div class="modal" role="dialog" aria-modal="true">${innerHtml}</div>
    </div>
  `;
  document.body.style.overflow = "hidden";
  const overlay = root.querySelector("[data-modal-overlay]");
  overlay.addEventListener("click", (event) => {
    if (event.target === overlay) closeModal();
  });
  const closeButton = root.querySelector("[data-modal-close]");
  if (closeButton) closeButton.addEventListener("click", closeModal);
}

export function closeModal() {
  const root = document.getElementById("modal-root");
  if (!root) return;
  root.innerHTML = "";
  document.body.style.overflow = "";
}

export function emptyState({ iconName = "music", title, text = "", action = "" }) {
  return `
    <div class="empty-state">
      <div class="empty-icon">${icon(iconName)}</div>
      <h3 class="empty-title">${escapeHtml(title)}</h3>
      ${text ? `<p class="empty-text">${escapeHtml(text)}</p>` : ""}
      ${action}
    </div>
  `;
}

export function loadingBlock(label = "Загружаем...") {
  return `
    <div class="loading-block">
      <span class="spinner"></span>
      <span>${escapeHtml(label)}</span>
    </div>
  `;
}
