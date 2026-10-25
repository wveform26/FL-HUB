"""PostgreSQL storage for FL HUB."""
from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from pathlib import Path

try:
    import psycopg2
    import psycopg2.extras
    from psycopg2 import sql as pg_sql
except ImportError:  # pragma: no cover
    raise SystemExit(
        "FL HUB: не найден psycopg2. Установите зависимости: pip install -r requirements.txt"
    )

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(
    os.environ.get("FLHUB_DATA_DIR", str(BASE_DIR / "data"))
).expanduser()
UPLOAD_DIR = DATA_DIR / "uploads"
COVER_DIR = DATA_DIR / "covers"

# Параметры подключения (переопределяются через окружение)
_PG_HOST = os.environ.get("PGHOST", "localhost")
_PG_PORT = int(os.environ.get("PGPORT", "5432"))
_PG_DB = os.environ.get("PGDATABASE", "flhub")
_PG_USER = os.environ.get("PGUSER", "postgres")
_PG_PASS = os.environ.get("PGPASSWORD", "")

# Таблицы с SERIAL-колонкой id — для них поддерживается lastrowid.
_ID_TABLES = {"users", "items", "comments"}
_INSERT_RE = re.compile(r"^\s*INSERT\s+INTO\s+(\w+)", re.IGNORECASE)


def _dsn_kwargs():
    """Параметры подключения: DATABASE_URL или PGHOST/PGPORT/PGDATABASE/PGUSER/PGPASSWORD."""
    database_url = os.environ.get("DATABASE_URL")
    if database_url:
        return database_url
    return {
        "host": _PG_HOST,
        "port": _PG_PORT,
        "dbname": _PG_DB,
        "user": _PG_USER,
        "password": _PG_PASS,
        "connect_timeout": int(os.environ.get("PGCONNECT_TIMEOUT", "10")),
    }


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id             SERIAL PRIMARY KEY,
    username       TEXT NOT NULL,
    email          TEXT NOT NULL,
    password_hash  TEXT NOT NULL,
    bio            TEXT NOT NULL DEFAULT '',
    avatar_color   TEXT NOT NULL DEFAULT '#ff7a1a',
    email_verified BOOLEAN NOT NULL DEFAULT TRUE,
    created_at     TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username ON users (LOWER(username));
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users (LOWER(email));

