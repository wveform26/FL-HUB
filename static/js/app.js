import { api } from "./api.js";
import { avatarHtml } from "./components.js";
import { icon, logoMark } from "./icons.js";
import { initPlayer, play as playTrack } from "./player.js";
import {
  cacheItem,
  currentPath,
  itemCache,
  navigate,
  setUser,
  state,
} from "./store.js";
import { closeModal, emptyState, toast } from "./ui.js";
import { escapeAttr, escapeHtml, formatCount } from "./utils.js";
import { renderHome } from "./views/home.js";
import { renderCatalog } from "./views/catalog.js";
import { renderItem } from "./views/item.js";
import { renderUpload } from "./views/upload.js";
import { renderProfile } from "./views/profile.js";
import { renderAuth } from "./views/auth.js";

const NAV_ITEMS = [
  { key: "catalog", label: "Каталог", href: "#/catalog" },
  { key: "music", label: "Музыка", href: "#/catalog?category=music" },
  { key: "project", label: "Проекты", href: "#/catalog?category=project" },
  { key: "plugin", label: "Плагины", href: "#/catalog?category=plugin" },
];

const ROUTES = [
  { pattern: /^\/$/, render: renderHome, title: "FL HUB — сообщество продюсеров FL Studio" },
  { pattern: /^\/catalog$/, render: renderCatalog, title: "Каталог — FL HUB" },
  { pattern: /^\/item\/(\d+)$/, render: renderItem, title: "Работа — FL HUB", param: "id" },
  { pattern: /^\/upload$/, render: renderUpload, title: "Загрузить работу — FL HUB" },
  { pattern: /^\/profile\/([A-Za-z0-9_]+)$/, render: renderProfile, title: "Профиль — FL HUB", param: "username" },
  { pattern: /^\/login$/, render: renderAuth, title: "Вход — FL HUB" },
  { pattern: /^\/register$/, render: renderAuth, title: "Регистрация — FL HUB" },
];

const main = document.getElementById("main");
const header = document.getElementById("site-header");
const footer = document.getElementById("site-footer");
let lastPath = null;

function parseLocation() {
  let raw = window.location.hash.startsWith("#")
    ? window.location.hash.slice(1)
    : window.location.hash;
  if (!raw) raw = "/";
  const [pathPart, queryPart = ""] = raw.split("?");
  let path = pathPart || "/";
  if (path.length > 1 && path.endsWith("/")) path = path.slice(0, -1);
  return { path, params: new URLSearchParams(queryPart) };
}

function matchRoute(path) {
  for (const route of ROUTES) {
    const match = path.match(route.pattern);
    if (match) {
      const params = new URLSearchParams(
        window.location.hash.includes("?") ? window.location.hash.split("?")[1] : ""
      );
      const ctx = { path, params };
      if (route.param) ctx[route.param] = match[1];
      return { route, ctx };
    }
  }
  return null;
}

function activeNavKey(path, params) {
  if (path !== "/catalog") return "";
  const category = params.get("category") || "";
  return ["music", "project", "plugin"].includes(category) ? category : "catalog";
}

function headerSearchValue(path, params) {
  return path === "/catalog" ? params.get("q") || "" : "";
}

function navLink(item, active) {
  return `<a class="nav-link ${active === item.key ? "is-active" : ""}" href="${item.href}"
             ${active === item.key ? 'aria-current="page"' : ""}>${escapeHtml(item.label)}</a>`;
}

function renderHeader(path = "/", params = new URLSearchParams()) {
  if (!header) return;
  const active = activeNavKey(path, params);
  const searchValue = headerSearchValue(path, params);
  const user = state.user;
  const nav = NAV_ITEMS.map((item) => navLink(item, active)).join("");
  const mobileNav = NAV_ITEMS.map((item) => navLink(item, active)).join("");

  header.innerHTML = `
    <div class="container header-inner">
      <a class="logo" href="#/" aria-label="FL HUB — на главную">
        <span class="logo-mark">${logoMark()}</span>
        <span class="logo-text">FL<span>HUB</span></span>
      </a>
      <nav class="nav" aria-label="Основная навигация">${nav}</nav>
      <div class="header-search">
        <form class="search-field" data-header-search role="search">
          ${icon("search")}
          <input type="search" name="q" value="${escapeAttr(searchValue)}" placeholder="Поиск по каталогу" aria-label="Поиск по каталогу" autocomplete="off">
        </form>
      </div>
      <div class="header-actions">
        <a class="btn btn-primary btn-sm btn-upload" href="#/upload">
          ${icon("upload")}<span class="btn-upload-label">Загрузить</span>
        </a>
        ${user ? `
          <div class="user-menu" data-user-menu>
            <button class="user-button" type="button" data-user-toggle aria-label="Меню профиля">
              ${avatarHtml(user, "avatar-sm")}
              ${icon("chevron-down")}
            </button>
            <div class="user-dropdown hidden" data-user-dropdown>
              <div class="dropdown-user">
                <strong>@${escapeHtml(user.username)}</strong>
                <span>Участник FL HUB</span>
              </div>
              <a class="dropdown-item" href="#/profile/${encodeURIComponent(user.username)}">${icon("user")} Мой профиль</a>
              <a class="dropdown-item" href="#/upload">${icon("upload")} Загрузить работу</a>
              <button class="dropdown-item danger" type="button" data-logout>${icon("logout")} Выйти</button>
            </div>
          </div>
        ` : `
          <a class="btn btn-ghost btn-sm" href="#/login">Войти</a>
        `}
        <button class="icon-btn menu-toggle" type="button" data-menu-toggle aria-label="Открыть меню">${icon("menu")}</button>
      </div>
    </div>
    <div class="mobile-nav container" id="mobile-nav">
      <form class="search-field" data-header-search role="search">
        ${icon("search")}
        <input type="search" name="q" value="${escapeAttr(searchValue)}" placeholder="Поиск по каталогу" aria-label="Поиск по каталогу" autocomplete="off">
      </form>
      ${mobileNav}
      ${user
        ? `<a class="nav-link" href="#/profile/${encodeURIComponent(user.username)}">Мой профиль</a>
           <button class="nav-link" type="button" data-logout>Выйти</button>`
        : `<a class="nav-link" href="#/login">Войти в аккаунт</a>`}
    </div>
  `;
}

