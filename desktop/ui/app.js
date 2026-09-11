const invoke = window.__TAURI__.core.invoke;
const dashboard = document.querySelector("#dashboard");
const lock = document.querySelector("#lock");
const password = document.querySelector("#password");
const pairing = document.querySelector("#pairing");
const copy = document.querySelector("#copy");
const submit = document.querySelector("#submit");
const status = document.querySelector("#status");

async function openDashboard() {
  lock.hidden = true;
  dashboard.hidden = false;
  dashboard.src = "http://127.0.0.1:39421/";
}

async function initialize() {
  if (await invoke("has_pairing")) {
    copy.textContent = "Masukkan password desktop untuk membuka aplikasi.";
    pairing.hidden = true;
    submit.textContent = "UNLOCK DESKTOP";
  }
}

submit.addEventListener("click", async () => {
  status.textContent = "";
  try {
    if (pairing.hidden) await invoke("unlock", { password: password.value });
    else await invoke("pair", { code: pairing.value.trim(), password: password.value });
    await openDashboard();
  } catch (error) {
    status.textContent = String(error);
  }
});

initialize();
