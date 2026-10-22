import { api } from "../api.js";
import {
  avatarHtml,
  categoryBadge,
  commentHtml,
  itemGrid,
} from "../components.js";
import { icon } from "../icons.js";
import { cacheItem, cacheItems, navigate, state } from "../store.js";
import { closeModal, emptyState, openModal, toast } from "../ui.js";
import {
  categoryMeta,
  escapeAttr,
  escapeHtml,
  fileFormat,
  formatBytes,
  formatCount,
  formatDate,
  formatDuration,
  timeAgo,
} from "../utils.js";

export async function renderItem(main, ctx) {
  const itemId = Number(ctx.id);
  main.innerHTML = `<div class="container"><div class="loading-block"><span class="spinner"></span><span>Загружаем работу...</span></div></div>`;

  let item;
  try {
    const data = await api.get(`/api/items/${itemId}`);
    item = data.item;
  } catch (error) {
    main.innerHTML = `<div class="container" style="padding-top:50px">${emptyState({
      iconName: "alert",
      title: error.status === 404 ? "Работа не найдена" : "Не удалось загрузить работу",
      text: error.status === 404 ? "Возможно, её удалили или ссылка неверна." : error.message,
      action: `<a class="btn btn-primary" href="#/catalog">Вернуться в каталог</a>`,
    })}</div>`;
    return;
  }

  cacheItem(item);
  document.title = `${item.title} — FL HUB`;

  let comments = [];
  let related = [];
  try {
    const [commentsData, relatedData] = await Promise.all([
      api.get(`/api/items/${itemId}/comments`),
      api.get(`/api/items?category=${encodeURIComponent(item.category)}&sort=popular&limit=5`),
    ]);
    comments = commentsData.comments || [];
    related = (relatedData.items || []).filter((entry) => entry.id !== item.id).slice(0, 4);
    cacheItems(related);
  } catch {
    comments = [];
    related = [];
  }

  const meta = categoryMeta(item.category);
  const isMusic = item.category === "music";
  const isOwner = item.is_owner || state.user?.username === item.author.username;
  const metaItems = [
    ["Жанр", item.genre || "—"],
    ["BPM", item.bpm || "—"],
    ["Тональность", item.key || "—"],
    ["Формат", fileFormat(item)],
    ["Размер", formatBytes(item.file_size)],
    ["Опубликовано", formatDate(item.created_at)],
  ];

  main.innerHTML = `
    <div class="container">
      <nav class="breadcrumbs" aria-label="Навигация">
        <a href="#/catalog">Каталог</a>
        ${icon("arrow-right")}
        <a href="#/catalog?category=${item.category}">${escapeHtml(meta.label)}</a>
        ${icon("arrow-right")}
        <span class="current">${escapeHtml(item.title)}</span>
      </nav>

      <article class="item-layout">
        <div class="item-visual">
          <div class="item-cover">
            <img src="${escapeAttr(item.cover_url)}" alt="Обложка ${escapeAttr(item.title)}">
            ${categoryBadge(item.category)}
            ${isMusic && item.duration ? `<span class="card-duration">${formatDuration(item.duration)}</span>` : ""}
          </div>
          <div class="item-actions">
            ${item.audio_url
              ? `<button class="play-big" data-play="${item.id}" data-play-label>${icon("play")}<span>Слушать</span></button>`
              : `<a class="play-big" href="/download/${item.id}" data-download="${item.id}">${icon("download")}<span>Скачать</span></a>`}
            <button class="icon-btn ${item.liked ? "is-liked" : ""}" data-like="${item.id}"
                    data-liked="${item.liked ? 1 : 0}" data-count="${item.likes}"
                    aria-pressed="${item.liked ? "true" : "false"}" aria-label="Нравится">
              ${icon("heart")}
            </button>
            <a class="icon-btn" href="/download/${item.id}" data-download="${item.id}" aria-label="Скачать файл">
              ${icon("download")}
            </a>
          </div>
          <div class="item-statline">
            ${isMusic ? `<span class="stat" data-plays="${item.id}">${icon("headphones")} ${formatCount(item.plays)}</span>` : ""}
            <span class="stat">${icon("download")} ${formatCount(item.downloads)}</span>
            <span class="stat" data-like-stat="${item.id}">${icon("heart")} ${formatCount(item.likes)}</span>
            <span class="stat" data-comments-stat="${item.id}">${icon("message")} ${formatCount(item.comments)}</span>
          </div>
          ${isOwner ? `
            <div class="owner-actions">
              <button type="button" data-delete-item="${item.id}">${icon("trash")} Удалить работу</button>
            </div>
          ` : ""}
        </div>

        <div class="item-info">
          <div class="item-category">
            <span class="cat-label" style="color:${meta.color}">${icon(meta.icon)} ${escapeHtml(meta.label)}</span>
            <span class="pill"><span class="dot"></span> ${timeAgo(item.created_at)}</span>
          </div>
          <h1 class="item-title">${escapeHtml(item.title)}</h1>
          <a class="item-author" href="#/profile/${encodeURIComponent(item.author.username)}">
            ${avatarHtml(item.author)}
            <span>
              <span class="author-name">@${escapeHtml(item.author.username)}</span>
              <span class="author-date">Автор работы</span>
            </span>
          </a>
          <p class="item-desc">${item.description ? escapeHtml(item.description) : "Автор пока не добавил описание."}</p>

          <div class="meta-grid">
            ${metaItems.map(([label, value]) => `
              <div class="meta-item">
                <div class="meta-label">${escapeHtml(label)}</div>
                <div class="meta-value">${escapeHtml(String(value))}</div>
              </div>
            `).join("")}
          </div>

          ${item.tags.length ? `
            <div class="tags">
              ${item.tags.map((tag) => `<a class="tag" href="#/catalog?q=${encodeURIComponent(tag)}">#${escapeHtml(tag)}</a>`).join("")}
            </div>
          ` : ""}

          <section class="comments-section">
            <div class="comments-head">
              <h2 class="comments-title">Комментарии <span class="comments-count" data-comments-count>${comments.length}</span></h2>
            </div>
            ${state.user ? `
              <form class="comment-form" data-comment-form>
                ${avatarHtml(state.user, "avatar-sm")}
                <div class="comment-input-wrap">
                  <textarea name="body" maxlength="1000" placeholder="Поделись впечатлением..." required></textarea>
                  <div class="comment-form-foot">
                    <span class="hint">Будь вежлив — здесь собираются свои.</span>
                    <button class="btn btn-primary btn-sm" type="submit">Отправить</button>
                  </div>
                </div>
              </form>
            ` : `
              <div class="comment-login">
                <span>Войди, чтобы оставить комментарий и поддерживать авторов.</span>
                <a class="btn btn-ghost btn-sm" href="#/login?next=${encodeURIComponent(`/item/${item.id}`)}">Войти</a>
              </div>
            `}
            <div class="comment-list" data-comment-list>
              ${comments.map(commentHtml).join("")}
            </div>
            ${comments.length ? "" : `<div class="comments-empty" data-comments-empty>Пока нет комментариев. Скажи первое слово.</div>`}
          </section>
        </div>
      </article>

      ${related.length ? `
        <section class="related">
          <div class="section-head">
            <div>
              <h2 class="section-title">Ещё в разделе «${escapeHtml(meta.label)}»</h2>
              <p class="section-sub">Похожие работы сообщества</p>
            </div>
            <a class="section-link" href="#/catalog?category=${item.category}">Смотреть всё ${icon("arrow-right")}</a>
          </div>
          ${itemGrid(related)}
        </section>
      ` : ""}
    </div>
  `;

  const commentForm = main.querySelector("[data-comment-form]");
  if (commentForm) {
    commentForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const textarea = commentForm.querySelector("textarea");
      const button = commentForm.querySelector("button[type='submit']");
      const body = textarea.value.trim();
      if (!body) return;
      button.disabled = true;
      button.textContent = "Отправляем...";
      try {
        const data = await api.post(`/api/items/${item.id}/comments`, { body });
        const list = main.querySelector("[data-comment-list]");
        list.insertAdjacentHTML("beforeend", commentHtml(data.comment));
        const empty = main.querySelector("[data-comments-empty]");
        if (empty) empty.remove();
        textarea.value = "";
        item.comments += 1;
        cacheItem(item);
        updateCommentCounters(main, item.id, item.comments);
        toast("Комментарий опубликован", "success");
      } catch (error) {
        toast(error.message, "error");
      } finally {
        button.disabled = false;
        button.textContent = "Отправить";
      }
    });
  }

  const deleteButton = main.querySelector("[data-delete-item]");
  if (deleteButton) {
    deleteButton.addEventListener("click", () => {
      openModal(`
        <div class="modal-head">
          <h3 class="modal-title">Удалить работу?</h3>
          <button class="modal-close" type="button" data-modal-close aria-label="Закрыть">${icon("close")}</button>
        </div>
        <p class="muted" style="font-size:13px;line-height:1.6">
          «${escapeHtml(item.title)}» исчезнет из каталога вместе с комментариями и лайками. Файл будет удалён с сервера.
        </p>
        <div class="modal-actions">
          <button class="btn btn-ghost" type="button" data-modal-close>Отмена</button>
          <button class="btn btn-danger" type="button" data-confirm-delete>Удалить</button>
        </div>
      `);
      const confirm = document.querySelector("[data-confirm-delete]");
      confirm?.addEventListener("click", async () => {
        confirm.disabled = true;
        confirm.textContent = "Удаляем...";
        try {
          await api.delete(`/api/items/${item.id}`);
          if (state.stats) {
            state.stats.items = Math.max(0, (state.stats.items || 0) - 1);
            if (state.stats.categories) {
              const category = item.category;
              state.stats.categories[category] = Math.max(
                0,
                (state.stats.categories[category] || 0) - 1
              );
            }
          }
          closeModal();
          toast("Работа удалена", "success");
          navigate("/catalog");
        } catch (error) {
          toast(error.message, "error");
          confirm.disabled = false;
          confirm.textContent = "Удалить";
        }
      });
    });
  }
}

function updateCommentCounters(main, itemId, count) {
  main.querySelectorAll("[data-comments-count]").forEach((node) => {
    node.textContent = String(count);
  });
  const stat = main.querySelector(`[data-comments-stat="${itemId}"]`);
  if (stat) stat.innerHTML = `${icon("message")} ${formatCount(count)}`;
}
