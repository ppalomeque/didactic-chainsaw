import hashlib
import hmac
import json
import os
import secrets
import sqlite3
from datetime import UTC, datetime, timedelta
from http import cookies
from pathlib import Path
from urllib.parse import parse_qs
from wsgiref.simple_server import make_server

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "todo.db"
SESSION_COOKIE = "todo_session"


def initialize_database(db_path: Path = DB_PATH) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS todos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                description TEXT NOT NULL,
                deadline TEXT NOT NULL,
                completed INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
            """
        )
        conn.commit()


def get_connection(db_path: Path = DB_PATH) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    return connection


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    derived = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=16384, r=8, p=1)
    return f"{salt.hex()}${derived.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    salt_hex, hash_hex = stored_hash.split("$", 1)
    salt = bytes.fromhex(salt_hex)
    derived = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=16384, r=8, p=1)
    return hmac.compare_digest(derived.hex(), hash_hex)


def parse_json_body(environ: dict) -> dict:
    length = int(environ.get("CONTENT_LENGTH") or 0)
    raw_body = environ["wsgi.input"].read(length) if length else b""
    if not raw_body:
        return {}
    return json.loads(raw_body.decode("utf-8"))


def json_response(start_response, status: str, payload: dict, headers=None):
    body = json.dumps(payload).encode("utf-8")
    response_headers = [("Content-Type", "application/json; charset=utf-8"), ("Content-Length", str(len(body)))]
    if headers:
        response_headers.extend(headers)
    start_response(status, response_headers)
    return [body]


def text_response(start_response, status: str, content: bytes, content_type: str):
    start_response(status, [("Content-Type", content_type), ("Content-Length", str(len(content)))])
    return [content]


def get_cookie(environ: dict, name: str) -> str | None:
    raw_cookie = environ.get("HTTP_COOKIE")
    if not raw_cookie:
        return None
    jar = cookies.SimpleCookie()
    jar.load(raw_cookie)
    morsel = jar.get(name)
    return morsel.value if morsel else None


def build_session_cookie(session_id: str, expires: str | None = None) -> tuple[str, str]:
    jar = cookies.SimpleCookie()
    jar[SESSION_COOKIE] = session_id
    jar[SESSION_COOKIE]["httponly"] = True
    jar[SESSION_COOKIE]["path"] = "/"
    jar[SESSION_COOKIE]["samesite"] = "Lax"
    if expires:
        jar[SESSION_COOKIE]["expires"] = expires
    return "Set-Cookie", jar.output(header="").strip()


def get_authenticated_user(environ: dict, db_path: Path) -> sqlite3.Row | None:
    session_id = get_cookie(environ, SESSION_COOKIE)
    if not session_id:
        return None
    with get_connection(db_path) as conn:
        return conn.execute(
            """
            SELECT users.id, users.username
            FROM sessions
            JOIN users ON users.id = sessions.user_id
            WHERE sessions.id = ?
            """,
            (session_id,),
        ).fetchone()


def require_user(environ: dict, start_response, db_path: Path):
    user = get_authenticated_user(environ, db_path)
    if user is None:
        return None, json_response(start_response, "401 Unauthorized", {"error": "Authentication required."})
    return user, None


def normalize_deadline(deadline: str) -> str:
    parsed = datetime.fromisoformat(deadline)
    return parsed.replace(second=0, microsecond=0).isoformat(timespec="minutes")


def serialize_task(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "description": row["description"],
        "deadline": row["deadline"],
        "completed": bool(row["completed"]),
    }


def handle_register(environ: dict, start_response, db_path: Path):
    payload = parse_json_body(environ)
    username = (payload.get("username") or "").strip()
    password = payload.get("password") or ""
    if not username or not password:
        return json_response(start_response, "400 Bad Request", {"error": "Username and password are required."})

    session_id = secrets.token_hex(24)
    timestamp = datetime.now(UTC).isoformat()
    try:
        with get_connection(db_path) as conn:
            cursor = conn.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (username, hash_password(password)),
            )
            conn.execute(
                "INSERT INTO sessions (id, user_id, created_at) VALUES (?, ?, ?)",
                (session_id, cursor.lastrowid, timestamp),
            )
            conn.commit()
    except sqlite3.IntegrityError:
        return json_response(start_response, "409 Conflict", {"error": "Username already exists."})

    headers = [build_session_cookie(session_id)]
    return json_response(start_response, "201 Created", {"username": username}, headers=headers)


def handle_login(environ: dict, start_response, db_path: Path):
    payload = parse_json_body(environ)
    username = (payload.get("username") or "").strip()
    password = payload.get("password") or ""
    if not username or not password:
        return json_response(start_response, "400 Bad Request", {"error": "Username and password are required."})

    with get_connection(db_path) as conn:
        user = conn.execute("SELECT id, username, password_hash FROM users WHERE username = ?", (username,)).fetchone()
        if user is None or not verify_password(password, user["password_hash"]):
            return json_response(start_response, "401 Unauthorized", {"error": "Invalid credentials."})
        session_id = secrets.token_hex(24)
        conn.execute(
            "INSERT INTO sessions (id, user_id, created_at) VALUES (?, ?, ?)",
            (session_id, user["id"], datetime.now(UTC).isoformat()),
        )
        conn.commit()

    headers = [build_session_cookie(session_id)]
    return json_response(start_response, "200 OK", {"username": user["username"]}, headers=headers)


def handle_logout(environ: dict, start_response, db_path: Path):
    session_id = get_cookie(environ, SESSION_COOKIE)
    if session_id:
        with get_connection(db_path) as conn:
            conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            conn.commit()
    headers = [build_session_cookie("", expires="Thu, 01 Jan 1970 00:00:00 GMT")]
    return json_response(start_response, "200 OK", {"message": "Logged out."}, headers=headers)


def handle_current_user(environ: dict, start_response, db_path: Path):
    user = get_authenticated_user(environ, db_path)
    if user is None:
        return json_response(start_response, "200 OK", {"authenticated": False})
    return json_response(start_response, "200 OK", {"authenticated": True, "username": user["username"]})


def list_tasks(user_id: int, db_path: Path, query: dict[str, list[str]]) -> list[dict]:
    search = (query.get("search", [""])[0]).strip().lower()
    status = query.get("status", ["all"])[0]
    sort = query.get("sort", ["deadline_asc"])[0]

    clauses = ["user_id = ?"]
    params: list[object] = [user_id]
    if search:
        clauses.append("LOWER(description) LIKE ?")
        params.append(f"%{search}%")
    if status == "completed":
        clauses.append("completed = 1")
    elif status == "pending":
        clauses.append("completed = 0")

    order_by = {
        "deadline_desc": "deadline DESC",
        "status": "completed ASC, deadline ASC",
    }.get(sort, "deadline ASC")

    with get_connection(db_path) as conn:
        rows = conn.execute(
            f"SELECT id, description, deadline, completed FROM todos WHERE {' AND '.join(clauses)} ORDER BY {order_by}",
            params,
        ).fetchall()
    return [serialize_task(row) for row in rows]


def handle_tasks(environ: dict, start_response, db_path: Path):
    user, unauthorized = require_user(environ, start_response, db_path)
    if unauthorized:
        return unauthorized

    method = environ["REQUEST_METHOD"]
    if method == "GET":
        query = parse_qs(environ.get("QUERY_STRING", ""), keep_blank_values=True)
        return json_response(start_response, "200 OK", {"tasks": list_tasks(user["id"], db_path, query)})

    if method == "POST":
        payload = parse_json_body(environ)
        description = (payload.get("description") or "").strip()
        deadline = payload.get("deadline") or ""
        if not description or not deadline:
            return json_response(start_response, "400 Bad Request", {"error": "Description and deadline are required."})
        try:
            normalized_deadline = normalize_deadline(deadline)
        except ValueError:
            return json_response(start_response, "400 Bad Request", {"error": "Deadline must be a valid date and time."})
        timestamp = datetime.now(UTC).isoformat()
        with get_connection(db_path) as conn:
            cursor = conn.execute(
                """
                INSERT INTO todos (user_id, description, deadline, completed, created_at, updated_at)
                VALUES (?, ?, ?, 0, ?, ?)
                """,
                (user["id"], description, normalized_deadline, timestamp, timestamp),
            )
            task = conn.execute(
                "SELECT id, description, deadline, completed FROM todos WHERE id = ? AND user_id = ?",
                (cursor.lastrowid, user["id"]),
            ).fetchone()
            conn.commit()
        return json_response(start_response, "201 Created", {"task": serialize_task(task)})

    return json_response(start_response, "405 Method Not Allowed", {"error": "Method not allowed."})


def handle_task_detail(environ: dict, start_response, db_path: Path, task_id: int):
    user, unauthorized = require_user(environ, start_response, db_path)
    if unauthorized:
        return unauthorized

    method = environ["REQUEST_METHOD"]
    if method == "PUT":
        payload = parse_json_body(environ)
        fields = []
        params: list[object] = []
        if "description" in payload:
            description = (payload.get("description") or "").strip()
            if not description:
                return json_response(start_response, "400 Bad Request", {"error": "Description cannot be empty."})
            fields.append("description = ?")
            params.append(description)
        if "deadline" in payload:
            try:
                fields.append("deadline = ?")
                params.append(normalize_deadline(payload.get("deadline") or ""))
            except ValueError:
                return json_response(start_response, "400 Bad Request", {"error": "Deadline must be a valid date and time."})
        if "completed" in payload:
            fields.append("completed = ?")
            params.append(1 if payload.get("completed") else 0)
        if not fields:
            return json_response(start_response, "400 Bad Request", {"error": "No valid fields were provided."})
        fields.append("updated_at = ?")
        params.append(datetime.now(UTC).isoformat())
        params.extend([task_id, user["id"]])
        with get_connection(db_path) as conn:
            cursor = conn.execute(
                f"UPDATE todos SET {', '.join(fields)} WHERE id = ? AND user_id = ?",
                params,
            )
            if cursor.rowcount == 0:
                return json_response(start_response, "404 Not Found", {"error": "Task not found."})
            task = conn.execute(
                "SELECT id, description, deadline, completed FROM todos WHERE id = ? AND user_id = ?",
                (task_id, user["id"]),
            ).fetchone()
            conn.commit()
        return json_response(start_response, "200 OK", {"task": serialize_task(task)})

    if method == "DELETE":
        with get_connection(db_path) as conn:
            cursor = conn.execute("DELETE FROM todos WHERE id = ? AND user_id = ?", (task_id, user["id"]))
            conn.commit()
        if cursor.rowcount == 0:
            return json_response(start_response, "404 Not Found", {"error": "Task not found."})
        return json_response(start_response, "200 OK", {"message": "Task deleted."})

    return json_response(start_response, "405 Method Not Allowed", {"error": "Method not allowed."})


def handle_reminders(environ: dict, start_response, db_path: Path):
    user, unauthorized = require_user(environ, start_response, db_path)
    if unauthorized:
        return unauthorized

    now = datetime.now().replace(second=0, microsecond=0)
    upcoming = (now + timedelta(hours=24)).isoformat(timespec="minutes")
    with get_connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT id, description, deadline, completed
            FROM todos
            WHERE user_id = ? AND completed = 0 AND deadline >= ? AND deadline <= ?
            ORDER BY deadline ASC
            """,
            (user["id"], now.isoformat(timespec="minutes"), upcoming),
        ).fetchall()
    return json_response(start_response, "200 OK", {"reminders": [serialize_task(row) for row in rows]})


