const api = window.__TAURI__.core;

const setup = document.querySelector("#setup");
const lock = document.querySelector("#lock");
const dashboard = document.querySelector("#dashboard");
const status = document.querySelector("#status");
const status2 = document.querySelector("#status2");

async function init() {
  const configured = await api.invoke("has_setup");
  if (!configured) {
    setup.hidden = false;
    return;
  }
  lock.hidden = false;
}

function showDashboard(url) {
  lock.hidden = true;
  setup.hidden = true;
  dashboard.hidden = false;
  dashboard.src = `${url}/`;
}

document.querySelector("#setupBtn").addEventListener("click", async () => {
  status.textContent = "";
  const config = {
    nine_router_url: document.querySelector("#router").value.trim(),
    nine_router_api_key: document.querySelector("#apikey").value.trim(),
    default_model: document.querySelector("#model").value.trim(),
  };
  const password = document.querySelector("#master").value;
  try {
    await api.invoke("save_config", { config, password });
    const url = await api.invoke("launch_backend", { config });
    showDashboard(url);
  } catch (error) {
    status.textContent = String(error);
  }
});

document.querySelector("#unlockBtn").addEventListener("click", async () => {
  status2.textContent = "";
  try {
    await api.invoke("unlock", { password: document.querySelector("#password").value });
    const url = await api.invoke("launch_backend");
    showDashboard(url);
  } catch (error) {
    status2.textContent = String(error);
  }
});

init();
