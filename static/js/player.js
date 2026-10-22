import { api } from "./api.js";
import { icon } from "./icons.js";
import { cacheItem, itemCache } from "./store.js";
import { toast } from "./ui.js";
import { escapeAttr, escapeHtml, formatCount, formatDuration } from "./utils.js";

const PLAYED_KEY = "flhub:played";

let audio = null;
let current = null;
let elements = null;
let seeking = false;
let mediaSessionReady = false;
let queue = [];
let queueIndex = -1;

function readPlayed() {
  try {
    return new Set(JSON.parse(window.sessionStorage.getItem(PLAYED_KEY) || "[]"));
  } catch {
    return new Set();
  }
}

function writePlayed(played) {
  try {
    window.sessionStorage.setItem(PLAYED_KEY, JSON.stringify([...played].slice(-200)));
  } catch {
    /* sessionStorage может быть недоступен */
  }
}

function emit(playing) {
  document.dispatchEvent(
    new CustomEvent("player:change", {
      detail: {
        id: current?.id || null,
        playing,
        queue: queue.map((item) => item.id),
      },
    })
  );
}

function totalDuration() {
  if (!audio) return 0;
  if (Number.isFinite(audio.duration) && audio.duration > 0) return audio.duration;
  return Number(current?.duration) || 0;
}

function updateTimeUi() {
  if (!elements || !audio) return;
  const total = totalDuration();
  const position = Number.isFinite(audio.currentTime) ? audio.currentTime : 0;
  const ratio = total > 0 ? Math.min(1, position / total) : 0;
  elements.current.textContent = formatDuration(position);
  elements.total.textContent = formatDuration(total);
  if (!seeking) {
    elements.seek.value = String(Math.round(ratio * 1000));
    elements.seek.style.setProperty("--progress", `${ratio * 100}%`);
  }
}

function updateToggleIcon() {
  if (!elements || !audio) return;
  const playing = !audio.paused;
  elements.toggle.innerHTML = icon(playing ? "pause" : "play");
  elements.toggle.setAttribute("aria-label", playing ? "Пауза" : "Играть");
}

function updateInfo() {
  if (!elements || !current) return;
  elements.cover.src = current.cover_url;
  elements.cover.alt = `Обложка ${current.title}`;
  elements.title.textContent = current.title;
  elements.title.href = `#/item/${current.id}`;
  elements.author.textContent = `@${current.author.username}`;
  elements.seek.value = "0";
  elements.seek.style.setProperty("--progress", "0%");
  elements.current.textContent = "0:00";
  elements.total.textContent = formatDuration(current.duration || 0);
}

function setupMediaSession() {
  if (mediaSessionReady || !("mediaSession" in navigator) || !current) return;
  mediaSessionReady = true;
  const handlers = {
    play: () => audio?.play(),
    pause: () => audio?.pause(),
    nexttrack: () => next(),
    previoustrack: () => previous(),
  };
  for (const [action, handler] of Object.entries(handlers)) {
    try {
      navigator.mediaSession.setActionHandler(action, handler);
    } catch {
      /* часть действий может быть не поддержана браузером */
    }
  }
}

function updateMediaSession() {
  if (!("mediaSession" in navigator) || !current) return;
  try {
    navigator.mediaSession.metadata = new MediaMetadata({
      title: current.title,
      artist: current.author.username,
      album: "FL HUB",
      artwork: [{ src: current.cover_url, sizes: "640x640" }],
    });
    setupMediaSession();
  } catch {
    /* Media Session API может быть недоступен */
  }
}

function reportPlay(item) {
  const played = readPlayed();
  if (played.has(item.id)) return;
  played.add(item.id);
  writePlayed(played);
  api
    .post(`/api/items/${item.id}/play`)
    .then((data) => {
      const cached = itemCache.get(item.id);
      if (cached) {
        cached.plays = data.plays;
        cacheItem(cached);
      }
      document.querySelectorAll(`[data-plays="${item.id}"]`).forEach((node) => {
        node.innerHTML = `${icon("headphones")} ${formatCount(data.plays)}`;
      });
    })
    .catch(() => {
      /* счётчик прослушиваний не критичен */
    });
}