function renderFooter() {
  if (!footer) return;
  const year = new Date().getFullYear();
  footer.innerHTML = `
    <div class="footer-inner">
      <div class="footer-top">
        <div class="footer-brand">
          <a class="logo" href="#/">
            <span class="logo-mark">${logoMark()}</span>
            <span class="logo-text">FL<span>HUB</span></span>
          </a>
          <p class="footer-tagline">Сообщество продюсеров FL Studio. Музыка, проекты, инструменты, плагины и драм-киты в одном месте.</p>
          <p class="footer-note">Неофициальный проект. FL Studio — торговая марка Image-Line. Сайт не связан с Image-Line.</p>
        </div>
        <div class="footer-col">
          <h4>Каталог</h4>
          <a href="#/catalog?category=music">Музыка</a>
          <a href="#/catalog?category=project">Проекты</a>
          <a href="#/catalog?category=instrument">Инструменты</a>
          <a href="#/catalog?category=plugin">Плагины</a>
          <a href="#/catalog?category=drumkit">Драм-киты</a>
        </div>
        <div class="footer-col">
          <h4>Сообщество</h4>
          <a href="#/upload">Загрузить работу</a>
          <a href="#/catalog">Каталог звуков</a>
          <a href="#/login">Войти</a>
          <a href="#/register">Регистрация</a>
        </div>
        <div class="footer-col">
          <h4>О проекте</h4>
          <a href="#/">Главная</a>
          <a href="#/catalog?sort=popular">Популярное</a>
          <a href="#/catalog?category=drumkit">Сэмплы и киты</a>
          <a href="#/catalog?q=free">Бесплатное</a>
        </div>
      </div>
      <div class="footer-bottom">
        <span>© ${year} FL HUB. Сделано для продюсеров.</span>
        <span>Демо-версия · Python + SQLite · без внешних зависимостей</span>
      </div>
    </div>
  `;
}

async function renderCurrent() {
  const { path, params } = parseLocation();
  const matched = matchRoute(path);
  if (!matched) {
    renderHeader(path, params);
    document.title = "Страница не найдена — FL HUB";
    main.innerHTML = `<div class="container" style="padding-top:60px">${emptyState({
      iconName: "alert",
      title: "Страница не найдена",
      text: "Похоже, ссылка устарела или в ней ошибка.",
      action: `<a class="btn btn-primary" href="#/">На главную</a>`,
    })}</div>`;
    return;
  }

  if (path === "/upload" && !state.user) {
    toast("Войди, чтобы загружать работы", "info");
    navigate(`/login?next=${encodeURIComponent("/upload")}`);
    return;
  }

  renderHeader(path, params);
  document.title = matched.route.title;
  const samePath = path === lastPath;
  lastPath = path;
  closeMobileMenu();
  closeUserDropdown();
  if (!samePath) window.scrollTo({ top: 0, behavior: "auto" });

  try {
    await matched.route.render(main, matched.ctx);
  } catch (error) {
    console.error(error);
    main.innerHTML = `<div class="container" style="padding-top:60px">${emptyState({
      iconName: "alert",
      title: "Что-то пошло не так",
      text: error.message || "Попробуйте обновить страницу.",
      action: `<button class="btn btn-primary" type="button" onclick="location.reload()">Обновить</button>`,
    })}</div>`;
  }
}

function closeUserDropdown() {
  document.querySelector("[data-user-dropdown]")?.classList.add("hidden");
}

function closeMobileMenu() {
  document.getElementById("mobile-nav")?.classList.remove("is-open");
}

