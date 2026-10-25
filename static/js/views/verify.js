import { api } from "../api.js";
import { icon } from "../icons.js";
import { navigate, setUser } from "../store.js";
import { toast } from "../ui.js";
import { escapeAttr, escapeHtml, safeNext } from "../utils.js";

const STORE_KEY = "flhub-verify";
const CODE_LENGTH = 6;
const RESEND_COOLDOWN = 60;

function submitForm(form) {
  if (typeof form.requestSubmit === "function") {
    form.requestSubmit();
  } else {
    form.dispatchEvent(new Event("submit", { cancelable: true, bubbles: true }));
  }
}

/** Запоминаем email и адрес возврата, чтобы экран кода переживал перезагрузку. */
export function rememberVerification({ email = "", hint = "", next = "/" } = {}) {
  try {
    sessionStorage.setItem(STORE_KEY, JSON.stringify({ email, hint, next }));
  } catch {
    /* приватный режим — обойдёмся без запоминалки */
  }
}

function readVerification() {
  try {
    return JSON.parse(sessionStorage.getItem(STORE_KEY) || "{}");
  } catch {
    return {};
  }
}

export function renderVerify(main, ctx) {
  const stored = readVerification();
  const email = ctx.params.get("email") || stored.email || "";
  const hint = ctx.params.get("hint") || stored.hint || "";
  const next = safeNext(ctx.params.get("next") || stored.next || "/");
  document.title = "Подтверждение email — FL HUB";

  main.innerHTML = `
    <div class="container auth-page">
      <div class="auth-layout">
        <div class="auth-art">
          <span class="auth-art-eyebrow">${icon("shield")} Шаг второй</span>
          <h1 class="auth-art-title">Одна цифровая<br>формальность —<br><span class="grad-text">и ты внутри</span></h1>
          <p class="auth-art-text">
            Подтверждение email отсекает ботов и чужие регистрации на твоё имя.
            Код приходит за секунды, действует 15 минут и подходит один раз.
          </p>
          <div class="auth-points">
            <div class="auth-point"><span class="point-icon">${icon("mail")}</span> Письмо ушло на указанный адрес</div>
            <div class="auth-point"><span class="point-icon">${icon("clock")}</span> 15 минут на ввод, 5 попыток</div>
            <div class="auth-point"><span class="point-icon">${icon("lock")}</span> Мы храним только хеш кода</div>
          </div>
        </div>

        <div class="auth-card">
          <div class="verify-badge">${icon("mail")}</div>
          <h2 class="auth-title">Введи код из письма</h2>
          <p class="auth-sub">
            ${hint
              ? `Мы отправили код на <strong>${escapeHtml(hint)}</strong>.`
              : "Мы отправили шестизначный код на твой email."}
            Письмо могло упасть в спам.
          </p>
          <form data-verify-form novalidate>
            <div class="field">
              <label class="label" for="verify-email">Email</label>
              <input class="input" id="verify-email" name="email" type="email"
                     autocomplete="email" placeholder="you@example.com"
                     value="${escapeAttr(email)}" required>
            </div>
            <div class="field">
              <span class="label">Код подтверждения</span>
              <div class="code-inputs" data-code-group>
                ${Array.from({ length: CODE_LENGTH }, (_, index) => `
                  <input class="code-cell" type="text" inputmode="numeric" autocomplete="one-time-code"
                         maxlength="1" pattern="\\d" aria-label="Цифра ${index + 1}" data-code-index="${index}">
                `).join("")}
              </div>
              <div class="code-hint">Можно вставить код целиком — цифры разложатся по ячейкам</div>
            </div>
            <div class="form-error" data-verify-error></div>
            <button class="btn btn-primary btn-block auth-submit" type="submit">Подтвердить email</button>
            <div class="verify-actions">
              <button class="link-btn" type="button" data-resend>Отправить код снова</button>
              <a href="#/login">Уже подтверждён? Войти</a>
            </div>
          </form>
        </div>
      </div>
    </div>
  `;

  const form = main.querySelector("[data-verify-form]");
  const cells = [...main.querySelectorAll("[data-code-index]")];
  const errorBox = main.querySelector("[data-verify-error]");
  const submit = form.querySelector("[type='submit']");
  const resendButton = form.querySelector("[data-resend]");
  const emailInput = form.querySelector("[name='email']");

  const readCode = () => cells.map((cell) => cell.value).join("");
  const clearErrorStyles = () => {
    errorBox.classList.remove("is-visible");
    cells.forEach((cell) => cell.classList.remove("is-error"));
  };

  cells.forEach((cell, index) => {
    cell.addEventListener("input", () => {
      cell.value = cell.value.replace(/\D+/g, "").slice(0, 1);
      cell.classList.toggle("is-filled", Boolean(cell.value));
      clearErrorStyles();
      if (cell.value && index < cells.length - 1) cells[index + 1].focus();
      if (readCode().length === CODE_LENGTH) submitForm(form);
    });
    cell.addEventListener("keydown", (event) => {
      if (event.key === "Backspace" && !cell.value && index > 0) {
        event.preventDefault();
        const previous = cells[index - 1];
        previous.value = "";
        previous.classList.remove("is-filled");
        previous.focus();
      }
      if (event.key === "ArrowLeft" && index > 0) cells[index - 1].focus();
      if (event.key === "ArrowRight" && index < cells.length - 1) cells[index + 1].focus();
    });
    cell.addEventListener("paste", (event) => {
      const digits = (event.clipboardData.getData("text") || "").replace(/\D+/g, "").slice(0, CODE_LENGTH);
      if (!digits) return;
      event.preventDefault();
      fillCells(digits);
      if (digits.length === CODE_LENGTH) submitForm(form);
    });
  });

  function fillCells(digits) {
    cells.forEach((cell, index) => {
      cell.value = digits[index] || "";
      cell.classList.toggle("is-filled", Boolean(cell.value));
    });
    const target = Math.min(digits.length, cells.length - 1);
    cells[target].focus();
  }

  function showVerifyError(message, payload = {}) {
    errorBox.textContent = message;
    errorBox.classList.add("is-visible");
    cells.forEach((cell) => cell.classList.add("is-error"));
    if (payload.code_expired || payload.code_sent) {
      toast(payload.code_sent ? "Мы отправили новый код" : "Код истёк — запроси новый", "info");
      resendButton.focus();
    }
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    clearErrorStyles();
    const address = emailInput.value.trim();
    const code = readCode();
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(address)) {
      return showFieldError(errorBox, "Введи корректный email");
    }
    if (code.length !== CODE_LENGTH) {
      return showVerifyError("Введи все 6 цифр из письма");
    }
    submit.disabled = true;
    const label = submit.textContent;
    submit.textContent = "Проверяем...";
    try {
      const data = await api.post("/api/verify-email", { email: address, code });
      setUser(data.user);
      try {
        sessionStorage.removeItem(STORE_KEY);
      } catch {
        /* не критично */
      }
      toast(`Аккаунт @${data.user.username} подтверждён`, "success");
      navigate(next);
    } catch (error) {
      const payload = error.payload || {};
      if (payload.already_verified) {
        toast(error.message, "info");
        navigate("/login");
        return;
      }
      showVerifyError(error.message, payload);
      submit.disabled = false;
      submit.textContent = label;
      cells[CODE_LENGTH - 1].focus();
    }
  });

  let cooldownTimer = null;
  function startCooldown(seconds) {
    let left = seconds;
    clearInterval(cooldownTimer);
    resendButton.disabled = true;
    const tick = () => {
      resendButton.textContent = left > 0 ? `Новый код через ${left} с` : "Отправить код снова";
      if (left <= 0) {
        clearInterval(cooldownTimer);
        resendButton.disabled = false;
        return;
      }
      left -= 1;
    };
    tick();
    cooldownTimer = setInterval(tick, 1000);
  }

  resendButton.addEventListener("click", async () => {
    clearErrorStyles();
    const address = emailInput.value.trim();
    if (!address) return showFieldError(errorBox, "Сначала укажи email");
    resendButton.disabled = true;
    try {
      const data = await api.post("/api/resend-code", { email: address });
      toast("Код отправлен ещё раз", "success");
      startCooldown(RESEND_COOLDOWN);
      if (data.email) {
        const sub = main.querySelector(".auth-sub");
        if (sub) sub.innerHTML = `Мы отправили код на <strong>${escapeHtml(data.email)}</strong>. Письмо могло упасть в спам.`;
      }
    } catch (error) {
      showFieldError(errorBox, error.message);
      resendButton.disabled = false;
    }
  });

  cells[0].focus();
}

function showFieldError(errorBox, message) {
  errorBox.textContent = message;
  errorBox.classList.add("is-visible");
  return undefined;
}