export function initPlayer() {
  const root = document.getElementById("player-root");
  if (!root) return;
  root.innerHTML = `
    <div class="player-queue" id="player-queue" data-player-queue aria-label="Очередь воспроизведения">
      <div class="queue-head">
        <span class="queue-title">${icon("list")} Очередь</span>
        <button class="queue-close" type="button" data-queue-close aria-label="Скрыть очередь">${icon("close")}</button>
      </div>
      <div class="queue-list" data-queue-list></div>
    </div>
    <div class="player-bar" id="player-bar" aria-label="Аудиоплеер">
      <div class="player-cover"><img alt="" width="54" height="54"></div>
      <div class="player-info">
        <a class="player-title" href="#/"></a>
        <span class="player-author"></span>
      </div>
      <div class="player-controls">
        <button class="player-skip" type="button" data-player-prev aria-label="Предыдущий трек">${icon("prev")}</button>
        <button class="player-toggle" data-player-toggle aria-label="Пауза">${icon("pause")}</button>
        <button class="player-skip" type="button" data-player-next aria-label="Следующий трек">${icon("next")}</button>
        <div class="player-timeline">
          <span class="player-time player-current">0:00</span>
          <input class="seek" type="range" min="0" max="1000" value="0" aria-label="Позиция трека">
          <span class="player-time player-total">0:00</span>
        </div>
      </div>
      <div class="player-volume">
        ${icon("volume")}
        <input type="range" min="0" max="100" value="80" aria-label="Громкость">
      </div>
      <button class="player-queue-toggle" type="button" data-queue-toggle aria-label="Показать очередь" aria-expanded="false">
        ${icon("list")}<span class="player-queue-badge" data-queue-count hidden></span>
      </button>
      <button class="player-close" data-player-close aria-label="Закрыть плеер">${icon("close")}</button>
    </div>
  `;

  audio = new Audio();
  audio.preload = "metadata";
  audio.volume = 0.8;

  const bar = root.querySelector("#player-bar");
  elements = {
    bar,
    cover: bar.querySelector(".player-cover img"),
    title: bar.querySelector(".player-title"),
    author: bar.querySelector(".player-author"),
    toggle: bar.querySelector("[data-player-toggle]"),
    prev: bar.querySelector("[data-player-prev]"),
    next: bar.querySelector("[data-player-next]"),
    seek: bar.querySelector(".seek"),
    current: bar.querySelector(".player-current"),
    total: bar.querySelector(".player-total"),
    volume: bar.querySelector(".player-volume input"),
    queuePanel: root.querySelector("[data-player-queue]"),
    queueToggle: bar.querySelector("[data-queue-toggle]"),
    queueCount: bar.querySelector("[data-queue-count]"),
    queueClose: root.querySelector("[data-queue-close]"),
    queueList: root.querySelector("[data-queue-list]"),
    close: bar.querySelector("[data-player-close]"),
  };

  elements.toggle.addEventListener("click", toggle);
  elements.prev.addEventListener("click", previous);
  elements.next.addEventListener("click", next);
  elements.close.addEventListener("click", closePlayer);
  elements.queueToggle.addEventListener("click", toggleQueue);
  elements.queueClose.addEventListener("click", closeQueue);
  elements.queueList.addEventListener("click", (event) => {
    const button = event.target.closest("[data-queue-index]");
    if (!button) return;
    const index = Number(button.dataset.queueIndex);
    if (index === queueIndex) {
      toggle();
      return;
    }
    queueIndex = index;
    load(queue[queueIndex]);
  });
  elements.seek.addEventListener("input", () => {
    seeking = true;
    const total = totalDuration();
    const ratio = Number(elements.seek.value) / 1000;
    elements.seek.style.setProperty("--progress", `${ratio * 100}%`);
    elements.current.textContent = formatDuration(ratio * total);
  });
  elements.seek.addEventListener("change", () => {
    const total = totalDuration();
    if (total > 0) audio.currentTime = (Number(elements.seek.value) / 1000) * total;
    seeking = false;
    updateTimeUi();
  });
  elements.volume.addEventListener("input", () => {
    const value = Number(elements.volume.value) / 100;
    audio.volume = value;
    elements.volume.style.setProperty("--progress", `${value * 100}%`);
  });
  elements.volume.style.setProperty("--progress", "80%");

  audio.addEventListener("timeupdate", updateTimeUi);
  audio.addEventListener("loadedmetadata", updateTimeUi);
  audio.addEventListener("durationchange", updateTimeUi);
  audio.addEventListener("play", () => {
    updateToggleIcon();
    renderQueue();
    if (current) reportPlay(current);
    emit(true);
  });
  audio.addEventListener("pause", () => {
    updateToggleIcon();
    renderQueue();
    emit(false);
  });
  audio.addEventListener("ended", () => {
    if (!next()) {
      updateToggleIcon();
      renderQueue();
      emit(false);
    }
  });
  audio.addEventListener("error", () => {
    if (audio.src) toast("Не удалось воспроизвести файл", "error");
  });

  renderQueue();
}