CREATE TABLE IF NOT EXISTS sessions (
    token      TEXT PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS items (
    id          SERIAL PRIMARY KEY,
    author_id   INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    category    TEXT NOT NULL,
    title       TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    genre       TEXT NOT NULL DEFAULT '',
    bpm         INTEGER,
    music_key   TEXT NOT NULL DEFAULT '',
    tags        TEXT NOT NULL DEFAULT '',
    cover_path  TEXT NOT NULL DEFAULT '',
    file_path   TEXT NOT NULL DEFAULT '',
    file_name   TEXT NOT NULL DEFAULT '',
    file_size   INTEGER NOT NULL DEFAULT 0,
    audio_path  TEXT NOT NULL DEFAULT '',
    duration    REAL,
    plays       INTEGER NOT NULL DEFAULT 0,
    downloads   INTEGER NOT NULL DEFAULT 0,
    featured    INTEGER NOT NULL DEFAULT 0,
    access      TEXT NOT NULL DEFAULT 'free',
    demo_path   TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS email_codes (
    id         SERIAL PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    code_hash  TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    attempts   INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS likes (
    item_id    INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    PRIMARY KEY (item_id, user_id)
);

CREATE TABLE IF NOT EXISTS comments (
    id         SERIAL PRIMARY KEY,
    item_id    INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    body       TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_items_category ON items(category);
CREATE INDEX IF NOT EXISTS idx_items_author ON items(author_id);
CREATE INDEX IF NOT EXISTS idx_items_created ON items(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_comments_item ON comments(item_id);
CREATE INDEX IF NOT EXISTS idx_email_codes_user ON email_codes(user_id);
CREATE INDEX IF NOT EXISTS idx_email_codes_expiry ON email_codes(expires_at);
"""

# Миграции для баз, созданных до появления этих полей. Каждая выполняется
# отдельно и безопасна при повторном запуске.
MIGRATIONS = [
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verified BOOLEAN NOT NULL DEFAULT TRUE",
]


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class _CursorProxy:
    """Результат execute: fetchone/fetchall + lastrowid для INSERT."""

    def __init__(self, cur, lastrowid=None):
        self._cur = cur
        self.lastrowid = lastrowid

    def fetchone(self):
        return self._cur.fetchone()

    def fetchall(self):
        return self._cur.fetchall()

    def fetchmany(self, size=None):
        return self._cur.fetchmany(size)

    def __iter__(self):
        return iter(self._cur.fetchall())


class _Conn:
    """Совместимость с SQLite-стилем: conn.execute(sql, args).fetchone().

    - `?`-плейсхолдеры транслируются в `%s`
    - `INSERT` в таблицы с id автоматически получает `RETURNING id`,
      доступный как `cursor.lastrowid`
    - `commit()` — no-op (соединение в autocommit)
    """

    def __init__(self, conn, cur):
        self._conn = conn
        self._cur = cur
        self.lastrowid = None

    def execute(self, query, args=None):
        text = str(query).replace("?", "%s")
        match = _INSERT_RE.match(text)
        wants_id = bool(match) and match.group(1).lower() in _ID_TABLES
        if wants_id and "RETURNING" not in text.upper():
            text += " RETURNING id"
        self._cur.execute(text, args)
        last_id = None
        if wants_id:
            row = self._cur.fetchone()
            if row:
                last_id = row["id"]
        self.lastrowid = last_id
        return _CursorProxy(self._cur, last_id)

    def executemany(self, query, args_list):
        return self._cur.executemany(str(query).replace("?", "%s"), args_list)

    def fetchone(self):
        return self._cur.fetchone()

    def fetchall(self):
        return self._cur.fetchall()

    def fetchmany(self, size=None):
        return self._cur.fetchmany(size)

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        try:
            self._cur.close()
        finally:
            self._conn.close()


def connect() -> _Conn:
    """Возвращает соединение PostgreSQL в SQLite-подобной обёртке."""
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    COVER_DIR.mkdir(parents=True, exist_ok=True)
    dsn = _dsn_kwargs()
    conn = psycopg2.connect(dsn) if isinstance(dsn, str) else psycopg2.connect(**dsn)
    conn.set_session(autocommit=True)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    return _Conn(conn, cur)


def init_db() -> None:
    """Создаёт базу (если не существует) и инициализирует таблицы."""
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    COVER_DIR.mkdir(parents=True, exist_ok=True)

    dsn = _dsn_kwargs()

    # 1. Создаём базу, если её нет (подключаемся к служебной базе postgres).
    if isinstance(dsn, dict):
        admin_kwargs = dict(dsn, dbname="postgres")
        admin_url = None
        db_name = dsn["dbname"]
    else:
        admin_url = _swap_db_in_url(dsn, "postgres")
        admin_kwargs = None
        db_name = _db_name_from_url(dsn)

    conn = psycopg2.connect(admin_url) if admin_url else psycopg2.connect(**admin_kwargs)
    conn.set_session(autocommit=True)
    cur = conn.cursor()
    try:
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db_name,))
        if not cur.fetchone():
            cur.execute(pg_sql.SQL("CREATE DATABASE {}").format(pg_sql.Identifier(db_name)))
            print(f"FL HUB: создана база данных '{db_name}'.")
    finally:
        cur.close()
        conn.close()

    # 2. Создаём таблицы и догоняем схему старых баз.
    conn2 = psycopg2.connect(dsn) if isinstance(dsn, str) else psycopg2.connect(**dsn)
    conn2.set_session(autocommit=True)
    cur2 = conn2.cursor()
    try:
        cur2.execute(SCHEMA)
        for statement in MIGRATIONS:
            cur2.execute(statement)
    finally:
        cur2.close()
        conn2.close()


def _db_name_from_url(url: str) -> str:
    """Достаёт имя базы из postgresql://user:pass@host:port/dbname."""
    match = re.search(r"/([^/?]+)(\?.*)?$", url)
    return match.group(1) if match else "postgres"


def _swap_db_in_url(url: str, new_db: str) -> str:
    """Меняет имя базы в URL на new_db."""
    return re.sub(r"/([^/?]+)(\?.*)?$", "/" + new_db + r"\2", url)
