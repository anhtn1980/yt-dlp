const $ = (id) => document.getElementById(id);
const form = $("download-form");
const urlInput = $("video-url");
let pollTimer = null;
let activeTask = null;

function toast(message) {
  const node = $("toast");
  node.textContent = message;
  node.classList.add("show");
  setTimeout(() => node.classList.remove("show"), 2200);
}
function formatDuration(seconds) {
  if (seconds == null) return "Thời lượng chưa rõ";
  const n = Math.max(0, Math.floor(seconds));
  return [Math.floor(n / 3600), Math.floor((n % 3600) / 60), n % 60]
    .filter((v, i) => v > 0 || i > 0).map(v => String(v).padStart(2, "0")).join(":");
}
function formatSpeed(bytesPerSecond) {
  if (!bytesPerSecond) return "";
  const units = ["B/s", "KB/s", "MB/s", "GB/s"];
  let value = bytesPerSecond, index = 0;
  while (value >= 1024 && index < units.length - 1) { value /= 1024; index++; }
  return value.toFixed(1) + " " + units[index];
}
async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || "Request failed");
  return data;
}
async function inspectUrl(url) {
  const preview = $("preview");
  preview.classList.add("hidden");
  const info = await api("/api/video/info", { method: "POST", body: JSON.stringify({ url }) });
  $("video-title").textContent = info.title || "Video";
  $("video-meta").textContent = [info.uploader, formatDuration(info.duration)].filter(Boolean).join(" · ");
  if (info.thumbnail) {
    $("thumbnail").src = info.thumbnail;
    $("thumbnail").classList.remove("hidden");
  } else {
    $("thumbnail").removeAttribute("src");
  }
  preview.classList.remove("hidden");
}
function showTask() {
  $("task-panel").classList.remove("hidden");
  $("task-error").classList.add("hidden");
  $("download-link").classList.add("hidden");
}
async function startDownload(url, format, button) {
  if (pollTimer) clearInterval(pollTimer);
  document.querySelectorAll(".action").forEach(el => el.disabled = true);
  button.dataset.original = button.innerHTML;
  button.querySelector("span:not(.action-icon)").textContent = "STARTING…";
  showTask();
  $("task-title").textContent = format.toUpperCase() + " download";
  $("task-state").textContent = "Queued";
  $("progress-message").textContent = "Đang tạo tác vụ…";
  $("progress-value").textContent = "0%";
  $("progress-bar").style.width = "0%";
  try {
    const result = await api("/api/download/" + format, {
      method: "POST", body: JSON.stringify({ url })
    });
    activeTask = result.task_id;
    pollTimer = setInterval(pollTask, 1000);
    await pollTask();
  } catch (error) {
    $("task-error").textContent = error.message;
    $("task-error").classList.remove("hidden");
    $("task-state").textContent = "Error";
    document.querySelectorAll(".action").forEach(el => el.disabled = false);
    button.innerHTML = button.dataset.original;
  }
}
async function pollTask() {
  if (!activeTask) return;
  try {
    const task = await api("/api/download/status/" + activeTask);
    const percent = task.percent == null ? 0 : Math.max(0, Math.min(100, task.percent));
    $("progress-bar").style.width = percent + "%";
    $("progress-value").textContent = Math.round(percent) + "%";
    const details = [formatSpeed(task.speed), task.eta != null ? "ETA " + formatDuration(task.eta) : ""].filter(Boolean);
    $("progress-message").textContent = [task.message || task.state, ...details].join(" · ");
    $("task-state").textContent = task.state;
    if (task.state === "completed") {
      clearInterval(pollTimer);
      $("download-link").href = "/api/download/file/" + activeTask;
      $("download-link").classList.remove("hidden");
      document.querySelectorAll(".action").forEach(el => el.disabled = false);
      document.querySelectorAll(".action").forEach(el => {
        const format = el.dataset.format;
        el.innerHTML = format === "mp4"
          ? '<span class="action-icon">▣</span><span>GET MP4</span><small>Video</small>'
          : '<span class="action-icon">♫</span><span>GET MP3</span><small>Audio</small>';
      });
      toast("File đã sẵn sàng!");
    } else if (task.state === "error") {
      clearInterval(pollTimer);
      $("task-error").textContent = task.error || "Download failed.";
      $("task-error").classList.remove("hidden");
      document.querySelectorAll(".action").forEach(el => el.disabled = false);
      document.querySelectorAll(".action").forEach(el => {
        el.innerHTML = el.dataset.format === "mp4"
          ? '<span class="action-icon">▣</span><span>GET MP4</span><small>Video</small>'
          : '<span class="action-icon">♫</span><span>GET MP3</span><small>Audio</small>';
      });
    }
  } catch (error) {
    clearInterval(pollTimer);
    $("task-error").textContent = error.message;
    $("task-error").classList.remove("hidden");
  }
}
form.addEventListener("submit", async event => {
  event.preventDefault();
  const button = event.submitter;
  const url = urlInput.value.trim();
  if (!url) return;
  try {
    await inspectUrl(url);
    await startDownload(url, button.dataset.format, button);
  } catch (error) {
    toast(error.message);
    $("task-panel").classList.remove("hidden");
    $("task-error").textContent = error.message;
    $("task-error").classList.remove("hidden");
  }
});
$("paste-btn").addEventListener("click", async () => {
  try {
    urlInput.value = await navigator.clipboard.readText();
    urlInput.focus();
  } catch {
    toast("Trình duyệt chưa cấp quyền đọc clipboard.");
  }
});
