const api = window.__TAURI__.core;

const setup = document.querySelector("#setup");
const lock = document.querySelector("#lock");
const dashboard = document.querySelector("#dashboard");
const status = document.querySelector("#status");
const status2 = document.querySelector("#status2");
const setupButton = document.querySelector("#setupBtn");
const unlockButton = document.querySelector("#unlockBtn");

async function init() {
  const configured = await api.invoke("has_setup");
  if (!configured) {
    setup.hidden = false;
    return;
  }
  lock.hidden = false;
}

function setLoading(button, message, target) {
  button.disabled = true;
  button.textContent = "MENYIAPKAN...";
  target.textContent = message;
}

function clearLoading(button, label, target) {
  button.disabled = false;
  button.textContent = label;
  target.textContent = "";
}

function showDashboard(url) {
  lock.hidden = true;
  setup.hidden = true;
  dashboard.hidden = false;
  dashboard.src = `${url}/`;
}

setupButton.addEventListener("click", async () => {
  const config = {
    nine_router_url: document.querySelector("#router").value.trim(),
    nine_router_api_key: document.querySelector("#apikey").value.trim(),
    default_model: document.querySelector("#model").value.trim(),
  };
  const password = document.querySelector("#master").value;
  setLoading(setupButton, "Menjalankan database dan data market lokal. Pertama kali bisa membutuhkan sekitar satu menit.", status);
  try {
    const url = await api.invoke("setup_and_launch", { config, password });
    showDashboard(url);
  } catch (error) {
    clearLoading(setupButton, "SAVE & LAUNCH", status);
    status.textContent = String(error);
  }
});

unlockButton.addEventListener("click", async () => {
  setLoading(unlockButton, "Menjalankan layanan lokal...", status2);
  try {
    await api.invoke("unlock", { password: document.querySelector("#password").value });
    const url = await api.invoke("launch_backend");
    showDashboard(url);
  } catch (error) {
    clearLoading(unlockButton, "UNLOCK", status2);
    status2.textContent = String(error);
  }
});

init();
