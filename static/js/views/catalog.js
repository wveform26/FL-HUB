import { api } from "../api.js";
import { itemCard, itemGrid, skeletonGrid } from "../components.js";
import { icon } from "../icons.js";
import { cacheItems, state } from "../store.js";
import { emptyState, toast } from "../ui.js";
import {
  CATEGORY_KEYS,
  GENRES,
  buildCatalogUrl,
  categoryMeta,
  escapeAttr,
  escapeHtml,
  formatCount,
} from "../utils.js";

const PAGE_LIMIT = 24;

const SORT_OPTIONS = [
  { value: "new", label: "Сначала новые" },
  { value: "popular", label: "Популярные" },
  { value: "downloads", label: "Больше скачиваний" },
];

export async function renderCatalog(main, ctx) {
  const category = ctx.params.get("category") || "";
  const q = ctx.params.get("q") || "";
  const genre = ctx.params.get("genre") || "";
  const sort = ctx.params.get("sort") || "new";

  main.innerHTML = `<div class="container">${skeletonCatalog()}</div>`;

  const apiParams = new URLSearchParams({ limit: String(PAGE_LIMIT), offset: "0", sort });
  if (category) apiParams.set("category", category);
  if (q) apiParams.set("q", q);
  if (genre) apiParams.set("genre", genre);

  let data;
  let stats;
  try {
    [data, stats] = await Promise.all([
      api.get(`/api/items?${apiParams.toString()}`),
      state.stats ? Promise.resolve(state.stats) : api.get("/api/stats"),
    ]);
  } catch (error) {
    main.innerHTML = `<div class="container">${emptyState({
      iconName: "alert",
      title: "Не удалось загрузить каталог",
      text: error.message,
      action: `<a class="btn btn-primary" href="#/catalog">Сбросить фильтры</a>`,
    })}</div>`;
    return;
  }

  state.stats = stats;
  const items = data.items || [];
  const total = data.total || 0;
  cacheItems(items);

  const activeMeta = category ? categoryMeta(category) : null;
  const pageTitle = activeMeta ? activeMeta.label : "Каталог звуков";
  const pageSub = activeMeta
    ? categorySubtitle(category)
    : "Треки, проекты, инструменты, плагины и драм-киты — всё, чем делятся продюсеры FL Studio.";
  document.title = `${pageTitle} — FL HUB`;

  const counts = stats.categories || {};
  const allCount = Object.values(counts).reduce((sum, value) => sum + Number(value || 0), 0);
  const tabs = [
    `<a class="filter-tab ${!category ? "is-active" : ""}" href="#${buildCatalogUrl({ q, genre, sort })}">Все <span class="count">${allCount}</span></a>`,
    ...CATEGORY_KEYS.map((key) => `
      <a class="filter-tab ${category === key ? "is-active" : ""}" href="#${buildCatalogUrl({ category: key, q, genre, sort })}">
        ${escapeHtml(categoryMeta(key).label)} <span class="count">${counts[key] || 0}</span>
      </a>
    `),
  ].join("");

  const genreOptions = GENRES.map((name) => `<option value="${escapeAttr(name)}" ${genre === name ? "selected" : ""}>${escapeHtml(name)}</option>`).join("");
  const sortOptions = SORT_OPTIONS.map((option) => `<option value="${option.value}" ${sort === option.value ? "selected" : ""}>${option.label}</option>`).join("");

  main.innerHTML = `
    <div class="container">
      <header class="page-head">
        <h1 class="page-title">${escapeHtml(pageTitle)}</h1>
        <p class="page-sub">${escapeHtml(pageSub)}</p>
      </header>

      <div class="catalog-filters">
        <div class="filter-tabs">${tabs}</div>
        <form class="filter-row" data-catalog-form>
          <div class="search-field">
            ${icon("search")}
            <input type="search" name="q" value="${escapeAttr(q)}" placeholder="Найти трек, пак или автора" autocomplete="off">
          </div>
          <select class="select" name="genre" aria-label="Жанр">
            <option value="">Все жанры</option>
            ${genreOptions}
          </select>
          <select class="select" name="sort" aria-label="Сортировка">
            ${sortOptions}
          </select>
        </form>
      </div>

      <div class="results-line">
        <span>${q ? `Поиск «${escapeHtml(q)}» · ` : ""}<strong>${formatCount(total)}</strong> ${pluralWorks(total)}</span>
        ${category || genre || q || sort !== "new" ? `<a class="section-link" href="#/catalog">Сбросить фильтры ${icon("close")}</a>` : ""}
      </div>

      <div data-results>
        ${items.length ? itemGrid(items) : emptyState({
          iconName: "search",
          title: "Ничего не найдено",
          text: "Попробуйте изменить запрос или сбросить фильтры.",
          action: `<a class="btn btn-ghost" href="#/catalog">Сбросить фильтры</a>`,
        })}
      </div>
      <div class="load-more-wrap">
        ${items.length < total ? `<button class="btn btn-ghost" data-load-more>Показать ещё</button>` : ""}
      </div>
    </div>
  `;

  const form = main.querySelector("[data-catalog-form]");
  const applyFilters = () => {
    const formData = new FormData(form);
    const nextQ = String(formData.get("q") || "").trim();
    const nextGenre = String(formData.get("genre") || "");
    const nextSort = String(formData.get("sort") || "new");
    window.location.hash = `#${buildCatalogUrl({ category, q: nextQ, genre: nextGenre, sort: nextSort })}`;
  };
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    applyFilters();
  });
  form.querySelectorAll("select").forEach((select) => select.addEventListener("change", applyFilters));

  const loadMore = main.querySelector("[data-load-more]");
  if (loadMore) {
    loadMore.addEventListener("click", async () => {
      loadMore.disabled = true;
      loadMore.textContent = "Загружаем...";
      const nextParams = new URLSearchParams(apiParams);
      nextParams.set("offset", String(items.length));
      try {
        const next = await api.get(`/api/items?${nextParams.toString()}`);
        const nextItems = next.items || [];
        cacheItems(nextItems);
        const grid = main.querySelector(".item-grid");
        if (grid) grid.insertAdjacentHTML("beforeend", nextItems.map(itemCard).join(""));
        items.push(...nextItems);
        if (items.length >= (next.total || total)) {
          loadMore.remove();
        } else {
          loadMore.disabled = false;
          loadMore.textContent = "Показать ещё";
        }
      } catch (error) {
        toast(error.message, "error");
        loadMore.disabled = false;
        loadMore.textContent = "Показать ещё";
      }
    });
  }
}

