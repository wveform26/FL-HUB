import { api } from "../api.js";
import { avatarHtml, itemGrid } from "../components.js";
import { icon } from "../icons.js";
import { cacheItems, navigate, setUser, state } from "../store.js";
import { closeModal, emptyState, openModal, toast } from "../ui.js";
import {
  escapeAttr,
  escapeHtml,
  formatCount,
  formatDate,
  initials,
} from "../utils.js";

const AVATAR_COLORS = [
  "#ff7a1a", "#ff5c8a", "#b794f6", "#7dd3fc", "#4fd1c5",
  "#ffd166", "#a3e635", "#f97316", "#f472b6", "#60a5fa",
];

export async function renderProfile(main, ctx) {
  const username = ctx.username;
  main.innerHTML = `<div class="container"><div class="loading-block"><span class="spinner"></span><span>Загружаем профиль...</span></div></div>`;

  let profile;
  let items = [];
  try {
    const [profileData, itemsData] = await Promise.all([
      api.get(`/api/users/${encodeURIComponent(username)}`),
      api.get(`/api/items?author=${encodeURIComponent(username)}&sort=new&limit=48`),
    ]);
    profile = profileData.user;
    items = itemsData.items || [];
  } catch (error) {
    main.innerHTML = `<div class="container" style="padding-top:50px">${emptyState({
      iconName: "user",
      title: error.status === 404 ? "Пользователь не найден" : "Не удалось загрузить профиль",
      text: error.status === 404 ? "Проверь имя пользователя в ссылке." : error.message,
      action: `<a class="btn btn-primary" href="#/catalog">В каталог</a>`,
    })}</div>`;
    return;
  }

  cacheItems(items);
  const isMe = Boolean(profile.is_me || state.user?.username?.toLowerCase() === profile.username.toLowerCase());
  document.title = `@${profile.username} — FL HUB`;

  main.innerHTML = `
    <div class="container profile-page">
      <div class="profile-banner" style="--user-color:${escapeAttr(profile.avatar_color)}"></div>

      <div class="profile-head">
        <div class="profile-avatar" style="--user-color:${escapeAttr(profile.avatar_color)}">${escapeHtml(initials(profile.username))}</div>
        <div class="profile-head-info">
          <h1 class="profile-name">@${escapeHtml(profile.username)}</h1>
          <div class="profile-joined">В сообществе с ${formatDate(profile.created_at)}</div>
        </div>
        <div class="profile-head-actions">
          ${isMe ? `
            <button class="btn btn-ghost btn-sm" type="button" data-edit-profile>${icon("edit")}<span>Редактировать</span></button>
            <a class="btn btn-primary btn-sm" href="#/upload">${icon("upload")}<span>Загрузить</span></a>
          ` : ""}
        </div>
      </div>

      <div class="profile-body">
        <p class="profile-bio">${profile.bio ? escapeHtml(profile.bio) : "Продюсер пока не рассказал о себе."}</p>
        <div class="profile-stats">
          <div class="profile-stat"><strong>${formatCount(profile.stats.items)}</strong><span>работ</span></div>
          <div class="profile-stat"><strong>${formatCount(profile.stats.likes)}</strong><span>лайков получено</span></div>
          <div class="profile-stat"><strong>${formatCount(profile.stats.downloads)}</strong><span>скачиваний</span></div>
          <div class="profile-stat"><strong>${formatCount(profile.stats.plays)}</strong><span>прослушиваний</span></div>
        </div>

        <section class="profile-works">
          <div class="section-head">
            <div>
              <h2 class="section-title">Работы</h2>
              <p class="section-sub">${items.length ? `${items.length} ${pluralWorks(items.length)} в каталоге` : "Здесь появятся публикации"}</p>
            </div>
          </div>
          ${items.length ? itemGrid(items) : emptyState({
            iconName: "music",
            title: isMe ? "У тебя пока нет работ" : "Пока нет работ",
            text: isMe ? "Загрузи первый трек или пак — профиль оживёт." : "Загляни позже или посмотри другие работы сообщества.",
            action: isMe
              ? `<a class="btn btn-primary" href="#/upload">Загрузить работу</a>`
              : `<a class="btn btn-ghost" href="#/catalog">Смотреть каталог</a>`,
          })}
        </section>
      </div>
    </div>
  `;

  const editButton = main.querySelector("[data-edit-profile]");
  if (editButton) {
    editButton.addEventListener("click", () => {
      let selectedColor = profile.avatar_color;
      const swatches = AVATAR_COLORS.map((color) => `
        <button class="swatch ${color.toLowerCase() === selectedColor.toLowerCase() ? "is-active" : ""}"
                type="button" style="--swatch:${color}" data-swatch="${color}" aria-label="Цвет ${color}"></button>
      `).join("");
      openModal(`
        <div class="modal-head">
          <h3 class="modal-title">Редактировать профиль</h3>
          <button class="modal-close" type="button" data-modal-close aria-label="Закрыть">${icon("close")}</button>
        </div>
        <form data-profile-form>
          <div class="field">
            <label class="label" for="profile-bio">О себе</label>
            <textarea class="textarea" id="profile-bio" name="bio" maxlength="280"
                      placeholder="Чем занимаешься, что любишь делать в FL Studio...">${escapeHtml(profile.bio)}</textarea>
            <span class="hint">До 280 символов</span>
          </div>
          <div class="field" style="margin-top:18px">
            <span class="label">Цвет аватара</span>
            <div class="color-swatches">${swatches}</div>
          </div>
          <div class="form-error" data-profile-error></div>
          <div class="modal-actions">
            <button class="btn btn-ghost" type="button" data-modal-close>Отмена</button>
            <button class="btn btn-primary" type="submit" data-profile-save>Сохранить</button>
          </div>
        </form>
      `);
      document.querySelectorAll("[data-swatch]").forEach((swatch) => {
        swatch.addEventListener("click", () => {
          selectedColor = swatch.dataset.swatch;
          document.querySelectorAll("[data-swatch]").forEach((node) => {
            node.classList.toggle("is-active", node === swatch);
          });
        });
      });
      const form = document.querySelector("[data-profile-form]");
      form.addEventListener("submit", async (event) => {
        event.preventDefault();
        const saveButton = form.querySelector("[data-profile-save]");
        const errorBox = form.querySelector("[data-profile-error]");
        errorBox.classList.remove("is-visible");
        saveButton.disabled = true;
        saveButton.textContent = "Сохраняем...";
        try {
          const data = await api.patch("/api/me", {
            bio: form.querySelector("#profile-bio").value.trim(),
            avatar_color: selectedColor,
          });
          setUser(data.user);
          profile.bio = data.user.bio;
          profile.avatar_color = data.user.avatar_color;
          closeModal();
          toast("Профиль обновлён", "success");
          renderProfile(main, ctx);
        } catch (error) {
          errorBox.textContent = error.message;
          errorBox.classList.add("is-visible");
          saveButton.disabled = false;
          saveButton.textContent = "Сохранить";
        }
      });
    });
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