async function handleLike(itemId) {
  if (!state.user) {
    toast("Войди, чтобы оценивать работы", "info");
    navigate(`/login?next=${encodeURIComponent(currentPath())}`);
    return;
  }
  const buttons = [...document.querySelectorAll(`[data-like="${itemId}"]`)];
  buttons.forEach((button) => { button.disabled = true; });
  try {
    const data = await api.post(`/api/items/${itemId}/like`);
    buttons.forEach((button) => {
      button.dataset.liked = data.liked ? "1" : "0";
      button.dataset.count = String(data.likes);
      button.classList.toggle("is-liked", data.liked);
      button.setAttribute("aria-pressed", data.liked ? "true" : "false");
      const count = button.querySelector(".like-count");
      if (count) count.textContent = formatCount(data.likes);
    });
    document.querySelectorAll(`[data-like-stat="${itemId}"]`).forEach((node) => {
      node.innerHTML = `${icon("heart")} ${formatCount(data.likes)}`;
    });
    const cached = itemCache.get(itemId);
    if (cached) {
      cached.liked = data.liked;
      cached.likes = data.likes;
      cacheItem(cached);
    }
  } catch (error) {
    toast(error.message, "error");
  } finally {
    buttons.forEach((button) => { button.disabled = false; });
  }
}

function collectQueue() {
  const seen = new Set();
  const entries = [];
  document.querySelectorAll("[data-play]").forEach((node) => {
    const id = Number(node.dataset.play);
    if (!id || seen.has(id)) return;
    const item = itemCache.get(id);
    if (!item || !item.audio_url) return;
    seen.add(id);
    entries.push(item);
  });
  return entries;
}

function handleDownload(itemId) {
  const link = document.createElement("a");
  link.href = `/download/${itemId}`;
  link.download = "";
  document.body.appendChild(link);
  link.click();
  link.remove();
  toast("Загрузка началась", "success");
}

async function handleLogout() {
  try {
    await api.post("/api/logout");
  } catch {
    /* сессия могла уже истечь */
  }
  setUser(null);
  toast("Ты вышел из аккаунта", "info");
  navigate("/");
}

function setupEvents() {
  document.addEventListener("click", (event) => {
    const playButton = event.target.closest("[data-play]");
    if (playButton) {
      event.preventDefault();
      const itemId = Number(playButton.dataset.play);
      const queue = collectQueue();
      const item = itemCache.get(itemId);
      if (item) {
        playTrack(item, queue);
      } else {
        api.get(`/api/items/${itemId}`).then((data) => {
          cacheItem(data.item);
          playTrack(data.item, queue);
        }).catch((error) => toast(error.message, "error"));
      }
      return;
    }

    const likeButton = event.target.closest("[data-like]");
    if (likeButton) {
      event.preventDefault();
      handleLike(Number(likeButton.dataset.like));
      return;
    }

    const downloadButton = event.target.closest("[data-download]");
    if (downloadButton) {
      event.preventDefault();
      handleDownload(Number(downloadButton.dataset.download));
      return;
    }

    if (event.target.closest("[data-user-toggle]")) {
      const dropdown = document.querySelector("[data-user-dropdown]");
      dropdown?.classList.toggle("hidden");
      return;
    }

    if (!event.target.closest("[data-user-menu]")) {
      closeUserDropdown();
    }

    if (event.target.closest("[data-menu-toggle]")) {
      document.getElementById("mobile-nav")?.classList.toggle("is-open");
      return;
    }

    if (event.target.closest("[data-logout]")) {
      handleLogout();
      return;
    }

    if (event.target.closest("[data-modal-close]")) {
      closeModal();
      return;
    }

    if (event.target.closest("#mobile-nav a")) {
      closeMobileMenu();
    }
  });

  header?.addEventListener("submit", (event) => {
    const form = event.target.closest("[data-header-search]");
    if (!form) return;
    event.preventDefault();
    const query = String(new FormData(form).get("q") || "").trim();
    closeMobileMenu();
    navigate(query ? `/catalog?q=${encodeURIComponent(query)}` : "/catalog");
  });

  document.addEventListener("player:change", (event) => {
    const { id, playing } = event.detail || {};
    document.querySelectorAll("[data-play]").forEach((button) => {
      const isActive = Number(button.dataset.play) === Number(id) && playing;
      button.classList.toggle("is-playing", isActive);
      if (button.hasAttribute("data-play-label")) {
        button.innerHTML = isActive
          ? `${icon("pause")}<span>Пауза</span>`
          : `${icon("play")}<span>Слушать</span>`;
      } else {
        button.innerHTML = icon(isActive ? "pause" : "play");
      }
    });
  });

  document.addEventListener("auth:change", () => {
    const { path, params } = parseLocation();
    renderHeader(path, params);
  });

  window.addEventListener("scroll", () => {
    header?.classList.toggle("is-scrolled", window.scrollY > 8);
  }, { passive: true });

  window.addEventListener("hashchange", renderCurrent);
  document.addEventListener("route:refresh", renderCurrent);
}

async function init() {
  renderFooter();
  initPlayer();
  renderHeader();
  setupEvents();

  try {
    const [me, stats] = await Promise.all([api.get("/api/me"), api.get("/api/stats")]);
    state.user = me.user;
    state.stats = stats;
  } catch (error) {
    console.warn("Не удалось загрузить состояние:", error);
  }

  if (!window.location.hash) {
    history.replaceState(null, "", "#/");
  }
  const { path, params } = parseLocation();
  renderHeader(path, params);
  await renderCurrent();
}

init();
