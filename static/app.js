const authSection = document.getElementById("auth-section");
const appSection = document.getElementById("app-section");
const registerForm = document.getElementById("register-form");
const loginForm = document.getElementById("login-form");
const logoutButton = document.getElementById("logout-button");
const taskForm = document.getElementById("task-form");
const taskIdInput = document.getElementById("task-id");
const descriptionInput = document.getElementById("description");
const deadlineInput = document.getElementById("deadline");
const searchInput = document.getElementById("search");
const statusFilter = document.getElementById("status-filter");
const sortOrder = document.getElementById("sort-order");
const taskList = document.getElementById("task-list");
const emptyState = document.getElementById("empty-state");
const welcomeMessage = document.getElementById("welcome-message");
const statusMessage = document.getElementById("status-message");
const reminderPanel = document.getElementById("reminder-panel");
const reminderList = document.getElementById("reminder-list");
const cancelEditButton = document.getElementById("cancel-edit-button");
const taskFormTitle = document.getElementById("task-form-title");
const saveTaskButton = document.getElementById("save-task-button");

let notificationPermissionRequested = false;

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    credentials: "same-origin",
    ...options,
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(body.error || "Request failed.");
  }
  return body;
}

function setMessage(message) {
  statusMessage.textContent = message;
}

function resetTaskForm() {
  taskIdInput.value = "";
  taskFormTitle.textContent = "Add task";
  saveTaskButton.textContent = "Save task";
  cancelEditButton.classList.add("hidden");
  taskForm.reset();
}

function formatDeadline(deadline) {
  return new Date(deadline).toLocaleString();
}

function maybeNotify(reminders) {
  if (!("Notification" in window) || reminders.length === 0) {
    return;
  }
  if (Notification.permission === "granted") {
    const first = reminders[0];
    new Notification("Todo reminder", {
      body: `${first.description} is due by ${formatDeadline(first.deadline)}.`,
    });
    return;
  }
  if (Notification.permission === "default" && !notificationPermissionRequested) {
    notificationPermissionRequested = true;
    Notification.requestPermission();
  }
}

async function loadReminders() {
  const { reminders } = await api("/api/reminders");
  reminderList.innerHTML = "";
  reminderPanel.classList.toggle("hidden", reminders.length === 0);
  reminders.forEach((task) => {
    const item = document.createElement("li");
    item.textContent = `${task.description} — due ${formatDeadline(task.deadline)}`;
    reminderList.appendChild(item);
  });
  maybeNotify(reminders);
}

function createTaskItem(task) {
  const item = document.createElement("li");
  item.className = `task-item${task.completed ? " completed" : ""}`;

  const checkbox = document.createElement("input");
  checkbox.type = "checkbox";
  checkbox.checked = task.completed;
  checkbox.addEventListener("change", async () => {
    await api(`/api/tasks/${task.id}`, {
      method: "PUT",
      body: JSON.stringify({ completed: checkbox.checked }),
    });
    setMessage("Task updated.");
    await refreshTasks();
  });

  const details = document.createElement("div");
  details.className = "task-details";
  const title = document.createElement("strong");
  title.textContent = task.description;
  const deadline = document.createElement("span");
  deadline.textContent = `Due: ${formatDeadline(task.deadline)}`;
  const state = document.createElement("span");
  state.textContent = task.completed ? "Completed" : "Pending";
  details.append(title, deadline, state);

  const buttons = document.createElement("div");
  buttons.className = "actions";
  const editButton = document.createElement("button");
  editButton.type = "button";
  editButton.className = "secondary";
  editButton.textContent = "Edit";
  editButton.addEventListener("click", () => {
    taskIdInput.value = task.id;
    descriptionInput.value = task.description;
    deadlineInput.value = task.deadline;
    taskFormTitle.textContent = "Edit task";
    saveTaskButton.textContent = "Save changes";
    cancelEditButton.classList.remove("hidden");
  });

  const deleteButton = document.createElement("button");
  deleteButton.type = "button";
  deleteButton.className = "danger";
  deleteButton.textContent = "Delete";
  deleteButton.addEventListener("click", async () => {
    await api(`/api/tasks/${task.id}`, { method: "DELETE" });
    setMessage("Task deleted.");
    await refreshTasks();
  });

  buttons.append(editButton, deleteButton);
  item.append(checkbox, details, buttons);
  return item;
}

async function refreshTasks() {
  const params = new URLSearchParams({
    search: searchInput.value,
    status: statusFilter.value,
    sort: sortOrder.value,
  });
  const { tasks } = await api(`/api/tasks?${params.toString()}`);
  taskList.innerHTML = "";
  emptyState.classList.toggle("hidden", tasks.length > 0);
  tasks.forEach((task) => taskList.appendChild(createTaskItem(task)));
  await loadReminders();
}

async function handleAuth(form, endpoint) {
  const payload = Object.fromEntries(new FormData(form).entries());
  const body = await api(endpoint, { method: "POST", body: JSON.stringify(payload) });
  welcomeMessage.textContent = `Welcome, ${body.username}!`;
  authSection.classList.add("hidden");
  appSection.classList.remove("hidden");
  form.reset();
  setMessage(endpoint === "/api/register" ? "Account created." : "Logged in.");
  await refreshTasks();
}

async function bootstrap() {
  const session = await api("/api/me");
  if (!session.authenticated) {
    authSection.classList.remove("hidden");
    appSection.classList.add("hidden");
    return;
  }
  welcomeMessage.textContent = `Welcome, ${session.username}!`;
  authSection.classList.add("hidden");
  appSection.classList.remove("hidden");
  await refreshTasks();
}

registerForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    await handleAuth(registerForm, "/api/register");
  } catch (error) {
    setMessage(error.message);
  }
});

loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    await handleAuth(loginForm, "/api/login");
  } catch (error) {
    setMessage(error.message);
  }
});

logoutButton.addEventListener("click", async () => {
  await api("/api/logout", { method: "POST", body: JSON.stringify({}) });
  resetTaskForm();
  appSection.classList.add("hidden");
  authSection.classList.remove("hidden");
  setMessage("Logged out.");
});

taskForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    const payload = {
      description: descriptionInput.value,
      deadline: deadlineInput.value,
    };
    const taskId = taskIdInput.value;
    if (taskId) {
      await api(`/api/tasks/${taskId}`, { method: "PUT", body: JSON.stringify(payload) });
      setMessage("Task updated.");
    } else {
      await api("/api/tasks", { method: "POST", body: JSON.stringify(payload) });
      setMessage("Task created.");
    }
    resetTaskForm();
    await refreshTasks();
  } catch (error) {
    setMessage(error.message);
  }
});

cancelEditButton.addEventListener("click", resetTaskForm);
searchInput.addEventListener("input", () => refreshTasks().catch((error) => setMessage(error.message)));
statusFilter.addEventListener("change", () => refreshTasks().catch((error) => setMessage(error.message)));
sortOrder.addEventListener("change", () => refreshTasks().catch((error) => setMessage(error.message)));

bootstrap().catch((error) => setMessage(error.message));
setInterval(() => {
  if (!appSection.classList.contains("hidden")) {
    loadReminders().catch(() => {});
  }
}, 60000);
