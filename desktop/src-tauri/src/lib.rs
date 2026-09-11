use std::sync::{Arc, Mutex};

use argon2::{Argon2, PasswordHash, PasswordHasher, PasswordVerifier};
use axum::{body::Body, extract::State, http::{HeaderValue, Request, StatusCode}, response::Response, routing::any, Router};
use keyring::Entry;
use rand::rngs::OsRng;
use reqwest::Client;
use tauri::State as TauriState;
use tokio::net::TcpListener;

const SERVICE: &str = "id.mqdd.stocksidx";
const ACCOUNT: &str = "desktop-device-token";
const DASHBOARD: &str = "https://stocks.mqdd.my.id";

type Credential = Arc<Mutex<Option<String>>>;

struct DesktopState(Credential);

fn keyring() -> Result<Entry, String> {
    Entry::new(SERVICE, ACCOUNT).map_err(|error| error.to_string())
}

#[tauri::command]
async fn pair(code: String, password: String, state: TauriState<'_, DesktopState>) -> Result<(), String> {
    if password.len() < 12 {
        return Err("Password desktop minimal 12 karakter.".into());
    }
    let response = Client::new()
        .post(format!("{DASHBOARD}/api/desktop/pairings/redeem"))
        .json(&serde_json::json!({"code": code, "label": "Stocks IDX Desktop"}))
        .send()
        .await
        .map_err(|error| error.to_string())?;
    if !response.status().is_success() {
        return Err("Pairing code tidak valid atau sudah kedaluwarsa.".into());
    }
    let token = response
        .json::<serde_json::Value>()
        .await
        .map_err(|error| error.to_string())?["device_token"]
        .as_str()
        .ok_or("Server tidak mengembalikan credential desktop.")?
        .to_string();
    let salt = argon2::password_hash::SaltString::generate(&mut OsRng);
    let hash = Argon2::default()
        .hash_password(password.as_bytes(), &salt)
        .map_err(|error| error.to_string())?
        .to_string();
    keyring()?
        .set_password(&format!("{hash}\n{token}"))
        .map_err(|error| error.to_string())?;
    *state.0.lock().map_err(|_| "Desktop state lock failed")? = Some(token);
    Ok(())
}

#[tauri::command]
fn unlock(password: String, state: TauriState<'_, DesktopState>) -> Result<(), String> {
    let stored = keyring()?
        .get_password()
        .map_err(|_| "Desktop belum dipair.")?;
    let (hash, token) = stored.split_once('\n').ok_or("Credential desktop rusak.")?;
    let parsed = PasswordHash::new(hash).map_err(|error| error.to_string())?;
    Argon2::default()
        .verify_password(password.as_bytes(), &parsed)
        .map_err(|_| "Password desktop salah.")?;
    *state.0.lock().map_err(|_| "Desktop state lock failed")? = Some(token.to_string());
    Ok(())
}

#[tauri::command]
fn has_pairing() -> bool {
    keyring().and_then(|entry| entry.get_password().map_err(|error| error.to_string())).is_ok()
}

async fn proxy(State(token): State<Credential>, request: Request<Body>) -> Response {
    let path = request.uri().path_and_query().map(|value| value.as_str()).unwrap_or("/");
    let url = format!("{DASHBOARD}{path}");
    let method = request.method().clone();
    let body = axum::body::to_bytes(request.into_body(), 10 * 1024 * 1024).await.unwrap_or_default();
    let client = Client::new();
    let mut upstream = client.request(method, url).body(body.to_vec());
    if let Some(device_token) = token.lock().ok().and_then(|value| value.clone()) {
        upstream = upstream.header("Authorization", format!("Desktop {device_token}"));
    }
    match upstream.send().await {
        Ok(response) => {
            let status = response.status();
            let headers = response.headers().clone();
            let body = response.bytes().await.unwrap_or_default();
            let mut output = Response::new(Body::from(body));
            *output.status_mut() = status;
            for (name, value) in headers.iter() {
                if name.as_str().eq_ignore_ascii_case("content-type") {
                    output.headers_mut().insert(name, value.clone());
                }
            }
            output
        }
        Err(_) => Response::builder()
            .status(StatusCode::BAD_GATEWAY)
            .header("content-type", HeaderValue::from_static("text/plain"))
            .body(Body::from("Dashboard server unavailable"))
            .unwrap(),
    }
}

async fn start_proxy(token: Credential) {
    let app = Router::new().fallback(any(proxy)).with_state(token);
    let listener = TcpListener::bind("127.0.0.1:39421").await.expect("desktop proxy bind failed");
    axum::serve(listener, app).await.expect("desktop proxy failed");
}

pub fn run() {
    let credential = Arc::new(Mutex::new(None));
    let proxy_credential = credential.clone();
    tauri::async_runtime::spawn(start_proxy(proxy_credential));
    tauri::Builder::default()
        .manage(DesktopState(credential))
        .invoke_handler(tauri::generate_handler![pair, unlock, has_pairing])
        .run(tauri::generate_context!())
        .expect("error while running desktop app");
}
