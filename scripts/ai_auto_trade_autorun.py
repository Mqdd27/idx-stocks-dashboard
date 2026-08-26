"""Queue AI Auto Trade once per scheduled IDX trading day."""
import httpx


def main():
    base = "http://127.0.0.1:8200/api/ai-auto-trade"
    with httpx.Client(timeout=30) as client:
        status = client.get(f"{base}/status").json()
        if not status.get("enabled") or not status.get("market", {}).get("is_open") or status.get("active_run_id"):
            return
        response = client.post(f"{base}/run")
        response.raise_for_status()


if __name__ == "__main__":
    main()
