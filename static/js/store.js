export const state = {
  user: null,
  stats: null,
};

export const itemCache = new Map();

export function cacheItems(items = []) {
  for (const item of items) {
    if (item && item.id) itemCache.set(Number(item.id), item);
  }
}

export function cacheItem(item) {
  if (item && item.id) itemCache.set(Number(item.id), item);
  return item;
}

export function setUser(user) {
  state.user = user;
  document.dispatchEvent(new CustomEvent("auth:change", { detail: user }));
}

export function navigate(path) {
  const target = `#${path.startsWith("/") ? path : `/${path}`}`;
  if (window.location.hash === target) {
    document.dispatchEvent(new CustomEvent("route:refresh"));
  } else {
    window.location.hash = target;
  }
}

export function refreshRoute() {
  document.dispatchEvent(new CustomEvent("route:refresh"));
}

export function currentPath() {
  const raw = window.location.hash.startsWith("#")
    ? window.location.hash.slice(1)
    : window.location.hash;
  return raw || "/";
}
