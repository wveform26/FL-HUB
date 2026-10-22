import { api } from "../api.js";
import { icon } from "../icons.js";
import { navigate, setUser } from "../store.js";
import { toast } from "../ui.js";
import { escapeAttr, escapeHtml, safeNext } from "../utils.js";

export function renderAuth(main, ctx) {
  const isRegister = ctx.path === "/register";
  const next = safeNext(ctx.params.get("next") || "/");
  document.title = `${isRegister ? "Регистрация" : "Вход"} — FL HUB`;

  const tabs = `
    <div class="auth-tabs">
      <a class="auth-tab ${!isRegister ? "is-active" : ""}" href="#/login?next=${encodeURIComponent(next)}">Вход</a>
      <a class="auth-tab ${isRegister ? "is-active" : ""}" href="#/register?next=${encodeURIComponent(next)}">Регистрация</a>
    </div>
  `;

  const form = isRegister ? registerForm() : loginForm();

  main.innerHTML = `
    <div class="container auth-page">
      <div class="auth-layout">
        <div class="auth-art">
          <span class="auth-art-eyebrow">${icon("wave")} FL HUB</span>
          <h1 class="auth-art-title">Твой звук<br>не должен<br><span class="grad-text">пылиться в папке</span></h1>
          <p class="auth-art-text">
            FL HUB — место, где продюсеры делятся треками, проектами, инструментами, плагинами и драм-китами.
            Загружай, слушай, находи своих людей.
          </p>
          <div class="auth-points">
            <div class="auth-point"><span class="point-icon">${icon("upload")}</span> Публикуй музыку и паки</div>
            <div class="auth-point"><span class="point-icon">${icon("download")}</span> Скачивай материалы сообщества</div>
            <div class="auth-point"><span class="point-icon">${icon("message")}</span> Общайся и находи коллаборации</div>
          </div>
          <div class="auth-art-cards">
            <div class="floating-card one">
              <div class="cover-mini" style="background:linear-gradient(140deg,#ff7a18,#7a1fd0)"></div>
              <div><strong>Neon Rain</strong><span>Trap · 140 BPM</span></div>
            </div>
            <div class="floating-card two">
              <div class="cover-mini" style="background:linear-gradient(140deg,#4fd1c5,#0a1f3d)"></div>
              <div><strong>Velvet Keys</strong><span>Instrument · 8 samples</span></div>
            </div>
          </div>
        </div>

        <div class="auth-card">
          ${tabs}
          <h2 class="auth-title">${isRegister ? "Создать аккаунт" : "С возвращением"}</h2>
          <p class="auth-sub">${isRegister ? "Пара шагов — и ты в сообществе." : "Войди, чтобы слушать, скачивать и публиковать."}</p>
          ${form}
          <div class="auth-alt">
            ${isRegister
              ? `Уже есть аккаунт? <a href="#/login?next=${encodeURIComponent(next)}">Войти</a>`
              : `Ещё нет аккаунта? <a href="#/register?next=${encodeURIComponent(next)}">Зарегистрироваться</a>`}
          </div>
        </div>
      </div>
    </div>
  `;

  const authForm = main.querySelector("[data-auth-form]");
  authForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const errorBox = authForm.querySelector("[data-auth-error]");
    const submit = authForm.querySelector("[type='submit']");
    errorBox.classList.remove("is-visible");

    const formData = new FormData(authForm);
    let payload;
    if (isRegister) {
      const username = String(formData.get("username") || "").trim();
      const email = String(formData.get("email") || "").trim();
      const password = String(formData.get("password") || "");
      const confirm = String(formData.get("confirm") || "");
      if (!/^[A-Za-z0-9_]{3,24}$/.test(username)) {
        return showError(errorBox, "Имя: 3–24 символа, латиница, цифры и _");
      }
      if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) {
        return showError(errorBox, "Введите корректный email");
      }
      if (password.length < 8) {
        return showError(errorBox, "Пароль должен быть не короче 8 символов");
      }
      if (password !== confirm) {
        return showError(errorBox, "Пароли не совпадают");
      }
      payload = { username, email, password };
    } else {
      const identifier = String(formData.get("identifier") || "").trim();
      const password = String(formData.get("password") || "");
      if (!identifier || !password) {
        return showError(errorBox, "Заполни все поля");
      }
      payload = { identifier, password };
    }

    submit.disabled = true;
    const initialLabel = submit.textContent;
    submit.textContent = isRegister ? "Создаём..." : "Входим...";
    try {
      const data = await api.post(isRegister ? "/api/register" : "/api/login", payload);
      setUser(data.user);
      toast(isRegister ? `Добро пожаловать, @${data.user.username}` : `С возвращением, @${data.user.username}`, "success");
      navigate(next);
    } catch (error) {
      showError(errorBox, error.message);
      submit.disabled = false;
      submit.textContent = initialLabel;
    }
  });
}

function loginForm() {
  return `
    <form class="auth-form" data-auth-form>
      <div class="field">
        <label class="label" for="login-identifier">Имя или email</label>
        <input class="input" id="login-identifier" name="identifier" type="text" autocomplete="username"
               placeholder="beatmaker" required>
      </div>
      <div class="field">
        <label class="label" for="login-password">Пароль</label>
        <input class="input" id="login-password" name="password" type="password" autocomplete="current-password"
               placeholder="••••••••" required>
      </div>
      <div class="form-error" data-auth-error></div>
      <button class="btn btn-primary btn-block auth-submit" type="submit">Войти</button>
    </form>
  `;
}

function registerForm() {
  return `
    <form class="auth-form" data-auth-form>
      <div class="field">
        <label class="label" for="register-username">Имя пользователя</label>
        <input class="input" id="register-username" name="username" type="text" autocomplete="username"
               minlength="3" maxlength="24" placeholder="beatmaker" required>
        <span class="hint">Латиница, цифры и _, 3–24 символа</span>
      </div>
      <div class="field">
        <label class="label" for="register-email">Email</label>
        <input class="input" id="register-email" name="email" type="email" autocomplete="email"
               placeholder="you@example.com" required>
      </div>
      <div class="field">
        <label class="label" for="register-password">Пароль</label>
        <input class="input" id="register-password" name="password" type="password" autocomplete="new-password"
               minlength="8" placeholder="Минимум 8 символов" required>
      </div>
      <div class="field">
        <label class="label" for="register-confirm">Повтори пароль</label>
        <input class="input" id="register-confirm" name="confirm" type="password" autocomplete="new-password"
               minlength="8" placeholder="Ещё раз" required>
      </div>
      <div class="form-error" data-auth-error></div>
      <button class="btn btn-primary btn-block auth-submit" type="submit">Создать аккаунт</button>
    </form>
  `;
}

function showError(errorBox, message) {
  errorBox.textContent = message;
  errorBox.classList.add("is-visible");
  return undefined;
}
