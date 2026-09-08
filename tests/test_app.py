import io
import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from wsgiref.util import setup_testing_defaults

from app import create_app


class TodoAppTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name)
        self.static_dir = self.base_path / "static"
        self.static_dir.mkdir()
        (self.static_dir / "index.html").write_text("ok", encoding="utf-8")
        self.app = create_app(self.base_path / "todo.db", self.static_dir)

    def tearDown(self):
        self.temp_dir.cleanup()

    def request(self, method, path, body=None, cookie=None):
        payload = json.dumps(body).encode("utf-8") if body is not None else b""
        environ = {}
        setup_testing_defaults(environ)
        environ["REQUEST_METHOD"] = method
        if "?" in path:
            environ["PATH_INFO"], environ["QUERY_STRING"] = path.split("?", 1)
        else:
            environ["PATH_INFO"] = path
            environ["QUERY_STRING"] = ""
        environ["CONTENT_LENGTH"] = str(len(payload))
        environ["wsgi.input"] = io.BytesIO(payload)
        environ["CONTENT_TYPE"] = "application/json"
        if cookie:
            environ["HTTP_COOKIE"] = cookie

        captured = {}

        def start_response(status, headers):
            captured["status"] = status
            captured["headers"] = headers

        response = b"".join(self.app(environ, start_response))
        captured["body"] = json.loads(response.decode("utf-8")) if response else None
        return captured

    @staticmethod
    def cookie_from(headers):
        for key, value in headers:
            if key == "Set-Cookie":
                return value.split(";", 1)[0]
        return None

    def test_tasks_are_scoped_to_the_logged_in_user(self):
        register = self.request("POST", "/api/register", {"username": "alice", "password": "secret"})
        alice_cookie = self.cookie_from(register["headers"])
        self.request(
            "POST",
            "/api/tasks",
            {"description": "Alice task", "deadline": "2099-01-01T10:00"},
            cookie=alice_cookie,
        )

        other_user = self.request("POST", "/api/register", {"username": "bob", "password": "secret"})
        bob_cookie = self.cookie_from(other_user["headers"])
        tasks = self.request("GET", "/api/tasks", cookie=bob_cookie)

        self.assertEqual(tasks["status"], "200 OK")
        self.assertEqual(tasks["body"], {"tasks": []})

    def test_search_filter_sort_and_reminders(self):
        register = self.request("POST", "/api/register", {"username": "carol", "password": "secret"})
        cookie = self.cookie_from(register["headers"])
        reminder_deadline = (datetime.now().replace(second=0, microsecond=0) + timedelta(hours=2)).isoformat(timespec="minutes")
        create_a = self.request(
            "POST",
            "/api/tasks",
            {"description": "Prepare report", "deadline": "2099-01-02T10:00"},
            cookie=cookie,
        )
        task_id = create_a["body"]["task"]["id"]
        self.request(
            "POST",
            "/api/tasks",
            {"description": "Book travel", "deadline": reminder_deadline},
            cookie=cookie,
        )
        self.request(
            "PUT",
            f"/api/tasks/{task_id}",
            {"completed": True},
            cookie=cookie,
        )

        filtered = self.request("GET", "/api/tasks?search=book&status=pending&sort=deadline_asc", cookie=cookie)
        self.assertEqual(filtered["status"], "200 OK")
        self.assertEqual(len(filtered["body"]["tasks"]), 1)
        self.assertEqual(filtered["body"]["tasks"][0]["description"], "Book travel")

        reminders = self.request("GET", "/api/reminders", cookie=cookie)
        self.assertEqual(reminders["status"], "200 OK")
        self.assertEqual(len(reminders["body"]["reminders"]), 1)
        self.assertEqual(reminders["body"]["reminders"][0]["description"], "Book travel")


if __name__ == "__main__":
    unittest.main()
