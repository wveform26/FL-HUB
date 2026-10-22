import { api } from "../api.js";
import {
  avatarHtml,
  categoryBadge,
  categoryTile,
  itemGrid,
  producerCard,
  skeletonGrid,
} from "../components.js";
import { icon } from "../icons.js";
import { cacheItems, state } from "../store.js";
import { emptyState } from "../ui.js";
import {
  CATEGORY_KEYS,
  escapeAttr,
  escapeHtml,
  formatCount,
  formatDuration,
} from "../utils.js";

export async function renderHome(main) {
  main.innerHTML = `<div class="container">${skeletonHome()}</div>`;
  const [stats, featuredData, popularData, freshData, authorsData] = await Promise.all([
    state.stats ? Promise.resolve(state.stats) : api.get("/api/stats"),
    api.get("/api/items?featured=1&limit=1"),
    api.get("/api/items?category=music&sort=popular&limit=1"),
    api.get("/api/items?sort=new&limit=8"),
    api.get("/api/authors?limit=4"),
  ]);
  state.stats = stats;

  const fresh = freshData.items || [];
  const featured =
    (featuredData.items || [])[0] ||
    (popularData.items || [])[0] ||
    fresh[0] ||
    null;
  const authors = authorsData.authors || [];
  cacheItems([...fresh, ...(popularData.items || []), ...(featured ? [featured] : [])]);

  const categories = CATEGORY_KEYS.map((key) => categoryTile(key, stats.categories?.[key] || 0)).join("");

  main.innerHTML = `
    <div class="container">
      <section class="hero">
        <div class="hero-copy">
          <span class="eyebrow"><span class="dot">${icon("wave")}</span> Сообщество продюсеров FL Studio</span>
          <h1 class="hero-title">Здесь живёт<br><span class="grad-text">твой звук</span></h1>
          <p class="hero-sub">
            Делись треками, проектами, инструментами, плагинами и драм-китами.
            Находи новые сэмплы, вдохновение и людей, с которыми хочется делать музыку.
          </p>
          <div class="hero-actions">
            <a class="btn btn-primary" href="#/catalog">${icon("headphones")} Слушать каталог</a>
            <a class="btn btn-ghost" href="#/upload">${icon("upload")} Загрузить работу</a>
          </div>
          <div class="hero-stats">
            <div class="hero-stat"><strong>${formatCount(stats.users)}</strong><span>продюсеров</span></div>
            <div class="hero-stat"><strong>${formatCount(stats.items)}</strong><span>работ в каталоге</span></div>
            <div class="hero-stat"><strong>${formatCount(stats.downloads)}</strong><span>скачиваний</span></div>
          </div>
        </div>
        ${featured ? featuredCard(featured) : `<div class="featured-wrap">${emptyState({
          iconName: "music",
          title: "Каталог пока пуст",
          text: "Стань первым, кто поделится звуком с сообществом.",
          action: `<a class="btn btn-primary" href="#/upload">Загрузить работу</a>`,
        })}</div>`}
      </section>

      <section class="category-strip">${categories}</section>

      <section class="section">
        <div class="section-head">
          <div>
            <h2 class="section-title">Свежее в сообществе</h2>
            <p class="section-sub">Новые треки и паки от продюсеров</p>
          </div>
          <a class="section-link" href="#/catalog">Весь каталог ${icon("arrow-right")}</a>
        </div>
        ${fresh.length ? itemGrid(fresh) : emptyState({
          iconName: "sparkles",
          title: "Пока тихо",
          text: "Загрузи первую работу — и здесь появится твой звук.",
          action: `<a class="btn btn-primary" href="#/upload">Загрузить работу</a>`,
        })}
      </section>

      ${authors.length ? `
      <section class="section">
        <div class="section-head">
          <div>
            <h2 class="section-title">Продюсеры сообщества</h2>
            <p class="section-sub">Те, кто громче всех делится звуком</p>
          </div>
          <a class="section-link" href="#/catalog">Смотреть работы ${icon("arrow-right")}</a>
        </div>
        <div class="producers-grid">${authors.map(producerCard).join("")}</div>
      </section>` : ""}

      <section class="cta-banner">
        <div>
          <h2 class="cta-title">Твой звук заслуживает быть услышанным</h2>
          <p class="cta-text">Загрузи трек, проект или пак — и найди своих слушателей, коллабораторов и единомышленников.</p>
        </div>
        <a class="btn btn-primary" href="#/upload">${icon("upload")} Поделиться работой</a>
      </section>
    </div>
  `;
}

function featuredCard(item) {
  const metaParts = [item.genre, item.bpm ? `${item.bpm} BPM` : ""].filter(Boolean);
  return `
    <div class="featured-wrap">
      <article class="featured-card">
        <img src="${escapeAttr(item.cover_url)}" alt="Обложка ${escapeAttr(item.title)}" fetchpriority="high">
        <div class="featured-overlay"></div>
        <div class="featured-top">
          ${categoryBadge(item.category)}
          <span class="badge">${icon("flame")} ${formatCount(item.likes)}</span>
        </div>
        <button class="featured-play" data-play="${item.id}" aria-label="Слушать ${escapeAttr(item.title)}">${icon("play")}</button>
        <div class="featured-body">
          <div class="featured-kicker">${icon("flame")} ${item.featured ? "Выбор редакции" : "Тренд недели"}</div>
          <a href="#/item/${item.id}"><h2 class="featured-title">${escapeHtml(item.title)}</h2></a>
          <a class="featured-author" href="#/profile/${encodeURIComponent(item.author.username)}">
            ${avatarHtml(item.author, "avatar-xs")} <span>@${escapeHtml(item.author.username)}</span>
          </a>
          <div class="featured-meta">
            ${metaParts.map((part, index) => `${index ? '<span class="dot"></span>' : ""}<span>${escapeHtml(part)}</span>`).join("")}
            ${item.duration ? `<span class="dot"></span><span>${formatDuration(item.duration)}</span>` : ""}
            <span class="spacer"></span>
            <span class="stat" data-plays="${item.id}">${icon("headphones")} ${formatCount(item.plays)}</span>
            <span class="stat">${icon("download")} ${formatCount(item.downloads)}</span>
          </div>
        </div>
      </article>
    </div>
  `;
}

function skeletonHome() {
  return `
    <section class="hero">
      <div class="hero-copy">
        <div class="skeleton" style="width:230px;height:30px;border-radius:99px"></div>
        <div class="skeleton" style="width:80%;height:64px;margin-top:24px"></div>
        <div class="skeleton" style="width:60%;height:64px;margin-top:10px"></div>
        <div class="skeleton" style="width:90%;height:16px;margin-top:26px"></div>
        <div class="skeleton" style="width:70%;height:16px;margin-top:10px"></div>
      </div>
      <div class="featured-wrap"><div class="skeleton" style="width:100%;aspect-ratio:.86;border-radius:26px"></div></div>
    </section>
    <div class="skeleton" style="width:100%;height:100px;border-radius:16px;margin-bottom:58px"></div>
    ${skeletonGrid(4)}
  `;
}
