export const CATEGORIES = {
  music: {
    label: "Музыка",
    short: "Треки",
    icon: "music",
    color: "#ff8a3d",
    accept: ".wav,.mp3,.ogg,.flac,.m4a",
    fileTitle: "Аудиофайл",
    fileHint: "WAV, MP3, OGG, FLAC или M4A · до 180 МБ",
  },
  project: {
    label: "Проекты",
    short: "Проекты",
    icon: "layers",
    color: "#9b8cff",
    accept: ".zip,.rar,.7z,.flp",
    fileTitle: "Архив проекта",
    fileHint: "ZIP, RAR, 7Z или FLP · stems и MIDI внутри",
  },
  instrument: {
    label: "Инструменты",
    short: "Банки",
    icon: "piano",
    color: "#4fd1c5",
    accept: ".zip,.rar,.7z,.sf2,.wav",
    fileTitle: "Банк инструмента",
    fileHint: "ZIP, RAR, 7Z, SF2 или WAV · до 180 МБ",
  },
  plugin: {
    label: "Плагины",
    short: "Плагины",
    icon: "puzzle",
    color: "#ffd166",
    accept: ".zip,.rar,.7z",
    fileTitle: "Архив плагина",
    fileHint: "ZIP, RAR или 7Z · до 180 МБ",
  },
  drumkit: {
    label: "Драм-киты",
    short: "Киты",
    icon: "drum",
    color: "#ff6b9d",
    accept: ".zip,.rar,.7z,.wav",
    fileTitle: "Архив драм-кита",
    fileHint: "ZIP, RAR, 7Z или WAV · до 180 МБ",
  },
};

export const CATEGORY_KEYS = Object.keys(CATEGORIES);

export const GENRES = [
  "Trap",
  "Hip-Hop",
  "Lo-Fi",
  "House",
  "Tech House",
  "Techno",
  "Drum & Bass",
  "Phonk",
  "Drill",
  "R&B / Soul",
  "Ambient",
  "Pop",
  "Experimental",
  "Mixing",
  "Other",
];

const compactNumber = new Intl.NumberFormat("ru-RU", {
  notation: "compact",
  maximumFractionDigits: 1,
});

const dateFormatter = new Intl.DateTimeFormat("ru-RU", {
  day: "numeric",
  month: "long",
  year: "numeric",
});

const relativeFormatter = new Intl.RelativeTimeFormat("ru", { numeric: "auto" });

export function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (character) => {
    switch (character) {
      case "&": return "&amp;";
      case "<": return "&lt;";
      case ">": return "&gt;";
      case '"': return "&quot;";
      case "'": return "&#39;";
      default: return character;
    }
  });
}

export const escapeAttr = escapeHtml;

export function formatCount(value) {
  const number = Number(value) || 0;
  if (Math.abs(number) < 1000) return String(number);
  return compactNumber.format(number);
}

export function formatDuration(value) {
  const total = Math.max(0, Math.round(Number(value) || 0));
  const minutes = Math.floor(total / 60);
  const seconds = total % 60;
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
}

export function formatBytes(bytes) {
  const size = Number(bytes) || 0;
  if (size < 1024) return `${size} Б`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1).replace(".", ",")} КБ`;
  if (size < 1024 * 1024 * 1024) return `${(size / (1024 * 1024)).toFixed(1).replace(".", ",")} МБ`;
  return `${(size / (1024 * 1024 * 1024)).toFixed(2).replace(".", ",")} ГБ`;
}

export function formatDate(value) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return dateFormatter.format(date);
}

export function timeAgo(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  const seconds = (Date.now() - date.getTime()) / 1000;
  if (seconds < 60) return "только что";
  if (seconds < 3600) return relativeFormatter.format(-Math.round(seconds / 60), "minute");
  if (seconds < 86400) return relativeFormatter.format(-Math.round(seconds / 3600), "hour");
  if (seconds < 86400 * 30) return relativeFormatter.format(-Math.round(seconds / 86400), "day");
  if (seconds < 86400 * 365) return relativeFormatter.format(-Math.round(seconds / (86400 * 30)), "month");
  return relativeFormatter.format(-Math.round(seconds / (86400 * 365)), "year");
}

export function initials(username) {
  const clean = String(username || "?").replace(/^@/, "");
  return clean.slice(0, 1).toUpperCase() || "?";
}

export function fileFormat(item) {
  const name = item?.file_name || "";
  const extension = name.includes(".") ? name.split(".").pop() : "";
  return extension ? extension.toUpperCase() : (CATEGORIES[item?.category]?.short || "FILE");
}

export function categoryMeta(key) {
  return CATEGORIES[key] || { label: key || "Работа", short: "Работа", icon: "disc", color: "#ff7a18" };
}

export function buildCatalogUrl({ category = "", q = "", genre = "", sort = "new" } = {}) {
  const params = new URLSearchParams();
  if (category) params.set("category", category);
  if (q) params.set("q", q);
  if (genre) params.set("genre", genre);
  if (sort && sort !== "new") params.set("sort", sort);
  const query = params.toString();
  return `/catalog${query ? `?${query}` : ""}`;
}

export function debounce(fn, delay = 250) {
  let timer = null;
  return (...args) => {
    window.clearTimeout(timer);
    timer = window.setTimeout(() => fn(...args), delay);
  };
}

export function safeNext(value) {
  if (!value) return "/";
  let next = value;
  try {
    next = decodeURIComponent(value);
  } catch {
    next = value;
  }
  if (!next.startsWith("/") || next.startsWith("//")) return "/";
  return next;
}
