export class ApiError extends Error {
  constructor(message, status = 0) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function parseResponse(response) {
  let data = {};
  const text = await response.text();
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = {};
    }
  }
  if (!response.ok) {
    const error = new ApiError(data.error || `Ошибка запроса (${response.status})`, response.status);
    error.payload = data;
    throw error;
  }
  return data;
}

async function request(path, options = {}) {
  const headers = {
    "X-Requested-With": "fetch",
    ...(options.body ? { "Content-Type": "application/json" } : {}),
    ...(options.headers || {}),
  };
  let response;
  try {
    response = await fetch(path, {
      method: options.method || "GET",
      headers,
      body: options.body ? JSON.stringify(options.body) : undefined,
      credentials: "same-origin",
    });
  } catch {
    throw new ApiError("Нет связи с сервером. Проверьте подключение.", 0);
  }
  return parseResponse(response);
}

export const api = {
  get(path) {
    return request(path);
  },
  post(path, body) {
    return request(path, { method: "POST", body: body ?? {} });
  },
  patch(path, body) {
    return request(path, { method: "PATCH", body: body ?? {} });
  },
  delete(path) {
    return request(path, { method: "DELETE" });
  },
};

export function uploadItem(formData, onProgress) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/items");
    xhr.setRequestHeader("X-Requested-With", "fetch");
    xhr.responseType = "text";
    xhr.upload.addEventListener("progress", (event) => {
      if (event.lengthComputable && typeof onProgress === "function") {
        onProgress(event.loaded / event.total);
      }
    });
    xhr.addEventListener("load", () => {
      let data = {};
      try {
        data = xhr.responseText ? JSON.parse(xhr.responseText) : {};
      } catch {
        data = {};
      }
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(data);
      } else {
        reject(new ApiError(data.error || `Не удалось загрузить файл (${xhr.status})`, xhr.status));
      }
    });
    xhr.addEventListener("error", () => {
      reject(new ApiError("Не удалось отправить файл. Проверьте соединение.", 0));
    });
    xhr.send(formData);
  });
}
