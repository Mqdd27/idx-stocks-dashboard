"""Re-apply the 9Router OpenAI->Ollama `think`/`keep_alive` passthrough patch.

9Router's bundled OpenAI->Ollama body transformer drops `think` (and any
other extra field), so qwen3 models burn all num_predict tokens on CoT and
return empty content. This patch adds `think` and `keep_alive` passthrough so
requests can disable thinking (our backend sends `think: False` for ollama-*
models) and keep the local model warm (we send `keep_alive: "30m"`; without
it the model unloads after ~5m and a cold CPU reload can push the request
past 9Router's upstream timeout -> 502).

Run after every 9Router update, then restart 9Router:
    python3 scripts/patch_9router_ollama_think.py
"""
import sys

CHUNK = "/home/mqdd/.nvm/versions/node/v24.19.0/lib/node_modules/9router/app/.next-cli-build/server/chunks/8499.js"

OLD = "stream:c};return void 0!==b.think&&(d.think=b.think),"
NEW = "stream:c};return void 0!==b.think&&(d.think=b.think),void 0!==b.keep_alive&&(d.keep_alive=b.keep_alive),"


def main() -> int:
    src = open(CHUNK).read()
    if NEW in src:
        print("already patched")
        return 0
    n = src.count(OLD)
    if n != 1:
        print(f"ERROR: expected 1 occurrence of target, found {n}. "
              "9Router chunk may have changed format.", file=sys.stderr)
        return 1
    open(CHUNK, "w").write(src.replace(OLD, NEW, 1))
    print("patched OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())