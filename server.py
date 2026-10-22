#!/usr/bin/env python3
"""FL HUB — a tiny community site for FL Studio musicians.

Pure standard library: HTTP server, SQLite, session auth, multipart uploads.
Run: python3 server.py
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import os
import re
import secrets
import traceback
import wave
from datetime import datetime, timedelta, timezone
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

import art
import db
import seed
import security

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
SESSION_COOKIE = "flhub_session"
SESSION_DAYS = 30
MAX_JSON_BODY = 1_000_000
MAX_UPLOAD_BODY = 180 * 1024 * 1024
PAGE_SIZE = 24

CATEGORIES = {"music", "project", "instrument", "plugin", "drumkit"}
SORTS = {"new", "popular", "downloads"}

AUDIO_EXT = {".wav", ".mp3", ".ogg", ".flac", ".m4a"}
ARCHIVE_EXT = {".zip", ".rar", ".7z"}
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif"}

CATEGORY_EXT = {
    "music": AUDIO_EXT,
    "project": ARCHIVE_EXT | {".flp"},
    "instrument": ARCHIVE_EXT | {".sf2", ".wav"},
    "plugin": ARCHIVE_EXT,
    "drumkit": ARCHIVE_EXT | {".wav"},
}

AVATAR_COLORS = [
    "#ff7a1a", "#ff5c8a", "#b794f6", "#7dd3fc", "#4fd1c5",
    "#ffd166", "#a3e635", "#f97316", "#f472b6", "#60a5fa",
]

USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,24}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
RANGE_RE = re.compile(r"^bytes=(\d*)-(\d*)$")


class ApiError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def public_user(row) -> dict:
    return {
        "id": row["id"],
        "username": row["username"],
        "bio": row["bio"],
        "avatar_color": row["avatar_color"],
        "created_at": row["created_at"],
    }


def clean_text(value: str, limit: int) -> str:
    return (value or "").strip()[:limit]


def media_url(folder: str, filename: str) -> str:
    if not filename:
        return ""
    return f"/media/{folder}/{quote(filename)}"


def item_dict(row, liked: bool = False, viewer_id: int | None = None) -> dict:
    return {
        "id": row["id"],
        "category": row["category"],
        "title": row["title"],
        "description": row["description"],
        "genre": row["genre"],
        "bpm": row["bpm"],
        "key": row["music_key"],
        "tags": [tag for tag in (row["tags"] or "").split(",") if tag],
        "cover_url": media_url("covers", row["cover_path"]),
        "audio_url": media_url("uploads", row["audio_path"]),
        "file_url": f"/download/{row['id']}",
        "file_name": row["file_name"],
        "file_size": row["file_size"],
        "duration": row["duration"],
        "plays": row["plays"],
        "downloads": row["downloads"],
        "likes": row["likes_count"],
        "comments": row["comments_count"],
        "featured": bool(row["featured"]),
        "liked": bool(liked),
        "is_owner": bool(viewer_id and viewer_id == row["author_id"]),
        "created_at": row["created_at"],
        "author": {
            "id": row["author_id"],
            "username": row["username"],
            "avatar_color": row["avatar_color"],
        },
    }


def comment_dict(row) -> dict:
    return {
        "id": row["id"],
        "body": row["body"],
        "created_at": row["created_at"],
        "author": {
            "id": row["user_id"],
            "username": row["username"],
            "avatar_color": row["avatar_color"],
        },
    }


def parse_tags(raw: str) -> str:
    seen: list[str] = []
    for chunk in (raw or "").split(","):
        tag = re.sub(r"\s+", " ", chunk.strip())[:24]
        if tag and tag.lower() not in {item.lower() for item in seen}:
            seen.append(tag)
        if len(seen) >= 8:
            break
    return ",".join(seen)


def validate_image(data: bytes, ext: str) -> bool:
    if ext in {".jpg", ".jpeg"}:
        return data.startswith(b"\xff\xd8\xff")
    if ext == ".png":
        return data.startswith(b"\x89PNG\r\n\x1a\n")
    if ext == ".gif":
        return data.startswith(b"GIF8")
    if ext == ".webp":
        return len(data) > 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    return False


def parse_multipart(body: bytes, boundary: bytes) -> tuple[dict[str, str], dict[str, dict]]:
    fields: dict[str, str] = {}
    files: dict[str, dict] = {}
    marker = b"--" + boundary
    for chunk in body.split(marker)[1:]:
        if chunk.startswith(b"--"):
            break
        if chunk.startswith(b"\r\n"):
            chunk = chunk[2:]
        if chunk.endswith(b"\r\n"):
            chunk = chunk[:-2]
        head, separator, payload = chunk.partition(b"\r\n\r\n")
        if not separator:
            continue
        headers: dict[str, str] = {}
        for line in head.split(b"\r\n"):
            if b":" in line:
                key, value = line.split(b":", 1)
                headers[key.strip().lower().decode("latin-1")] = value.strip().decode(
                    "latin-1", errors="replace"
                )
        disposition = headers.get("content-disposition", "")
        name_match = re.search(r'name="([^"]*)"', disposition)
        if not name_match:
            continue
        name = name_match.group(1)
        filename_match = re.search(r'filename="([^"]*)"', disposition)
        if filename_match:
            files[name] = {
                "filename": Path(filename_match.group(1)).name,
                "content_type": headers.get("content-type", "application/octet-stream"),
                "data": payload,
            }
        else:
            fields[name] = payload.decode("utf-8", errors="replace")
    return fields, files


class Handler(BaseHTTPRequestHandler):
    server_version = "FLHub/1.0"
    protocol_version = "HTTP/1.1"

    # -- infrastructure ---------------------------------------------------
    def log_message(self, fmt: str, *args) -> None:
        print(f"[{self.log_date_time_string()}] {fmt % args}")

    def do_GET(self) -> None:
        self.dispatch("GET")

    def do_POST(self) -> None:
        self.dispatch("POST")

    def do_PATCH(self) -> None:
        self.dispatch("PATCH")

    def do_DELETE(self) -> None:
        self.dispatch("DELETE")

    def dispatch(self, method: str) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        self._body = b""
        try:
            if path.startswith("/api/"):
                if method in {"POST", "PATCH", "DELETE"}:
                    length = int(self.headers.get("Content-Length") or 0)
                    if length > MAX_UPLOAD_BODY:
                        self.close_connection = True
                        raise ApiError(413, "Файл слишком большой (максимум 180 МБ)")
                    self._body = self.rfile.read(length) if length else b""
                self.check_csrf(method)
                self.handle_api(method, path, parse_qs(parsed.query))
            elif path.startswith("/media/"):
                self.handle_media(path)
            elif path.startswith("/download/"):
                self.handle_download(path)
            else:
                self.handle_static(path)
        except ApiError as error:
            if path.startswith("/api/"):
                self.send_json({"error": error.message}, error.status)
            else:
                self.send_text(error.message, error.status)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception:
            traceback.print_exc()
            try:
                self.send_json({"error": "Внутренняя ошибка сервера"}, 500)
            except Exception:
                pass

    def check_csrf(self, method: str) -> None:
        if method == "GET":
            return
        if self.headers.get("X-Requested-With") != "fetch":
            raise ApiError(403, "Недостаточно прав для этого запроса")
        origin = self.headers.get("Origin")
        if origin:
            host = self.headers.get("Host", "")
            if urlparse(origin).netloc != host:
                raise ApiError(403, "Запрос с неверного источника")

    def read_json(self) -> dict:
        raw = self._body or b"{}"
        if len(raw) > MAX_JSON_BODY:
            raise ApiError(413, "Слишком большой запрос")
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ApiError(400, "Некорректный JSON")
        if not isinstance(data, dict):
            raise ApiError(400, "Ожидается JSON-объект")
        return data

    def send_json(self, payload, status: int = 200, cookie: str | None = None) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        self.wfile.write(body)

    def send_text(self, message: str, status: int = 200) -> None:
        body = message.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def current_user(self, conn):
        cookie_header = self.headers.get("Cookie", "")
        if not cookie_header:
            return None
        try:
            jar = SimpleCookie()
            jar.load(cookie_header)
        except Exception:
            return None
        morsel = jar.get(SESSION_COOKIE)
        if not morsel:
            return None
        cutoff = (datetime.now(timezone.utc) - timedelta(days=SESSION_DAYS)).replace(
            microsecond=0
        ).isoformat()
        return conn.execute(
            "SELECT u.* FROM sessions s JOIN users u ON u.id = s.user_id "
            "WHERE s.token = ? AND s.created_at >= ?",
            (morsel.value, cutoff),
        ).fetchone()

    def create_session(self, conn, user_id: int) -> str:
        token = security.new_token()
        conn.execute(
            "INSERT INTO sessions (token, user_id, created_at) VALUES (?, ?, ?)",
            (token, user_id, now_iso()),
        )
        return token

    @staticmethod
    def session_cookie(token: str) -> str:
        return (
            f"{SESSION_COOKIE}={token}; Path=/; HttpOnly; SameSite=Lax; "
            f"Max-Age={SESSION_DAYS * 86400}"
        )

    @staticmethod
    def clear_cookie() -> str:
        return f"{SESSION_COOKIE}=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0"

    # -- API --------------------------------------------------------------
    def handle_api(self, method: str, path: str, query: dict) -> None:
        conn = db.connect()
        try:
            user = self.current_user(conn)
            viewer_id = user["id"] if user else None

            if method == "GET":
                if path == "/api/me":
                    self.send_json({"user": public_user(user) if user else None})
                    return
                if path == "/api/stats":
                    self.send_json(self.build_stats(conn))
                    return
                if path == "/api/authors":
                    self.handle_authors(conn, query)
                    return
                if path == "/api/items":
                    self.handle_items(conn, query, viewer_id)
                    return

                match = re.fullmatch(r"/api/items/(\d+)", path)
                if match:
                    self.handle_item(conn, int(match.group(1)), viewer_id)
                    return

                match = re.fullmatch(r"/api/items/(\d+)/comments", path)
                if match:
                    self.handle_comments_list(conn, int(match.group(1)))
                    return

                match = re.fullmatch(r"/api/users/([A-Za-z0-9_]+)", path)
                if match:
                    self.handle_profile(conn, match.group(1), viewer_id)
                    return

                raise ApiError(404, "Не найдено")

            if method == "POST":
                if path == "/api/register":
                    self.handle_register(conn)
                    return
                if path == "/api/login":
                    self.handle_login(conn)
                    return
                if path == "/api/logout":
                    self.handle_logout(conn, user)
                    return
                if path == "/api/items":
                    self.handle_upload(conn, user)
                    return

                match = re.fullmatch(r"/api/items/(\d+)/like", path)
                if match:
                    self.handle_like(conn, int(match.group(1)), user)
                    return

                match = re.fullmatch(r"/api/items/(\d+)/play", path)
                if match:
                    self.handle_play(conn, int(match.group(1)))
                    return

                match = re.fullmatch(r"/api/items/(\d+)/comments", path)
                if match:
                    self.handle_comment_create(conn, int(match.group(1)), user)
                    return

                raise ApiError(404, "Не найдено")

            if method == "PATCH":
                if path == "/api/me":
                    self.handle_profile_update(conn, user)
                    return
                raise ApiError(404, "Не найдено")

            if method == "DELETE":
                match = re.fullmatch(r"/api/items/(\d+)", path)
                if match:
                    self.handle_item_delete(conn, int(match.group(1)), user)
                    return
                raise ApiError(404, "Не найдено")

            raise ApiError(405, "Метод не поддерживается")
        finally:
            conn.close()

    # -- read endpoints ---------------------------------------------------
    def build_stats(self, conn) -> dict:
        row = conn.execute(
            "SELECT (SELECT COUNT(*) FROM users) AS users, "
            "(SELECT COUNT(*) FROM items) AS items, "
            "(SELECT COALESCE(SUM(downloads), 0) FROM items) AS downloads, "
            "(SELECT COALESCE(SUM(plays), 0) FROM items) AS plays"
        ).fetchone()
        categories = {key: 0 for key in CATEGORIES}
        for item in conn.execute("SELECT category, COUNT(*) AS n FROM items GROUP BY category"):
            categories[item["category"]] = item["n"]
        return {
            "users": row["users"],
            "items": row["items"],
            "downloads": row["downloads"],
            "plays": row["plays"],
            "categories": categories,
        }

    def handle_authors(self, conn, query: dict) -> None:
        limit = max(1, min(12, int(query.get("limit", ["4"])[0] or 4)))
        rows = conn.execute(
            "SELECT u.id, u.username, u.bio, u.avatar_color, u.created_at, "
            "COUNT(i.id) AS item_count, COALESCE(SUM(i.downloads), 0) AS downloads, "
            "COALESCE(SUM(i.plays), 0) AS plays "
            "FROM users u JOIN items i ON i.author_id = u.id "
            "GROUP BY u.id ORDER BY downloads DESC, item_count DESC, u.created_at ASC LIMIT ?",
            (limit,),
        ).fetchall()
        self.send_json({"authors": [dict(row) for row in rows]})

    def handle_items(self, conn, query: dict, viewer_id: int | None) -> None:
        category = query.get("category", [""])[0]
        if category and category not in CATEGORIES:
            raise ApiError(400, "Неизвестная категория")
        genre = clean_text(query.get("genre", [""])[0], 40)
        search = clean_text(query.get("q", [""])[0], 80)
        author = clean_text(query.get("author", [""])[0], 24)
        featured = query.get("featured", [""])[0]
        sort = query.get("sort", ["new"])[0]
        if sort not in SORTS:
            sort = "new"
        try:
            limit = max(1, min(60, int(query.get("limit", [str(PAGE_SIZE)])[0])))
            offset = max(0, int(query.get("offset", ["0"])[0]))
        except ValueError:
            raise ApiError(400, "Некорректная пагинация")

        where: list[str] = []
        params: list = []
        if category:
            where.append("i.category = ?")
            params.append(category)
        if genre:
            where.append("i.genre = ?")
            params.append(genre)
        if author:
            where.append("u.username = ? COLLATE NOCASE")
            params.append(author)
        if featured in {"1", "true"}:
            where.append("i.featured = 1")
        if search:
            like = f"%{search}%"
            where.append(
                "(i.title LIKE ? OR i.description LIKE ? OR i.tags LIKE ? OR u.username LIKE ?)"
            )
            params.extend([like, like, like, like])
        clause = f"WHERE {' AND '.join(where)}" if where else ""

        order = {
            "new": "i.created_at DESC",
            "popular": "(likes_count * 4 + i.downloads * 2 + i.plays * 0.25) DESC, i.created_at DESC",
            "downloads": "i.downloads DESC, i.created_at DESC",
        }[sort]

        rows = conn.execute(
            "SELECT i.*, u.username, u.avatar_color, "
            "(SELECT COUNT(*) FROM likes l WHERE l.item_id = i.id) AS likes_count, "
            "(SELECT COUNT(*) FROM comments c WHERE c.item_id = i.id) AS comments_count "
            "FROM items i JOIN users u ON u.id = i.author_id "
            f"{clause} ORDER BY {order} LIMIT ? OFFSET ?",
            (*params, limit, offset),
        ).fetchall()
        total = conn.execute(
            "SELECT COUNT(*) AS n FROM items i JOIN users u ON u.id = i.author_id "
            f"{clause}",
            params,
        ).fetchone()["n"]
        liked_ids = self.liked_ids(conn, viewer_id, [row["id"] for row in rows])
        items = [
            item_dict(row, row["id"] in liked_ids, viewer_id)
            for row in rows
        ]
        self.send_json({"items": items, "total": total})

    @staticmethod
    def liked_ids(conn, viewer_id: int | None, item_ids: list[int]) -> set[int]:
        if not viewer_id or not item_ids:
            return set()
        placeholders = ",".join("?" for _ in item_ids)
        rows = conn.execute(
            f"SELECT item_id FROM likes WHERE user_id = ? AND item_id IN ({placeholders})",
            (viewer_id, *item_ids),
        ).fetchall()
        return {row["item_id"] for row in rows}

    def fetch_item(self, conn, item_id: int):
        return conn.execute(
            "SELECT i.*, u.username, u.avatar_color, "
            "(SELECT COUNT(*) FROM likes l WHERE l.item_id = i.id) AS likes_count, "
            "(SELECT COUNT(*) FROM comments c WHERE c.item_id = i.id) AS comments_count "
            "FROM items i JOIN users u ON u.id = i.author_id WHERE i.id = ?",
            (item_id,),
        ).fetchone()

    def handle_item(self, conn, item_id: int, viewer_id: int | None) -> None:
        row = self.fetch_item(conn, item_id)
        if not row:
            raise ApiError(404, "Работа не найдена")
        liked = bool(
            viewer_id
            and conn.execute(
                "SELECT 1 FROM likes WHERE item_id = ? AND user_id = ?",
                (item_id, viewer_id),
            ).fetchone()
        )
        self.send_json({"item": item_dict(row, liked, viewer_id)})

    def handle_comments_list(self, conn, item_id: int) -> None:
        if not conn.execute("SELECT 1 FROM items WHERE id = ?", (item_id,)).fetchone():
            raise ApiError(404, "Работа не найдена")
        rows = conn.execute(
            "SELECT c.*, u.username, u.avatar_color FROM comments c "
            "JOIN users u ON u.id = c.user_id WHERE c.item_id = ? "
            "ORDER BY c.created_at ASC",
            (item_id,),
        ).fetchall()
        self.send_json({"comments": [comment_dict(row) for row in rows]})

    def handle_profile(self, conn, username: str, viewer_id: int | None) -> None:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ? COLLATE NOCASE", (username,)
        ).fetchone()
        if not row:
            raise ApiError(404, "Пользователь не найден")
        stats = conn.execute(
            "SELECT COUNT(i.id) AS items, COALESCE(SUM(i.downloads), 0) AS downloads, "
            "COALESCE(SUM(i.plays), 0) AS plays, "
            "(SELECT COUNT(*) FROM likes l JOIN items li ON li.id = l.item_id "
            " WHERE li.author_id = u.id) AS likes_received "
            "FROM users u LEFT JOIN items i ON i.author_id = u.id "
            "WHERE u.id = ? GROUP BY u.id",
            (row["id"],),
        ).fetchone()
        payload = public_user(row)
        payload.update(
            {
                "stats": {
                    "items": stats["items"],
                    "downloads": stats["downloads"],
                    "plays": stats["plays"],
                    "likes": stats["likes_received"],
                },
                "is_me": bool(viewer_id == row["id"]),
            }
        )
        self.send_json({"user": payload})

    # -- auth -------------------------------------------------------------
    def handle_register(self, conn) -> None:
        data = self.read_json()
        username = clean_text(str(data.get("username", "")), 24)
        email = clean_text(str(data.get("email", "")), 120).lower()
        password = str(data.get("password", ""))
        if not USERNAME_RE.match(username):
            raise ApiError(400, "Имя: 3–24 символа, латиница, цифры и _")
        if not EMAIL_RE.match(email):
            raise ApiError(400, "Введите корректный email")
        if len(password) < 8 or len(password) > 128:
            raise ApiError(400, "Пароль должен быть от 8 до 128 символов")
        existing = conn.execute(
            "SELECT 1 FROM users WHERE username = ? COLLATE NOCASE OR email = ? COLLATE NOCASE",
            (username, email),
        ).fetchone()
        if existing:
            raise ApiError(409, "Такое имя или email уже заняты")
        color = AVATAR_COLORS[sum(username.lower().encode()) % len(AVATAR_COLORS)]
        cursor = conn.execute(
            "INSERT INTO users (username, email, password_hash, bio, avatar_color, created_at) "
            "VALUES (?, ?, ?, '', ?, ?)",
            (username, email, security.hash_password(password), color, now_iso()),
        )
        token = self.create_session(conn, cursor.lastrowid)
        conn.commit()
        row = conn.execute("SELECT * FROM users WHERE id = ?", (cursor.lastrowid,)).fetchone()
        self.send_json(
            {"user": public_user(row)}, 201, self.session_cookie(token)
        )

    def handle_login(self, conn) -> None:
        data = self.read_json()
        identifier = clean_text(str(data.get("identifier", "")), 120)
        password = str(data.get("password", ""))
        if not identifier or not password:
            raise ApiError(400, "Заполните все поля")
        row = conn.execute(
            "SELECT * FROM users WHERE username = ? COLLATE NOCASE OR email = ? COLLATE NOCASE",
            (identifier, identifier),
        ).fetchone()
        if not row or not security.verify_password(password, row["password_hash"]):
            raise ApiError(401, "Неверное имя или пароль")
        cutoff = (datetime.now(timezone.utc) - timedelta(days=SESSION_DAYS)).replace(
            microsecond=0
        ).isoformat()
        conn.execute("DELETE FROM sessions WHERE created_at < ?", (cutoff,))
        token = self.create_session(conn, row["id"])
        conn.commit()
        self.send_json({"user": public_user(row)}, 200, self.session_cookie(token))

    def handle_logout(self, conn, user) -> None:
        cookie_header = self.headers.get("Cookie", "")
        if cookie_header:
            try:
                jar = SimpleCookie()
                jar.load(cookie_header)
                morsel = jar.get(SESSION_COOKIE)
                if morsel:
                    conn.execute("DELETE FROM sessions WHERE token = ?", (morsel.value,))
                    conn.commit()
            except Exception:
                pass
        self.send_json({"ok": True}, 200, self.clear_cookie())

    def require_user(self, user):
        if not user:
            raise ApiError(401, "Нужно войти в аккаунт")
        return user

    def handle_profile_update(self, conn, user) -> None:
        user = self.require_user(user)
        data = self.read_json()
        bio = clean_text(str(data.get("bio", "")), 280)
        color = str(data.get("avatar_color", "") or user["avatar_color"])
        if not COLOR_RE.match(color):
            raise ApiError(400, "Некорректный цвет")
        conn.execute("UPDATE users SET bio = ?, avatar_color = ? WHERE id = ?", (bio, color, user["id"]))
        conn.commit()
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user["id"],)).fetchone()
        self.send_json({"user": public_user(row)})

    # -- uploads ----------------------------------------------------------
    def handle_upload(self, conn, user) -> None:
        user = self.require_user(user)
        content_type = self.headers.get("Content-Type", "")
        match = re.search(r"boundary=(?:\"([^\"]+)\"|([^;]+))", content_type)
        if "multipart/form-data" not in content_type or not match:
            raise ApiError(400, "Ожидается multipart/form-data")
        boundary = (match.group(1) or match.group(2) or "").encode("latin-1")
        body = self._body
        if not body:
            raise ApiError(400, "Пустой запрос")
        fields, files = parse_multipart(body, boundary)

        category = fields.get("category", "")
        if category not in CATEGORIES:
            raise ApiError(400, "Выберите категорию")
        title = clean_text(fields.get("title", ""), 120)
        description = clean_text(fields.get("description", ""), 4000)
        genre = clean_text(fields.get("genre", ""), 40)
        music_key = clean_text(fields.get("key", ""), 20)
        tags = parse_tags(fields.get("tags", ""))
        bpm = None
        raw_bpm = (fields.get("bpm") or "").strip()
        if raw_bpm:
            try:
                bpm = int(raw_bpm)
            except ValueError:
                raise ApiError(400, "BPM должен быть числом")
            if not 20 <= bpm <= 300:
                raise ApiError(400, "BPM должен быть от 20 до 300")
        if len(title) < 3:
            raise ApiError(400, "Название должно быть не короче 3 символов")

        main_file = files.get("file")
        if not main_file or not main_file["data"]:
            raise ApiError(400, "Прикрепите файл")
        original_name = clean_text(main_file["filename"], 160) or "file"
        extension = Path(original_name).suffix.lower()
        allowed = CATEGORY_EXT[category]
        if extension not in allowed:
            raise ApiError(
                400,
                "Неподдерживаемый формат файла: " + (extension or "без расширения"),
            )

        cover_file = files.get("cover")
        cover_ext = ""
        if cover_file and cover_file["data"]:
            cover_ext = Path(cover_file["filename"]).suffix.lower()
            if cover_ext not in IMAGE_EXT:
                raise ApiError(400, "Обложка: JPG, PNG, WEBP или GIF")
            if len(cover_file["data"]) > 8 * 1024 * 1024:
                raise ApiError(400, "Обложка больше 8 МБ")
            if not validate_image(cover_file["data"], cover_ext):
                raise ApiError(400, "Файл обложки повреждён")

        stored_name = f"{secrets.token_hex(12)}{extension}"
        stored_path = db.UPLOAD_DIR / stored_name
        stored_path.write_bytes(main_file["data"])

        duration = None
        audio_path = ""
        if category == "music":
            audio_path = stored_name
            if extension == ".wav":
                try:
                    with wave.open(str(stored_path), "rb") as handle:
                        duration = round(handle.getnframes() / handle.getframerate(), 1)
                except wave.Error:
                    duration = None

        if cover_ext:
            cover_name = f"upload_{secrets.token_hex(10)}{cover_ext}"
            (db.COVER_DIR / cover_name).write_bytes(cover_file["data"])
        else:
            cover_name = f"auto_{secrets.token_hex(10)}.svg"
            (db.COVER_DIR / cover_name).write_text(
                art.generate_cover_svg(title, category, stored_name), encoding="utf-8"
            )

        cursor = conn.execute(
            "INSERT INTO items (author_id, category, title, description, genre, bpm, "
            "music_key, tags, cover_path, file_path, file_name, file_size, audio_path, "
            "duration, plays, downloads, featured, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0, ?)",
            (
                user["id"], category, title, description, genre, bpm, music_key, tags,
                cover_name, stored_name, original_name, len(main_file["data"]),
                audio_path, duration, now_iso(),
            ),
        )
        conn.commit()
        row = self.fetch_item(conn, cursor.lastrowid)
        self.send_json({"item": item_dict(row, False, user["id"])}, 201)

    def handle_item_delete(self, conn, item_id: int, user) -> None:
        user = self.require_user(user)
        row = conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
        if not row:
            raise ApiError(404, "Работа не найдена")
        if row["author_id"] != user["id"]:
            raise ApiError(403, "Можно удалять только свои работы")
        conn.execute("DELETE FROM items WHERE id = ?", (item_id,))
        conn.commit()
        for folder, name in ((db.UPLOAD_DIR, row["file_path"]), (db.COVER_DIR, row["cover_path"])):
            if name:
                path = folder / name
                if path.is_file():
                    path.unlink(missing_ok=True)
        self.send_json({"ok": True})

    # -- interactions -----------------------------------------------------
    def handle_like(self, conn, item_id: int, user) -> None:
        user = self.require_user(user)
        if not conn.execute("SELECT 1 FROM items WHERE id = ?", (item_id,)).fetchone():
            raise ApiError(404, "Работа не найдена")
        exists = conn.execute(
            "SELECT 1 FROM likes WHERE item_id = ? AND user_id = ?", (item_id, user["id"])
        ).fetchone()
        if exists:
            conn.execute(
                "DELETE FROM likes WHERE item_id = ? AND user_id = ?", (item_id, user["id"])
            )
            liked = False
        else:
            conn.execute(
                "INSERT INTO likes (item_id, user_id, created_at) VALUES (?, ?, ?)",
                (item_id, user["id"], now_iso()),
            )
            liked = True
        conn.commit()
        count = conn.execute(
            "SELECT COUNT(*) AS n FROM likes WHERE item_id = ?", (item_id,)
        ).fetchone()["n"]
        self.send_json({"liked": liked, "likes": count})

    def handle_play(self, conn, item_id: int) -> None:
        row = conn.execute("SELECT id, audio_path FROM items WHERE id = ?", (item_id,)).fetchone()
        if not row:
            raise ApiError(404, "Работа не найдена")
        if row["audio_path"]:
            conn.execute("UPDATE items SET plays = plays + 1 WHERE id = ?", (item_id,))
            conn.commit()
        plays = conn.execute(
            "SELECT plays FROM items WHERE id = ?", (item_id,)
        ).fetchone()["plays"]
        self.send_json({"plays": plays})

    def handle_comment_create(self, conn, item_id: int, user) -> None:
        user = self.require_user(user)
        if not conn.execute("SELECT 1 FROM items WHERE id = ?", (item_id,)).fetchone():
            raise ApiError(404, "Работа не найдена")
        data = self.read_json()
        body = clean_text(str(data.get("body", "")), 1000)
        if not body:
            raise ApiError(400, "Комментарий не может быть пустым")
        cursor = conn.execute(
            "INSERT INTO comments (item_id, user_id, body, created_at) VALUES (?, ?, ?, ?)",
            (item_id, user["id"], body, now_iso()),
        )
        conn.commit()
        row = conn.execute(
            "SELECT c.*, u.username, u.avatar_color FROM comments c "
            "JOIN users u ON u.id = c.user_id WHERE c.id = ?",
            (cursor.lastrowid,),
        ).fetchone()
        self.send_json({"comment": comment_dict(row)}, 201)

    # -- files ------------------------------------------------------------
    def handle_media(self, path: str) -> None:
        parts = path.split("/")
        if len(parts) != 4:
            raise ApiError(404, "Файл не найден")
        folder, filename = parts[2], parts[3]
        if folder not in {"covers", "uploads"} or Path(filename).name != filename:
            raise ApiError(404, "Файл не найден")
        directory = db.COVER_DIR if folder == "covers" else db.UPLOAD_DIR
        target = directory / filename
        if not target.is_file():
            raise ApiError(404, "Файл не найден")
        content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        if filename.endswith(".svg"):
            content_type = "image/svg+xml"
        self.serve_file(target, content_type)

    def handle_download(self, path: str) -> None:
        match = re.fullmatch(r"/download/(\d+)", path)
        if not match:
            raise ApiError(404, "Файл не найден")
        item_id = int(match.group(1))
        conn = db.connect()
        try:
            row = conn.execute(
                "SELECT file_path, file_name FROM items WHERE id = ?", (item_id,)
            ).fetchone()
            if not row or not row["file_path"]:
                raise ApiError(404, "Файл не найден")
            target = db.UPLOAD_DIR / row["file_path"]
            if not target.is_file():
                raise ApiError(404, "Файл не найден")
            conn.execute("UPDATE items SET downloads = downloads + 1 WHERE id = ?", (item_id,))
            conn.commit()
            self.serve_file(target, "application/octet-stream", download_name=row["file_name"])
        finally:
            conn.close()

    def handle_static(self, path: str) -> None:
        if path in ("/", "/index.html"):
            target = STATIC_DIR / "index.html"
        elif path.startswith("/static/"):
            target = (STATIC_DIR / path[len("/static/"):]).resolve()
            try:
                target.relative_to(STATIC_DIR.resolve())
            except ValueError:
                raise ApiError(404, "Файл не найден")
        else:
            target = STATIC_DIR / "index.html"
        if not target.is_file():
            raise ApiError(404, "Файл не найден")
        content_type = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        if content_type.startswith("text/") or content_type in {
            "application/javascript", "application/json", "image/svg+xml"
        }:
            content_type += "; charset=utf-8"
        self.serve_file(target, content_type, cache="no-cache" if target.name == "index.html" else "public, max-age=3600")

    def serve_file(self, path: Path, content_type: str, cache: str = "public, max-age=604800",
                   download_name: str | None = None) -> None:
        size = path.stat().st_size
        start, end = 0, size - 1
        status = 200
        range_header = self.headers.get("Range")
        if range_header:
            match = RANGE_RE.match(range_header.strip())
            if not match:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{size}")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            raw_start, raw_end = match.groups()
            if raw_start:
                start = int(raw_start)
            if raw_end:
                end = min(int(raw_end), size - 1)
            if start >= size or start > end:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{size}")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            status = 206

        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", cache)
        self.send_header("X-Content-Type-Options", "nosniff")
        if status == 206:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Content-Length", str(end - start + 1))
        if download_name:
            fallback = re.sub(r"[^A-Za-z0-9._-]", "_", download_name) or "download"
            self.send_header(
                "Content-Disposition",
                f"attachment; filename=\"{fallback}\"; filename*=UTF-8''{quote(download_name)}",
            )
        self.end_headers()
        remaining = end - start + 1
        with path.open("rb") as handle:
            handle.seek(start)
            while remaining > 0:
                chunk = handle.read(min(65536, remaining))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)


def main() -> None:
    parser = argparse.ArgumentParser(description="FL HUB demo server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reseed", action="store_true", help="пересоздать демо-контент")
    args = parser.parse_args()

    db.init_db()
    seed.seed(force=args.reseed)

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    server.daemon_threads = True
    print()
    print("  ███████╗██╗     ██╗  ██╗██╗   ██╗██████╗ ")
    print("  ██╔════╝██║     ██║  ██║██║   ██║██╔══██╗")
    print("  █████╗  ██║     ███████║██║   ██║██████╔╝")
    print("  ██╔══╝  ██║     ██╔══██║██║   ██║██╔══██╗")
    print("  ██║     ███████╗██║  ██║╚██████╔╝██████╔╝")
    print("  ╚═╝     ╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚═════╝ ")
    print()
    print(f"  FL HUB запущен: http://{args.host}:{args.port}")
    print(f"  Демо-вход: nightdrive / {seed.DEMO_PASSWORD}")
    print("  Ctrl+C — остановить сервер")
    print()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nFL HUB: сервер остановлен.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