def serve_static(path: str, start_response, static_dir: Path):
    asset_name = "index.html" if path in {"", "/"} else path.lstrip("/")
    allowed_assets = {
        "index.html": static_dir / "index.html",
        "app.js": static_dir / "app.js",
        "styles.css": static_dir / "styles.css",
    }
    target = allowed_assets.get(asset_name)
    if target is None or not target.is_file():
        return text_response(start_response, "404 Not Found", b"Not found", "text/plain; charset=utf-8")
    content_type = {
        ".html": "text/html; charset=utf-8",
        ".js": "application/javascript; charset=utf-8",
        ".css": "text/css; charset=utf-8",
    }.get(target.suffix, "application/octet-stream")
    return text_response(start_response, "200 OK", target.read_bytes(), content_type)


def create_app(db_path: Path = DB_PATH, static_dir: Path = STATIC_DIR):
    initialize_database(db_path)

    def application(environ, start_response):
        path = environ.get("PATH_INFO", "/")
        method = environ.get("REQUEST_METHOD", "GET")
        try:
            if path == "/api/register" and method == "POST":
                return handle_register(environ, start_response, db_path)
            if path == "/api/login" and method == "POST":
                return handle_login(environ, start_response, db_path)
            if path == "/api/logout" and method == "POST":
                return handle_logout(environ, start_response, db_path)
            if path == "/api/me" and method == "GET":
                return handle_current_user(environ, start_response, db_path)
            if path == "/api/tasks":
                return handle_tasks(environ, start_response, db_path)
            if path.startswith("/api/tasks/"):
                task_id = int(path.rsplit("/", 1)[-1])
                return handle_task_detail(environ, start_response, db_path, task_id)
            if path == "/api/reminders" and method == "GET":
                return handle_reminders(environ, start_response, db_path)
            if path.startswith("/api/"):
                return json_response(start_response, "404 Not Found", {"error": "Not found."})
            return serve_static(path, start_response, static_dir)
        except ValueError:
            return json_response(start_response, "400 Bad Request", {"error": "Invalid request."})
        except json.JSONDecodeError:
            return json_response(start_response, "400 Bad Request", {"error": "Invalid JSON payload."})

    return application


def run_server(host: str = "127.0.0.1", port: int = 8000):
    app = create_app()
    with make_server(host, port, app) as server:
        print(f"Todo app available at http://{host}:{port}")
        server.serve_forever()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    run_server(port=port)
