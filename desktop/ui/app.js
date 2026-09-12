const api = window.__TAURI__.core;
const setup = document.querySelector("#setup");
const lock = document.querySelector("#lock");
const dashboard = document.querySelector("#dashboard");
const status = document.querySelector("#status");
const status2 = document.querySelector("#status2");
const setupButton = document.querySelector("#setupBtn");
const unlockButton = document.querySelector("#unlockBtn");

async function init() {
  if (await api.invoke("has_setup")) lock.hidden = false;
  else setup.hidden = false;
}
function setLoading(button, message, target) { button.disabled = true; button.textContent = "MENYIAPKAN..."; target.textContent = message; }
function clearLoading(button, label, target) { button.disabled = false; button.textContent = label; target.textContent = ""; }
function showDashboard(url) { lock.hidden = true; setup.hidden = true; dashboard.hidden = false; dashboard.src = `${url}/`; }

setupButton.addEventListener("click", async () => {
  const password = document.querySelector("#master").value;
  setLoading(setupButton, "Menjalankan database dan data market lokal. Pertama kali bisa membutuhkan sekitar satu menit.", status);
  try { showDashboard(await api.invoke("setup_and_launch", { password })); }
  catch (error) { clearLoading(setupButton, "SAVE & LAUNCH", status); status.textContent = String(error); }
});
unlockButton.addEventListener("click", async () => {
  setLoading(unlockButton, "Menjalankan layanan lokal...", status2);
  try { await api.invoke("unlock", { password: document.querySelector("#password").value }); showDashboard(await api.invoke("launch_backend")); }
  catch (error) { clearLoading(unlockButton, "UNLOCK", status2); status2.textContent = String(error); }
});

window.addEventListener("message", async (event) => {
  if (event.origin !== "http://127.0.0.1:8200") return;
  if (event.data?.type === "stocks-desktop-load-ai") {
    dashboard.contentWindow.postMessage({ type: "stocks-desktop-ai-config", config: await api.invoke("load_config") }, event.origin);
    return;
  }
  if (event.data?.type === "stocks-desktop-restart") {
    await api.invoke("restart_app");
    return;
  }
  if (event.data?.type !== "stocks-desktop-save-ai") return;
  try {
    await api.invoke("save_config", { config: event.data.config });
    dashboard.contentWindow.postMessage({ type: "stocks-desktop-ai-saved" }, event.origin);
  } catch (error) {
    dashboard.contentWindow.postMessage({ type: "stocks-desktop-ai-error", error: String(error) }, event.origin);
  }
});
init();
