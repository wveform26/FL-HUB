import { uploadItem } from "../api.js";
import { icon } from "../icons.js";
import { cacheItem, navigate, state } from "../store.js";
import { emptyState, toast } from "../ui.js";
import {
  CATEGORIES,
  CATEGORY_KEYS,
  GENRES,
  escapeHtml,
  formatBytes,
} from "../utils.js";

export function renderUpload(main) {
  if (!state.user) {
    main.innerHTML = `<div class="container" style="padding-top:50px">${emptyState({
      iconName: "user",
      title: "Нужно войти в аккаунт",
      text: "Загружать работы могут только участники сообщества.",
      action: `<a class="btn btn-primary" href="#/login?next=/upload">Войти</a>`,
    })}</div>`;
    return;
  }

  const categoryOptions = CATEGORY_KEYS.map((key, index) => {
    const meta = CATEGORIES[key];
    return `
      <label class="category-option ${index === 0 ? "is-active" : ""}" style="--cat:${meta.color}" data-category-option="${key}">
        <input type="radio" name="category" value="${key}" ${index === 0 ? "checked" : ""}>
        <span class="cat-option-inner">${icon(meta.icon)}<span>${escapeHtml(meta.label)}</span></span>
      </label>
    `;
  }).join("");

  const genreOptions = GENRES.map((genre) => `<option value="${escapeHtml(genre)}">${escapeHtml(genre)}</option>`).join("");

  main.innerHTML = `
    <div class="container">
      <header class="page-head">
        <h1 class="page-title">Загрузить работу</h1>
        <p class="page-sub">Поделись треком, проектом, инструментом, плагином или драм-китом. Заполни карточку — и работа появится в каталоге.</p>
      </header>

      <div class="upload-layout">
        <form class="panel upload-form" data-upload-form novalidate>
          <div class="form-section">
            <div class="form-section-title">Что ты публикуешь?</div>
            <div class="category-picker">${categoryOptions}</div>
          </div>

          <div class="form-section">
            <div class="form-section-title">Основное</div>
            <div class="field">
              <label class="label" for="upload-title">Название <span class="req">*</span></label>
              <input class="input" id="upload-title" name="title" type="text" maxlength="120"
                     placeholder="Например, Neon Rain" autocomplete="off" required>
            </div>
            <div class="field" style="margin-top:16px">
              <label class="label" for="upload-description">Описание</label>
              <textarea class="textarea" id="upload-description" name="description" maxlength="4000"
                        placeholder="Расскажи о работе: настроение, инструменты, для кого подойдёт, что внутри архива..."></textarea>
              <span class="hint">Чем понятнее описание, тем чаще работу скачивают.</span>
            </div>
            <div class="field-row" style="margin-top:16px">
              <div class="field">
                <label class="label" for="upload-genre">Жанр</label>
                <select class="select" id="upload-genre" name="genre">
                  <option value="">Выбери жанр</option>
                  ${genreOptions}
                </select>
              </div>
              <div class="field">
                <label class="label" for="upload-tags">Теги</label>
                <input class="input" id="upload-tags" name="tags" type="text" maxlength="200"
                       placeholder="trap, 808, dark" autocomplete="off">
                <span class="hint">До 8 тегов через запятую</span>
              </div>
            </div>
            <div class="field-row" style="margin-top:16px" data-music-fields>
              <div class="field">
                <label class="label" for="upload-bpm">BPM</label>
                <input class="input" id="upload-bpm" name="bpm" type="number" min="20" max="300" placeholder="140">
              </div>
              <div class="field">
                <label class="label" for="upload-key">Тональность</label>
                <input class="input" id="upload-key" name="key" type="text" maxlength="20" placeholder="A minor">
              </div>
            </div>
          </div>

      <div class="form-section">
          <div class="form-section-title">Доступ</div>
          <div class="access-picker" data-access-picker>
            <label class="access-option is-active" data-access-option="free">
              <input type="radio" name="access" value="free" checked>
              <span class="access-option-inner">
                <span class="access-icon">${icon("unlock")}</span>
                <span class="access-label">Общий</span>
                <span class="access-desc">Все могут слушать и скачивать</span>
              </span>
            </label>
            <label class="access-option" data-access-option="paid">
              <input type="radio" name="access" value="paid">
              <span class="access-option-inner">
                <span class="access-icon">${icon("lock")}</span>
                <span class="access-label">Платный</span>
                <span class="access-desc">Демо для всех, полный файл — для скачивания</span>
              </span>
            </label>
          </div>
          <div class="demo-upload hidden" data-demo-upload>
            <label class="dropzone" data-demo-dropzone>
              <input type="file" name="demo" accept=".wav,.mp3,.ogg,.flac,.m4a,.zip,.rar,.7z,.fpx" data-demo-input>
              <span class="dropzone-icon" data-demo-dropzone-icon>${icon("disc")}</span>
              <span class="dropzone-title" data-demo-dropzone-title>Перетащи демо-файл или <span>выбери файл</span></span>
              <span class="dropzone-hint" data-demo-dropzone-hint>WAV, MP3, OGG, FLAC, M4A, ZIP, RAR, 7Z · до 180 МБ</span>
            </label>
            <div class="file-meta hidden" data-demo-file-meta style="margin-top:10px"></div>
            <p class="hint" style="margin-top:8px">Демо-версия будет доступна для прослушивания всем. Полный файл — только для скачивания владельцем.</p>
          </div>
        </div>
          <div class="form-section">
          <div class="form-section-title">Файлы</div>
            <label class="dropzone" data-dropzone>
              <input type="file" name="file" accept="${CATEGORIES.music.accept}" data-file-input required>
              <span class="dropzone-icon" data-dropzone-icon>${icon("upload")}</span>
              <span class="dropzone-title" data-dropzone-title>Перетащи аудиофайл или <span>выбери файл</span></span>
              <span class="dropzone-hint" data-dropzone-hint>${escapeHtml(CATEGORIES.music.fileHint)}</span>
            </label>
            <div class="file-meta hidden" data-file-meta style="margin-top:10px"></div>

            <div class="cover-row" style="margin-top:18px">
              <div class="cover-preview" data-cover-preview>${icon("disc")}</div>
              <div>
                <label class="cover-drop">
                  <input type="file" name="cover" accept=".jpg,.jpeg,.png,.webp,.gif" data-cover-input>
                  <span>Загрузить обложку</span>
                </label>
                <p class="hint" style="margin-top:5px">Необязательно. JPG, PNG, WEBP или GIF до 8 МБ. Если не загрузить — сгенерируем сами.</p>
              </div>
            </div>
          </div>

          <div class="upload-progress" data-progress>
            <div class="progress-label"><span>Загружаем файл...</span><span data-progress-value>0%</span></div>
            <div class="progress-track"><div class="progress-bar" data-progress-bar></div></div>
          </div>
          <div class="form-error" data-form-error></div>

          <button class="btn btn-primary btn-block" type="submit" data-submit>
            ${icon("upload")} Опубликовать работу
          </button>
        </form>

        <aside class="panel tips-card">
          <div class="tips-title">Перед публикацией</div>
          <div class="tip-item">
            <span class="tip-icon">${icon("music")}</span>
            <div class="tip-text"><strong>Музыка</strong>Загружай WAV или MP3 — файл будет доступен для прослушивания и скачивания.</div>
          </div>
          <div class="tip-item">
            <span class="tip-icon">${icon("layers")}</span>
            <div class="tip-text"><strong>Проекты и паки</strong>Собери ZIP: stems, MIDI, пресеты и README. Так работу удобнее разбирать.</div>
          </div>
          <div class="tip-item">
            <span class="tip-icon">${icon("piano")}</span>
            <div class="tip-text"><strong>BPM и тональность</strong>Укажи их для музыкальных работ — по ним проще находить нужное.</div>
          </div>
          <div class="tip-item">
            <span class="tip-icon">${icon("lock")}</span>
            <div class="tip-text"><strong>Платный доступ</strong>Укажи «Платный» и прикрепи демо-версию. Полный файл доступен только для скачивания.</div>
          </div>
          <div class="tip-item">
            <span class="tip-icon">${icon("shield")}</span>
            <div class="tip-text"><strong>Права</strong>Загружай только свои материалы или те, на которые у тебя есть права.</div>
          </div>
          <div class="tip-item">
            <span class="tip-icon">${icon("sparkles")}</span>
            <div class="tip-text"><strong>Обложка</strong>Квадратная картинка делает карточку заметнее в каталоге.</div>
          </div>
        </aside>
      </div>
    </div>
  `;

  const form = main.querySelector("[data-upload-form]");
  const fileInput = form.querySelector("[data-file-input]");
  const coverInput = form.querySelector("[data-cover-input]");
  const dropzone = form.querySelector("[data-dropzone]");
  const dropzoneTitle = form.querySelector("[data-dropzone-title]");
  const dropzoneHint = form.querySelector("[data-dropzone-hint]");
  const fileMeta = form.querySelector("[data-file-meta]");
  const coverPreview = form.querySelector("[data-cover-preview]");
  const musicFields = form.querySelector("[data-music-fields]");
  const progress = form.querySelector("[data-progress]");
  const progressBar = form.querySelector("[data-progress-bar]");
  const progressValue = form.querySelector("[data-progress-value]");
  const errorBox = form.querySelector("[data-form-error]");
  const submit = form.querySelector("[data-submit]");
  let coverUrl = null;

  const selectedCategory = () => form.querySelector("input[name='category']:checked")?.value || "music";

  function updateCategory() {
    const key = selectedCategory();
    const meta = CATEGORIES[key];
    form.querySelectorAll("[data-category-option]").forEach((option) => {
      option.classList.toggle("is-active", option.dataset.categoryOption === key);
    });
    fileInput.accept = meta.accept;
    dropzoneTitle.innerHTML = `Перетащи ${meta.fileTitle.toLowerCase()} или <span>выбери файл</span>`;
    dropzoneHint.textContent = meta.fileHint;
    musicFields.classList.toggle("hidden", !["music", "project", "drumkit"].includes(key));
  }

  form.querySelectorAll("input[name='category']").forEach((radio) => {
    radio.addEventListener("change", updateCategory);
  });

  // Access type switching
  const accessOptions = form.querySelectorAll("[data-access-option]");
  const demoUpload = form.querySelector("[data-demo-upload]");
  const demoInput = form.querySelector("[data-demo-input]");
  const demoDropzone = form.querySelector("[data-demo-dropzone]");
  const demoDropzoneTitle = form.querySelector("[data-demo-dropzone-title]");
  const demoDropzoneHint = form.querySelector("[data-demo-dropzone-hint]");
  const demoFileMeta = form.querySelector("[data-demo-file-meta]");

  accessOptions.forEach((option) => {
    option.addEventListener("click", () => {
      accessOptions.forEach((o) => o.classList.toggle("is-active", o === option));
      demoUpload.classList.toggle("hidden", option.dataset.accessOption !== "paid");
    });
  });

  function updateDemoMeta() {
    const file = demoInput.files?.[0];
    if (!file) {
      demoDropzone.classList.remove("has-file");
      demoFileMeta.classList.add("hidden");
      demoFileMeta.innerHTML = "";
      return;
    }
    demoDropzone.classList.add("has-file");
    demoDropzoneTitle.innerHTML = escapeHtml(file.name);
    demoDropzoneHint.textContent = `${formatBytes(file.size)} · готов к загрузке`;
    demoFileMeta.classList.remove("hidden");
    demoFileMeta.innerHTML = `
      <span>${icon("disc")}</span>
      <strong>${escapeHtml(file.name)}</strong>
      <span class="dim">${formatBytes(file.size)}</span>
      <button type="button" class="clear-file" data-clear-demo aria-label="Убрать демо">${icon("close")}</button>
    `;
    demoFileMeta.querySelector("[data-clear-demo]").addEventListener("click", () => {
      demoInput.value = "";
      updateDemoMeta();
    });
  }

  demoInput?.addEventListener("change", updateDemoMeta);

  if (demoDropzone) {
    ["dragenter", "dragover"].forEach((eventName) => {
      demoDropzone.addEventListener(eventName, (event) => {
        event.preventDefault();
        demoDropzone.classList.add("is-dragover");
      });
    });
    ["dragleave", "dragend"].forEach((eventName) => {
      demoDropzone.addEventListener(eventName, () => demoDropzone.classList.remove("is-dragover"));
    });
    demoDropzone.addEventListener("drop", (event) => {
      event.preventDefault();
      demoDropzone.classList.remove("is-dragover");
      const file = event.dataTransfer?.files?.[0];
      if (!file) return;
      const transfer = new DataTransfer();
      transfer.items.add(file);
      demoInput.files = transfer.files;
      updateDemoMeta();
    });
  }

  function updateFileMeta() {
    const file = fileInput.files?.[0];
    if (!file) {
      dropzone.classList.remove("has-file");
      fileMeta.classList.add("hidden");
      fileMeta.innerHTML = "";
      return;
    }
    dropzone.classList.add("has-file");
    dropzoneTitle.innerHTML = escapeHtml(file.name);
    dropzoneHint.textContent = `${formatBytes(file.size)} · готов к загрузке`;
    fileMeta.classList.remove("hidden");
    fileMeta.innerHTML = `
      <span>${icon("file")}</span>
      <strong>${escapeHtml(file.name)}</strong>
      <span class="dim">${formatBytes(file.size)}</span>
      <button type="button" class="clear-file" data-clear-file aria-label="Убрать файл">${icon("close")}</button>
    `;
    fileMeta.querySelector("[data-clear-file]").addEventListener("click", () => {
      fileInput.value = "";
      updateFileMeta();
    });
  }

  fileInput.addEventListener("change", updateFileMeta);

  ["dragenter", "dragover"].forEach((eventName) => {
    dropzone.addEventListener(eventName, (event) => {
      event.preventDefault();
      dropzone.classList.add("is-dragover");
    });
  });
  ["dragleave", "dragend"].forEach((eventName) => {
    dropzone.addEventListener(eventName, () => dropzone.classList.remove("is-dragover"));
  });
  dropzone.addEventListener("drop", (event) => {
    event.preventDefault();
    dropzone.classList.remove("is-dragover");
    const file = event.dataTransfer?.files?.[0];
    if (!file) return;
    const transfer = new DataTransfer();
    transfer.items.add(file);
    fileInput.files = transfer.files;
    updateFileMeta();
  });

  coverInput.addEventListener("change", () => {
    const file = coverInput.files?.[0];
    if (coverUrl) {
      URL.revokeObjectURL(coverUrl);
      coverUrl = null;
    }
    if (!file) {
      coverPreview.innerHTML = icon("disc");
      return;
    }
    coverUrl = URL.createObjectURL(file);
    coverPreview.innerHTML = `<img src="${coverUrl}" alt="Предпросмотр обложки">`;
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    errorBox.classList.remove("is-visible");
    const title = form.querySelector("#upload-title").value.trim();
    if (title.length < 3) {
      showError("Название должно быть не короче 3 символов.");
      form.querySelector("#upload-title").focus();
      return;
    }
    if (!fileInput.files?.length) {
      showError("Прикрепи файл работы.");
      dropzone.scrollIntoView({ behavior: "smooth", block: "center" });
      return;
    }
    const accessType = form.querySelector("input[name='access']:checked")?.value || "free";
    if (accessType === "paid" && !demoInput.files?.length) {
      showError("Для платного контента прикрепи демо-версию.");
      demoDropzone?.scrollIntoView({ behavior: "smooth", block: "center" });
      return;
    }
    const formData = new FormData(form);
    submit.disabled = true;
    submit.innerHTML = `${icon("upload")} Публикуем...`;
    progress.classList.add("is-visible");
    progressBar.style.width = "0%";
    progressValue.textContent = "0%";
    try {
      const data = await uploadItem(formData, (ratio) => {
        const percent = Math.min(99, Math.round(ratio * 100));
        progressBar.style.width = `${percent}%`;
        progressValue.textContent = `${percent}%`;
      });
      progressBar.style.width = "100%";
      progressValue.textContent = "100%";
      cacheItem(data.item);
      if (state.stats) {
        state.stats.items = (state.stats.items || 0) + 1;
        if (state.stats.categories) {
          const category = data.item.category;
          state.stats.categories[category] = (state.stats.categories[category] || 0) + 1;
        }
      }
      toast("Работа опубликована", "success");
      navigate(`/item/${data.item.id}`);
    } catch (error) {
      showError(error.message);
      progress.classList.remove("is-visible");
      submit.disabled = false;
      submit.innerHTML = `${icon("upload")} Опубликовать работу`;
    }
  });

  function showError(message) {
    errorBox.textContent = message;
    errorBox.classList.add("is-visible");
    errorBox.scrollIntoView({ behavior: "smooth", block: "center" });
    toast(message, "error");
  }
}
