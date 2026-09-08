# didactic-chainsaw

A small local-first todo application with account-based task lists, deadlines, reminders, search, filtering, and editing.

## Features

- User registration and login
- Private per-user task lists backed by SQLite
- Create, edit, complete, and delete todo tasks
- Search tasks by keyword
- Filter tasks by completion status
- Sort tasks by deadline or completion status
- Upcoming deadline reminders for incomplete tasks due within 24 hours
- Browser-based client served by a lightweight Python API server

## Tech stack

- **Python 3 standard library** for the HTTP server, routing, password hashing, and tests
- **SQLite** for persistent local storage
- **Vanilla HTML, CSS, and JavaScript** for the browser client

This stack was chosen to keep the app easy to run on any developer machine without requiring extra package installation while still meeting the database-backed client-server requirement.

## Architecture

The application follows a simple client-server architecture:

- **Server (`/home/runner/work/didactic-chainsaw/didactic-chainsaw/app.py`)**
  - Serves the static frontend assets
  - Exposes JSON API endpoints for authentication, tasks, and reminders
  - Hashes passwords with `hashlib.scrypt`
  - Stores users, sessions, and tasks in SQLite
- **Client (`/home/runner/work/didactic-chainsaw/didactic-chainsaw/static/`)**
  - Provides forms for authentication and task management
  - Calls the server with `fetch()`
  - Shows task search, filtering, sorting, and reminder UI
- **Database (`/home/runner/work/didactic-chainsaw/didactic-chainsaw/data/todo.db`)**
  - Created automatically on first run
  - Persists data locally between server restarts

## Run locally

### Prerequisites

- Python 3.11 or newer

### Start the application

```bash
cd /home/runner/work/didactic-chainsaw/didactic-chainsaw
python app.py
```

The app will start at `http://127.0.0.1:8000`.

You can optionally choose a different port:

```bash
cd /home/runner/work/didactic-chainsaw/didactic-chainsaw
PORT=8080 python app.py
```

### Use the application

1. Open the app in your browser
2. Create an account or log in
3. Add tasks with descriptions and deadlines
4. Search, filter, sort, edit, complete, or delete tasks
5. Check the reminder panel for tasks due in the next 24 hours

## Run tests

```bash
cd /home/runner/work/didactic-chainsaw/didactic-chainsaw
python -m unittest discover -s tests -v
```
