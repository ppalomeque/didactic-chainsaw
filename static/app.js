const authSection = document.getElementById("auth-section");
const appSection = document.getElementById("app-section");
const registerForm = document.getElementById("register-form");
const loginForm = document.getElementById("login-form");
const authToggle = document.getElementById("auth-toggle");
const showLoginButton = document.getElementById("show-login-button");
const showRegisterButton = document.getElementById("show-register-button");
const authBackButtons = document.querySelectorAll(".auth-back-button");
const authMessage = document.getElementById("auth-message");
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
const pagination = document.getElementById("pagination");
const paginationStatus = document.getElementById("pagination-status");
const prevPageButton = document.getElementById("prev-page-button");
const nextPageButton = document.getElementById("next-page-button");

const TASKS_PER_PAGE = 5;
let currentPage = 1;
let allTasks = [];

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

let statusMessageTimeoutId = null;

function setMessage(message) {
  if (statusMessageTimeoutId) {
    clearTimeout(statusMessageTimeoutId);
    statusMessageTimeoutId = null;
  }
  if (!message) {
    statusMessage.textContent = "";
    statusMessage.classList.add("hidden");
    return;
  }
  statusMessage.textContent = message;
  statusMessage.classList.remove("hidden");
  statusMessageTimeoutId = setTimeout(() => {
    statusMessage.classList.add("hidden");
    statusMessageTimeoutId = null;
  }, 3000);
}

function setAuthMessage(message) {
  authMessage.textContent = message;
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

function renderTaskPage() {
  const totalPages = Math.max(1, Math.ceil(allTasks.length / TASKS_PER_PAGE));
  currentPage = Math.min(currentPage, totalPages);
  const start = (currentPage - 1) * TASKS_PER_PAGE;
  const pageTasks = allTasks.slice(start, start + TASKS_PER_PAGE);

  taskList.innerHTML = "";
  emptyState.classList.toggle("hidden", allTasks.length > 0);
  pageTasks.forEach((task) => taskList.appendChild(createTaskItem(task)));

  pagination.classList.toggle("hidden", allTasks.length === 0);
  paginationStatus.textContent = `Page ${currentPage} of ${totalPages}`;
  prevPageButton.disabled = currentPage <= 1;
  nextPageButton.disabled = currentPage >= totalPages;
}

async function refreshTasks() {
  const params = new URLSearchParams({
    search: searchInput.value,
    status: statusFilter.value,
    sort: sortOrder.value,
  });
  const { tasks } = await api(`/api/tasks?${params.toString()}`);
  allTasks = tasks;
  renderTaskPage();
  await loadReminders();
}

function showAuthForm(form) {
  authToggle.classList.add("hidden");
  registerForm.classList.add("hidden");
  loginForm.classList.add("hidden");
  form.classList.remove("hidden");
  setAuthMessage("");
}

function showAuthToggle() {
  registerForm.classList.add("hidden");
  loginForm.classList.add("hidden");
  authToggle.classList.remove("hidden");
  setAuthMessage("");
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
    showAuthToggle();
    return;
  }
  welcomeMessage.textContent = `Welcome, ${session.username}!`;
  authSection.classList.add("hidden");
  appSection.classList.remove("hidden");
  await refreshTasks();
}

showLoginButton.addEventListener("click", () => showAuthForm(loginForm));
showRegisterButton.addEventListener("click", () => showAuthForm(registerForm));
authBackButtons.forEach((button) => button.addEventListener("click", showAuthToggle));

registerForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    await handleAuth(registerForm, "/api/register");
  } catch (error) {
    setAuthMessage(error.message);
  }
});

loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    await handleAuth(loginForm, "/api/login");
  } catch (error) {
    setAuthMessage(error.message);
  }
});

logoutButton.addEventListener("click", async () => {
  await api("/api/logout", { method: "POST", body: JSON.stringify({}) });
  resetTaskForm();
  appSection.classList.add("hidden");
  authSection.classList.remove("hidden");
  showAuthToggle();
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
searchInput.addEventListener("input", () => {
  currentPage = 1;
  refreshTasks().catch((error) => setMessage(error.message));
});
statusFilter.addEventListener("change", () => {
  currentPage = 1;
  refreshTasks().catch((error) => setMessage(error.message));
});
sortOrder.addEventListener("change", () => {
  currentPage = 1;
  refreshTasks().catch((error) => setMessage(error.message));
});
prevPageButton.addEventListener("click", () => {
  currentPage -= 1;
  renderTaskPage();
});
nextPageButton.addEventListener("click", () => {
  currentPage += 1;
  renderTaskPage();
});

bootstrap().catch((error) => setMessage(error.message));
setInterval(() => {
  if (!appSection.classList.contains("hidden")) {
    loadReminders().catch(() => {});
  }
}, 60000);
