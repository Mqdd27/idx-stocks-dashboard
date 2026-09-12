use std::process::Child;
use std::sync::Mutex;

use argon2::{Argon2, PasswordHash, PasswordHasher, PasswordVerifier};
use keyring::Entry;
use rand::rngs::OsRng;
use serde::{Deserialize, Serialize};
use tauri::Manager;
use tauri::State as TauriState;

const SERVICE: &str = "id.mqdd.stocksidx";
const CONFIG_ACCOUNT: &str = "desktop-config";
const AUTH_ACCOUNT: &str = "desktop-auth";
const BACKEND_PORT: u16 = 8200;

#[derive(Serialize, Deserialize, Default, Clone)]
pub struct ProviderConfig {
    pub nine_router_url: String,
    pub nine_router_api_key: String,
    pub default_model: String,
}

struct Desktop {
    child: Mutex<Option<Child>>,
}

fn auth_keyring() -> Result<Entry, String> {
    Entry::new(SERVICE, AUTH_ACCOUNT).map_err(|e| e.to_string())
}

fn config_keyring() -> Result<Entry, String> {
    Entry::new(SERVICE, CONFIG_ACCOUNT).map_err(|e| e.to_string())
}

#[tauri::command]
fn has_setup() -> bool {
    config_keyring()
        .and_then(|entry| entry.get_password().map_err(|e| e.to_string()))
        .is_ok()
}

#[tauri::command]
fn load_config() -> Result<ProviderConfig, String> {
    let stored = config_keyring()?
        .get_password()
        .map_err(|_| "Konfigurasi belum dibuat.".to_string())?;
    serde_json::from_str(&stored).map_err(|e| e.to_string())
}

fn save_auth(password: &str) -> Result<(), String> {
    if password.len() < 12 {
        return Err("Password master minimal 12 karakter.".to_string());
    }
    let salt = argon2::password_hash::SaltString::generate(&mut OsRng);
    let hash = Argon2::default()
        .hash_password(password.as_bytes(), &salt)
        .map_err(|e| e.to_string())?
        .to_string();
    auth_keyring()?.set_password(&hash).map_err(|e| e.to_string())
}

#[tauri::command]
fn save_config(config: ProviderConfig, password: String) -> Result<(), String> {
    if config.nine_router_url.is_empty()
        || config.nine_router_api_key.is_empty()
        || config.default_model.is_empty()
    {
        return Err("Konfigurasi 9Router dan model wajib diisi.".to_string());
    }
    save_auth(&password)?;
    let serialized = serde_json::to_string(&config).map_err(|e| e.to_string())?;
    config_keyring()?.set_password(&serialized).map_err(|e| e.to_string())
}

#[tauri::command]
fn unlock(password: String) -> Result<(), String> {
    let stored = auth_keyring()?
        .get_password()
        .map_err(|_| "Belum ada password desktop.".to_string())?;
    let parsed = PasswordHash::new(&stored).map_err(|e| e.to_string())?;
    Argon2::default()
        .verify_password(password.as_bytes(), &parsed)
        .map_err(|_| "Password desktop salah.".to_string())
}

fn port_ready(port: u16) -> bool {
    std::net::TcpStream::connect(("127.0.0.1", port)).is_ok()
}

fn env_payload(config: &ProviderConfig, database_path: String, static_dir: String) -> serde_json::Value {
    serde_json::json!({
        "DATABASE_URL": format!("sqlite:///{database_path}"),
        "NINE_ROUTER_URL": config.nine_router_url,
        "NINE_ROUTER_API_KEY": config.nine_router_api_key,
        "DEFAULT_AI_MODEL": config.default_model,
        "OLLAMA_URL": "http://127.0.0.1:11434",
        "AI_TRADING_ENABLED": "true",
        "CORS_ALLOWED_ORIGINS": "http://127.0.0.1",
        "ADMIN_COOKIE_SECURE": "false",
        "DESKTOP_LOCAL_AUTH": "true",
        "DESKTOP_STATIC_DIR": static_dir,
        "DESKTOP_PORT": BACKEND_PORT.to_string(),
    })
}

#[tauri::command]
async fn launch_backend(app: tauri::AppHandle, state: TauriState<'_, Desktop>) -> Result<String, String> {
    if port_ready(BACKEND_PORT) {
        return Ok(format!("http://127.0.0.1:{BACKEND_PORT}"));
    }
    let config = load_config()?;
    let dir = app.path().app_data_dir().map_err(|e| e.to_string())?;
    std::fs::create_dir_all(&dir).map_err(|e| e.to_string())?;
    let env_path = dir.join("backend-env.json");
    let database_path = dir.join("stocks.db").to_string_lossy().to_string();
    let static_dir = app.path().resource_dir().map_err(|e| e.to_string())?.join("frontend").to_string_lossy().to_string();
    let env = env_payload(&config, database_path, static_dir);
    std::fs::write(&env_path, serde_json::to_string_pretty(&env).map_err(|e| e.to_string())?)
        .map_err(|e| e.to_string())?;

    let child = std::process::Command::new("stocks-backend")
        .arg(env_path)
        .spawn()
        .map_err(|e| format!("Gagal menjalankan backend lokal: {e}"))?;
    *state.child.lock().map_err(|_| "lock".to_string())? = Some(child);

    for _ in 0..120 {
        std::thread::sleep(std::time::Duration::from_millis(500));
        if port_ready(BACKEND_PORT) {
            return Ok(format!("http://127.0.0.1:{BACKEND_PORT}"));
        }
    }
    Err("Backend lokal tidak merespons dalam 60 detik.".to_string())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .manage(Desktop { child: Mutex::new(None) })
        .invoke_handler(tauri::generate_handler![
            has_setup,
            load_config,
            save_config,
            unlock,
            launch_backend
        ])
        .run(tauri::generate_context!())
        .expect("error while running desktop app");
}
