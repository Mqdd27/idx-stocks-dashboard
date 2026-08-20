"""Re-apply the 9Router patches needed for our local Ollama (qwen3) models.

1. OpenAI->Ollama body transformer: pass `think` and `keep_alive` through.
   9Router's bundled transformer drops `think` (so qwen3 burns all num_predict
   tokens on CoT and returns empty content) and `keep_alive` (model unloads
   after ~5m; cold CPU reload can push the request past the upstream timeout).

2. Streaming gates: accept `application/x-ndjson` as a streamable content-type.
   Ollama's /api/chat returns NDJSON (not text/event-stream), so 9Router
   rejected every streaming request with "upstream non-SSE" -> Provider error
   -> 30s model lock -> 503. With this patched, streaming works and 9Router
   records ollama usage natively.

Run after every 9Router update, then restart 9Router:
    python3 scripts/patch_9router_ollama_think.py
"""
import sys

CHUNK = "/home/mqdd/.nvm/versions/node/v24.19.0/lib/node_modules/9router/app/.next-cli-build/server/chunks/8499.js"
CHUNK2 = "/home/mqdd/.nvm/versions/node/v24.19.0/lib/node_modules/9router/app/.next-cli-build/server/chunks/8895.js"

PATCHES = [
    (
        CHUNK,
        "stream:c};return void 0!==b.think&&(d.think=b.think),",
        "stream:c};return void 0!==b.think&&(d.think=b.think),void 0!==b.keep_alive&&(d.keep_alive=b.keep_alive),",
    ),
    (
        CHUNK2,
        'let E=a.headers.get("content-type")||"";if(!(E.includes("text/event-stream")||""===E&&n(d)))return null;',
        'let E=a.headers.get("content-type")||"";if(!(E.includes("text/event-stream")||E.includes("application/x-ndjson")||""===E&&n(d)))return null;',
    ),
    (
        CHUNK2,
        'if(K&&!K.includes("text/event-stream")&&!K.includes("application/json")){',
        'if(K&&!K.includes("text/event-stream")&&!K.includes("application/json")&&!K.includes("application/x-ndjson")){',
    ),
]


def main() -> int:
    ok = True
    for chunk, old, new in PATCHES:
        src = open(chunk).read()
        if new in src:
            print(f"already patched: {chunk.split('/')[-1]}")
            continue
        n = src.count(old)
        if n != 1:
            print(f"ERROR: expected 1 occurrence of target in {chunk}, found {n}. "
                  "9Router chunk may have changed format.", file=sys.stderr)
            ok = False
            continue
        open(chunk, "w").write(src.replace(old, new, 1))
        print(f"patched OK: {chunk.split('/')[-1]}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