function categorySubtitle(category) {
  switch (category) {
    case "music": return "Треки продюсеров сообщества: от тёмного трэпа до лёгкого lo-fi. Слушай, сохраняй, находи референсы.";
    case "project": return "Каркасы проектов, stems и MIDI — чтобы быстрее добраться до идеи и разобрать чужой грув.";
    case "instrument": return "Банки и пресеты для твоих инструментов. Скачивай, подключай и играй.";
    case "plugin": return "Плагины и утилиты для микса, обработки и вдохновения.";
    case "drumkit": return "Драм-киты, one-shot'ы и брейки для твоего следующего бита.";
    default: return "";
  }
}

function pluralWorks(count) {
  const number = Number(count) || 0;
  const mod10 = number % 10;
  const mod100 = number % 100;
  if (mod10 === 1 && mod100 !== 11) return "работа";
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return "работы";
  return "работ";
}

function skeletonCatalog() {
  return `
    <header class="page-head">
      <div class="skeleton" style="width:280px;height:44px"></div>
      <div class="skeleton" style="width:460px;max-width:100%;height:16px;margin-top:14px"></div>
    </header>
    <div class="skeleton" style="width:100%;height:130px;border-radius:16px;margin-bottom:28px"></div>
    ${skeletonGrid(8)}
  `;
}
