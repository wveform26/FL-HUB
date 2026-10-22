import { icon } from "./icons.js";
import {
  CATEGORIES,
  categoryMeta,
  escapeAttr,
  escapeHtml,
  fileFormat,
  formatCount,
  formatDuration,
  initials,
  timeAgo,
} from "./utils.js";

export function avatarHtml(user, size = "") {
  const username = user?.username || "?";
  const color = user?.avatar_color || "#ff7a1a";
  return `<span class="avatar ${size}" style="--avatar:${escapeAttr(color)}" aria-hidden="true">${escapeHtml(initials(username))}</span>`;
}

export function categoryBadge(category, className = "") {
  const meta = categoryMeta(category);
  return `<span class="badge ${className}" data-category="${escapeAttr(category)}">${icon(meta.icon)}${escapeHtml(meta.label)}</span>`;
}

export function itemCard(item) {
  const meta = categoryMeta(item.category);
  const isMusic = item.category === "music";
  const hasAudio = Boolean(item.audio_url);
  const format = fileFormat(item);
  const metaParts = [];
  if (item.genre) metaParts.push(item.genre);
  if (item.bpm) metaParts.push(`${item.bpm} BPM`);
  if (!metaParts.length && item.key) metaParts.push(item.key);

  const action = isMusic && hasAudio
    ? `<button class="card-play" data-play="${item.id}" aria-label="Слушать ${escapeAttr(item.title)}">${icon("play")}</button>`
    : `<button class="card-play" data-download="${item.id}" aria-label="Скачать ${escapeAttr(item.title)}">${icon("download")}</button>`;

  return `
    <article class="item-card" data-item-id="${item.id}">
      <div class="card-cover">
        <a class="cover-link" href="#/item/${item.id}" aria-label="Открыть ${escapeAttr(item.title)}"></a>
        <img src="${escapeAttr(item.cover_url)}" alt="Обложка ${escapeAttr(item.title)}" loading="lazy" decoding="async">
        ${categoryBadge(item.category, "card-badge")}
        <span class="card-format">${escapeHtml(format)}</span>
        ${action}
        ${isMusic && item.duration ? `<span class="card-duration">${formatDuration(item.duration)}</span>` : ""}
      </div>
      <div class="card-body">
        <div class="card-title-row">
          <h3 class="card-title"><a href="#/item/${item.id}">${escapeHtml(item.title)}</a></h3>
          <button class="like-btn ${item.liked ? "is-liked" : ""}" data-like="${item.id}"
                  data-liked="${item.liked ? 1 : 0}" data-count="${item.likes}"
                  aria-pressed="${item.liked ? "true" : "false"}" aria-label="Нравится">
            ${icon("heart")}<span class="like-count">${formatCount(item.likes)}</span>
          </button>
        </div>
        <a class="card-author" href="#/profile/${encodeURIComponent(item.author.username)}">
          ${avatarHtml(item.author, "avatar-xs")}<span>@${escapeHtml(item.author.username)}</span>
        </a>
        <div class="card-meta">
          ${metaParts.map((part, index) => `${index ? '<span class="dot"></span>' : ""}<span>${escapeHtml(part)}</span>`).join("")}
        </div>
        <div class="card-foot">
          <div class="stats">
            <span class="stat">${icon("download")} ${formatCount(item.downloads)}</span>
            ${isMusic ? `<span class="stat" data-plays="${item.id}">${icon("headphones")} ${formatCount(item.plays)}</span>` : `<span class="stat">${icon("message")} ${formatCount(item.comments)}</span>`}
          </div>
          <span>${timeAgo(item.created_at)}</span>
        </div>
      </div>
    </article>
  `;
}

export function itemGrid(items) {
  return `<div class="item-grid">${items.map(itemCard).join("")}</div>`;
}

export function skeletonGrid(count = 8) {
  return `<div class="item-grid">${Array.from({ length: count }, () => `
    <div class="skeleton-card">
      <div class="skeleton skeleton-cover"></div>
      <div class="skeleton skeleton-line"></div>
      <div class="skeleton skeleton-line w-70"></div>
      <div class="skeleton skeleton-line w-45"></div>
    </div>
  `).join("")}</div>`;
}

export function producerCard(author) {
  const meta = `${author.item_count} ${pluralWorks(author.item_count)} · ${formatCount(author.downloads)} скачиваний`;
  return `
    <a class="producer-card" href="#/profile/${encodeURIComponent(author.username)}">
      ${avatarHtml(author, "avatar-sm")}
      <div class="producer-info">
        <div class="producer-name">@${escapeHtml(author.username)}</div>
        <div class="producer-meta">${escapeHtml(meta)}</div>
      </div>
      <span class="producer-badge">${icon("arrow-up-right")}</span>
    </a>
  `;
}

function pluralWorks(count) {
  const number = Number(count) || 0;
  const mod10 = number % 10;
  const mod100 = number % 100;
  if (mod10 === 1 && mod100 !== 11) return "работа";
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return "работы";
  return "работ";
}

export function categoryTile(key, count) {
  const meta = CATEGORIES[key];
  if (!meta) return "";
  return `
    <a class="category-tile" href="#/catalog?category=${key}" style="--cat:${meta.color}">
      <span class="category-icon">${icon(meta.icon)}</span>
      <span class="category-info">
        <span>
          <span class="category-name">${escapeHtml(meta.label)}</span>
          <span class="category-count">${count} ${pluralWorks(count)}</span>
        </span>
        <span class="category-arrow">${icon("arrow-up-right")}</span>
      </span>
    </a>
  `;
}

export function commentHtml(comment) {
  return `
    <div class="comment" data-comment-id="${comment.id}">
      ${avatarHtml(comment.author, "avatar-sm")}
      <div class="comment-body-wrap">
        <div class="comment-head">
          <a class="comment-author" href="#/profile/${encodeURIComponent(comment.author.username)}">@${escapeHtml(comment.author.username)}</a>
          <span class="comment-time">${timeAgo(comment.created_at)}</span>
        </div>
        <div class="comment-text">${escapeHtml(comment.body)}</div>
      </div>
    </div>
  `;
}

export function formatCategoryName(category) {
  return categoryMeta(category).label;
}