function load(item) {
  if (!audio || !item) return;
  current = item;
  audio.src = item.audio_url;
  audio.currentTime = 0;
  updateInfo();
  updateMediaSession();
  elements.bar.classList.add("is-visible");
  document.body.classList.add("has-player");
  renderQueue();
  const promise = audio.play();
  if (promise && typeof promise.catch === "function") {
    promise.catch(() => toast("Не удалось запустить воспроизведение", "error"));
  }
  updateToggleIcon();
}

function toggleQueue() {
  if (!elements) return;
  const open = !elements.queuePanel.classList.contains("is-open");
  elements.queuePanel.classList.toggle("is-open", open);
  elements.queueToggle.setAttribute("aria-expanded", open ? "true" : "false");
}

function closeQueue() {
  if (!elements) return;
  elements.queuePanel.classList.remove("is-open");
  elements.queueToggle.setAttribute("aria-expanded", "false");
}

function renderQueue() {
  if (!elements) return;
  const active = queueIndex >= 0 ? queue[queueIndex] : null;
  elements.queueCount.textContent = String(queue.length);
  elements.queueCount.hidden = queue.length < 2;
  elements.queueToggle.classList.toggle("has-queue", queue.length > 1);
  if (!queue.length) {
    elements.queueList.innerHTML =
      `<div class="queue-empty">Очередь пуста. Нажми «Слушать» на любой работе.</div>`;
    return;
  }
  elements.queueList.innerHTML = queue
    .map((item, index) => {
      const isActive = Boolean(active && item.id === active.id);
      const isPaused = isActive && audio && audio.paused;
      return `
        <button class="queue-item ${isActive ? "is-active" : ""}" type="button" data-queue-index="${index}">
          <img class="queue-item-cover" src="${escapeAttr(item.cover_url)}" alt="" loading="lazy" decoding="async">
          <span class="queue-item-text">
            <span class="queue-item-title">${escapeHtml(item.title)}</span>
            <span class="queue-item-author">@${escapeHtml(item.author.username)}</span>
          </span>
          <span class="queue-item-state">${isActive ? icon(isPaused ? "play" : "pause") : ""}</span>
        </button>
      `;
    })
    .join("");
}

export function play(item, list = null) {
  if (!audio || !item) return;
  if (!item.audio_url) {
    window.location.href = `/download/${item.id}`;
    return;
  }

  if (Array.isArray(list) && list.length) {
    const entries = list.filter((entry) => entry && entry.audio_url);
    if (!entries.some((entry) => entry.id === item.id)) entries.unshift(item);
    queue = entries;
  } else if (!queue.some((entry) => entry.id === item.id)) {
    queue = [item];
  }
  queueIndex = queue.findIndex((entry) => entry.id === item.id);
  renderQueue();

  if (current && current.id === item.id) {
    toggle();
    return;
  }
  load(item);
}

export function next() {
  if (!audio || queueIndex < 0 || queueIndex >= queue.length - 1) return false;
  queueIndex += 1;
  load(queue[queueIndex]);
  return true;
}

export function previous() {
  if (!audio || !current) return;
  if (audio.currentTime > 3 || queueIndex <= 0) {
    audio.currentTime = 0;
    updateTimeUi();
    return;
  }
  queueIndex -= 1;
  load(queue[queueIndex]);
}

export function toggle() {
  if (!audio || !current) return;
  if (audio.paused) {
    audio.play().catch(() => toast("Не удалось запустить воспроизведение", "error"));
  } else {
    audio.pause();
  }
}

export function closePlayer() {
  if (!audio || !elements) return;
  audio.pause();
  audio.removeAttribute("src");
  audio.load();
  current = null;
  queue = [];
  queueIndex = -1;
  closeQueue();
  renderQueue();
  elements.bar.classList.remove("is-visible");
  document.body.classList.remove("has-player");
  emit(false);
}

export function isPlaying(itemId) {
  return Boolean(current && current.id === Number(itemId) && audio && !audio.paused);
}

export function currentItem() {
  return current;
}
